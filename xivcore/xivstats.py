"""Statistical distributions and damage calculation utilities for XIV gameplay mechanics."""

from abc import ABC, abstractmethod
from typing import Union, Optional, List, Tuple

import numpy as np
import scipy

from xivcore.common import ActionID


class BoundedDistribution(ABC):
    """Abstract base class for all bounded distributions with min/max values"""

    @property
    @abstractmethod
    def min(self) -> float:
        """Minimum possible value of the distribution"""

    @property
    @abstractmethod
    def max(self) -> float:
        """Maximum possible value of the distribution"""

    @property
    @abstractmethod
    def mean(self) -> float:
        """Mean (expected value) of the distribution"""

    @property
    @abstractmethod
    def var(self) -> float:
        """Variance of the distribution"""

    @property
    def std(self) -> float:
        """Standard deviation of the distribution"""
        return np.sqrt(self.var)

    @abstractmethod
    def sample(self, size: Optional[int] = None) -> Union[float, np.ndarray]:
        """Sample values from the distribution"""

    @abstractmethod
    def cdf(self, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Cumulative distribution function at x"""

    def prob_at_least(self, x: float) -> Union[float, np.ndarray]:
        """Probability that value is at least x: P(X ≥ x)"""
        # We subtract a small epsilon (1e-9) to handle the boundary case in continuous distributions
        # This ensures we calculate P(X ≥ x) rather than P(X > x) by evaluating the CDF at a point
        # just below x, avoiding floating-point precision issues at exact boundaries
        return 1.0 - self.cdf(x - 1e-9)

    def prob_at_most(self, x: float) -> Union[float, np.ndarray]:
        """Probability that value is at most x: P(X ≤ x)"""
        return self.cdf(x)


class UniformDistribution(BoundedDistribution):
    """Uniform distribution between min and max values"""

    def __init__(self, min_value: float, max_value: float):
        """
        Parameters:
        -----------
        min_value : float
            Minimum possible value
        max_value : float
            Maximum possible value
        """
        self._min = min_value
        self._max = max_value
        self._mean = (min_value + max_value) / 2
        self._var = ((max_value - min_value) ** 2) / 12

    @property
    def min(self) -> float:
        return self._min

    @property
    def max(self) -> float:
        return self._max

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def var(self) -> float:
        return self._var

    def sample(self, size: Optional[int] = None) -> Union[float, np.ndarray]:
        return np.random.uniform(self._min, self._max, size=size)

    def cdf(self, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        return (x - self._min) / (self._max - self._min)


class MixtureDistribution(BoundedDistribution):
    """
    Mixture of bounded distributions, each with a probability weight
    """

    def __init__(self, components: List[UniformDistribution], weights: List[float]):
        """
        Parameters:
        -----------
        components : list of UniformDistribution
            The component distributions
        weights : list of float
            The probability weight for each component
        """
        if len(components) != len(weights):
            raise ValueError("Must provide same number of components and weights")

        if not np.isclose(sum(weights), 1.0, rtol=1e-5):
            # Normalize weights
            total = sum(weights)
            weights = [w / total for w in weights]

        self._components = components
        self._weights = weights

        # Filter out zero-weight components
        nonzero_indices = [i for i, w in enumerate(weights) if w > 0]
        self._nonzero_components = [components[i] for i in nonzero_indices]
        self._nonzero_weights = [weights[i] for i in nonzero_indices]

        # Pre-calculate stats
        self._calculate_stats()

    def _calculate_stats(self):
        """Calculate statistical properties of the mixture"""
        # Components with non-zero weight
        if not self._nonzero_components:
            self._min_value = 0
            self._max_value = 0
            self._mean_value = 0
            self._var_value = 0
            return

        # Min and max based on component extremes
        self._min_value = min(comp.min for comp in self._nonzero_components)
        self._max_value = max(comp.max for comp in self._nonzero_components)

        # Mean is weighted average of component means
        self._mean_value = sum(
            w * comp.mean
            for w, comp in zip(self._nonzero_weights, self._nonzero_components)
        )

        # Variance calculation for mixture
        # 1. Component variance contribution
        var_term1 = sum(
            w * comp.var
            for w, comp in zip(self._nonzero_weights, self._nonzero_components)
        )

        # 2. Mean deviation contribution
        var_term2 = sum(
            w * (comp.mean - self._mean_value) ** 2
            for w, comp in zip(self._nonzero_weights, self._nonzero_components)
        )

        self._var_value = var_term1 + var_term2

    @property
    def min(self) -> float:
        return self._min_value

    @property
    def max(self) -> float:
        return self._max_value

    @property
    def mean(self) -> float:
        return self._mean_value

    @property
    def var(self) -> float:
        return self._var_value

    def sample(self, size: Optional[int] = None) -> Union[float, np.ndarray]:
        # Manual sampling from mixture
        single_sample = size is None
        actual_size = 1 if size is None else size

        # Select components based on weights
        component_indices = np.random.choice(
            len(self._nonzero_components), size=actual_size, p=self._nonzero_weights
        )

        # Sample from selected components
        if single_sample:
            comp_idx = int(component_indices)  # Ensure integer type
            sample = self._nonzero_components[comp_idx].sample()
            return sample
        else:
            # Create array with proper size
            samples = np.zeros(actual_size, dtype=float)

            # Convert to list if it's an ndarray to avoid attribute errors
            if isinstance(component_indices, np.ndarray):
                indices = component_indices.tolist()
            else:
                indices = [component_indices]

            # Sample from each selected component
            for i, comp_idx in enumerate(indices):
                samples[i] = self._nonzero_components[comp_idx].sample()

            return samples

    def cdf(self, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        # Manual CDF calculation (weighted sum of component CDFs)
        result = np.zeros_like(x, dtype=float) if isinstance(x, np.ndarray) else 0.0
        for w, comp in zip(self._nonzero_weights, self._nonzero_components):
            result += w * comp.cdf(x)
        return result


class SumDistribution(BoundedDistribution):
    """
    Distribution representing the sum of multiple bounded distributions
    Uses FFT convolution for accurate statistics and CDF calculation
    """

    def __init__(self, distributions: List[BoundedDistribution]):
        """
        Parameters:
        -----------
        distributions : list of BoundedDistribution
            The distributions to sum
        """
        self._distributions = distributions

        # Calculate statistical properties
        self._min_value = sum(dist.min for dist in distributions)
        self._max_value = sum(dist.max for dist in distributions)
        self._mean_value = sum(dist.mean for dist in distributions)
        self._var_value = sum(dist.var for dist in distributions)

        # For FFT convolution, we'll compute PMF on first call to cdf or sample
        self._pmf_computed = False
        self._x_values = None
        self._pmf = None
        self._domain_step = 1  # Integer step for damage values

    def _compute_pmf(self):
        """Compute the PMF of the sum using FFT convolution"""
        if self._pmf_computed:
            return

        # Define domain grid with appropriate step size
        domain_min = int(self._min_value) - 1
        domain_max = int(self._max_value) + 1
        step = self._domain_step

        self._x_values = np.arange(domain_min, domain_max + step, step)
        x_grid = self._x_values

        # Start with first distribution
        if not self._distributions:
            self._pmf = np.zeros_like(x_grid)
            self._pmf_computed = True
            return

        # Sample first distribution for PMF approximation
        first_dist = self._distributions[0]
        n_samples = 100000  # Large number for good approximation
        samples = np.floor(first_dist.sample(size=n_samples)).astype(int)

        # Create histogram as discrete PMF
        hist, _ = np.histogram(
            samples,
            bins=np.arange(domain_min, domain_max + 2 * step, step),
            density=True,
        )

        # Normalize for proper PMF
        pmf = hist / np.sum(hist)

        # Convolve with each additional distribution
        for dist in self._distributions[1:]:
            # Approximate next PMF
            samples = np.floor(dist.sample(size=n_samples)).astype(int)
            next_pmf, _ = np.histogram(
                samples,
                bins=np.arange(domain_min, domain_max + 2 * step, step),
                density=True,
            )
            next_pmf = next_pmf / np.sum(next_pmf)

            # Use FFT for efficient convolution
            pmf = scipy.signal.fftconvolve(pmf, next_pmf, mode="full")

            # Truncate to same domain size
            pmf = pmf[: len(x_grid)]

            # Renormalize
            pmf = pmf / np.sum(pmf)

        self._pmf = pmf
        self._pmf_computed = True

    @property
    def min(self) -> float:
        return self._min_value

    @property
    def max(self) -> float:
        return self._max_value

    @property
    def mean(self) -> float:
        return self._mean_value

    @property
    def var(self) -> float:
        return self._var_value

    def sample(self, size: Optional[int] = None) -> Union[float, np.ndarray]:
        """
        Sample from the sum distribution using the precomputed PMF
        or by sampling directly from components if PMF not available
        """
        # Ensure PMF is computed
        self._compute_pmf()

        if self._pmf is None or len(self._pmf) == 0:
            # Fall back to direct sampling if PMF computation failed
            return self._direct_sample(size)

        # Sample from PMF
        single_sample = size is None
        actual_size = 1 if single_sample else size

        # Sample indices based on PMF probabilities
        indices = np.random.choice(len(self._x_values), size=actual_size, p=self._pmf)

        # Convert indices to values
        samples = self._x_values[indices]

        if single_sample:
            return int(samples)
        return samples.astype(int)

    def _direct_sample(self, size: Optional[int] = None) -> Union[float, np.ndarray]:
        """Sample by directly summing samples from component distributions"""
        single_sample = size is None
        actual_size = 1 if size is None else size
        # Initialize with zeros
        result = np.zeros(actual_size)

        # Add samples from each distribution
        for dist in self._distributions:
            result += dist.sample(size=actual_size)

        if single_sample:
            return int(result[0])
        return result

    def cdf(self, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Compute the CDF using the precomputed PMF
        """
        # Ensure PMF is computed
        self._compute_pmf()

        if self._pmf is None or len(self._pmf) == 0:
            # Fall back to CLT approximation if PMF computation failed
            return self._approximate_cdf(x)

        # Convert to array for consistent processing
        x_array = np.asarray(x) if isinstance(x, np.ndarray) else np.array([x])
        result = np.zeros_like(x_array, dtype=float)

        # For each value, sum probabilities of all values less than or equal to it
        for i, val in enumerate(x_array):
            # Find index in x_values grid
            idx = np.searchsorted(self._x_values, val, side="right")
            # Sum PMF up to that index
            result[i] = np.sum(self._pmf[:idx])

        return result if isinstance(x, np.ndarray) else result[0]

    def _approximate_cdf(self, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Approximate CDF using Central Limit Theorem
        This is a fallback if PMF computation failed
        """
        # Use normal approximation (CLT)
        mu = self.mean
        sigma = np.sqrt(self.var)

        # Create normal approximation with continuity correction
        return scipy.stats.norm(loc=mu, scale=sigma).cdf(x + 0.5)


class DamageResult:
    """Class for sampling from a damage distribution with different hit types"""

    def __init__(
            self,
            action_id: ActionID,
            potency: float,
            normal_hit: Tuple[float, int, int],
            critical_hit: Tuple[float, int, int],
            direct_hit: Tuple[float, int, int],
            critical_direct_hit: Tuple[float, int, int],
    ):
        """
        Initialize a damage distribution with different hit types.

        Parameters:
        -----------
        normal_hit : EventHit
            Event representing normal hits
        critical_hit : EventHit
            Event representing critical hits
        direct_hit : EventHit
            Event representing direct hits
        critical_direct_hit : EventHit
            Event representing critical direct hits

        Notes:
        ------
        All hit probabilities must sum to 1.0
        """
        self.action_id = action_id
        self.potency = potency

        self.normal_hit = UniformDistribution(
            min_value=normal_hit[1], max_value=normal_hit[2]
        )
        self.critical_hit = UniformDistribution(
            min_value=critical_hit[1], max_value=critical_hit[2]
        )
        self.direct_hit = UniformDistribution(
            min_value=direct_hit[1], max_value=direct_hit[2]
        )
        self.critical_direct_hit = UniformDistribution(
            min_value=critical_direct_hit[1], max_value=critical_direct_hit[2]
        )

        # Calculate statistics
        self.distrib = MixtureDistribution(
            components=[
                self.normal_hit,
                self.critical_hit,
                self.direct_hit,
                self.critical_direct_hit,
            ],
            weights=[
                normal_hit[0],
                critical_hit[0],
                direct_hit[0],
                critical_direct_hit[0],
            ],
        )

    def __repr__(self):
        return f"{self.action_id.name:<24} {round(self.distrib.mean, 2):>10} ± {round(self.distrib.std, 2):>8}"

    def sample(self, size=None) -> Union[float, np.ndarray]:
        """
        Sample values from this damage distribution

        Parameters:
        -----------
        size : int or tuple of ints, optional
            Output shape. If not provided, returns a single sample.

        Returns:
        --------
        float or ndarray
            Sampled value(s) from the damage distribution.
        """
        # Use the stats RandomVariable's sample method
        return self.distrib.sample(size=size)
