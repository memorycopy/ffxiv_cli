"""
FFXIV Battle Simulation Core
============================

This module implements the core battle simulation system for FFXIV, modeling gameplay mechanics
including status effects, actions, job gauges, and damage calculations.

Key Components:
--------------
- StatusEffect: Base class for all buffs and debuffs
- ActionManager: Handles action cooldowns, casting, and combo management
- JobGauge: Tracks job-specific resources (like Kenki for Samurai)
- BattleCharacter: Base class for all entities in battle
- Player: Character controlled by a player with stats, gearsets, and jobs
- World: Simulation environment managing entities and event scheduling

The module uses a discrete event simulation approach to model combat with accurate
timing and stat-based calculations reflecting the game's mechanics.
"""

import heapq
import json
import math
from abc import ABC, abstractmethod
from enum import IntEnum, Enum
from typing import Dict, List, Optional, Callable, Tuple

from xivcore.common import (
    Role,
    StatusID,
    ActionID,
    JobClass,
    DamageType,
    SpeedFlags,
    LEVEL_MODIFIERS,
    JOB_STAT_MODIFIERS,
    CharacterGearset,
    Sen,
    ComboFlag,
    format_ms,
    RECAST_GROUP_GCD,
    ANIMATION_LOCK,
    get_role_for_job,
)
from xivcore.task import Task
from xivcore.xivstats import DamageResult


def update_step_size(
    step_size: Optional[int], new_step: Optional[int]
) -> Optional[int]:
    if new_step is not None:
        if step_size is None or new_step < step_size:
            return new_step
    return step_size


class StatusEffect:
    """
    Base class for all status effects (buffs and debuffs) in the battle system.

    Status effects represent temporary modifications to character stats or behavior
    that can be applied by actions. Examples include damage buffs, DoTs, and speed
    modifications.

    Attributes:
        status_id (StatusID): Unique identifier for this status effect
        action_id (ActionID): The action that applied this status
        target (BattleCharacter): The character the status is applied to
        source (BattleCharacter): The character that applied the status
        duration (int): Current remaining duration in milliseconds
        initial_duration (int): Starting duration in milliseconds
        time_elapsed (int): Time that has passed since application
        is_buff (bool): Whether this is a beneficial effect (True) or harmful effect (False)
        has_stacks (bool): Whether this effect uses a stacking mechanism
        stacks (int): Current number of stacks (if applicable)
        max_stacks (int): Maximum number of stacks (if applicable)
    """

    def __init__(
        self,
        status_id: StatusID,
        action_id: ActionID,
        target: "BattleCharacter",
        source: "BattleCharacter",
        duration: int,
        has_stacks: bool = False,
        stacks: int = 0,
        max_stacks: int = 0,
        is_buff: bool = True,
    ):
        """
        Initialize a new status effect.

        Args:
            status_id: Unique identifier for this status effect
            action_id: The action that applied this status
            target: The character the status is applied to
            source: The character that applied the status
            duration: Duration in milliseconds
            has_stacks: Whether this effect uses a stacking mechanism
            stacks: Initial number of stacks (if applicable)
            max_stacks: Maximum number of stacks (if applicable)
            is_buff: Whether this is a beneficial effect (True) or harmful effect (False)
        """
        self.status_id = status_id
        self.action_id = action_id
        self.target = target
        self.source = source
        self.initial_duration = duration
        self.duration = duration
        self.time_elapsed = 0
        self.is_buff = is_buff
        self.has_stacks = has_stacks
        self.stacks = stacks
        self.max_stacks = max_stacks

    def step(self, delta_time: int):
        """
        Update the status for the given time step.

        Args:
            delta_time: Time in milliseconds to advance the simulation
        """
        # Tick down duration
        self.duration = max(0, self.duration - delta_time)
        self.time_elapsed += delta_time

    def refresh(self, other: "StatusEffect"):
        """
        Updates this status when refreshed by a new application.

        Different behavior for stackable and refreshable statuses.

        Args:
            other: The new status effect being applied
        """
        self.source = other.source
        self.duration = other.duration
        self.initial_duration = other.initial_duration

        if self.has_stacks:
            _old_stacks = self.stacks
            self.stacks = min(self.max_stacks, other.stacks)

    def tick(self):
        """Apply tick mechanics using snapshot values - called by the server tick system"""

    def on_apply(self):
        """Called when the status is first applied"""

    def on_remove(self):
        """Called when the status is removed"""

    def on_damage_taken(self):
        """Called when the target takes damage"""

    def on_start_using(self, action_id: ActionID):
        """Called when the target starts using an action"""

    def is_expired(self, tolerance: int = 0) -> bool:
        """
        Check if the status has expired.

        Returns:
            bool: True if the status has zero duration or zero stacks (for stackable effects)
        """
        return self.duration <= tolerance or (self.has_stacks and self.stacks <= 0)

    @property
    def remaining_duration(self) -> int:
        """
        Get the status remaining duration in milliseconds.

        Returns:
            int: Remaining duration in milliseconds
        """
        return max(0, self.duration)
    
    @property
    def progress(self) -> float:
        """Get the percentage of the duration that has elapsed"""
        if self.duration > 0:
            return self.remaining_duration / self.initial_duration
        return 0.0

    @property
    def remaining_duration_seconds(self) -> float:
        """
        Get the status remaining duration in seconds.

        Returns:
            float: Remaining duration in seconds
        """
        return self.remaining_duration / 1000.0

    def extend(self, additional_duration: int):
        """
        Extend the status duration.

        Args:
            additional_duration: Extra time in milliseconds to add
        """
        self.duration += additional_duration

    def reset_duration(self):
        """Reset the status to its initial duration"""
        self.duration = self.initial_duration

    @property
    def main_stat_bonus(self) -> float:
        return 0.0

    @property
    def main_stat_bonus_max(self) -> int:
        return 0

    @property
    def damage_multiplier(self) -> float:
        """
        Get the damage multiplier for this status.

        Returns:
            float: Multiplier to apply to damage calculations (default: 1.0)
        """
        return 1.0

    @property
    def speed_multiplier(self) -> float:
        """
        Get the speed multiplier for this status.

        Returns:
            float: Multiplier to apply to cast/recast times (default: 1.0)
        """
        return 1.0

    @property
    def speed_flags(self) -> SpeedFlags:
        """
        Get the flags of abilities affected by this status's speed modifier.

        Returns:
            SpeedFlags: Flags indicating which types of actions are affected
        """
        return SpeedFlags.NONE

    @property
    def critical_hit_bonus(self) -> float:
        """
        Get the critical hit chance bonus from this status.

        Returns:
            float: Additional critical hit chance (0.0-1.0)
        """
        return 0.0

    @property
    def direct_hit_bonus(self) -> float:
        """
        Get the direct hit chance bonus from this status.

        Returns:
            float: Additional direct hit chance (0.0-1.0)
        """
        return 0.0


class StackableStatus(StatusEffect):
    """Base class for status effects with stacks"""

    def __init__(
        self,
        status_id: StatusID,
        action_id: ActionID,
        target: "BattleCharacter",
        source: "BattleCharacter",
        duration: int,
        stacks: int,
        max_stacks: int,
        is_buff: bool = True,
    ):
        super().__init__(
            status_id=status_id,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            has_stacks=True,
            stacks=stacks,
            max_stacks=max_stacks,
            is_buff=is_buff,
        )

    def consume_stack(self) -> bool:
        """Consume one stack and return True if successful"""
        if self.stacks > 0:
            _old_stacks = self.stacks
            self.stacks -= 1
            return True
        return False

    def add_stack(self, count: int = 1) -> bool:
        """Add stacks up to max_stacks and return True if changed"""
        if self.stacks < self.max_stacks:
            old_stacks = self.stacks
            self.stacks = min(self.max_stacks, self.stacks + count)
            if old_stacks != self.stacks:
                return True
        return False


class DoTStatus(StatusEffect):
    """Base class for all Damage-over-Time status effects with snapshot mechanics"""

    def __init__(
        self,
        status_id: StatusID,
        action_id: ActionID,
        target: "BattleCharacter",
        source: "BattleCharacter",
        duration: int,
        potency: float,
        is_buff: bool = False,
    ):
        super().__init__(
            status_id=status_id,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            has_stacks=False,
            is_buff=is_buff,
        )
        self.potency = potency
        # Snapshot value - the damage distribution to apply on each tick
        self.snapshot_damage = None
        # Take the snapshot at creation
        self.take_snapshot()

    def take_snapshot(self):
        """Take a snapshot of current stats for DoT calculation"""
        if self.source:
            # Calculate damage based on current stats and effects
            # Use "DoT" damage type for proper calculation
            self.snapshot_damage = self.source.calculate_potency_damage(
                potency=self.potency,
                action_id=self.action_id,
                damage_type=DamageType.DOT,
            )

    def refresh(self, other: "StatusEffect"):
        """When DoT is refreshed, take a new snapshot"""
        super().refresh(other)
        self.take_snapshot()

    def tick(self):
        """Apply DoT tick damage using snapshot values - called by the server tick system"""
        if self.target and self.snapshot_damage:
            self.target.take_damage(self.snapshot_damage)


class BuffStatus(StatusEffect):
    """Base class for buffs that modify character stats"""

    def __init__(
        self,
        status_id: StatusID,
        action_id: ActionID,
        target: "BattleCharacter",
        source: "BattleCharacter",
        duration: int,
        main_stat_bonus: float = 0,
        main_stat_bonus_max: int = 0,
        damage_multiplier: float = 1.0,
        speed_multiplier: float = 1.0,
        speed_scope: SpeedFlags = SpeedFlags.NONE,
        critical_hit_bonus: float = 0.0,
        direct_hit_bonus: float = 0.0,
    ):
        super().__init__(
            status_id=status_id,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )
        self._main_stat_bonus = main_stat_bonus
        self._main_stat_bonus_max = main_stat_bonus_max
        self._damage_multiplier = damage_multiplier
        self._speed_multiplier = speed_multiplier
        self._speed_scope = speed_scope
        self._critical_hit_bonus = critical_hit_bonus
        self._direct_hit_bonus = direct_hit_bonus

    @property
    def main_stat_bonus(self) -> float:
        return self._main_stat_bonus

    @property
    def main_stat_bonus_max(self) -> int:
        return self._main_stat_bonus_max

    @property
    def damage_multiplier(self) -> float:
        return self._damage_multiplier

    @property
    def speed_multiplier(self) -> float:
        return self._speed_multiplier

    @property
    def speed_flags(self) -> SpeedFlags:
        return self._speed_scope

    @property
    def critical_hit_bonus(self) -> float:
        return self._critical_hit_bonus

    @property
    def direct_hit_bonus(self) -> float:
        return self._direct_hit_bonus


class StatusManager:
    """
    Manages all status effects on a battle character.

    This class handles the application, expiration, and interactions of status effects,
    including tracking their durations, removing expired effects, and calculating
    combined stat modifiers from all active effects.

    Attributes:
        owner (BattleCharacter): The character that owns this status manager
        statuses (Dict[StatusID, StatusEffect]): Dictionary of active status effects
    """

    def __init__(self, owner: "BattleCharacter"):
        """
        Initialize a status manager for a character.

        Args:
            owner: The character this manager belongs to
        """
        self.owner = owner
        self.statuses: Dict[StatusID, StatusEffect] = {}

    def add_status(self, status: StatusEffect) -> bool:
        """
        Add a status effect to the entity or refresh existing status.

        If the status already exists, it will be refreshed using the
        status's refresh logic.

        Args:
            status: The status effect to apply

        Returns:
            bool: True if the status was added or refreshed
        """
        status_id = status.status_id

        # If the status already exists, update it
        if status_id in self.statuses:
            existing_status = self.statuses[status_id]
            existing_status.refresh(status)
            return True

        # New status, add it
        self.statuses[status_id] = status

        # Trigger the apply event
        status.on_apply()
        return True

    def has_status(self, status_id: StatusID, tolerance: int = 0) -> bool:
        """
        Check if an entity has a specific status effect that hasn't expired.

        Args:
            status_id: The status ID to check for

        Returns:
            bool: True if the entity has the non-expired status
        """
        return status_id in self.statuses and not self.statuses[status_id].is_expired(tolerance=tolerance)

    def get_status(self, status_id: StatusID) -> Optional[StatusEffect]:
        """
        Get a specific status effect if it exists and hasn't expired.

        Args:
            status_id: The status ID to retrieve

        Returns:
            Optional[StatusEffect]: The status effect or None if not found
        """
        if self.has_status(status_id):
            return self.statuses[status_id]
        return None

    def get_status_remaining(self, status_id: StatusID) -> int:
        """
        Get remaining duration of a status in milliseconds.

        Args:
            status_id: The status ID to check

        Returns:
            int: Remaining duration in milliseconds, or 0 if not found
        """
        if self.has_status(status_id):
            return self.statuses[status_id].remaining_duration
        return 0
    
    def get_status_progress(self, status_id: StatusID) -> float:
        """
        Get progress duration of a status in milliseconds.

        Args:
            status_id: The status ID to check
        """
        if self.has_status(status_id):
            return self.statuses[status_id].progress
        return 0
    
    def get_status_stacks(self, status_id: StatusID) -> int:
        """
        Get the number of stacks for a status.

        Args:
            status_id: The status ID to check

        Returns:
            int: Number of stacks, or 0 if not found or not a stacking status
        """
        if self.has_status(status_id):
            status = self.statuses[status_id]
            return status.stacks if status.has_stacks else 0
        return 0

    def remove_status(self, status_id: StatusID) -> bool:
        """
        Remove a status effect from an entity.

        Args:
            status_id: The status ID to remove

        Returns:
            bool: True if the status was found and removed
        """
        if status_id in self.statuses:
            status = self.statuses[status_id]
            status.on_remove()
            del self.statuses[status_id]
            return True
        return False

    def remove_all_statuses(self):
        """Remove all status effects from an entity"""
        self.statuses.clear()

    def step(self, delta_time: int):
        """
        Update all status effects for the given time step.

        This method advances the time for all statuses and removes
        any that have expired.

        Args:
            delta_time: Time in milliseconds to advance
        """
        # First update all statuses
        for status in list(self.statuses.values()):
            status.step(delta_time)

        # Then remove expired statuses
        expired_statuses = [
            status_id
            for status_id, status in self.statuses.items()
            if status.is_expired()
        ]
        for status_id in expired_statuses:
            self.remove_status(status_id)

    def calc_step_size(self) -> Optional[int]:
        """
        Calculates the step size needed for the next event based on status durations.

        This helps the simulation determine how far to advance time until the next
        status expires.

        Returns:
            Optional[int]: Milliseconds until next status expiration, or None if no statuses
        """
        step_size = None

        for status in self.statuses.values():
            if status.is_expired():
                step_size = 0  # Expired status, no need to wait
            else:
                if step_size is None or status.duration < step_size:
                    step_size = status.duration

        return step_size

    def get_damage_multiplier(self) -> float:
        """
        Calculate the total damage multiplier from all active status effects.

        Returns:
            float: Combined damage multiplier (multiplicative)
        """
        multiplier = 1.0
        for status in self.statuses.values():
            if not status.is_expired():
                multiplier *= status.damage_multiplier
        return multiplier

    def get_speed_multiplier(self, flags: SpeedFlags) -> float:
        """
        Calculate the total speed multiplier for actions with specified flags.

        Args:
            flags: The speed flags to match against status effects

        Returns:
            float: Combined speed multiplier (multiplicative)
        """
        multiplier = 1.0
        for status in self.statuses.values():
            if not status.is_expired() and (status.speed_flags & flags):
                multiplier *= status.speed_multiplier
        return multiplier

    def get_critical_hit_bonus(self) -> float:
        """
        Calculate the total critical hit bonus from all active status effects.

        Returns:
            float: Combined critical hit chance bonus (additive)
        """
        bonus = 0.0
        for status in self.statuses.values():
            if not status.is_expired():
                bonus += status.critical_hit_bonus
        return bonus

    def get_direct_hit_bonus(self) -> float:
        """
        Calculate the total direct hit bonus from all active status effects.

        Returns:
            float: Combined direct hit chance bonus (additive)
        """
        bonus = 0.0
        for status in self.statuses.values():
            if not status.is_expired():
                bonus += status.direct_hit_bonus
        return bonus

    def get_active_statuses(self) -> List[StatusEffect]:
        """
        Get a list of all active status effects.

        Returns:
            List[StatusEffect]: All non-expired status effects
        """
        return [status for status in self.statuses.values() if not status.is_expired()]


class ActionType(IntEnum):
    """
    Enumeration of different types of actions in the battle system.

    These types determine how the action behaves in terms of
    animation locks, casting times, and other game mechanics.
    """

    WEAPONSKILL = 1
    SPELL = 2
    ABILITY = 3
    AUTOATTACK = 4
    PERSISTENT = 5  # For ground-targeted persistent effects
    MOVEMENT = 6


class PvEAction(ABC):
    """
    Base class for all combat actions (weaponskills, spells, abilities).

    Actions represent the skills and abilities that characters can use in combat.
    Each action has properties like cast time, recast time (cooldown), and
    cooldown group that determines how it interacts with other actions.

    This is an abstract class that requires implementation of can_use and execute methods.

    Attributes:
        action_id (ActionID): Unique identifier for this action
        name (str): Human-readable name of the action
        cast_time (int): Time in milliseconds required to cast the action
        recast_time (int): Cooldown time in milliseconds after use for each charge
        cooldown_group (int): Primary cooldown group ID that determines shared cooldowns
        additional_cooldown_group (int): Secondary cooldown group ID (if applicable)
        max_charges (int): Maximum number of charges this action can have
    """

    def __init__(
        self,
        action_id: ActionID,
        name: str,
        cast_time: int,
        recast_time: int,
        cooldown_group: int,
        additional_recast_time: int = 0,
        additional_cooldown_group: int = 0,
        max_charges: int = 1,
        animation_lock: int = ANIMATION_LOCK,
    ):
        """
        Initialize a new action.

        Args:
            action_id: Unique identifier for this action
            name: Human-readable name of the action
            cast_time: Time in milliseconds required to cast the action
            recast_time: Cooldown time in milliseconds after use for each charge
            cooldown_group: Primary cooldown group ID
            additional_recast_time: Secondary cooldown time (if applicable)
            additional_cooldown_group: Secondary cooldown group ID (if applicable)
            max_charges: Maximum number of charges this action can have (default 1)
            animation_lock: Animation lock time in milliseconds (default ANIMATION_LOCK)
        """
        self.action_id = action_id
        self.name = name
        self.cast_time = cast_time
        self.recast_time = recast_time
        self.cooldown_group = cooldown_group
        self.additional_recast_time = additional_recast_time
        self.additional_cooldown_group = additional_cooldown_group
        self.max_charges = max_charges
        self.animation_lock = animation_lock

    @property
    def is_gcd(self) -> bool:
        """Check if the action is a GCD"""
        return self.cooldown_group == RECAST_GROUP_GCD

    @property
    def shares_recast_with_gcd(self) -> bool:
        """Check if the action shares a recast group with the GCD"""
        return (
            self.cooldown_group == RECAST_GROUP_GCD
            or self.additional_cooldown_group == RECAST_GROUP_GCD
        )

    def can_use(
        self, caster: "BattleCharacter", target: Optional["BattleCharacter"] = None, tolerance: int = 0
    ) -> bool:
        """
        Check if the action can be used in the current context.

        Args:
            caster: Character attempting to use the action
            target: Optional target character of the action
            tolerance: Advanced time in milliseconds to check if the action is ready to be used
            
        Returns:
            bool: True if the action can be used, False otherwise
        """

        # Check if the caster is able to use any action
        if caster.action_manager.is_locked(tolerance=tolerance):
            return False

        # Check if the action is off cooldown
        if not caster.action_manager.is_action_offcooldown(self.action_id, tolerance=tolerance):
            return False

        return True

    def execute(
        self, caster: "BattleCharacter", target: Optional["BattleCharacter"] = None
    ) -> bool:
        """
        Execute the action.

        This method performs the action, applying its effects to the target
        and starting appropriate cooldowns.

        Args:
            caster: Character using the action
            target: Optional target character of the action

        Returns:
            bool: True if the action was successfully executed
        """
        if not self.can_use(caster, target):
            return False

        caster.action_manager.start_cooldown(action_id=self.action_id)

        if self.cast_time > 0:
            caster.action_manager.start_casting(
                action_id=self.action_id,
                cast_time=self.cast_time,
                on_apply=lambda: self._on_casting_ready_to_finish(caster, target),
            )
        else:
            self._apply_effect(caster, target)
            caster.action_manager.animation_lock = self.animation_lock

        return True

    def _on_casting_ready_to_finish(
        self, caster: "BattleCharacter", target: Optional["BattleCharacter"]
    ):
        """
        Called when the action is ready to be applied after casting.
        """
        # TODO: check if target.is_attackable()
        self._apply_effect(caster, target)
        casting_time_remain = (
            caster.action_manager.casting_time_max - caster.action_manager.casting_time
        )
        caster.action_manager.animation_lock = casting_time_remain + 100

    def _apply_effect(
        self, caster: "BattleCharacter", target: Optional["BattleCharacter"]
    ):
        """
        Apply the action's effects to the target.
        """
        # TODO: check if target.is_attackable()
        pass


class RecastDetail:
    """
    Tracks the cooldown state of an action or cooldown group.

    This class manages the timing details of an action's cooldown,
    including how much time has elapsed and how much remains.

    Attributes:
        action_id (ActionID): The action associated with this cooldown
        time_elapsed (int): Time in milliseconds that has passed since cooldown started
        total (int): Total cooldown duration in milliseconds
    """

    def __init__(self):
        """Initialize a new recast detail with no active cooldown."""
        self.action_id = ActionID.NONE
        self.time_elapsed = 0
        self.total = 0

    @property
    def remaining(self):
        """
        Calculate the remaining cooldown time.

        Returns:
            int: Milliseconds remaining on the cooldown
        """
        return self.total - self.time_elapsed

    @property
    def is_active(self):
        """
        Check if this cooldown is currently active.

        Returns:
            bool: True if the cooldown is active and not complete
        """
        return self.total > 0 and 0 <= self.time_elapsed < self.total

    def is_charge_exhausted(self, max_charges: int = 1):
        """
        Check if an action's charges are exhausted.

        For multi-charge actions, determines if at least one charge is available.

        Args:
            max_charges: Maximum number of charges this action can have

        Returns:
            bool: True if no charges are available
        """
        if max_charges > 1:
            return self.total / max_charges >= self.time_elapsed
        return self.is_active

    def step(self, delta_time: int):
        """
        Update the cooldown state for the given time step.

        Args:
            delta_time: Time in milliseconds to advance
        """
        self.time_elapsed += delta_time
        if self.time_elapsed >= self.total:
            self.time_elapsed = 0
            self.total = 0
            
    @property
    def progress(self) -> float:
        """Get the percentage of the cooldown that has elapsed"""
        if self.is_active:
            return self.time_elapsed / self.total
        return 1.0

class ActionManager:
    """
    Manages action usage, casting, and cooldowns for a battle character.

    This class handles all aspects of action execution including cooldown tracking,
    combo state management, casting progress, and animation locks.

    Attributes:
        owner (BattleCharacter): Character this manager belongs to
        actions (Dict[ActionID, PvEAction]): Dictionary of registered actions
        cooldowns (Dict[int, RecastDetail]): Dictionary of cooldown groups
        animation_lock (int): Current animation lock in milliseconds
        casting_action_id (ActionID): Currently casting action, if any
        casting_time (int): Current progress of cast in milliseconds
        casting_time_max (int): Total required cast time in milliseconds
        last_combo_action_id (ActionID): Last action used in a combo
        last_combo_time (int): Time remaining on combo window in milliseconds
    """

    def __init__(self, owner: "BattleCharacter"):
        """
        Initialize an action manager for a character.

        Args:
            owner: Character this manager belongs to
        """
        self.owner: "BattleCharacter" = owner
        self.actions: Dict[ActionID, PvEAction] = {}
        self.cooldowns: Dict[int, RecastDetail] = {}
        self.animation_lock: int = 0

        # Track the current casting action and progress
        self.casting_action_id: ActionID = ActionID.NONE
        self.casting_time: int = 0
        self.casting_time_max: int = 0
        # Callback for applying the action if remaining cast time less than 400ms
        self.casting_apply_callback: Optional[Callable] = None

        # Track the last used action and time for combo purposes
        self.last_combo_action_id: ActionID = ActionID.NONE
        self.last_combo_time: int = 0

        self.last_action_id: ActionID = ActionID.NONE
        self.time_since_last_action: int = 0

    def get_step_size_for_next_gcd(self) -> int:
        """
        Get the step size for the next GCD.
        """
        return self.get_gcd_remaining()

    def get_step_size_for_next_ogcd(self) -> int:
        """
        Get the step size for the next OGCD.
        """
        next_action_time = self.get_step_size_next_action()
        gcd_remaining = self.get_gcd_remaining()

        time_remaining = gcd_remaining - next_action_time

        num_ogcds = max(0, int(time_remaining / ANIMATION_LOCK))
        if num_ogcds > 0:
            # If there are OGCDs remaining, return the next action time
            return next_action_time

        # no OGCDs remaining
        return gcd_remaining

    def get_step_size_next_action(self) -> int:
        """
        Get the step size for the next action (GCD clipping not considered).
        """
        unlock_animation = max(0, self.animation_lock)
        return max(unlock_animation, self.casting_time_max - self.casting_time)

    def is_locked(self, tolerance: int = 0) -> bool:
        """
        Check if the owner is unable to perform actions due to animation lock or casting.
        """
        return self.animation_lock > tolerance or self.get_casting_time_remaining() > tolerance

    def step(self, step_size: int):
        """
        Updates the action manager state by advancing time.

        This method updates the action casting progress, combo state,
        and cooldown timers based on the provided time step.

        Args:
            step_size: Time in milliseconds to advance the simulation
        """
        self.time_since_last_action += step_size
        self.animation_lock = max(0, self.animation_lock - step_size)
        self._update_action_cast(step_size=step_size)
        self._update_combo_state(step_size=step_size)
        for recast_detail in self.cooldowns.values():
            recast_detail.step(delta_time=step_size)

    def _update_action_cast(self, step_size: int):
        """
        Update the state of the currently casting action.

        Args:
            step_size: Time in milliseconds to advance
        """
        if self.is_casting:
            self.casting_time = min(
                self.casting_time + step_size, self.casting_time_max
            )
            remaining_cast_time = self.casting_time_max - self.casting_time
            if remaining_cast_time <= 400 and self.casting_apply_callback is not None:
                self.casting_apply_callback()
                self.casting_apply_callback = None
            if remaining_cast_time <= 0:
                self.casting_action_id = ActionID.NONE
                self.casting_time = 0
                self.casting_time_max = 0
        else:
            self.casting_action_id = ActionID.NONE
            self.casting_time = 0
            self.casting_time_max = 0
            self.casting_apply_callback = None

    def _update_combo_state(self, step_size: int):
        """
        Update the combo state and timer.

        Args:
            step_size: Time in milliseconds to advance
        """
        if self.last_combo_action_id != ActionID.NONE:
            self.last_combo_time = max(0, self.last_combo_time - step_size)
            if self.last_combo_time <= 0:
                self.last_combo_action_id = ActionID.NONE
                self.last_combo_time = 0
        else:
            self.last_combo_time = 0

    def calc_step_size(self) -> Optional[int]:
        """
        Calculate the step size for the next action-related event.

        Determines the time until the next significant event like an
        animation lock ending, cast completing, combo expiring, or
        cooldown finishing.

        Returns:
            Optional[int]: Milliseconds until next event, or None if no events pending
        """
        step_size = None

        if self.animation_lock > 0:
            step_size = self.animation_lock

        if self.is_casting:
            remaining_cast_time = self.casting_time_max - self.casting_time
            if self.casting_apply_callback is not None:
                time_for_apply = max(0, remaining_cast_time - 400)
                if step_size is None or time_for_apply < step_size:
                    step_size = time_for_apply  # Apply the action immediately
            else:
                step_size = remaining_cast_time

        if self.last_combo_action_id != ActionID.NONE:
            combo_expirery_time = self.last_combo_time - self.casting_time
            if step_size is None or combo_expirery_time < step_size:
                step_size = combo_expirery_time

        for recast_detail in self.cooldowns.values():
            if recast_detail.is_active:
                if step_size is None or recast_detail.remaining < step_size:
                    step_size = recast_detail.remaining

        return step_size

    def start_casting(
        self, action_id: ActionID, cast_time: int, on_apply: Optional[Callable] = None
    ):
        """
        Start casting an action with an optional callback.

        Args:
            action_id: ID of the action being cast
            cast_time: Time in milliseconds required to complete the cast
            on_apply: Callback function to execute when cast is nearly complete
        """
        self.casting_action_id = action_id
        self.casting_time = 0
        self.casting_time_max = cast_time
        self.casting_apply_callback = on_apply

    def cancel_casting(self):
        """Cancel the current casting action"""
        self.casting_action_id = ActionID.NONE
        self.casting_time = 0
        self.casting_time_max = 0
        self.casting_apply_callback = None

    def set_last_cast(
        self, action_id: ActionID, combo_flag: ComboFlag = ComboFlag.NONE
    ):
        """
        Set the last cast action for combo purposes.

        Args:
            action_id: ID of the action that was cast
            combo_flag: Flag indicating how this affects combo state
        """
        self.last_action_id = action_id
        self.time_since_last_action = 0
        if combo_flag == ComboFlag.RESET:
            self.reset_combo()
        elif combo_flag == ComboFlag.SUCCESS:
            self.start_combo(action_id)

    def start_combo(self, action_id: ActionID, combo_time: int = 30_000):
        """
        Start a combo timer for the given action.

        Args:
            action_id: ID of the action starting the combo
            combo_time: Duration in milliseconds the combo remains active
        """
        self.last_combo_action_id = action_id
        self.last_combo_time = combo_time

    def reset_combo(self):
        """Reset the current combo state"""
        self.last_combo_action_id = ActionID.NONE
        self.last_combo_time = 0

    def check_combo_chain(self, precombo_action_id: ActionID) -> bool:
        """
        Check if the current action is a valid combo chain from the previous action.

        Args:
            precombo_action_id: The action ID that should have been used previously

        Returns:
            bool: True if the combo is valid (previous action matches and combo is active)
        """
        return (
            self.last_combo_action_id == precombo_action_id and self.last_combo_time > 0
        )

    @property
    def is_casting(self) -> bool:
        """
        Check if currently casting an action.

        Returns:
            bool: True if an action is being cast
        """
        return (
            self.casting_action_id != ActionID.NONE
            and self.casting_time_max > 0
            and 0 <= self.casting_time < self.casting_time_max
        )

    def register_action(self, action: PvEAction):
        """Register an action with this manager"""
        self.actions[action.action_id] = action

        # Initialize cooldown groups if they don't exist
        if action.cooldown_group > 0 and action.cooldown_group not in self.cooldowns:
            self.cooldowns[action.cooldown_group] = RecastDetail()
            self.cooldowns[action.cooldown_group].action_id = action.action_id

        if (
            action.additional_cooldown_group > 0
            and action.additional_cooldown_group not in self.cooldowns
        ):
            self.cooldowns[action.additional_cooldown_group] = RecastDetail()
            self.cooldowns[action.additional_cooldown_group].action_id = (
                action.action_id
            )

    def clear_actions(self):
        """Clear all registered actions"""
        self.actions.clear()

    def get_action(self, action_id: ActionID) -> Optional[PvEAction]:
        """Get action by its ID"""
        return self.actions.get(action_id)

    def get_recast_group(self, action_id: ActionID) -> int:
        """Get the cooldown group for a specific action"""
        action = self.get_action(action_id)
        if action:
            return action.cooldown_group
        return 0

    def get_additional_recast_group(self, action_id: ActionID) -> int:
        """Get the additional cooldown group for a specific action"""
        action = self.get_action(action_id)
        if action:
            return action.additional_cooldown_group
        return 0

    def get_recast_detail(self, action_id: ActionID) -> Optional[RecastDetail]:
        """Get the RecastDetail for a specific action"""
        recast_group = self.get_recast_group(action_id)
        if recast_group in self.cooldowns:
            return self.cooldowns[recast_group]
        return None
    
    def get_action_cooldown_progress(self, action_id: ActionID) -> float:
        """Get the RecastDetail for a specific action"""
        recast_group = self.get_recast_group(action_id)
        if recast_group in self.cooldowns:
            return self.cooldowns[recast_group].progress
        return 1.0
    
    def get_additional_recast_detail(
        self, action_id: ActionID
    ) -> Optional[RecastDetail]:
        """Get the additional RecastDetail for a specific action"""
        add_recast_group = self.get_additional_recast_group(action_id)
        if add_recast_group and add_recast_group in self.cooldowns:
            return self.cooldowns[add_recast_group]
        return None

    def get_max_charges(self, action_id: ActionID) -> int:
        """Get the maximum number of charges for a specific action"""
        action = self.get_action(action_id)
        if action is not None:
            return action.max_charges
        return 1

    def get_adjusted_cast_time(self, action_id: ActionID) -> int:
        """Get the adjusted cast time for a specific action based on character's status effects"""
        action = self.get_action(action_id)
        if action is None:
            return 0

        # Get base recast time
        cast_time = action.cast_time
        if action.cooldown_group == RECAST_GROUP_GCD:
            speed_modifier = self.owner.status_manager.get_speed_multiplier(
                SpeedFlags.CAST
            )
            cast_time *= speed_modifier
            cast_time = int(math.floor(cast_time / 10) * 10)

        return cast_time

    def get_adjusted_recast_time(self, action_id: ActionID) -> int:
        """Get the adjusted recast time for a specific action based on character's status effects"""
        action = self.get_action(action_id)
        if action is None:
            return 0

        # Get base recast time
        recast_time = action.recast_time
        if action.cooldown_group == RECAST_GROUP_GCD:
            speed_modifier = self.owner.status_manager.get_speed_multiplier(
                SpeedFlags.RECAST
            )
            recast_time *= speed_modifier
            recast_time = int(math.floor(recast_time / 10) * 10)

        return recast_time

    def get_adjusted_additional_recast_time(self, action_id: ActionID) -> int:
        """Get the adjusted additional recast time for a specific action"""
        action = self.get_action(action_id)
        if action is None:
            return 0

        recast_time = (
            action.recast_time
        )  # FIXME: this should be the additional recast time
        if action.additional_cooldown_group == RECAST_GROUP_GCD:
            speed_modifier = self.owner.status_manager.get_speed_multiplier(
                SpeedFlags.RECAST
            )
            recast_time *= speed_modifier
            recast_time = int(math.floor(recast_time / 10) * 10)

        return recast_time

    def is_action_offcooldown(self, action_id: ActionID, tolerance: int = None) -> bool:
        """
        Determines if a specified action is off cooldown.

        This method checks whether the given action is currently off cooldown
        based on its recast details and additional recast details. It also
        considers an optional time tolerance value when determining the cooldown
        status. The action is deemed off cooldown if it is not in an active
        cooldown state and any additional cooldown constraints are met.

        Parameters:
          action_id (ActionID): The identifier of the action whose cooldown
            status is being checked.
          tolerance (int, optional): An optional non-negative time tolerance
            value in seconds. Defaults to None, which is treated as 0.

        Returns:
          bool: True if the action is determined to be off cooldown; otherwise,
            False.
        """
        recast_detail = self.get_recast_detail(action_id)
        if recast_detail is None:
            return False

        time_tolerance = tolerance if (tolerance is not None and tolerance >= 0) else 0

        add_recast_detail = self.get_additional_recast_detail(action_id)
        if (
            add_recast_detail is not None
            and add_recast_detail.is_active
            and add_recast_detail.remaining > time_tolerance
        ):
            return False

        if recast_detail.is_active:
            max_charges = self.get_max_charges(action_id)
            # TODO: check if owner can cast the action with current jobclass
            first_charge = recast_detail.total / max_charges
            if recast_detail.time_elapsed + time_tolerance < first_charge:
                return False

        return True

    def get_action_cooldown_remaining(self, action_id: ActionID) -> int:
        recast_detail = self.get_recast_detail(action_id)
        if recast_detail is None:
            return 0

        remaining = None

        add_recast_detail = self.get_additional_recast_detail(action_id)
        if (
            add_recast_detail is not None
            and add_recast_detail.is_active
            and add_recast_detail.remaining >= 0
        ):
            remaining = add_recast_detail.remaining

        if recast_detail.is_active:
            max_charges = self.get_max_charges(action_id)
            # TODO: check if owner can cast the action with current jobclass
            next_charge_remain = max(
                0, int(recast_detail.total / max_charges) - recast_detail.time_elapsed
            )
            if remaining is None or next_charge_remain < remaining:
                remaining = next_charge_remain

        return remaining

    def get_casting_time_remaining(self) -> int:
        """Get the remaining casting time for the currently casting action"""
        if self.is_casting:
            return self.casting_time_max - self.casting_time
        return 0

    def get_gcd_remaining(self) -> int:
        """Get the remaining time for the next GCD"""
        if RECAST_GROUP_GCD in self.cooldowns:
            return self.cooldowns[RECAST_GROUP_GCD].remaining
        return 0
    
    def get_gcd_max(self) -> int:
        """Get the remaining time for the next GCD"""
        recast_time = 2500
        speed_modifier = self.owner.status_manager.get_speed_multiplier(SpeedFlags.RECAST)
        recast_time *= speed_modifier
        recast_time = int(math.floor(recast_time / 10) * 10)
        return recast_time
    
    def is_charge_exhausted(self, action_id: ActionID) -> bool:
        """Check if an action's charge is exhausted"""
        recast_detail = self.get_recast_detail(action_id)
        if recast_detail is None:
            return False

        add_recast_detail = self.get_additional_recast_detail(action_id)
        if add_recast_detail is not None and add_recast_detail.is_active:
            return True

        if recast_detail.is_active:
            return False

        max_charges = self.get_max_charges(action_id)
        return recast_detail.is_charge_exhausted(max_charges=max_charges)

    def get_recast_time_elapsed(self, action_id: ActionID) -> int:
        """Get the time elapsed for a specific action"""
        recast_detail = self.get_recast_detail(action_id)
        if recast_detail is None:
            return 0
        return recast_detail.time_elapsed

    def get_additional_recast_time_elapsed(self, action_id: ActionID) -> int:
        """Get the additional time elapsed for a specific action"""
        add_recast_detail = self.get_additional_recast_detail(action_id)
        if add_recast_detail is None:
            return 0
        return add_recast_detail.time_elapsed

    def start_cooldown(self, action_id: ActionID):
        """Start a cooldown for a specific action"""
        recast_detail = self.get_recast_detail(action_id)
        if recast_detail is None:
            return

        addjusted_recast_time = self.get_adjusted_recast_time(action_id)
        max_charges = self.get_max_charges(action_id)
        if max_charges <= 1:
            recast_detail.time_elapsed = 0
            recast_detail.total = addjusted_recast_time
        else:
            adjusted_total = max_charges * addjusted_recast_time
            if not recast_detail.is_active or adjusted_total < recast_detail.total:
                recast_detail.time_elapsed = adjusted_total - addjusted_recast_time
                recast_detail.total = adjusted_total
            else:
                recast_detail.time_elapsed -= addjusted_recast_time
                if recast_detail.time_elapsed < 0:
                    recast_detail.time_elapsed = 0

        # recast_group = self.get_recast_group(action_id)
        # if recast_group == RECAST_GROUP_GCD:
        #     print(f"{format_ms(self.owner.current_time)}  GCD: {recast_detail.remaining}")

        add_recast_detail = self.get_additional_recast_detail(action_id)
        if add_recast_detail is not None:
            addjusted_additional_recast_time = self.get_adjusted_additional_recast_time(
                action_id
            )
            add_recast_detail.time_elapsed = 0
            add_recast_detail.total = addjusted_additional_recast_time

        # TODO: if action_type is ACTION
        recast_detail.action_id = action_id

    def can_cast_action_on_target(
        self, action_id: ActionID, target: Optional["BattleCharacter"], tolerance: int = 0
    ) -> bool:
        """Check if the action can be used by the owner"""
        action = self.get_action(action_id)
        if action is None:
            return False
        return action.can_use(caster=self.owner, target=target, tolerance=tolerance)

    def use_action(
        self, action_id: ActionID, target: Optional["BattleCharacter"]
    ) -> bool:
        """Use the action if it is available"""
        action = self.get_action(action_id)
        if action is None:
            return False
        return action.execute(caster=self.owner, target=target)


class TargetType(Enum):
    """
    Defines different targeting strategies for actions in rotations.

    Attributes:
        CURRENT: Use the player's current target
        MAIN_TANK: Target the player that is currently targeted by the player's target (the "tank" of your target)
        OFF_TANK: Target a tank that is not the main tank (not currently targeted by the enemy)
        SELF: Target self (the player executing the rotation)
        NEAREST: Target the nearest enemy
        LOWEST_HP: Target the party member with the lowest HP percentage
        HEALER: Target a random healer in the party
        DPS: Target a random DPS in the party
        SPECIFIC: Target a specific entity by ID
    """

    CURRENT = "current"
    MAIN_TANK = "main_tank"
    OFF_TANK = "off_tank"
    SELF = "self"
    NEAREST = "nearest"
    LOWEST_HP = "lowest_hp"
    HEALER = "healer"
    DPS = "dps"
    SPECIFIC = "specific"  # Use with specific target_id


class RotationAction:
    """
    Represents an action in a rotation sequence for a battle scenario.

    This class is used to define the specific action to be executed, its timing,
    and an optional condition that determines whether the action should be
    performed. It facilitates the coordination of multiple actions within a
    sequence.

    Attributes:
        action_id (ActionID): The identifier of the action to be executed.
        time (Optional[int]): Indicates the time in milliseconds at which the
            action should be executed in the sequence. If None, the action does
            not have a specific timing.
        condition (Optional[Callable[["Player", "BattleCharacter"], bool]]): A
            callable condition that takes a Player and a BattleCharacter as
            arguments and returns a boolean indicating whether the action should
            be executed. If None, the action is unconditional.
        target_type (TargetType): Specifies the targeting strategy for this action.
        target_id (Optional[int]): If target_type is SPECIFIC, the entity ID to target.
    """

    def __init__(
        self,
        action_id: ActionID,
        time: Optional[int] = None,
        condition: Optional[Callable[["Player", "BattleCharacter"], bool]] = None,
        target_type: TargetType = TargetType.CURRENT,
        target_id: Optional[int] = None,
    ):
        self.action_id = action_id
        self.time = time
        self.condition = condition
        self.target_type = target_type
        self.target_id = target_id


class Rotation:
    """
    Represents a predefined sequence of actions for a player to execute.

    This class allows defining ordered sequences of actions (rotations) that players
    can execute automatically during the simulation.

    Attributes:
        name (str): Name of the rotation
        actions (List[Tuple[ActionID, Optional[Callable[[Player, BattleCharacter], bool]]]):
            Ordered list of action IDs with optional condition functions
        owner (Player): The player this rotation is assigned to
        current_index (int): Current position in the rotation sequence
        enabled (bool): Whether the rotation is currently enabled
    """

    def __init__(self, name: str):
        """
        Initialize a new rotation.

        Args:
            name: Descriptive name for this rotation
        """
        self.name = name
        self.actions: List[RotationAction] = []
        self.owner: Optional[Player] = None
        self.current_index = 0
        self.enabled = False
        self.last_cast_time: Optional[int] = None
        self.gcd_used: Optional[int] = None

    def calc_step_size(self) -> Optional[int]:
        if not self.enabled or self.owner is None or self.owner.world is None:
            return None

        if self.current_index < len(self.actions):
            next_entry = self.actions[self.current_index]
            if next_entry.time is not None:
                return next_entry.time - self.owner.world.current_time

        return None

    def add_action(
        self,
        action_id: ActionID,
        time: Optional[int] = None,
        condition: Optional[Callable[["Player", "BattleCharacter"], bool]] = None,
        target_type: TargetType = TargetType.CURRENT,
        target_id: Optional[int] = None,
    ):
        """
        Add an action to the rotation sequence.

        Args:
            action_id: The action to execute
            time: Optional time at which to execute the action
            condition: Optional function that returns True if action should be executed
            target_type: Targeting strategy for this action
            target_id: If target_type is SPECIFIC, the entity ID to target
        """
        self.actions.append(
            RotationAction(
                action_id=action_id,
                time=time,
                condition=condition,
                target_type=target_type,
                target_id=target_id,
            )
        )

    def set_owner(self, player: "Player"):
        """
        Assign this rotation to a player.

        Args:
            player: The player who will execute this rotation
        """
        self.owner = player

    def enable(self):
        """Enable this rotation to start executing during simulation."""
        self.enabled = True

    def disable(self):
        """Disable this rotation from executing during simulation."""
        self.enabled = False

    def reset(self):
        """Reset rotation to the beginning of the sequence."""
        self.current_index = 0

    def execute_next(self, current_time: int) -> bool:
        """
        Executes the next action in a sequence if conditions are met and the action is valid.

        The method evaluates the current state of the object to determine whether the next
        action in the sequence can be executed. It checks multiple conditions, including
        the enabled state, the validity of the owner, the current index of the
        action sequence, and specific conditions tied to the next action. If all conditions
        are satisfied, it attempts to execute the action and moves to the next one in
        the sequence if successful.

        Args:
            current_time (int): The current simulation time.

        Returns:
            bool: True if the next action was successfully executed, otherwise False.
        """
        if not self.enabled or self.owner is None:
            return False

        if self.current_index >= len(self.actions):
            # End of rotation reached
            return False

        next_action = self.actions[self.current_index]

        # Time is provided and not reached yet
        if next_action.time is not None and next_action.time > current_time:
            return False

        # Resolve the target based on target_type
        target = self._resolve_target(next_action)
        if target is None:
            raise RuntimeError("Cannot execute action without a valid target")

        # Skip if condition is provided and returns False
        if next_action.condition is not None and not next_action.condition(
            self.owner, target
        ):
            self.current_index += 1  # Skip to next action
            return False

        # Try to execute the action
        success = self.owner.action_manager.use_action(next_action.action_id, target)
        if success:
            self.current_index += 1

            # logging
            action = self.owner.action_manager.get_action(next_action.action_id)
            if action is not None and action.cooldown_group == RECAST_GROUP_GCD:
                if self.gcd_used is None:
                    self.gcd_used = 0
                self.gcd_used += 1

                cast_interval = (
                    current_time - self.last_cast_time
                    if self.last_cast_time is not None
                    else "???"
                )

                self.last_cast_time = current_time
                # print(f"[{self.gcd_used:03d}] {format_ms(current_time)} {cast_interval} {self.owner.action_manager.get_action_cooldown_remaining(next_action.action_id)} {next_action.action_id.name}")
            return True

        else:
            if (
                self.owner.action_manager.is_action_offcooldown(next_action.action_id)
                and self.owner.action_manager.animation_lock <= 0
                and not self.owner.action_manager.is_casting
            ):
                raise RuntimeError("Action failed to execute but is off cooldown")

        return False

    def to_dict(self) -> Dict:
        """
        Convert rotation to dictionary representation for serialization.

        Returns:
            Dict: Dictionary representation of rotation (without condition functions)
        """
        return {
            "name": self.name,
            "actions": [
                {
                    str(a.action_id.name): {
                        "id": a.action_id.value,
                        "time": a.time,
                        "has_condition": a.condition is not None,
                    }
                }
                for a in self.actions
            ],
        }

    def save_to_file(self, file_path: str):
        """
        Save rotation to a JSON file.

        Args:
            file_path: Path to save the rotation JSON file
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> "Rotation":
        """
        Create a rotation from a dictionary representation.

        Args:
            data: Dictionary containing rotation data

        Returns:
            Rotation: New rotation instance
        """
        rotation = cls(name=data["name"])

        for action_entry in data["actions"]:
            for action_name, action_details in action_entry.items():
                action_id = getattr(ActionID, action_name, None)
                if action_id is not None:
                    time = action_details.get("time", None)
                    rotation.add_action(action_id=action_id, time=time)

        return rotation

    @classmethod
    def load_from_json(cls, file_path: str) -> "Rotation":
        """
        Load a rotation from a JSON file.

        Args:
            file_path: Path to the rotation JSON file

        Returns:
            Rotation: Loaded rotation instance
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def _resolve_target(self, action: RotationAction) -> Optional["BattleCharacter"]:
        """
        Resolves the target for an action based on its targeting strategy.

        Args:
            action: The rotation action containing targeting information

        Returns:
            Optional[BattleCharacter]: The resolved target, or None if no valid target found
        """
        if action.target_type == TargetType.CURRENT:
            # The target might be any Entity now, cast to BattleCharacter if appropriate
            target = self.owner.current_target
            if isinstance(target, BattleCharacter):
                return target
            return None

        elif action.target_type == TargetType.SELF:
            return self.owner

        elif action.target_type == TargetType.SPECIFIC and action.target_id is not None:
            # Find entity by ID in the world
            if self.owner.world:
                # Check players
                for player in self.owner.world.players:
                    if player.entity_id == action.target_id:
                        return player

                # Check enemies
                for enemy in self.owner.world.enemies:
                    if enemy.entity_id == action.target_id:
                        return enemy

        elif action.target_type == TargetType.MAIN_TANK:
            # Find the player that the current target is targeting (the "tank" of the current target)
            current_target = self.owner.current_target
            if current_target and current_target.current_target:
                # The target's target might be any Entity, cast to BattleCharacter if appropriate
                tank = current_target.current_target
                if isinstance(tank, BattleCharacter):
                    return tank

        elif action.target_type == TargetType.OFF_TANK:
            # Find a tank that is not the main tank
            # First identify the main tank
            main_tank = None
            current_target = self.owner.current_target
            if current_target and current_target.current_target:
                target_target = current_target.current_target
                if isinstance(target_target, BattleCharacter):
                    main_tank = target_target

            # Then find a tank that is not the main tank
            if self.owner.world:
                tanks = [
                    p
                    for p in self.owner.world.players
                    if get_role_for_job(p.job) == Role.TANK
                ]
                if not tanks:
                    return None

                # Filter out the main tank if it exists
                if main_tank:
                    off_tanks = [t for t in tanks if t != main_tank]
                    if off_tanks:
                        return off_tanks[0]  # Return the first off tank

                # If no main tank or no off tanks left, return the first tank
                return tanks[0]

        elif action.target_type == TargetType.HEALER:
            # Find a healer in the party
            if self.owner.world:
                healers = [
                    p
                    for p in self.owner.world.players
                    if get_role_for_job(p.job) == Role.HEALER
                ]
                if healers:
                    return healers[0]  # First healer

        elif action.target_type == TargetType.DPS:
            # Find a DPS in the party
            if self.owner.world:
                dps_roles = [
                    Role.DPS_MELEE,
                    Role.DPS_RANGED_PHYSICAL,
                    Role.DPS_RANGED_MAGICAL,
                ]
                dps = [
                    p
                    for p in self.owner.world.players
                    if get_role_for_job(p.job) in dps_roles
                ]
                if dps:
                    return dps[0]  # First DPS

        elif action.target_type == TargetType.NEAREST:
            # Simplified nearest - just returns first enemy for now
            # In a real implementation you would calculate distances
            if self.owner.world and self.owner.world.enemies:
                return self.owner.world.enemies[0]

        elif action.target_type == TargetType.LOWEST_HP:
            # Find party member with the lowest HP percentage
            if self.owner.world:
                # For now just return first player
                # In a real implementation you would track HP and calculate percentages
                if self.owner.world.players:
                    return self.owner.world.players[0]

        # Default case - no valid target found
        return None


class DamageRecord:
    def __init__(self, time: int, damage: DamageResult):
        self.time = time
        self.damage = damage

    def __repr__(self):
        return f"{format_ms(self.time)}: {self.damage}"


class Entity:
    """
    Base class for all entities in the simulation.

    This provides the fundamental identity and world-interaction capabilities
    that all simulation entities require.

    Attributes:
        entity_id (int): Unique identifier for this entity
        world (Optional[Arena]): Reference to the world simulation this entity exists in
    """

    def __init__(self, entity_id: int):
        """
        Initialize a base entity.

        Args:
            entity_id: Unique identifier for this entity
        """
        self.entity_id = entity_id
        self.world: Optional["Arena"] = None
        self.local_time = 0

    @property
    def current_time(self):
        return self.world.current_time if self.world is not None else self.local_time

    def step(self, step_size: int):
        """
        Update the entity state for the given time step.

        Args:
            step_size: Time in milliseconds to advance the simulation
        """
        self.local_time += step_size

    def calc_step_size(self) -> Optional[int]:
        """
        Calculate the time until the next event for this entity.

        Returns:
            Optional[int]: Milliseconds until next event, or None if no events pending
        """
        return None


class BattleCharacter(Entity):
    """
    Base class for all entities that can participate in battle.

    This class provides core battle functionality shared by all combat participants,
    including status effect management, action usage, and damage calculation.

    Attributes:
        damage_dealt (List[DamageRecord]): Record of damage dealt by this character
        damage_taken (List[DamageRecord]): Record of damage taken by this character
        status_manager (StatusManager): Manages status effects on this character
        action_manager (ActionManager): Manages actions and cooldowns for this character
        current_target (Optional[Entity]): Current target of this entity
    """

    def __init__(self, entity_id: int):
        """
        Initialize a battle character.

        Args:
            entity_id: Unique identifier for this character
        """
        super().__init__(entity_id=entity_id)
        self.damage_dealt: List[DamageRecord] = []
        self.damage_taken: List[DamageRecord] = []
        self.status_manager = StatusManager(owner=self)
        self.action_manager = ActionManager(owner=self)
        self.current_target: Optional["BattleCharacter"] = None

    def step(self, step_size: int):
        """
        Update the character state for the given time step.

        Args:
            step_size: Time in milliseconds to advance the simulation
        """
        super().step(step_size)
        self.status_manager.step(step_size)
        self.action_manager.step(step_size)

    def set_target(self, target: Optional["BattleCharacter"]):
        """
        Set the entity's current target.

        Args:
            target: The new target, or None to clear targeting
        """
        self.current_target = target

    def get_target(self) -> Optional["BattleCharacter"]:
        """
        Get the entity's current target.

        Returns:
            Optional[BattleCharacter]: The current target, or None if no target is set
        """
        return self.current_target

    def calc_step_size(self) -> Optional[int]:
        """
        Calculate the time until the next event for this character.

        This method determines the smallest step size across the character's
        status manager and action manager, helping the simulation
        efficiently advance to the next relevant event.

        Returns:
            Optional[int]: Milliseconds until next event, or None if no events pending
        """
        step_size: Optional[int] = super().calc_step_size()

        status_step_size = self.status_manager.calc_step_size()
        step_size = update_step_size(step_size, status_step_size)

        action_step_size = self.action_manager.calc_step_size()
        step_size = update_step_size(step_size, action_step_size)

        return step_size

    def is_action_locked(self, tolerance: int = 0) -> bool:
        """
        Check if the character is unable to perform actions due to animation lock or casting.
        """
        return self.action_manager.is_locked(tolerance)

    def has_status(self, status_id: StatusID) -> bool:
        """
        Check if the character has a specific status effect.

        Args:
            status_id: The status ID to check for

        Returns:
            bool: True if the character has the status
        """
        return self.status_manager.has_status(status_id)

    def get_status_remaining(self, status_id: StatusID) -> int:
        """
        Get remaining duration of a status in milliseconds.

        Args:
            status_id: The status ID to check

        Returns:
            int: Remaining duration in milliseconds, or 0 if not found
        """
        return self.status_manager.get_status_remaining(status_id)

    def get_status_stacks(self, status_id: StatusID) -> int:
        """
        Get the number of stacks for a status.

        Args:
            status_id: The status ID to check

        Returns:
            int: Number of stacks, or 0 if not found or not a stacking status
        """
        return self.status_manager.get_status_stacks(status_id)

    def get_status(self, status_id: StatusID) -> Optional[StatusEffect]:
        """
        Get a specific status effect if it exists.

        Args:
            status_id: The status ID to retrieve

        Returns:
            Optional[StatusEffect]: The status effect or None if not found
        """
        return self.status_manager.get_status(status_id)

    def add_status(self, status: StatusEffect):
        """
        Add a status effect to the character.

        Args:
            status: The status effect to apply
        """
        self.status_manager.add_status(status)

    def remove_status(self, status_id: StatusID) -> bool:
        """
        Remove a status effect from the character.

        Args:
            status_id: The status ID to remove

        Returns:
            bool: True if the status was found and removed
        """
        return self.status_manager.remove_status(status_id)

    @abstractmethod
    def calculate_potency_damage(
        self,
        action_id: ActionID,
        potency: float,
        damage_type: DamageType,
        auto_crt: bool = False,
        auto_dht: bool = False,
    ) -> DamageResult:
        """
        Calculate damage from a potency value based on character stats and buffs.

        Args:
            action_id: The ID of the action being used
            potency: The potency value of the action
            damage_type: The type of damage calculation to use
            auto_crt: Guarantee a critical hit
            auto_dht: Guarantee a direct hit

        Returns:
            DamageResult: The calculated damage distribution
        """
        pass

    def prepare_action_damage(
        self,
        action_id: ActionID,
        target: Optional["BattleCharacter"],
        potency: float,
        damage_type: DamageType,
        auto_crt: bool = False,
        auto_dht: bool = False,
        delay: int = ANIMATION_LOCK,
    ):
        """
        Prepare to apply damage to the target. The damage is calculated at this point and applied later.
        """
        dmg = self.calculate_potency_damage(
            action_id=action_id,
            potency=potency,
            damage_type=damage_type,
            auto_crt=auto_crt,
            auto_dht=auto_dht,
        )
        self.prepare_damage(target=target, damage=dmg, delay=delay)

    def prepare_damage(
        self,
        target: Optional["BattleCharacter"],
        damage: DamageResult,
        delay: int = ANIMATION_LOCK,
    ):
        """
        Prepare to apply damage to the target. The damage is calculated at this point and applied later.
        """
        self.world.schedule_task(
            delay=delay,
            callback=target.take_damage,
            damage=damage,
        )
        # print(f"      {format_ms(self.current_time)}: Preparing {damage.action_id.name}({damage.action_id.value})")

    def take_damage(self, damage: DamageResult):
        """
        Record damage taken by the character.

        Args:
            damage: The damage result to record
        """
        # FIXME: Check if the entity is attackable
        record = DamageRecord(time=self.current_time, damage=damage)
        self.damage_taken.append(record)

        # print(f"[{len(self.damage_taken):03d}] {record}")


class JobGauge(ABC):
    """
    Base class for all job-specific mechanics.

    This class handles job-specific resources, gauges, and mechanics
    independently from the character class hierarchy.
    """

    def __init__(self, owner: "Player"):
        """
        Initialize job mechanics.

        Args:
            owner: The player that uses these job mechanics
        """
        self.owner = owner

    @abstractmethod
    def reset(self):
        """Reset the job mechanics to its default state"""

    @abstractmethod
    def step(self, step_size: int):
        """Update job mechanics for the given time step"""

    @abstractmethod
    def calc_step_size(self) -> Optional[int]:
        """Calculate the optimal step size to advance the simulation"""


class SamuraiGauge(JobGauge):
    """
    Samurai job-specific mechanics implementation.

    Tracks:
    - Kenki (resource used for special attacks)
    - Sen (Setsu, Getsu, Ka - combo finishers that enable iaijutsu)
    - Meditation stacks
    - Meditation timer
    - Kaeshi Action
    """

    def __init__(self, owner: "Player"):
        super().__init__(owner)
        self.kenki = 0
        self.sen = Sen.NONE

        self.meditation_stacks = 0
        self.meditation_timer = 0

        self.kaeshi_namikiri_ready = False
        self.kaeshi_namikiri_timer = 0

        self.tsubamegaeshi_action = ActionID.NONE
        self.tsubamegaeshi_timer = 0

    def reset(self):
        """Reset the gauge to default state"""
        self.kenki = 0
        self.sen = Sen.NONE

        self.meditation_stacks = 0
        self.meditation_timer = 0

        self.kaeshi_namikiri_ready = False
        self.kaeshi_namikiri_timer = 0

        self.tsubamegaeshi_action = ActionID.NONE
        self.tsubamegaeshi_timer = 0

    def step(self, step_size: int):
        """Update gauge state for the given time step"""
        if self.meditation_timer > 0:
            self.meditation_timer = max(0, self.meditation_timer - step_size)

        # Kaeshi action timer update
        if self.tsubamegaeshi_timer > 0:
            self.tsubamegaeshi_timer = max(0, self.tsubamegaeshi_timer - step_size)
        if self.tsubamegaeshi_timer <= 0:
            self.tsubamegaeshi_action = ActionID.NONE

    def calc_step_size(self) -> Optional[int]:
        step_size = None
        if self.meditation_timer > 0:
            step_size = self.meditation_timer
        if self.tsubamegaeshi_timer > 0:
            if step_size is None or self.tsubamegaeshi_timer < step_size:
                step_size = self.tsubamegaeshi_timer
        return step_size

    def add_kenki(self, amount: int, allow_overflow: bool = True):
        """Add Kenki gauge, capped at 100"""
        new_kenki = self.kenki + amount
        if allow_overflow:
            self.kenki = new_kenki
        else:
            self.kenki = min(100, new_kenki)

    def spend_kenki(self, amount: int) -> bool:
        """
        Spend Kenki if sufficient amount available
        Returns True if successful, False if insufficient
        """
        if self.kenki >= amount:
            self.kenki -= amount
            return True
        return False

    def add_sen(self, sen_flag: Sen):
        """Add a Sen to the gauge"""
        self.sen |= sen_flag

    def remove_sen(self, sen_flag: Sen):
        """Remove a specific Sen from the gauge"""
        self.sen &= ~sen_flag

    def clear_sen(self):
        """Clear all Sen"""
        self.sen = Sen.NONE

    def has_sen(self, sen_flag: Sen) -> bool:
        """Check if gauge has specific Sen"""
        return bool(self.sen & sen_flag)

    def count_sen(self) -> int:
        """Count the number of Sen currently held"""
        count = 0
        if self.has_sen(Sen.SETSU):
            count += 1
        if self.has_sen(Sen.GETSU):
            count += 1
        if self.has_sen(Sen.KA):
            count += 1
        return count

    def add_meditation(self, stacks: int = 1):
        """Add meditation stacks, capped at 3"""
        self.meditation_stacks = min(3, self.meditation_stacks + stacks)

    def use_meditation(self) -> bool:
        """Use 3 meditation stacks if available"""
        if self.meditation_stacks >= 3:
            self.meditation_stacks -= 3
            return True
        return False

    def set_tsubamegaeshi(self, action_id: ActionID, duration: int = 30_000):
        """Set Kaeshi action and timer"""
        self.tsubamegaeshi_action = action_id
        self.tsubamegaeshi_timer = duration

    def check_tsubamegaeshi(self, action_id: ActionID, tolerance: int = 0):
        """Check if the current Kaeshi action matches the given action"""
        if self.tsubamegaeshi_action != action_id:
            return False
        return self.tsubamegaeshi_timer > tolerance

    def reset_tsubamegaeshi(self):
        """Reset Kaeshi action and timer"""
        self.tsubamegaeshi_action = ActionID.NONE
        self.tsubamegaeshi_timer = 0

    def set_kaeshi_namikiri_ready(self, duration: int = 30_000):
        """Set Kaeshi Namikiri ready flag and timer"""
        self.kaeshi_namikiri_ready = True
        self.kaeshi_namikiri_timer = duration

    def reset_kaeshi_namikiri(self):
        """Reset Kaeshi Namikiri ready flag and timer"""
        self.kaeshi_namikiri_ready = False
        self.kaeshi_namikiri_timer = 0


class StatCalculator:
    """
    Handles stat calculations for characters.

    This class encapsulates the logic for calculating derived stats,
    damage formulas, and stat-based effects.
    """

    def __init__(self, level: int, job: JobClass):
        self.level = level
        self.job = job

    def calculate_critical_hit_chance(self, critical_hit: float) -> float:
        """Calculate critical hit chance from critical hit stat"""
        level_mod = LEVEL_MODIFIERS[self.level]
        tmp = 200.0 * (critical_hit - level_mod.substract) / level_mod.division
        crit_chance = (tmp + 50.0) / 1000.0
        return max(
            0.0, math.floor(crit_chance * 1000) / 1000.0
        )  # Floor to 3 decimal places

    def calculate_direct_hit_chance(self, direct_hit: float) -> float:
        """Calculate direct hit chance from direct hit stat"""
        level_mod = LEVEL_MODIFIERS[self.level]

        tmp = 550.0 * (direct_hit - level_mod.substract) / level_mod.division
        dh_chance = tmp / 1000.0
        return max(
            0.0, math.floor(dh_chance * 1000) / 1000.0
        )  # Floor to 3 decimal places

    def calculate_critical_hit_power(self, critical_hit: float) -> float:
        """Calculate critical hit power multiplier from critical hit stat"""
        level_mod = LEVEL_MODIFIERS[self.level]
        tmp = 200.0 * (critical_hit - level_mod.substract) / level_mod.division
        crit_power = (1400.0 + tmp) / 1000.0
        return math.floor(crit_power * 1000) / 1000.0  # Floor to 3 decimal places

    def calculate_attack_power_multiplier(self, main_attribute: float) -> float:
        """Calculate attack power multiplier from main attribute"""
        level_mod = LEVEL_MODIFIERS[self.level]
        tmp = (
            level_mod.attack_power
            * (main_attribute - level_mod.main_attribute)
            / level_mod.main_attribute
        )
        ap_multiplier = 1.0 + math.floor(tmp) / 100.0
        return ap_multiplier

    def calculate_determination_multiplier(self, determination: float) -> float:
        """Calculate determination multiplier from determination stat"""
        level_mod = LEVEL_MODIFIERS[self.level]
        tmp = 140.0 * (determination - level_mod.main_attribute) / level_mod.division
        det_multiplier = 1.0 + math.floor(tmp) / 1000.0
        return det_multiplier

    def calculate_auto_direct_hit_multiplier(self, direct_hit: float) -> float:
        """Calculate auto direct hit multiplier"""
        level_mod = LEVEL_MODIFIERS[self.level]

        tmp = 140.0 * (direct_hit - level_mod.substract) / level_mod.division
        auto_dh_multiplier = 1.0 + math.floor(tmp) / 1000.0
        return auto_dh_multiplier

    def calculate_weapon_damage_multiplier(self, weapon_damage: float) -> float:
        """Calculate weapon damage multiplier"""
        level_mod = LEVEL_MODIFIERS[self.level]
        job_mod = JOB_STAT_MODIFIERS[self.job]

        tmp = level_mod.main_attribute * job_mod.main_attribute / 1000.0
        weapon_multiplier = (math.floor(tmp) + weapon_damage) / 100.0
        return weapon_multiplier

    def calculate_weapon_auto_attack_power(
        self, weapon_damage: float, weapon_delay: float
    ) -> float:
        """Calculate weapon auto attack power"""
        level_mod = LEVEL_MODIFIERS[self.level]
        job_mod = JOB_STAT_MODIFIERS[self.job]

        tmp = level_mod.main_attribute * job_mod.main_attribute / 1000.0
        delay = int(weapon_delay / 3.0 * 100.0) / 100.0
        auto_attack = math.floor((tmp + weapon_damage) * delay) / 100.0
        return auto_attack

    def calculate_speed_multiplier(self, speed: float, truncated: bool = True) -> float:
        """Calculate speed multiplier from speed stat"""
        level_mod = LEVEL_MODIFIERS[self.level]

        speed_value = 130.0 * (speed - level_mod.substract) / level_mod.division
        if truncated:
            speed_value = math.floor(speed_value)

        speed_multiplier = 1.0 + speed_value / 1000.0
        return speed_multiplier


class Player(BattleCharacter):
    """
    Player-controlled battle character with job specialization and gear stats.

    This class extends BattleCharacter with player-specific functionality including
    gear-based stat calculations, job mechanics, and player-specific damage formulas.

    Attributes:
        gearset (CharacterGearset): The character's equipment and stats
        job_gauge (JobGauge): Job-specific resource tracker and mechanics
        rotation (Optional[Rotation]): The player's current rotation if assigned
        stat_calculator (StatCalculator): Handles stat-based calculations
        auto_attack_timer (int): Current time remaining until next auto attack
        auto_attack_delay (int): Base delay between auto attacks in milliseconds
        auto_attack_enabled (bool): Whether auto-attacks are enabled
    """

    def __init__(self, entity_id: int, gearset: CharacterGearset):
        """
        Initialize a player character.

        Args:
            entity_id: Unique identifier for this character
            gearset: The character's equipment and stats

        Raises:
            NotImplementedError: If the job in the gearset is not supported
        """
        super().__init__(entity_id=entity_id)

        self.gearset = gearset
        self.rotation: Optional[Rotation] = None
        self.stat_calculator = StatCalculator(level=gearset.level, job=gearset.job)

        # Initialize auto-attack properties
        self.auto_attack_timer = 0
        self.auto_attack_delay = int(
            gearset.weapon_delay * 1000
        )  # Convert to milliseconds
        self.auto_attack_enabled = True
        self.was_casting = False
        self.first_auto_attack = True  # Flag to track first auto-attack

        # Initialize job-specific mechanics based on job
        if self.gearset.job == JobClass.SAMURAI:
            self.job_gauge = SamuraiGauge(owner=self)
        else:
            raise NotImplementedError(f"Job {self.gearset.job} not supported")

    def _should_simulate_auto_attacks(self) -> bool:
        """
        Determine if auto-attacks should be simulated for this job.

        Most magic casters deal only 1 damage with auto-attacks, so we skip simulation
        for them except for Scholar and Summoner.

        Returns:
            bool: True if auto-attacks should be simulated, False otherwise
        """
        # Magic caster jobs that deal negligible auto-attack damage
        job_role = get_role_for_job(self.job)
        if job_role == Role.HEALER or job_role == Role.DPS_RANGED_MAGICAL:
            return False

        return True

    def _process_auto_attack(self, step_size: int, finished_casting: bool = False):
        """
        Process auto-attack timer and deliver auto-attacks when ready.

        Args:
            step_size: Time in milliseconds to advance
            finished_casting: True if the player just finished casting in this step
        """
        if not self.auto_attack_enabled or not self._should_simulate_auto_attacks():
            return

        # Get current world time
        current_time = self.world.current_time if self.world else self.local_time

        # Handle first auto-attack at time=0 (start of fight)
        if self.first_auto_attack:
            # Only deliver first auto-attack exactly at or after time=0 (not in prepull)
            if current_time >= 0:
                self._deliver_auto_attack()
                self.first_auto_attack = False
                return  # Return after delivering first auto-attack
            else:
                return  # Skip auto-attack processing during prepull

        # Update auto-attack timer
        if self.auto_attack_timer > 0:
            self.auto_attack_timer = max(0, self.auto_attack_timer - step_size)

        # Check if auto-attack is ready and can be delivered
        if self.auto_attack_timer <= 0 and not self.action_manager.is_casting:
            # Deliver auto-attack if we have a target
            self._deliver_auto_attack()

    def _deliver_auto_attack(self):
        """Deliver an auto-attack to the current target and reset the timer"""
        # Use the player's current target instead of just taking the first enemy
        target = self.current_target

        if target:
            # Get job-specific auto-attack potency
            potency = self._get_auto_attack_potency()

            # Calculate and apply damage
            self.prepare_action_damage(
                action_id=ActionID.ATTACK,
                target=target,
                potency=potency,
                damage_type=DamageType.AUTO_ATTACK,
            )

            # print(f"{format_ms(self.current_time)}: Auto-attack delivered")

            # Reset timer based on weapon delay and haste buffs
            self._reset_auto_attack_timer()

    def _reset_auto_attack_timer(self):
        """Reset the auto-attack timer based on weapon delay and speed buffs"""
        # Get auto-attack speed modifier from status effects
        speed_modifier = self.status_manager.get_speed_multiplier(
            SpeedFlags.AUTO_ATTACK
        )

        # Calculate adjusted delay
        adjusted_delay = int(self.auto_attack_delay * speed_modifier)

        # Set the timer
        self.auto_attack_timer = adjusted_delay

    def _get_auto_attack_potency(self) -> float:
        """
        Get the auto-attack potency based on job.

        Returns:
            float: The potency value for this job's auto-attack
        """
        # Magic caster jobs have minimal auto-attack potency
        job_role = get_role_for_job(self.job)
        if job_role == Role.HEALER or job_role == Role.DPS_RANGED_MAGICAL:
            return 1.0  # Minimal potency for magic casters

        # Jobs with normal auto-attack potency
        job_potencies = {
            JobClass.SAMURAI: 90.0,
            JobClass.MONK: 90.0,
            JobClass.DRAGOON: 90.0,
            JobClass.NINJA: 90.0,
        }

        # Return job-specific potency or default
        return job_potencies.get(self.job, 90.0)  # Default potency

    def step(self, step_size: int):
        """
        Update the player state for the given time step.

        Args:
            step_size: Time in milliseconds to advance the simulation
        """
        # Check if we were casting before updating
        was_casting = self.action_manager.is_casting
        current_time = self.current_time

        super().step(step_size=step_size)
        self.job_gauge.step(step_size)

        # Execute rotation if available, not casting, and no animation lock
        if (
            self.rotation is not None
            and self.rotation.enabled
            and not self.action_manager.is_casting
            and self.action_manager.animation_lock <= 0
        ):
            # Pass the current time from the world to execute_next

            self.rotation.execute_next(current_time=current_time)

        # Check if we finished casting this step
        finished_casting = was_casting and not self.action_manager.is_casting

        # Handle auto-attack
        self._process_auto_attack(step_size, finished_casting)

    def calc_step_size(self) -> Optional[int]:
        step_size: Optional[int] = super().calc_step_size()

        job_gauge_step_size = self.job_gauge.calc_step_size()
        step_size = update_step_size(step_size, job_gauge_step_size)

        if self.rotation:
            rotation_step_size = self.rotation.calc_step_size()
            step_size = update_step_size(step_size, rotation_step_size)

        # Consider auto-attack timer for step size only for jobs that simulate auto-attacks
        if (
            self.auto_attack_enabled
            and self.auto_attack_timer > 0
            and self._should_simulate_auto_attacks()
        ):
            step_size = update_step_size(step_size, self.auto_attack_timer)

        return step_size

    def set_rotation(self, rotation: Rotation):
        """
        Assign a rotation to this player.

        Args:
            rotation: The rotation to assign
        """
        self.rotation = rotation
        rotation.set_owner(self)

    def start_rotation(self, target: Optional[BattleCharacter] = None):
        """
        Start executing the assigned rotation.

        Args:
            target: Optional target override for the rotation
        """
        if self.rotation is not None:
            if target is not None:
                # Set the player's target directly
                self.set_target(target)
            self.rotation.reset()
            self.rotation.enable()

    def stop_rotation(self):
        """Stop the current rotation from executing."""
        if self.rotation is not None:
            self.rotation.disable()

    @property
    def job(self) -> JobClass:
        """
        Get the player's job class.

        Returns:
            JobClass: The player's current job
        """
        return self.gearset.job

    @property
    def level(self) -> int:
        """
        Get the player's level.

        Returns:
            int: The player's current level
        """
        return self.gearset.level

    def get_main_stat(self):
        """
        Calculates and returns the main stat value.

        This function computes the main stat based on the `gearset` object's main attribute,
        party bonus, and the bonuses from active buff statuses managed by the `status_manager`.
        The bonus provided by each buff status is limited by the status' `main_stat_bonus_max`.

        Returns:
            int: The calculated main stat value considering party bonuses and buffs.
        """
        main_stat = int(self.gearset.main_attribute * self.gearset.party_bonus)
        for status in self.status_manager.statuses.values():
            if isinstance(status, BuffStatus):
                bonus = min(
                    status.main_stat_bonus_max, int(main_stat * status.main_stat_bonus)
                )
                main_stat += bonus

        return main_stat

    def calculate_potency_damage(
        self,
        action_id: ActionID,
        potency: float,
        damage_type: DamageType,
        auto_crt: bool = False,
        auto_dht: bool = False,
    ) -> DamageResult:
        """
        Calculate damage from a potency value based on character stats and buffs.

        This implements the full FFXIV damage formula, including:
        - Base damage calculation from potency and weapon damage
        - Critical hit and direct hit chances and multipliers
        - Job-specific trait multipliers
        - Status effect modifiers
        - Variance ranges for different hit types

        Args:
            action_id: The ID of the action being used
            potency: The potency value of the action
            damage_type: The type of damage (DoT, auto-attack, spell, or weaponskill)
            auto_crt: Guarantee a critical hit
            auto_dht: Guarantee a direct hit

        Returns:
            DamageResult: A complete damage distribution with probabilities for different hit types
        """
        # Get base stats from character's gearset
        weapon_damage = self.gearset.weapon_damage
        weapon_delay = self.gearset.weapon_delay
        main_attribute = self.get_main_stat()
        critical_hit = self.gearset.critical_hit
        determination = self.gearset.determination
        direct_hit = self.gearset.direct_hit
        speed = self.gearset.speed

        # Calculate base chances
        base_crit_chance = self.stat_calculator.calculate_critical_hit_chance(
            critical_hit
        )
        base_dht_chance = self.stat_calculator.calculate_direct_hit_chance(direct_hit)

        # Get additional chances from status effects
        crit_chance_bonus = self.status_manager.get_critical_hit_bonus()
        dht_chance_bonus = self.status_manager.get_direct_hit_bonus()

        # Final chances
        crit_chance = min(1.0, base_crit_chance + crit_chance_bonus)
        dht_chance = min(1.0, base_dht_chance + dht_chance_bonus)

        if auto_crt:
            crit_chance = 1.0

        if auto_dht:
            dht_chance = 1.0

        # Calculate power multipliers
        critical_hit_power = self.stat_calculator.calculate_critical_hit_power(
            critical_hit
        )
        direct_hit_power = 1.25  # Fixed at 25% increase

        if auto_crt:
            critical_hit_power_bonus = (
                1 + (critical_hit_power - 1.0) * crit_chance_bonus
            )
            critical_hit_power *= critical_hit_power_bonus

        if auto_dht:
            direct_hit_power_bonus = 1 + 0.25 * dht_chance_bonus
            direct_hit_power *= direct_hit_power_bonus

        # Calculate stat multipliers
        f_ap = self.stat_calculator.calculate_attack_power_multiplier(main_attribute)
        f_det = self.stat_calculator.calculate_determination_multiplier(determination)
        f_wd = self.stat_calculator.calculate_weapon_damage_multiplier(weapon_damage)
        f_auto = self.stat_calculator.calculate_weapon_auto_attack_power(
            weapon_damage, weapon_delay
        )
        f_spd = self.stat_calculator.calculate_speed_multiplier(speed)

        # Calculate base damage based on damage type
        damage = potency

        # Apply different formulas based on damage type
        # THESE STUFFS REALLY DOESN'T MATTER
        # WHAT YOU GET IS JUST THE ROUNDING ERRORS, SAY 10 ON THE LOWER/UPPER BOUND, WHILE YOUR EXPECTATION DOESN'T CHANGE
        # SO LET'S JUST FUCK IT OFF
        if damage_type == DamageType.DOT:
            # DoT damage formula
            damage = int(damage * f_ap)
            damage = int(damage * f_det)
            damage = int(damage * f_wd)
            damage = int(damage * f_spd)
            damage_min = damage - 1
            damage_max = damage
        elif damage_type == DamageType.AUTO_ATTACK:
            # Auto attack damage formula
            damage = int(damage * f_ap)
            damage = int(damage * f_det)
            damage = int(damage * f_auto)
            damage = int(damage * f_spd)
            damage_min = damage + 1
            damage_max = damage + 1
        elif damage_type == DamageType.SPELL:
            # Spell damage formula
            damage = int(damage * f_wd)
            damage = int(damage * f_ap)
            damage = int(damage * f_det)
            damage_min = damage - 2
            damage_max = damage
        else:
            # Weaponskill/Ability damage formula
            damage = int(damage * f_ap)
            damage = int(damage * f_det)
            damage = int(damage * f_wd)
            damage_min = damage - 1
            damage_max = damage

        # Apply job trait multiplier
        job_modifiers = JOB_STAT_MODIFIERS[self.job]
        job_trait_multiplier = job_modifiers.damage_trait_multiplier
        damage_min = int(damage_min * job_trait_multiplier)
        damage_max = int(damage_max * job_trait_multiplier)

        # Calculate probabilities for different hit types
        prob_crit = crit_chance * (1 - dht_chance)
        prob_dht = (1 - crit_chance) * dht_chance
        prob_crit_dht = crit_chance * dht_chance
        prob_normal = 1 - prob_crit - prob_dht - prob_crit_dht

        # Calculate different hit types
        # Direct hit
        dht_min = int(damage_min * direct_hit_power)
        dht_max = int(damage_max * direct_hit_power)

        # Critical hit
        crit_min = int(damage_min * critical_hit_power)
        crit_max = int(damage_max * critical_hit_power)

        # Critical direct hit
        crit_dht_min = int(crit_min * direct_hit_power)
        crit_dht_max = int(crit_max * direct_hit_power)

        # Apply variance (0.95-1.05 range)
        normal_min = int(damage_min * 0.95)
        normal_max = int(damage_max * 1.05)

        dht_min = int(dht_min * 0.95)
        dht_max = int(dht_max * 1.05)

        crit_min = int(crit_min * 0.95)
        crit_max = int(crit_max * 1.05)

        crit_dht_min = int(crit_dht_min * 0.95)
        crit_dht_max = int(crit_dht_max * 1.05)

        # Apply damage multiplier from status effects
        damage_multiplier = self.status_manager.get_damage_multiplier()
        if damage_multiplier != 1.0:
            normal_min = int(normal_min * damage_multiplier)
            normal_max = int(normal_max * damage_multiplier)

            crit_min = int(crit_min * damage_multiplier)
            crit_max = int(crit_max * damage_multiplier)

            dht_min = int(dht_min * damage_multiplier)
            dht_max = int(dht_max * damage_multiplier)

            crit_dht_min = int(crit_dht_min * damage_multiplier)
            crit_dht_max = int(crit_dht_max * damage_multiplier)

        # Return damage result with all components
        return DamageResult(
            action_id=action_id,
            potency=potency,
            normal_hit=(prob_normal, normal_min, normal_max),
            critical_hit=(prob_crit, crit_min, crit_max),
            direct_hit=(prob_dht, dht_min, dht_max),
            critical_direct_hit=(prob_crit_dht, crit_dht_min, crit_dht_max),
        )


class Enemy(BattleCharacter):
    """
    Enemy character in battle with simplified mechanics.

    This class represents NPCs, monsters, and bosses in the simulation
    with their own stats and behaviors.

    Attributes:
        stats (Dict[str, float]): Basic enemy stats
    """

    def __init__(self, entity_id: int, level: int, stats: Dict[str, float]):
        """
        Initialize an enemy character.

        Args:
            entity_id: Unique identifier for this character
            level: Enemy level
            stats: Dict of enemy stats
        """
        super().__init__(entity_id=entity_id)
        self.level = level
        self.stats = stats

    def calculate_potency_damage(
        self,
        action_id: ActionID,
        potency: float,
        damage_type: DamageType,
        auto_crt: bool = False,
        auto_dht: bool = False,
    ) -> DamageResult:
        """
        Calculate enemy damage based on simplified formulas.

        Args:
            action_id: The ID of the action being used
            potency: The potency value of the action
            damage_type: The type of damage calculation to use
            auto_crt: Guarantee a critical hit
            auto_dht: Guarantee a direct hit

        Returns:
            DamageResult: The calculated damage
        """
        # Simplified enemy damage calculation
        base_damage = int(
            potency * (self.level / 100) * self.stats.get("attack_power", 100)
        )
        damage_multiplier = self.status_manager.get_damage_multiplier()

        final_damage = int(base_damage * damage_multiplier)

        # Return simplified damage result
        return DamageResult(
            action_id=action_id,
            potency=potency,
            normal_hit=(1.0, final_damage, final_damage),
            critical_hit=(0.0, 0, 0),
            direct_hit=(0.0, 0, 0),
            critical_direct_hit=(0.0, 0, 0),
        )


class Arena:
    """
    FFXIV Arena that contains all entities and manages the battle simulation.

    The Arena class is the central coordinator of the battle simulation, responsible for:
    - Managing all battle entities (players and enemies)
    - Scheduling and processing events
    - Advancing the simulation time
    - Coordinating state updates for all entities

    It uses a discrete event simulation approach to efficiently advance time
    to the next significant event rather than using fixed time steps.

    Attributes:
        task_queue (list): Priority queue of scheduled events
        current_time (int): Current simulation time in milliseconds. The time is a relative time to the start of the fight. Timestamp in pre-pull stage will be negative.
        players (List[Player]): List of player characters in the simulation
        enemies (List[BattleCharacter]): List of enemy characters in the simulation
    """

    def __init__(self, time: int = -30_000):
        """Initialize a new battle simulation world."""
        self.task_queue = []
        self.current_time = time
        self.players: List[Player] = []
        self.enemies: List[BattleCharacter] = []

    def get_player(self, player_id: int) -> Optional[Player]:
        """
        Get a player by their ID.
        """
        if player_id in self.players:
            return self.players[player_id]
        else:
            return None

    def add_player(self, player: Player):
        """
        Add a player character to the simulation.

        Args:
            player: The player character to add
        """
        self.players.append(player)
        player.world = self
        player.local_time = self.current_time

        # Set the default target if enemies exist
        if not player.current_target and self.enemies:
            player.set_target(self.enemies[0])

    def add_enemy(self, enemy: BattleCharacter):
        """
        Add an enemy character to the simulation.

        Args:
            enemy: The enemy character to add
        """
        self.enemies.append(enemy)
        enemy.world = self
        enemy.local_time = self.current_time

        # Set default targets for players that don't have targets
        self.set_default_targets()

    def set_default_targets(self):
        """
        Set default targets for all players that don't have a target set.
        """
        if not self.enemies:
            return

        default_target = self.enemies[0]
        for player in self.players:
            if not player.current_target:
                player.set_target(default_target)

    def schedule_task(self, delay: int, callback: Callable, *args, **kwargs):
        """
        Schedule a task to execute after a specified delay.

        Args:
            delay: Time in milliseconds until the event should occur
            callback: Function to call when the event occurs
            *args: Positional arguments to pass to the callback function
            **kwargs: Keyword arguments to pass to the callback function
        """
        heapq.heappush(self.task_queue, Task(self.current_time + delay, callback, args, kwargs))

    def step(self, frame_delta: int):
        """
        Run the simulation for the specified duration.

        This method advances the simulation time, processes events, and
        updates entity states until the duration is reached.

        Args:
            frame_delta: Time in milliseconds between two frames
        """
        remaining_time = frame_delta
        while True:
            self._process_events()
            if remaining_time <= 0:
                break

            # update entities
            step_size = self._calc_step_size()
            if step_size is None or step_size > remaining_time:
                step_size = remaining_time

            remaining_time -= step_size
            self.current_time += step_size

            for player in self.players:
                player.step(step_size=step_size)
            for enemy in self.enemies:
                enemy.step(step_size=step_size)

    def _process_events(self):
        """
        Process all events that are due based on the current simulation time.

        This method executes all scheduled event callbacks that have reached
        their scheduled time.
        """
        if len(self.task_queue) <= 0:
            return

        event = self.task_queue[0]
        while True:
            if event.time > self.current_time:
                break

            event.execute()
            heapq.heappop(self.task_queue)
            if len(self.task_queue) <= 0:
                break

            event = self.task_queue[0]

    def _calc_step_size(self) -> Optional[int]:
        """
        Calculate the optimal step size to advance the clock.

        This method determines the time until the next relevant event by
        examining the scheduled events and entity states. This allows
        the simulation to efficiently skip periods where nothing significant
        happens.

        Returns:
            Optional[int]: Milliseconds to advance the simulation, or None if
                          no future events are scheduled
        """
        step_size: Optional[int] = None
        if len(self.task_queue) > 0:
            event = self.task_queue[0]
            step_size_next_event = event.time - self.current_time
            if step_size is None or step_size_next_event < step_size:
                step_size = step_size_next_event

        for player in self.players:
            step_size_player = player.calc_step_size()
            if step_size_player is not None:
                if step_size is None or step_size_player < step_size:
                    step_size = step_size_player

        for enemy in self.enemies:
            step_size_enemy = enemy.calc_step_size()
            if step_size_enemy is not None:
                if step_size is None or step_size_enemy < step_size:
                    step_size = step_size_enemy

        return step_size

    def start_server_tick(self, delay: int = 0):
        """
        Start the regular server tick system for periodic effects.

        This sets up a recurring event that applies "tick" effects for
        all status effects (like DoTs) on a 3-second interval, matching
        the game's server tick behavior.
        """

        def server_tick():
            for character in self.players:
                for status in character.status_manager.get_active_statuses():
                    status.tick()

            for character in self.enemies:
                for status in character.status_manager.get_active_statuses():
                    status.tick()

            self.schedule_task(delay=3000, callback=server_tick)

        self.schedule_task(delay=delay, callback=server_tick)
