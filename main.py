"""
Example script demonstrating Samurai rotation simulation.

This script shows how to set up a character with a Samurai job,
run a combat simulation, and analyze the results using Monte Carlo methods.
"""

import numpy as np
import matplotlib.pyplot as plt

import xivcore.job
from montecarlo import (
    DEFAULT_QUANTILES,
    MonteCarloSimulator,
    analyze_monte_carlo_results,
)
from xivcore.common import CharacterGearset, format_ms
from xivcore.core import BattleCharacter, Arena, Player, Rotation

MINS = 60 * 1000
SECS = 1000


def track_dps_over_time(world, enemy, _player, time_limit, interval=10 * SECS):
    """
    Track DPS over time during a simulation.

    Args:
        world: The simulation world
        enemy: The enemy receiving damage
        player: The player character
        time_limit: Total time limit for simulation in milliseconds
        interval: Time interval for DPS sampling in milliseconds

    Returns:
        tuple: Lists of timestamps, mean DPS values, DPS standard deviations,
              total damage means, and total damage standard deviations
    """
    timestamps = []
    dps_means = []
    dps_stds = []
    total_damage_means = []
    total_damage_stds = []

    # If starting before combat (pre-pull), wait until combat starts
    current_time = world.current_time

    # Start tracking from 0 (or current time if already in combat)
    start_time = max(0, current_time)

    # Reset damage log for tracking purposes
    enemy.damage_taken = []

    # Track from start to time_limit at specified intervals
    for time_ms in range(start_time, time_limit, interval):
        # Step the world forward to the next checkpoint
        step_duration = time_ms - world.current_time
        if step_duration > 0:
            world.step(frame_delta=step_duration)

        # Calculate DPS at this point
        total_mean = 0
        total_var = 0

        # If no damage yet, record 0 DPS
        if not enemy.damage_taken:
            timestamps.append(time_ms / 1000)  # Convert to seconds
            dps_means.append(0)
            dps_stds.append(0)
            total_damage_means.append(0)
            total_damage_stds.append(0)
            continue

        combat_finish_time = enemy.damage_taken[-1].time
        for record in enemy.damage_taken:
            total_mean += record.damage.distrib.mean
            total_var += record.damage.distrib.var

        # Record time in seconds for plotting
        secs_total = combat_finish_time / 1000
        if secs_total > 0:
            dps_mean = total_mean / secs_total
            dps_std = np.sqrt(total_var) / secs_total
        else:
            dps_mean = 0
            dps_std = 0

        timestamps.append(secs_total)
        dps_means.append(dps_mean)
        dps_stds.append(dps_std)
        total_damage_means.append(total_mean)
        total_damage_stds.append(np.sqrt(total_var))

    # Ensure we have the final value
    if world.current_time < time_limit:
        world.step(frame_delta=time_limit - world.current_time)

        total_mean = 0
        total_var = 0

        if enemy.damage_taken:
            combat_finish_time = enemy.damage_taken[-1].time
            for record in enemy.damage_taken:
                total_mean += record.damage.distrib.mean
                total_var += record.damage.distrib.var

            secs_total = combat_finish_time / 1000
            if secs_total > 0:
                dps_mean = total_mean / secs_total
                dps_std = np.sqrt(total_var) / secs_total

                timestamps.append(secs_total)
                dps_means.append(dps_mean)
                dps_stds.append(dps_std)
                total_damage_means.append(total_mean)
                total_damage_stds.append(np.sqrt(total_var))

    return timestamps, dps_means, dps_stds, total_damage_means, total_damage_stds


def plot_dps_over_time(timestamps, dps_means, dps_stds, title="DPS over Time"):
    """
    Create a plot showing DPS mean and standard deviation over time.

    Args:
        timestamps: List of time points in seconds
        dps_means: List of mean DPS values at each time point
        dps_stds: List of DPS standard deviations at each time point
        title: Title for the plot
    """
    plt.figure(figsize=(12, 6))

    # Plot mean DPS line
    plt.plot(timestamps, dps_means, "b-", label="mean")

    # Calculate upper and lower bounds for the standard deviation area
    upper_bound = [mean + 3 * std for mean, std in zip(dps_means, dps_stds)]
    lower_bound = [mean - 3 * std for mean, std in zip(dps_means, dps_stds)]

    # Plot standard deviation as shaded area
    plt.fill_between(
        timestamps, lower_bound, upper_bound, color="b", alpha=0.2, label="3 std-dev"
    )

    # Add grid for better readability
    plt.grid(True, linestyle="--", alpha=0.7)

    # Add labels and title
    plt.xlabel("Time (seconds)")
    plt.ylabel("DPS")
    plt.title(title)
    plt.xticks(range(0, int(timestamps[-1]) + 1, 60))
    plt.legend()

    # Ensure y-axis starts at 0
    plt.ylim(bottom=0)

    # Save the figure
    plt.savefig("dps_over_time.png", dpi=300, bbox_inches="tight")

    # Show the plot
    plt.show()


def plot_total_damage_over_time(
    timestamps, total_damage_means, total_damage_stds, title="Total Damage over Time"
):
    """
    Create a plot showing total damage with error bars over time.

    Args:
        timestamps: List of time points in seconds
        total_damage_means: List of mean total damage values at each time point
        total_damage_stds: List of total damage standard deviations at each time point
        title: Title for the plot
    """
    plt.figure(figsize=(12, 6))

    # Plot mean total damage line
    plt.plot(timestamps, total_damage_means, "r-", label="Mean Total Damage")

    # Calculate upper and lower bounds for the 3*standard deviation error bars
    upper_bound = [
        mean + 3 * std for mean, std in zip(total_damage_means, total_damage_stds)
    ]
    lower_bound = [
        mean - 3 * std for mean, std in zip(total_damage_means, total_damage_stds)
    ]

    # Plot standard deviation as shaded area
    plt.fill_between(
        timestamps, lower_bound, upper_bound, color="r", alpha=0.2, label="3σ Error"
    )

    # Add grid for better readability
    plt.grid(True, linestyle="--", alpha=0.7)

    # Format y-axis with comma separators for larger numbers
    plt.gca().get_yaxis().set_major_formatter(
        plt.matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ","))
    )

    # Add labels and title
    plt.xlabel("Time (seconds)")
    plt.ylabel("Total Damage")
    plt.xticks(range(0, int(timestamps[-1]) + 1, 60))
    plt.title(title)
    plt.legend()

    # Ensure y-axis starts at 0
    plt.ylim(bottom=0)

    # Save the figure
    plt.savefig("total_damage_over_time.png", dpi=300, bbox_inches="tight")

    # Show the plot
    plt.show()


def run_samurai_rotation(
    file_path: str,
    time_limit,
    num_fights=100000,
    simulation_method="auto",
    track_time_dps=False,
    dps_interval=10 * SECS,
):
    """
    Run a Samurai rotation simulation and analyze the results.

    Args:
        file_path: Path to the rotation JSON file to use for simulation
        time_limit: Time limit for the simulation in milliseconds
        num_fights: Number of simulated fights for Monte Carlo analysis
        simulation_method: Method to use for simulation ('standard', 'parallel', 'numba',
                           'memory_efficient', or 'auto')
        track_time_dps: Whether to track and plot DPS over time
        dps_interval: Time interval for DPS tracking in milliseconds

    Returns:
        tuple: Mean DPS, standard deviation, and quantile values
    """
    # Initialize the world
    world = Arena(time=-30_000)  # Start at -30s to simulate pre-pull

    # Create player
    gearset = CharacterGearset.from_rotation_json(file_path)
    player = Player(entity_id=1, gearset=gearset)
    xivcore.job.register_common_actions(player)
    xivcore.job.samurai.register_samurai_actions(player)
    world.add_player(player)

    # Add an enemy (dummy target)
    enemy = BattleCharacter(entity_id=2)
    world.add_enemy(enemy)

    # Start server ticks for DoTs
    world.start_server_tick()

    # Create a simple Samurai rotation
    rotation = Rotation.load_from_json(file_path)

    # Assign rotation to player
    player.set_rotation(rotation)

    # Set target and start rotation
    player.set_target(enemy)
    player.start_rotation()

    # Track DPS over time if requested
    timestamps = None
    dps_means = None
    dps_stds = None
    total_damage_means = None
    total_damage_stds = None

    if track_time_dps:
        timestamps, dps_means, dps_stds, total_damage_means, total_damage_stds = (
            track_dps_over_time(world, enemy, player, time_limit, interval=dps_interval)
        )
    else:
        # Run simulation normally
        print("Starting Samurai rotation simulation...")
        world.step(frame_delta=time_limit - world.current_time)

    # Print damage results
    print(f"\nDamage summary after {format_ms(time_limit)}:")
    total_mean = 0
    total_var = 0

    num_auto_attacks = 0

    combat_finish_time = np.inf
    for i, record in enumerate(enemy.damage_taken):
        total_mean += record.damage.distrib.mean
        total_var += record.damage.distrib.var
        combat_finish_time = record.time
        if record.damage.action_id == xivcore.job.ActionID.ATTACK:
            num_auto_attacks += 1
        print(f"[{i:03d}] {record}")

    secs_total = combat_finish_time / 1000
    dps_mean = total_mean / secs_total
    dps_std = np.sqrt(total_var) / secs_total

    print("\nGearset:")
    gearset.print()

    print("\nAuto-Attacks:", num_auto_attacks)
    print(
        f"\nTotal damage: {round(total_mean, 2):,} ± {round(np.sqrt(total_var), 2):,} ({secs_total:.2f}s)"
    )
    print(f"DPS: {dps_mean:.2f} ± {dps_std:.2f}")

    # Plot DPS over time if tracked
    if track_time_dps and timestamps and dps_means and dps_stds:
        job_name = rotation.job_name if hasattr(rotation, "job_name") else "Samurai"
        plot_dps_over_time(
            timestamps,
            dps_means,
            dps_stds,
            title=f"{job_name} DPS over Time ({secs_total:.2f}s)",
        )

        # Plot total damage over time
        plot_total_damage_over_time(
            timestamps,
            total_damage_means,
            total_damage_stds,
            title=f"{job_name} Total Damage over Time ({secs_total:.2f}s)",
        )

    # Run Monte Carlo simulation
    print("\nMonte-Carlo Simulation:")
    quantiles = DEFAULT_QUANTILES

    # Create simulator and run simulation
    simulator = MonteCarloSimulator(enemy.damage_taken, secs_total)
    results = simulator.run(num_fights, method=simulation_method, quantiles=quantiles)

    # Analyze and print results
    return analyze_monte_carlo_results(results, quantiles)


if __name__ == "__main__":
    # Run the simulation with default parameters
    run_samurai_rotation(
        file_path="rotations/sam_820.json",
        time_limit=8 * MINS + 20 * SECS,
        num_fights=100_000,
        simulation_method="auto",
        track_time_dps=True,  # Enable DPS tracking over time
        dps_interval=5 * SECS,  # Sample DPS every 5 seconds
    )
