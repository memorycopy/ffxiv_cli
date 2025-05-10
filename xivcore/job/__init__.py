from xivcore.core import *

import xivcore.job.samurai
import xivcore.job.ninja
import xivcore.job.monk
import xivcore.job.dragoon
import xivcore.job.viper
import xivcore.job.pictomancer


class PotionEffect(BuffStatus):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 30_000,
            main_stat_bonus=0.1,
            main_stat_bonus_max=392
    ):
        super().__init__(
            status_id=StatusID.ENHANCED_ENPI,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            main_stat_bonus=main_stat_bonus,
            main_stat_bonus_max=main_stat_bonus_max
        )


class Potion(PvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.POTION,
            name="强化药",
            cast_time=0,
            recast_time=270_000,
            cooldown_group=59,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        caster.status_manager.remove_status(StatusID.MEDITATE)
        caster.status_manager.add_status(PotionEffect(
            action_id=self.action_id, source=caster, target=caster))

        caster.action_manager.start_cooldown(self.action_id)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)
        caster.action_manager.animation_lock = ANIMATION_LOCK


def register_common_actions(caster: "BattleCharacter"):
    """Register all common actions for the given caster"""

    # GCDs
    caster.action_manager.register_action(Potion())
