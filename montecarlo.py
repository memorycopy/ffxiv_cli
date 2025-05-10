"""
Monte Carlo simulation utilities for damage distribution analysis.
Provides multiple implementation strategies optimized for different scenarios.
"""

import math
import time
import numpy as np
from collections import Counter
from typing import List, Tuple, Any, Optional
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

# Add Numba for JIT compilation if available
try:
    from numba import jit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range

# NOTE: We can't use Numba for simulation with actual damage distributions
# because we need to use the proper distribution sampling methods from the damage records
# which can't be JIT-compiled by Numba.


DEFAULT_QUANTILES = [0.25, 0.5, 0.75, 0.9, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 0.995, 0.999]


# Helper function for parallel processing - must be at module level for pickling
def sample_distribution(args):
    """Sample from a damage distribution.
    
    Args:
        args: Tuple of (record, n_fights, record_index, total_records)
        
    Returns:
        tuple: (record_index, sampled damage values)
    """
    record, n_fights, record_index, total_records = args
    # This uses the proper distribution sampling method
    return record_index, record.damage.distrib.sample(size=n_fights)


class ProgressBar:
    """Simple progress bar for tracking simulation progress."""
    
    def __init__(self, total, prefix='Progress:', suffix='Complete', length=50):
        self.total = total
        self.prefix = prefix
        self.suffix = suffix
        self.length = length
        self.start_time = time.time()
        self.current = 0
        
    def update(self, current=None, additional_info=None):
        if current is not None:
            self.current = current
        else:
            self.current += 1
            
        percent = 100 * (self.current / float(self.total))
        filled_length = int(self.length * self.current // self.total)
        bar = '█' * filled_length + '-' * (self.length - filled_length)
        
        # Calculate time elapsed and estimate time remaining
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = elapsed * (self.total / self.current - 1)
            time_info = f" | {self._format_time(elapsed)}<{self._format_time(eta)}"
        else:
            time_info = ""
            
        # Include additional info if provided
        info_str = f" | {additional_info}" if additional_info else ""
        
        sys.stdout.write(f'\r{self.prefix} |{bar}| {percent:.1f}%{time_info}{info_str} {self.suffix}')
        sys.stdout.flush()
        
        if self.current == self.total:
            sys.stdout.write('\n')
            
    def _format_time(self, seconds):
        """Format time in seconds to a readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds %= 60
            return f"{int(minutes)}m{int(seconds)}s"
        else:
            hours = seconds // 3600
            seconds %= 3600
            minutes = seconds // 60
            return f"{int(hours)}h{int(minutes)}m"


class MonteCarloSimulator:
    """
    Monte Carlo simulator for damage calculations with multiple implementation strategies.
    
    This class provides several strategies for running Monte Carlo simulations:
    - Standard: Basic implementation using NumPy and original damage distributions
    - Parallel: Uses multiprocessing to parallelize computation
    - Vectorized: Uses NumPy vectorization for improved performance
    - Memory-efficient: Processes data in batches to minimize memory usage
    """
    
    def __init__(self, damage_records, time_seconds):
        """
        Initialize the simulator with damage records and combat time.
        
        Args:
            damage_records: List of damage records from combat
            time_seconds: Combat duration in seconds
        """
        self.damage_records = damage_records
        self.time_seconds = time_seconds
        self.n_records = len(damage_records)
    
    def run_standard(self, num_fights: int):
        """
        Run a standard Monte Carlo simulation using the actual damage distributions.
        This method adds samples directly to the result array without storing individual contributions,
        resulting in lower memory usage.
        
        Args:
            num_fights: Number of simulated fights
            
        Returns:
            numpy.ndarray: Simulated DPS values for each fight
        """
        print(f"Running standard simulation with {self.n_records} damage records and {num_fights:,} fights...")
        
        # Preallocate the result array for better performance
        result_array = np.zeros(num_fights)
        
        # Create progress bar
        progress = ProgressBar(self.n_records, prefix='Sampling:', suffix='Complete')
        
        # Sample from each distribution and add to result directly
        for i, record in enumerate(self.damage_records):
            # This uses the proper distribution sampling method
            samples = record.damage.distrib.sample(size=num_fights)
            result_array += samples
            
            # Update progress with additional info about the current action
            action_name = getattr(record.damage, 'action_name', f"Action {i}")
            progress.update(current=i+1, additional_info=f"{action_name}")
        
        # Convert to DPS
        result_array /= self.time_seconds
        
        return result_array
    
    def run_parallel(self, num_fights: int):
        """
        Run a parallel Monte Carlo simulation using multiprocessing.
        
        Args:
            num_fights: Number of simulated fights
            
        Returns:
            numpy.ndarray: Simulated DPS values for each fight
        """
        print(f"Running parallel simulation with {self.n_records} damage records and {num_fights:,} fights using {mp.cpu_count()} CPU cores...")
        
        # Create progress bar
        progress = ProgressBar(self.n_records, prefix='Sampling:', suffix='Complete')
        monte_carlo_result = [None] * self.n_records
        
        # Use process pool to parallelize sampling with progress tracking
        with ProcessPoolExecutor() as executor:
            # Submit all tasks
            futures = [
                executor.submit(
                    sample_distribution, 
                    (record, num_fights, i, self.n_records)
                ) for i, record in enumerate(self.damage_records)
            ]
            
            # Process results as they complete
            for future in as_completed(futures):
                index, samples = future.result()
                monte_carlo_result[index] = samples
                
                # Get action name if available
                action_name = getattr(self.damage_records[index].damage, 'action_name', f"Action {index}")
                
                # Update progress with additional info
                completed = sum(1 for r in monte_carlo_result if r is not None)
                progress.update(current=completed, additional_info=f"{action_name}")
        
        # Convert to numpy array and calculate DPS
        monte_carlo_result = np.array(monte_carlo_result)
        result = np.sum(monte_carlo_result, axis=0) / self.time_seconds
        
        return result
    
    def run_memory_efficient(self, num_fights: int, quantiles=None):
        """
        Run a memory-efficient Monte Carlo simulation that computes statistics
        progressively without storing all samples.
        
        Args:
            num_fights: Number of simulated fights
            quantiles: List of quantiles to compute (default: [0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999])
            
        Returns:
            Tuple[float, float, List[float]]: Mean DPS, standard deviation, and quantile values
        """
        if quantiles is None:
            quantiles = DEFAULT_QUANTILES
        
        print(f"Running memory-efficient simulation with {self.n_records} damage records and {num_fights:,} fights...")
        
        # Calculate batch size - we'll process the simulation in batches to avoid memory issues
        batch_size = min(10000, num_fights)
        num_batches = math.ceil(num_fights / batch_size)
        
        # Statistics variables
        sum_x = 0.0
        sum_x2 = 0.0
        
        # For quantiles, we'll use a dictionary-based approach similar to t-digest
        # For simplicity, we'll just use a limited number of bins
        num_bins = 1000
        bin_counts = Counter()
        min_val = float('inf')
        max_val = float('-inf')
        
        print(f"Processing {num_fights:,} simulations in {num_batches} batches of {batch_size:,}")
        
        # Create progress bar
        progress = ProgressBar(num_batches, prefix='Batches:', suffix='Complete')
        
        # Process in batches
        for batch in range(num_batches):
            current_batch_size = min(batch_size, num_fights - batch * batch_size)
            
            # Simulate a batch of fights
            batch_results = np.zeros(current_batch_size)
            
            # Create a nested progress bar for records within each batch
            if batch == 0:  # Only show for first batch to avoid cluttering rotations
                record_progress = ProgressBar(self.n_records, prefix='  Records:', suffix='Complete')
            
            # Sample from each damage distribution and sum
            for i, record in enumerate(self.damage_records):
                # This uses the proper distribution sampling method
                samples = record.damage.distrib.sample(size=current_batch_size)
                batch_results += samples
                
                # Update record progress only for the first batch
                if batch == 0:
                    action_name = getattr(record.damage, 'action_name', f"Action {i}")
                    record_progress.update(additional_info=f"{action_name}")
            
            # Convert to DPS
            batch_results = batch_results / self.time_seconds
            
            # Update running statistics
            sum_x += np.sum(batch_results)
            sum_x2 += np.sum(batch_results ** 2)
            
            # Update min/max
            batch_min = np.min(batch_results)
            batch_max = np.max(batch_results)
            min_val = min(min_val, batch_min)
            max_val = max(max_val, batch_max)
            
            # Update quantile bins
            bin_width = (max_val - min_val) / num_bins if max_val > min_val else 1.0
            for value in batch_results:
                bin_idx = min(int((value - min_val) / bin_width), num_bins - 1)
                bin_counts[bin_idx] += 1
            
            # Update batch progress
            progress.update(additional_info=f"Processed {(batch+1)*batch_size:,}/{num_fights:,} fights")
        
        print("\nCalculating final statistics...")
        
        # Calculate mean and std
        mean = sum_x / num_fights
        variance = (sum_x2 / num_fights) - (mean ** 2)
        std = math.sqrt(variance)
        
        # Calculate quantiles
        quantile_results = []
        cumulative_counts = 0
        sorted_bins = sorted(bin_counts.items())
        
        for q in quantiles:
            target_count = q * num_fights
            found_quantile = False
            cumulative_counts = 0
            
            for bin_idx, count in sorted_bins:
                cumulative_counts += count
                if cumulative_counts >= target_count:
                    # Estimate value at this quantile
                    quantile_val = min_val + (bin_idx + 0.5) * bin_width
                    quantile_results.append(quantile_val)
                    found_quantile = True
                    break
            
            # In case we didn't find a quantile (should not happen)
            if not found_quantile:
                quantile_results.append(max_val)
        
        return mean, std, quantile_results
    
    def run(self, num_fights: int, method: str = 'auto', quantiles=None):
        """
        Run a Monte Carlo simulation using the specified method.
        
        Args:
            num_fights: Number of simulated fights
            method: Simulation method ('standard', 'parallel', 'memory_efficient', 'auto')
            quantiles: List of quantiles to compute (for memory_efficient method)
            
        Returns:
            Union[numpy.ndarray, Tuple[float, float, List[float]]]: Simulation results
        """
        # Choose method automatically if 'auto'
        if method == 'auto':
            if num_fights > 10_000_000:
                method = 'memory_efficient'
            elif mp.cpu_count() > 1:
                method = 'parallel'
            else:
                method = 'standard'
        
        # Run the appropriate simulation method
        if method == 'standard':
            return self.run_standard(num_fights)
        elif method == 'parallel':
            return self.run_parallel(num_fights)
        elif method == 'memory_efficient':
            return self.run_memory_efficient(num_fights, quantiles)
        else:
            raise ValueError(f"Unknown simulation method: {method}")


def analyze_monte_carlo_results(results, quantiles=None):
    """
    Analyze Monte Carlo simulation results and print statistics.
    
    Args:
        results: Simulation results (array of DPS values or tuple from memory_efficient simulation)
        quantiles: List of quantiles to compute (default: [0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999])
    """
    if quantiles is None:
        quantiles = DEFAULT_QUANTILES
    
    # Handle different result formats
    if isinstance(results, tuple) and len(results) == 3:
        # Results from memory_efficient simulation
        mean, std, quantile_results = results
        print(f"DPS: {mean:.2f} ± {std:.2f}")
        
        for i, q in enumerate(quantiles):
            percent = (1 - q) * 100
            print(f"{round(percent, 6):>8}%: {quantile_results[i]:.2f}")
    else:
        # Results as array of DPS values
        mean = np.mean(results)
        std = np.std(results)
        print(f"DPS: {mean:.2f} ± {std:.2f}")
        
        quantile_results = np.quantile(results, q=quantiles)
        for i, q in enumerate(quantiles):
            percent = (1 - q) * 100
            print(f"{round(percent, 6):>8}%: {quantile_results[i]:.2f}")
    
    return mean, std, quantile_results 