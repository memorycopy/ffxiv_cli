"""
Samurai Job Module for FFXIV Combat Simulation

This module implements the Samurai job mechanics from Final Fantasy XIV, including:
- Weapon skills and abilities
- Sen gauge management
- Iaijutsu and Tsubamegaeshi techniques
- Job-specific status effects and buffs
- Combo system interactions

The implementation follows the in-game mechanics with a focus on accurate damage
calculations, combo flows, and gauge management. Classes represent different
weapon skills and status effects while functions handle common operations like
meditation management and combo validation.
"""

from xivcore.core import *


def is_samurai(caster: "BattleCharacter") -> bool:
    """
    Checks if the caster is a Samurai job.

    Args:
        caster: The battle character to check.

    Returns:
        bool: True if the caster is a Samurai, False otherwise.
    """
    if not isinstance(caster, Player) or caster.job != JobClass.SAMURAI:
        return False

    job_gauge = caster.job_gauge
    if not isinstance(job_gauge, SamuraiGauge):
        return False

    return True


def consume_meikyo(caster: "BattleCharacter"):
    """
    Consumes one stack of Meikyo Shisui status effect from the caster.

    Meikyo Shisui allows the Samurai to use combo finishers without
    performing the preceding combo actions.

    Args:
        caster: The battle character whose Meikyo Shisui status will be consumed.

    Returns:
        bool: True if a stack was successfully consumed, False if the status
              doesn't exist or has no stacks remaining.
    """
    meikyo = caster.status_manager.get_status(StatusID.MEIKYO)
    if meikyo is not None:
        return meikyo.consume_stack()
    return False


def check_combo_chain(caster: "BattleCharacter", precombo_action_id: ActionID):
    """
    Checks if the caster has a valid combo chain.

    Args:
        caster: The battle character checking the combo chain.
        precombo_action_id: The action ID of the preceding combo action.

    Returns:
        bool: True if the combo chain is valid, False otherwise.
    """
    if caster.status_manager.has_status(StatusID.MEIKYO):
        return True
    return caster.action_manager.check_combo_chain(precombo_action_id)


def get_samurai_gauge(caster: "BattleCharacter") -> Optional["SamuraiGauge"]:
    """
    Gets the Samurai gauge from the caster.

    Args:
        caster: The battle character whose Samurai gauge will be retrieved.

    Returns:
        SamuraiGauge: The Samurai gauge of the caster, or None if not found.
    """
    if hasattr(caster, 'job_gauge') and isinstance(caster.job_gauge, SamuraiGauge):
        return caster.job_gauge
    return None


class EnhancedEnpiEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 15_000,
    ):
        super().__init__(
            status_id=StatusID.ENHANCED_ENPI,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )


class MeditateEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 15_000,
    ):
        super().__init__(
            status_id=StatusID.MEDITATE,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )

    def tick(self):
        job_gauge = get_samurai_gauge(self.target)
        if job_gauge is not None:
            job_gauge.add_kenki(amount=10)
            job_gauge.add_meditation()

    def on_start_using(self, action_id: ActionID):
        # Stops the meditation effect when player acts
        self.target.status_manager.remove_status(status_id=self.status_id)


class TengetsuEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 4_000,
    ):
        super().__init__(
            status_id=StatusID.THIRD_EYE,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )

    def on_damage_taken(self):
        jog_gauge = get_samurai_gauge(self.target)
        jog_gauge.add_kenki(amount=10)


class FugetsuEffect(BuffStatus):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 40_000,
    ):
        super().__init__(
            status_id=StatusID.FUGETSU,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            damage_multiplier=1.13,
        )


class FukaEffect(BuffStatus):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 40_000,
    ):
        super().__init__(
            status_id=StatusID.FUKA,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            speed_multiplier=0.87,
            speed_scope=SpeedFlags.RECAST | SpeedFlags.AUTO_ATTACK,
        )


class MeikyoShisuiEffect(StackableStatus):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 20_000,
            stacks: int = 3,
            max_stacks: int = 3,
    ):
        super().__init__(
            status_id=StatusID.MEIKYO,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            stacks=stacks,
            max_stacks=max_stacks,
            is_buff=True,
        )


class TsubamegaeshiEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 30_000,
    ):
        super().__init__(
            status_id=StatusID.TSUBAMEGAESHI,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )

    def on_remove(self):
        pass


class NamikiriReadyEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 30_000,
    ):
        super().__init__(
            status_id=StatusID.NAMIKIRI_READY,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )


class ZanshinReadyEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 30_000,
    ):
        super().__init__(
            status_id=StatusID.ZANSHIN_READY,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )


class TendoEffect(StatusEffect):
    def __init__(
            self,
            action_id: ActionID,
            target: "BattleCharacter",
            source: "BattleCharacter",
            duration: int = 30_000,
    ):
        super().__init__(
            status_id=StatusID.TENDO,
            action_id=action_id,
            target=target,
            source=source,
            duration=duration,
            is_buff=True,
        )


class SamuraiPvEAction(PvEAction):
    def can_use(self, caster: "BattleCharacter", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False
        if not is_samurai(caster):
            return False
        return True


class SamuraiWeaponSkill(SamuraiPvEAction):
    def __init__(
            self,
            action_id: ActionID,
            name: str,
            cast_time: int = 0,
            additional_cooldown_group: int = 0,
            max_charges: int = 1,
            animation_lock: int = ANIMATION_LOCK,
    ):
        super().__init__(
            action_id=action_id,
            name=name,
            cast_time=cast_time,
            recast_time=2500,
            cooldown_group=RECAST_GROUP_GCD,
            additional_cooldown_group=additional_cooldown_group,
            max_charges=max_charges,
            animation_lock=animation_lock
        )

    def can_use(self, caster: "BattleCharacter", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        # Weapon skill requirements an enmity target
        if target is None or target.entity_id == caster.entity_id:
            return False

        return True


class Enpi(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.ENPI, name="燕飞")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.add_kenki(amount=10)
        job_gauge.reset_kaeshi_namikiri()

        potency = 100
        if caster.status_manager.remove_status(StatusID.ENHANCED_ENPI):
            potency = 270

        damage = caster.calculate_potency_damage(
            action_id=self.action_id,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
        )
        caster.world.schedule_task(
            delay=ANIMATION_LOCK,
            callback=target.take_damage,
            damage=damage,
        )
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)
        return True


class Gyofu(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.GYOFU, name="晓风")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        consume_meikyo(caster)
        job_gauge.add_kenki(amount=5)
        job_gauge.reset_kaeshi_namikiri()

        potency = 240
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.SUCCESS)


class Jinpu(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.JINPU, name="阵风")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.reset_kaeshi_namikiri()

        potency = 140
        if check_combo_chain(caster, ActionID.HAKAZE) or check_combo_chain(caster, ActionID.GYOFU):
            potency = 300
            consume_meikyo(caster)
            job_gauge.add_kenki(amount=5)
            caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.SUCCESS)
            caster.world.schedule_task(
                delay=ANIMATION_LOCK,
                callback=caster.status_manager.add_status,
                status=FugetsuEffect(
                    action_id=self.action_id,
                    target=target,
                    source=caster
                ),
            )
        else:
            caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.RESET)

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )


class Shifu(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.SHIFU, name="士风")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.reset_kaeshi_namikiri()

        potency = 140
        if check_combo_chain(caster, ActionID.HAKAZE) or check_combo_chain(caster, ActionID.GYOFU):
            potency = 300
            consume_meikyo(caster)
            job_gauge.add_kenki(amount=5)
            caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.SUCCESS)
            caster.world.schedule_task(
                delay=ANIMATION_LOCK,
                callback=caster.status_manager.add_status,
                status=FukaEffect(
                    action_id=self.action_id,
                    target=target,
                    source=caster
                ),
            )
        else:
            caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.RESET)

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )


class Yukikaze(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.YUKIKAZE, name="雪风")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.reset_kaeshi_namikiri()

        potency = 160
        if check_combo_chain(caster, ActionID.HAKAZE) or check_combo_chain(caster, ActionID.GYOFU):
            potency = 340
            consume_meikyo(caster)
            job_gauge.add_kenki(amount=15)
            job_gauge.add_sen(sen_flag=Sen.SETSU)

        caster.action_manager.set_last_cast(
            action_id=self.action_id, combo_flag=ComboFlag.RESET
        )

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )


class Gekko(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.GEKKO, name="月光")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.reset_kaeshi_namikiri()

        potency = 210
        if check_combo_chain(caster, ActionID.JINPU):
            potency = 420
            job_gauge.add_kenki(amount=10)
            job_gauge.add_sen(sen_flag=Sen.GETSU)

            # grants buff if a meikyo stack is consumed
            if consume_meikyo(caster):
                caster.world.schedule_task(
                    delay=ANIMATION_LOCK,
                    callback=caster.status_manager.add_status,
                    status=FugetsuEffect(
                        action_id=self.action_id,
                        target=target,
                        source=caster
                    )
                )

        caster.action_manager.set_last_cast(
            action_id=self.action_id, combo_flag=ComboFlag.RESET
        )

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )


class Kasha(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.KASHA, name="花车")

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.reset_kaeshi_namikiri()

        potency = 210
        if check_combo_chain(caster, ActionID.SHIFU):
            potency = 420
            job_gauge.add_kenki(amount=10)
            job_gauge.add_sen(sen_flag=Sen.KA)

            # grants buff if a meikyo stack is consumed
            if consume_meikyo(caster):
                caster.world.schedule_task(
                    delay=ANIMATION_LOCK,
                    callback=caster.status_manager.add_status,
                    status=FukaEffect(
                        action_id=self.action_id,
                        target=target,
                        source=caster
                    )
                )

        caster.action_manager.set_last_cast(
            action_id=self.action_id, combo_flag=ComboFlag.RESET
        )

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )


class Higanbana(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.HIGANBANA, name="彼岸花", cast_time=1300)

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() != 1:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        potency = 200
        dot_potency = 50

        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        target.add_status(DoTStatus(
            status_id=StatusID.HIGANBANA,
            action_id=self.action_id,
            target=target,
            source=caster,
            duration=60_000,
            potency=dot_potency,
        ))

        # Since patch 7.05 there is no need to set tsubamegaeshi and break kaeshi_namikiri

        job_gauge.clear_sen()
        job_gauge.add_meditation()
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class TenkaGoken(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(
            action_id=ActionID.TENKA_GOKEN, name="天下五剑", cast_time=1300
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        if caster.status_manager.has_status(StatusID.TENDO):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() != 2:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.set_tsubamegaeshi(self.action_id)
        # job_gauge.reset_kaeshi_namikiri()
        job_gauge.clear_sen()
        job_gauge.add_meditation()

        potency = 300
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        caster.status_manager.add_status(TsubamegaeshiEffect(
            action_id=self.action_id,
            target=caster,
            source=caster,
            duration=30_000
        ))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class KaeshiGoken(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.KAESHI_GOKEN, name="回返五剑")

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if not job_gauge.check_tsubamegaeshi(ActionID.TENKA_GOKEN, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.reset_tsubamegaeshi()
        job_gauge.reset_kaeshi_namikiri()

        potency = 300
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        caster.status_manager.remove_status(StatusID.TSUBAMEGAESHI)

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class MidareSetsugekka(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.MIDARE_SETSUGEKKA, name="纷乱雪月花", cast_time=1300)

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        if caster.status_manager.has_status(StatusID.TENDO, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() != 3:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.clear_sen()
        job_gauge.add_meditation()
        job_gauge.set_tsubamegaeshi(self.action_id)

        potency = 640
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.status_manager.add_status(TsubamegaeshiEffect(
            action_id=self.action_id,
            target=caster,
            source=caster
        ))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class KaeshiSetsugekka(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.KAESHI_SETSUGEKKA, name="回返雪月花")

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if not job_gauge.check_tsubamegaeshi(ActionID.MIDARE_SETSUGEKKA, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.reset_tsubamegaeshi()
        job_gauge.reset_kaeshi_namikiri()

        potency = 640
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.status_manager.remove_status(StatusID.TSUBAMEGAESHI)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class OgiNamikiri(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.OGI_NAMIKIRI, name="奥义斩浪", cast_time=1300)

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        if not caster.status_manager.has_status(StatusID.NAMIKIRI_READY, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        # NAMIKIRI_READY expired before applying the action effect
        if not caster.status_manager.has_status(StatusID.NAMIKIRI_READY):
            # FIXME: reset the cooldown
            return

        job_gauge = get_samurai_gauge(caster)
        job_gauge.set_kaeshi_namikiri_ready()
        job_gauge.add_meditation()

        potency = 1000
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.status_manager.remove_status(StatusID.NAMIKIRI_READY)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class KaeshiNamikiri(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.KAESHI_NAMIKIRI, name="回返斩浪")

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if not job_gauge.kaeshi_namikiri_ready or job_gauge.kaeshi_namikiri_timer <= tolerance:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.reset_kaeshi_namikiri()

        potency = 1000
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class TendoGoken(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.TENDO_GOKEN, name="天道五剑", cast_time=1300)

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        if not caster.status_manager.has_status(StatusID.TENDO, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() != 2:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        # Tendo expired before applying the action effect
        if not caster.status_manager.has_status(StatusID.TENDO):
            # FIXME: reset the cooldown
            return

        job_gauge = get_samurai_gauge(caster)
        job_gauge.clear_sen()
        job_gauge.add_meditation()
        job_gauge.set_tsubamegaeshi(self.action_id)

        potency = 410
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        caster.status_manager.remove_status(StatusID.TENDO)
        caster.status_manager.add_status(TsubamegaeshiEffect(
            action_id=self.action_id,
            target=caster,
            source=caster,
            duration=30_000
        ))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class TendoKaeshiGoken(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.TENDO_KAESHI_GOKEN, name="天道回返五剑")

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if not job_gauge.check_tsubamegaeshi(ActionID.TENDO_GOKEN, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.reset_tsubamegaeshi()
        job_gauge.reset_kaeshi_namikiri()

        potency = 410
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK
        )

        caster.status_manager.remove_status(StatusID.TSUBAMEGAESHI)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class TendoSetsugekka(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.TENDO_SETSUGEKKA, name="天道雪月花", cast_time=1300)

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        if not caster.status_manager.has_status(StatusID.TENDO, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() != 3:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        # Tendo expired before applying the action effect
        if not caster.status_manager.has_status(StatusID.TENDO):
            # FIXME: reset the cooldown
            return

        job_gauge = get_samurai_gauge(caster)
        job_gauge.clear_sen()
        job_gauge.add_meditation()
        job_gauge.set_tsubamegaeshi(self.action_id)

        potency = 1100
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.status_manager.remove_status(StatusID.TENDO)
        caster.status_manager.add_status(TsubamegaeshiEffect(
            action_id=self.action_id,
            target=caster,
            source=caster,
            duration=30_000
        ))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class TendoKaeshiSetsugekka(SamuraiWeaponSkill):
    def __init__(self):
        super().__init__(action_id=ActionID.TENDO_KAESHI_SETSUGEKKA, name="天道回返雪月花")

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=target, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if not job_gauge.check_tsubamegaeshi(ActionID.TENDO_SETSUGEKKA, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.reset_tsubamegaeshi()
        job_gauge.reset_kaeshi_namikiri()

        potency = 1100
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
            auto_crt=True
        )

        caster.status_manager.remove_status(StatusID.TSUBAMEGAESHI)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class MeikyoShisui(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.MEIKYO_SHISUI,
            name="明镜止水",
            cast_time=0,
            recast_time=55_000,
            cooldown_group=19,
            additional_cooldown_group=0,
            max_charges=2,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False
        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        # job_gauge = get_samurai_gauge(caster)

        caster.status_manager.add_status(MeikyoShisuiEffect(
            action_id=self.action_id, source=caster, target=caster))
        caster.status_manager.add_status(TendoEffect(
            action_id=self.action_id, source=caster, target=caster))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Ikishoten(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.IKISHOTEN,
            name="意气冲天",
            cast_time=0,
            recast_time=120_000,
            cooldown_group=20,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False
        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)

        job_gauge.add_kenki(amount=50)
        caster.status_manager.add_status(NamikiriReadyEffect(
            action_id=self.action_id, source=caster, target=caster))
        caster.status_manager.add_status(ZanshinReadyEffect(
            action_id=self.action_id, source=caster, target=caster))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Zanshin(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.ZANSHIN,
            name="残心",
            cast_time=0,
            recast_time=1_000,
            cooldown_group=3,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        if not caster.status_manager.has_status(StatusID.ZANSHIN_READY, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.kenki < 50:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.spend_kenki(amount=50)

        potency = 940
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.status_manager.remove_status(StatusID.ZANSHIN_READY)
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Shoha(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.SHOHA,
            name="照破",
            cast_time=0,
            recast_time=15_000,
            cooldown_group=8,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.meditation_stacks < 3:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.use_meditation()

        potency = 640
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class HissatsuSenei(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.HISSATSU_SENEI,
            name="必杀剑：闪影",
            cast_time=0,
            recast_time=60_000,
            cooldown_group=22,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.kenki < 25:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.spend_kenki(amount=25)

        potency = 800
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class HissatsuShinten(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.HISSATSU_SHINTEN,
            name="必杀剑：震天",
            cast_time=0,
            recast_time=1_000,
            cooldown_group=2,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.kenki < 25:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.spend_kenki(amount=25)

        potency = 250
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class HissatsuGyoten(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.HISSATSU_GYOTEN,
            name="必杀剑：晓天",
            cast_time=0,
            recast_time=5_000,
            cooldown_group=5,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.kenki < 10:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.spend_kenki(amount=10)

        potency = 100
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class HissatsuYaten(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.HISSATSU_YATEN,
            name="必杀剑：夜天",
            cast_time=0,
            recast_time=10_000,
            cooldown_group=6,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.kenki < 10:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.spend_kenki(amount=10)

        potency = 100
        caster.prepare_action_damage(
            action_id=self.action_id,
            target=target,
            potency=potency,
            damage_type=DamageType.WEAPON_SKILL,
            delay=ANIMATION_LOCK,
        )

        caster.status_manager.add_status(EnhancedEnpiEffect(
            action_id=self.action_id,
            source=caster,
            target=caster
        ))

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Tengetsu(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.THIRD_EYE,
            name="天眼通",
            cast_time=0,
            recast_time=15_000,
            cooldown_group=7,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.add_kenki(amount=10, allow_overflow=True)  # FIXME: remove this if boss machanism is implemented
        caster.status_manager.add_status(TengetsuEffect(
            action_id=self.action_id,
            source=caster,
            target=caster
        ))
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Meditate(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.MEDITATE,
            name="默想",
            cast_time=0,
            recast_time=60_000,
            cooldown_group=13,
            additional_recast_time=2500,
            additional_cooldown_group=RECAST_GROUP_GCD
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        caster.status_manager.add_status(MeditateEffect(
            action_id=self.action_id,
            source=caster,
            target=caster
        ))
        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


class Hagakure(SamuraiPvEAction):
    def __init__(self):
        super().__init__(
            action_id=ActionID.HAGAKURE,
            name="叶隐",
            cast_time=0,
            recast_time=5_000,
            cooldown_group=4,
            additional_cooldown_group=0,
            max_charges=1,
        )

    def can_use(self, caster: "Player", target: Optional["BattleCharacter"] = None, tolerance: int = 0) -> bool:
        if not super().can_use(caster=caster, target=caster, tolerance=tolerance):
            return False

        job_gauge = get_samurai_gauge(caster)
        if job_gauge.count_sen() < 1:
            return False

        return True

    def _apply_effect(self, caster: "BattleCharacter", target: Optional["BattleCharacter"]):
        job_gauge = get_samurai_gauge(caster)
        job_gauge.clear_sen()
        num_sen = job_gauge.count_sen()
        job_gauge.add_kenki(amount=num_sen * 10)

        caster.action_manager.set_last_cast(action_id=self.action_id, combo_flag=ComboFlag.NONE)


def register_samurai_actions(caster: "BattleCharacter"):
    """Register all samurai actions for the given caster"""

    # GCDs
    caster.action_manager.register_action(Enpi())
    caster.action_manager.register_action(Gyofu())
    caster.action_manager.register_action(Jinpu())
    caster.action_manager.register_action(Shifu())
    caster.action_manager.register_action(Yukikaze())
    caster.action_manager.register_action(Gekko())
    caster.action_manager.register_action(Kasha())
    caster.action_manager.register_action(Higanbana())
    caster.action_manager.register_action(TenkaGoken())
    caster.action_manager.register_action(KaeshiGoken())
    caster.action_manager.register_action(MidareSetsugekka())
    caster.action_manager.register_action(KaeshiSetsugekka())
    caster.action_manager.register_action(OgiNamikiri())
    caster.action_manager.register_action(KaeshiNamikiri())
    caster.action_manager.register_action(TendoGoken())
    caster.action_manager.register_action(TendoKaeshiGoken())
    caster.action_manager.register_action(TendoSetsugekka())
    caster.action_manager.register_action(TendoKaeshiSetsugekka())

    # oGCDs
    caster.action_manager.register_action(MeikyoShisui())
    caster.action_manager.register_action(Ikishoten())
    caster.action_manager.register_action(Zanshin())
    caster.action_manager.register_action(Shoha())
    caster.action_manager.register_action(HissatsuSenei())
    caster.action_manager.register_action(HissatsuShinten())
    caster.action_manager.register_action(HissatsuGyoten())
    caster.action_manager.register_action(HissatsuYaten())
    caster.action_manager.register_action(Tengetsu())
    caster.action_manager.register_action(Meditate())
    caster.action_manager.register_action(Hagakure())
