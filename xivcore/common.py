"""Common definitions and utilities for XIV gameplay mechanics.

This module contains constants, enumerations, and utility functions for
modeling Final Fantasy XIV gameplay mechanics, including job-specific
properties, combat calculations, and game systems.
"""

from enum import IntEnum, Flag
from dataclasses import dataclass

# Global timing constants (in milliseconds)
SERVER_TICK_DURATION = 3000  # Server tick duration in milliseconds
ANIMATION_LOCK = 700  # Animation lock duration after using an ability
NETWORK_DELAY = 100  # Average network delay for client-server communication
GCD_MAX = 2500  # Maximum Global Cooldown (GCD) recast time
GCD_PENALTY = 12  # GCD penalty coefficient used in reduction calculations
AUTO_PENALTY = 8  # Auto-attack penalty coefficient (server tick interval)
AUTO_ATTACK_BEFORE_CAST = 300  # Time before cast for auto-attack to register
RECAST_GROUP_GCD = 57  # GCD recast group ID in the game data


def format_ms(ms: int):
    """
    Format integer milliseconds to "mm:ss.000" string format,
    handling both positive and negative values.

    Args:
        ms (int): Time in milliseconds (positive or negative)

    Returns:
        str: Formatted time string "±mm:ss.000" with optional "-" sign for negative values
    """
    # Handle negative values
    is_negative = ms < 0
    abs_ms = abs(ms)

    # Calculate minutes, seconds, and remaining milliseconds
    minutes = (abs_ms // 60000) % 60
    seconds = (abs_ms // 1000) % 60
    milliseconds = abs_ms % 1000

    # Format as "mm:ss.000" with a negative sign if needed
    if is_negative:
        return f"-{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    else:
        return f"+{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class DamageType(IntEnum):
    """Enumeration of different damage types in the game.

    Attributes:
        WEAPON_SKILL: Damage from physical weaponskills
        SPELL: Damage from magical spells
        DOT: Damage over time effects
        AUTO_ATTACK: Damage from auto-attacks
    """

    WEAPON_SKILL = 0
    SPELL = 1
    DOT = 2
    AUTO_ATTACK = 3


class SpeedFlags(Flag):
    """Flags representing different types of speed modifiers.

    These flags are used to specify which types of actions are affected by
    speed modifiers from status effects.

    Attributes:
        NONE: No speed modifiers.
        CAST: Affects spell cast times.
        RECAST: Affects ability recast times (cooldowns).
        AUTO_ATTACK: Affects auto-attack speed.
        ALL: Affects all types of speed (cast, recast, and auto-attack).
    """

    NONE = 0
    CAST = 1
    RECAST = 2
    AUTO_ATTACK = 4
    ALL = CAST | RECAST | AUTO_ATTACK


class ComboFlag(IntEnum):
    """Flags indicating combo action states.

    Attributes:
        NONE: No combo effect active
        SUCCESS: Successful combo execution
        RESET: Combo chain has been reset
    """

    NONE = 0
    SUCCESS = 1
    RESET = 2


# Job-specific enums
class Fury(IntEnum):
    """Astrologian Fury gauge states.

    Attributes:
        NONE: No Fury stance active
        SOLAR: Solar Fury stance active
        LUNAR: Lunar Fury stance active
    """

    NONE = 0
    SOLAR = 1
    LUNAR = 2


class Form(IntEnum):
    """Monk form states.

    Attributes:
        NONE: No form stance active
        OPO: Opo-Opo form stance active
        RAPTOR: Raptor form stance active
        COEURL: Coeurl form stance active
    """

    NONE = 0
    OPO = 1
    RAPTOR = 2
    COEURL = 3


class Nadi(IntEnum):
    """Monk Nadi gauge states in Endwalker.

    Attributes:
        NONE: No Nadi active
        LUNAR: Lunar Nadi active
        SOLAR: Solar Nadi active
    """

    NONE = 0
    LUNAR = 1
    SOLAR = 2


class Sen(Flag):
    """Samurai Sen gauge flags.

    These flags can be combined to represent multiple Sen.

    Attributes:
        NONE: No Sen accumulated
        SETSU: Setsu Sen accumulated
        GETSU: Getsu Sen accumulated
        KA: Ka Sen accumulated
    """

    NONE = 0
    SETSU = 1
    GETSU = 2
    KA = 4


# Job IDs - aligned with FFXIV's official ClassJob enum
class JobClass(IntEnum):
    """Job and class IDs matching FFXIV's official ClassJob enumeration.

    Contains all playable jobs and classes in the game.
    """

    # Base classes
    ADVENTURER = 0
    GLADIATOR = 1
    PUGILIST = 2
    MARAUDER = 3
    LANCER = 4
    ARCHER = 5
    CONJURER = 6
    THAUMATURGE = 7

    # Crafters
    CARPENTER = 8
    BLACKSMITH = 9
    ARMORER = 10
    GOLDSMITH = 11
    LEATHERWORKER = 12
    WEAVER = 13
    ALCHEMIST = 14
    CULINARIAN = 15

    # Gatherers
    MINER = 16
    BOTANIST = 17
    FISHER = 18

    # Jobs
    PALADIN = 19
    MONK = 20
    WARRIOR = 21
    DRAGOON = 22
    BARD = 23
    WHITE_MAGE = 24
    BLACK_MAGE = 25
    ARCANIST = 26
    SUMMONER = 27
    SCHOLAR = 28
    ROGUE = 29
    NINJA = 30
    MACHINIST = 31
    DARK_KNIGHT = 32
    ASTROLOGIAN = 33
    SAMURAI = 34
    RED_MAGE = 35
    BLUE_MAGE = 36
    GUNBREAKER = 37
    DANCER = 38
    REAPER = 39
    SAGE = 40
    VIPER = 41
    PICTOMANCER = 42


# Role Categories - aligned with FFXIV's role system
class Role(IntEnum):
    """Role categories matching FFXIV's role system.

    Contains both primary roles and more specific sub-roles.

    Attributes:
        NONE: No specific role
        TANK: Tank role
        HEALER: Healer role
        DPS: General DPS role
        CRAFTER: Crafting classes
        GATHERER: Gathering classes
        DPS_MELEE: Melee DPS sub-role
        DPS_RANGED_PHYSICAL: Physical ranged DPS sub-role
        DPS_RANGED_MAGICAL: Magical ranged DPS sub-role
    """

    NONE = 0
    TANK = 1
    HEALER = 2
    DPS = 3
    CRAFTER = 4
    GATHERER = 5

    # Sub-roles for more specific categorization
    DPS_MELEE = 10
    DPS_RANGED_PHYSICAL = 11
    DPS_RANGED_MAGICAL = 12


# Status and buff IDs from the game
class StatusID(IntEnum):
    """Status effect IDs from FFXIV.

    Contains IDs for buffs, debuffs, and job-specific status effects.
    These match the official game IDs.
    """

    # General
    POTION = 49

    # Role status effects
    FEINT = 1195
    ARMS_LENGTH = 1209
    BLOOD_BATH = 84
    TRUE_NORTH = 1250
    SWIFT_CAST = 167
    SURE_CAST = 168
    ADDLE = 1203
    LUCID_DREAMING = 1204

    # Job gauges status effects
    # Monk
    OPOOPO_FORM = 109
    RAPTOR_FORM = 107
    COEURL_FORM = 108
    PERFECT_BALANCE = 110
    LEADEN_FIST = 1861
    DISCIPLINED_FIST = 3001
    DEMOLISH = 246
    BROTHERHOOD = 1185
    FORMLESS_FIST = 2513
    RIDDLE_OF_WIND = 2687
    RIDDLE_OF_FIRE = 1181
    MEDITATIVE_BROTHERHOOD = 1182

    # Samurai
    HIGANBANA = 1228
    MEDITATE = 1231
    THIRD_EYE = 1232
    MEIKYO = 1233
    ENHANCED_ENPI = 1236
    FUGETSU = 1298  # Jinpu buff
    FUKA = 1299  # Shifu buff
    NAMIKIRI_READY = 2959
    TENDO = 3600  # New in 7.0, granted by Meikyo Shisui
    ZANSHIN_READY = 3601  # New in 7.0, granted by Ikishoten
    TSUBAMEGAESHI = 3852  # New in 7.05, granted by laijutsu except higanbana

    # Dragoon
    DRAGON_SIGHT = 1911
    BATTLE_LITANY = 786

    # Dancer
    STANDARD_FINISH = 1821
    TECHNICAL_FINISH = 1822
    DEVILMENT = 1825

    # Reaper
    DEATHS_DESIGN = 2586
    SOUL_REAVER = 2587
    ENHANCED_GIBBET = 2588
    ENHANCED_GALLOWS = 2589
    ENHANCED_VOID_REAPING = 2590
    ENHANCED_CROSS_REAPING = 2591
    IMMORTAL_SACRIFICE = 2592
    ENSHROUDED = 2593
    SOUL_SOW = 2594
    THRESHOLD = 2595
    CREST_TIME_BORROWED = 2597
    ARCANE_CIRCLE = 2599
    CIRCLE_OF_SACRIFICE = 2600
    ENHANCED_HARPE = 2845

    # Astrologian
    DIVINATION = 1878
    THE_ARROW = 1885
    THE_BALANCE = 3887

    # Scholar
    CHAIN_STRATAGEM = 1221

    # Bard
    BATTLE_VOICE = 141
    THE_WANDERERS_MINUET = 2216
    MAGES_BALLAD = 2217
    ARMYS_PAEON = 2218
    RADIANT_FINALE = 2964

    # Red Mage
    EMBOLDEN = 1239

    # Summoner
    SEARING_LIGHT = 2703

    # Black Mage
    TRIPLE_CAST = 3

    # Pictomancer
    SUBTRACTIVE_PALETTE = 3674
    AETHERHUES = 3675
    AETHERHUES_II = 3676
    RAINBOW_BRIGHT = 3679
    HAMMER_TIME = 3680
    STAR_STRUCK = 3681
    SMUDGE = 3684
    STARRY_MUSE = 3685
    TEMPERA_COAT = 3686
    TEMPERA_GRASSA = 3687
    HYPER_PHANTASIA = 3688
    INSPIRATION = 3689

    # Tank raid buffs
    DIVINE_VEIL = 726  # Paladin
    SHAKE_IT_OFF = 1209  # Warrior - same as Arms Length
    DARK_MISSIONARY = 1894  # Dark Knight
    HEART_OF_LIGHT = 1839  # Gunbreaker

    # Healer raid buffs
    TEMPERANCE = 1872  # White Mage

    # DPS raid buffs
    DOKUMORI = 638  # Ninja


# Action IDs from the game
class ActionID(IntEnum):
    """Action ability IDs from FFXIV.

    Contains IDs for weaponskills, spells, and abilities that match
    the official game IDs.
    """

    NONE = 0  # For initialization

    ATTACK=7,

    # General actions
    SPRINT = 3
    MELEE = 7
    SHOT = 8
    POTION = 846
    FOOD = 847

    # Role actions - Tank
    RAMPART = 7531
    PROVOKE = 7533
    REPRISAL = 7535
    SHIRK = 7537
    INTERJECT = 7538
    LOW_BLOW = 7540

    # Role actions - Healer
    ESUNA = 7568
    RESCUE = 7571
    REPOSE = 16560

    # Role actions - Physical DPS
    SECOND_WIND = 7541
    BLOOD_BATH = 7542
    TRUE_NORTH = 7546
    ARMS_LENGTH = 7548
    FEINT = 7549
    LEG_SWEEP = 7863

    # Role actions - Magical DPS
    SURE_CAST = 7559
    ADDLE = 7560
    SWIFT_CAST = 7561
    LUCID_DREAMING = 7562
    SLEEP = 25880

    # Warrior actions - basic combo
    HEAVY_SWING = 31
    MAIM = 37
    STORMS_PATH = 42
    STORMS_EYE = 45
    INNER_BEAST = 49

    # Paladin actions
    FAST_BLADE = 9
    RIOT_BLADE = 15
    ROYAL_AUTHORITY = 3539

    # White Mage actions
    GLARE = 16533
    DIA = 16532
    ASSIZE = 3571

    # Samurai actions
    HAKAZE = 7477
    GYOFU = 36963
    JINPU = 7478
    SHIFU = 7479
    YUKIKAZE = 7480
    GEKKO = 7481
    KASHA = 7482
    MANGETSU = 7484
    OKA = 7485
    ENPI = 7486
    # IAIJUTSU = 7487  # Base action for iaijutsu
    MIDARE_SETSUGEKKA = 7487
    TENKA_GOKEN = 7488
    HIGANBANA = 7489
    HISSATSU_SHINTEN = 7490
    HISSATSU_GYOTEN = 7492
    HISSATSU_YATEN = 7493
    HAGAKURE = 7495
    MEDITATE = 7497
    THIRD_EYE = 7498
    MEIKYO_SHISUI = 7499
    KAESHI_SETSUGEKKA = 16486
    HISSATSU_SENEI = 16481
    IKISHOTEN = 16482
    SHOHA = 16487
    KAESHI_GOKEN = 16485
    FUKO = 25780
    OGI_NAMIKIRI = 25781
    KAESHI_NAMIKIRI = 25782
    DOOM_OF_THE_LIVING = 7861
    ZANSHIN = 36964
    TENDO_GOKEN = 36965
    TENDO_SETSUGEKKA = 36966
    TENDO_KAESHI_GOKEN = 36967
    TENDO_KAESHI_SETSUGEKKA = 36968

    # Monk actions
    BOOTSHINE = 53
    TRUE_STRIKE = 54
    SNAP_PUNCH = 56
    TWIN_SNAKES = 61
    MANTRA = 65
    DEMOLISH = 66
    PERFECT_BALANCE = 69
    DRAGON_KICK = 74
    ELIXIR_FIELD = 3545
    FORBIDDEN_CHAKRA = 3547
    FORM_SHIFT = 4262
    RIDDLE_OF_EARTH = 7394
    RIDDLE_OF_FIRE = 7395
    BROTHERHOOD_ACTION = 7396
    RIDDLE_OF_WIND = 25766
    SIX_SIDED_STAR = 16476
    THUNDERCLAP = 25762
    MASTERFUL_BLITZ = 25764
    CELESTIAL_REVOLUTION = 25765
    RISING_PHOENIX = 25768
    PHANTOM_RUSH = 25769

    # Reaper actions
    SLICE = 24373
    WAXING_SLICE = 24374
    INFERNAL_SLICE = 24375
    SHADOW_OF_DEATH = 24378
    SOUL_SLICE = 24380
    GIBBET = 24382
    GALLOWS = 24383
    PLENTIFUL_HARVEST = 24385
    HARPE = 24386
    SOULSOW = 24387
    HARVEST_MOON = 24388
    BLOOD_STALK = 24389
    UNVEILED_GIBBET = 24390
    UNVEILED_GALLOWS = 24391
    GLUTTONY = 24393
    ENSHROUD = 24394
    VOID_REAPING = 24395
    CROSS_REAPING = 24396
    COMMUNIO = 24398
    LEMURES_SLICE = 24399
    HELLS_INGRESS = 24401
    HELLS_EGRESS = 24402
    REGRESS = 24403
    ARCANE_CREST = 24404
    ARCANE_CIRCLE = 24405

    # Viper actions
    STEEL_FANGS = 34606
    REAVING_FANGS = 34607
    HUNTERS_STING = 34608
    SWIFTSKINS_STING = 34609
    FLANKSTING_STRIKE = 34610
    FLANKSBANE_FANG = 34611
    HINDSTING_STRIKE = 34612
    HINDSBANE_FANG = 34613
    VICEWINDER = 34620
    HUNTERS_COIL = 34621
    SWIFTSKINS_COIL = 34622

    # Pictomancer actions
    FIRE_IN_RED = 34650
    AERO_IN_GREEN = 34651
    WATER_IN_BLUE = 34652
    BLIZZARD_IN_CYAN = 34653
    STONE_IN_YELLOW = 34654
    THUNDER_IN_MAGENTA = 34655
    FIRE_II_IN_RED = 34656
    AERO_II_IN_GREEN = 34657
    WATER_II_IN_BLUE = 34658
    BLIZZARD_II_IN_CYAN = 34659
    STONE_II_IN_YELLOW = 34660
    THUNDER_II_IN_MAGENTA = 34661
    HOLY_IN_WHITE = 34662
    COMET_IN_BLACK = 34663

    # Raid buff actions
    BATTLE_LITANY = 116
    CHAIN_STRATAGEM = 7436
    BROTHERHOOD_BUFF = 7396
    EMBOLDEN = 7520
    DIVINATION = 16552
    TECHNICAL_STEP = 16004
    STANDARD_STEP = 15997


def get_gcd_recastime_for_job(job_id: JobClass) -> int:
    if job_id == JobClass.MONK:
        return 200
    return 2500


def get_role_for_job(job_id: JobClass) -> Role:
    """Returns the primary role for a given job ID.

    Args:
        job_id: The JobClass enumeration value to find the role for

    Returns:
        The Role enumeration value corresponding to the job's primary role
    """

    # Tanks
    if job_id in [
        JobClass.GLADIATOR,
        JobClass.MARAUDER,
        JobClass.PALADIN,
        JobClass.WARRIOR,
        JobClass.DARK_KNIGHT,
        JobClass.GUNBREAKER,
    ]:
        return Role.TANK

    # Healers
    elif job_id in [
        JobClass.CONJURER,
        JobClass.WHITE_MAGE,
        JobClass.SCHOLAR,
        JobClass.ASTROLOGIAN,
        JobClass.SAGE,
    ]:
        return Role.HEALER

    # Crafters
    elif JobClass.CARPENTER <= job_id <= JobClass.CULINARIAN:
        return Role.CRAFTER

    # Gatherers
    elif JobClass.MINER <= job_id <= JobClass.FISHER:
        return Role.GATHERER

    # All other combat jobs are DPS
    elif job_id != JobClass.ADVENTURER:  # Exclude generic adventurer
        return Role.DPS

    # Default
    return Role.NONE


def get_dps_role_for_job(job_id: JobClass) -> Role:
    """Returns the specific DPS sub-role for a job.

    Args:
        job_id: The JobClass enumeration value to find the DPS sub-role for

    Returns:
        The Role enumeration value corresponding to the job's DPS sub-role,
        or Role.NONE if the job is not a DPS role
    """

    # Not a DPS role
    if get_role_for_job(job_id) != Role.DPS:
        return Role.NONE

    # Melee DPS
    if job_id in [
        JobClass.PUGILIST,
        JobClass.LANCER,
        JobClass.ROGUE,
        JobClass.MONK,
        JobClass.DRAGOON,
        JobClass.NINJA,
        JobClass.SAMURAI,
        JobClass.REAPER,
    ]:
        return Role.DPS_MELEE

    # Ranged Physical DPS
    elif job_id in [
        JobClass.ARCHER,
        JobClass.BARD,
        JobClass.MACHINIST,
        JobClass.DANCER,
    ]:
        return Role.DPS_RANGED_PHYSICAL

    # Ranged Magical DPS (casters)
    elif job_id in [
        JobClass.THAUMATURGE,
        JobClass.ARCANIST,
        JobClass.BLACK_MAGE,
        JobClass.SUMMONER,
        JobClass.RED_MAGE,
        JobClass.BLUE_MAGE,
        JobClass.PICTOMANCER,
    ]:
        return Role.DPS_RANGED_MAGICAL

    # Default - should not reach here for valid DPS jobs
    return Role.NONE


@dataclass
class JobStatModifier:
    """Class representing job-specific stat modifiers.

    These modifiers are applied to base stats to determine
    job-specific values for calculations.

    Attributes:
        main_attribute: Modifier for the main attribute (STR, DEX, INT, etc.)
        vitality: Modifier for vitality (affects HP)
        health_point: Modifier for base health points
        damage_trait_multiplier: Optional trait multiplier for damage (default 1.0)
    """

    main_attribute: float
    vitality: float
    health_point: float
    damage_trait_multiplier: float = 1.0


# Job stat modifiers dictionary (values from const.h)
JOB_STAT_MODIFIERS = {
    JobClass.SAMURAI: JobStatModifier(112.0, 100.0, 109.0),
    JobClass.MONK: JobStatModifier(110.0, 100.0, 110.0),
    JobClass.REAPER: JobStatModifier(115.0, 105.0, 115.0),
    JobClass.VIPER: JobStatModifier(110.0, 100.0, 100.0),
    JobClass.PICTOMANCER: JobStatModifier(115.0, 100.0, 105.0, 1.3),
}


@dataclass
class LevelModifier:
    """Class representing level-specific stat modifiers.

    These modifiers are used in various damage, health, and attribute
    calculations that scale with character level.

    Attributes:
        main_attribute: Modifier for main attribute scaling
        substract: Base subtraction value for stat calculations
        division: Division factor for secondary stat calculations
        determination: Determination stat scaling factor
        determination_truncation: Truncation value for determination
        attack_power: Base attack power scaling
        attack_power_tank: Tank-specific attack power scaling
        health_point: Health point scaling factor
        vitality: Vitality scaling factor
        vitality_tank: Tank-specific vitality scaling
    """

    main_attribute: float
    substract: float
    division: float
    determination: float
    determination_truncation: float
    attack_power: float
    attack_power_tank: float
    health_point: float
    vitality: float
    vitality_tank: float


# Level modifiers from const.h
LEVEL_MODIFIERS = {
    70: LevelModifier(
        main_attribute=292.0,
        substract=364.0,
        division=900.0,
        determination=900.0,
        determination_truncation=1.0,
        attack_power=125.0,
        attack_power_tank=105.0,
        health_point=17.0,
        vitality=14.0,
        vitality_tank=18.8,
    ),
    80: LevelModifier(
        main_attribute=340.0,
        substract=380.0,
        division=1300.0,
        determination=1300.0,
        determination_truncation=1.0,
        attack_power=165.0,
        attack_power_tank=115.0,
        health_point=20.0,
        vitality=18.8,
        vitality_tank=26.6,
    ),
    90: LevelModifier(
        main_attribute=390.0,
        substract=400.0,
        division=1900.0,
        determination=1900.0,
        determination_truncation=1.0,
        attack_power=195.0,
        attack_power_tank=156.0,
        health_point=30.0,
        vitality=24.3,
        vitality_tank=34.6,
    ),
    100: LevelModifier(
        main_attribute=440.0,
        substract=420.0,
        division=2780.0,
        determination=2780.0,
        determination_truncation=1.0,
        attack_power=237.0,
        attack_power_tank=190.0,
        health_point=40.0,
        vitality=30.1,
        vitality_tank=43.0,
    ),
}


class GameVersion:
    """Class representing a FFXIV game version.

    Provides utilities for handling game versions in various formats
    and comparing between versions.

    Attributes:
        major: Major version number (e.g., 7 in 7.2)
        minor: Minor version number (e.g., 2 in 7.2)
    """

    def __init__(self, major: int, minor: int):
        """Initialize a GameVersion object.

        Args:
            major: Major version number
            minor: Minor version number
        """
        self.major = major
        self.minor = minor

    def __int__(self) -> int:
        """Convert to integer format (e.g. 7.2 -> 720)

        Returns:
            Integer representation of the version
        """
        return self.major * 100 + self.minor

    @classmethod
    def from_int(cls, version_int: int) -> "GameVersion":
        """Create from integer format (e.g. 720 -> 7.2)

        Args:
            version_int: Integer representation of the version

        Returns:
            GameVersion object representing the version
        """
        major = version_int // 100
        minor = version_int % 100
        return cls(major, minor)

    def __str__(self) -> str:
        """Convert to string representation (e.g., "7.2")

        Returns:
            String representation of the version
        """
        return f"{self.major}.{self.minor}"

    def __hash__(self) -> int:
        """Make GameVersion hashable for use as dictionary keys

        Returns:
            Hash value for the object
        """
        return hash((self.major, self.minor))

    def __lt__(self, other: "GameVersion") -> bool:
        """Less than comparison between versions

        Args:
            other: GameVersion to compare against

        Returns:
            True if this version is less than other, False otherwise
        """
        if isinstance(other, GameVersion):
            if self.major != other.major:
                return self.major < other.major
            return self.minor < other.minor
        return NotImplemented

    def __le__(self, other: "GameVersion") -> bool:
        """Less than or equal comparison between versions

        Args:
            other: GameVersion to compare against

        Returns:
            True if this version is less than or equal to other, False otherwise
        """
        if isinstance(other, GameVersion):
            if self.major != other.major:
                return self.major < other.major
            return self.minor <= other.minor
        return NotImplemented

    def __eq__(self, other) -> bool:
        """Equal comparison between versions

        Args:
            other: Object to compare against

        Returns:
            True if versions are equal, False otherwise
        """
        if isinstance(other, GameVersion):
            return self.major == other.major and self.minor == other.minor
        return NotImplemented

    def __ne__(self, other) -> bool:
        """Not equal comparison between versions

        Returns:
            True if versions are not equal, False otherwise
        """
        return not self.__eq__(other)

    def __gt__(self, other: "GameVersion") -> bool:
        """Greater than comparison between versions

        Args:
            other: GameVersion to compare against

        Returns:
            True if this version is greater than other, False otherwise
        """
        if isinstance(other, GameVersion):
            if self.major != other.major:
                return self.major > other.major
            return self.minor > other.minor
        return NotImplemented

    def __ge__(self, other: "GameVersion") -> bool:
        """Greater than or equal comparison between versions

        Args:
            other: GameVersion to compare against

        Returns:
            True if this version is greater than or equal to other, False otherwise
        """
        if isinstance(other, GameVersion):
            if self.major != other.major:
                return self.major > other.major
            return self.minor >= other.minor
        return NotImplemented


@dataclass
class CharacterGearset:
    """Class representing a character's gear and stats.

    Contains the fundamental character stats used in damage calculations,
    including primary and secondary attributes.

    Attributes:
        name: Name of the gearset/character
        job: JobClass enumeration value
        level: Character level
        party_bonus: Party bonus multiplier (typically 1.0 or 1.05)
        weapon_damage: Weapon damage value
        weapon_delay: Weapon delay value (affects auto-attack timing)
        main_attribute: Primary attribute value (STR, DEX, INT, etc.)
        critical_hit: Critical hit stat value
        determination: Determination stat value
        direct_hit: Direct hit stat value
        speed: Speed stat value (skill or spell speed depending on job)
    """

    name: str
    job: JobClass
    level: int
    party_bonus: float
    weapon_damage: float
    weapon_delay: float
    main_attribute: float
    critical_hit: float
    determination: float
    direct_hit: float
    speed: float
    
    @classmethod
    def from_json(cls, json_path):
        """Load a CharacterGearset from a JSON file.
        
        Args:
            json_path: Path to the JSON file containing gearset data
            
        Returns:
            CharacterGearset object with data loaded from the JSON file
        """
        import json
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        gearset_data = data.get('gearset', data)  # Use data directly if no gearset key
        
        # Convert job string to JobClass enum
        job_str = gearset_data.get('job')
        job = None
        
        # Find matching job in JobClass enum
        for job_enum in JobClass:
            if job_enum.name.upper() == job_str.upper():
                job = job_enum
                break
                
        if job is None:
            raise ValueError(f"Unknown job: {job_str}")
            
        return cls(
            name=gearset_data.get('name', 'Unnamed Gearset'),
            job=job,
            level=int(gearset_data.get('level', 100)),
            party_bonus=float(gearset_data.get('party_bonus', 1.0)),
            weapon_damage=float(gearset_data.get('weapon_damage', 0)),
            weapon_delay=float(gearset_data.get('weapon_delay', 0)),
            main_attribute=int(gearset_data.get('main_attribute', 0)  ),
            critical_hit=int(gearset_data.get('critical_hit', 0)),
            determination=int(gearset_data.get('determination', 0)),
            direct_hit=int(gearset_data.get('direct_hit', 0)),
            speed=int(gearset_data.get('speed', 0))
        )
        
    @classmethod
    def from_rotation_json(cls, json_path):
        """Load a CharacterGearset from a rotation JSON file.
        
        This method is specifically for loading from rotation files like sam_820.json
        that contain both a rotation and a gearset.
        
        Args:
            json_path: Path to the rotation JSON file containing gearset data
            
        Returns:
            CharacterGearset object with data loaded from the rotation JSON file
        """
        import json
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Ensure there's a gearset section
        if 'gearset' not in data:
            raise ValueError("No gearset data found in rotation file")
            
        return cls.from_json(json_path)
    
    
    def print(self):
        print(f"{self.name}")
        print(f"  {self.job.name}({self.job.value}) Lv.{self.level}")
        print(f"  Party Bonus: {self.party_bonus}")
        print(f"  Weapon Damage: {self.weapon_damage}")
        print(f"  Weapon Delay: {self.weapon_delay}")
        print(f"  Main Attribute: {self.main_attribute}")
        print(f"  Critical Hit: {self.critical_hit}")
        print(f"  Determination: {self.determination}")
        print(f"  Direct Hit: {self.direct_hit}")
        print(f"  Speed: {self.speed}")
        
