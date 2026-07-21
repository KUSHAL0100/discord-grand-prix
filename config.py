import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord & API config
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
if GUILD_ID:
    try:
        GUILD_ID = int(GUILD_ID)
    except ValueError:
        GUILD_ID = None

DATABASE_PATH = os.getenv("DATABASE_PATH", "game.db")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin")

ANNOUNCEMENT_CHANNEL_ID = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
if ANNOUNCEMENT_CHANNEL_ID:
    try:
        ANNOUNCEMENT_CHANNEL_ID = int(ANNOUNCEMENT_CHANNEL_ID)
    except ValueError:
        ANNOUNCEMENT_CHANNEL_ID = None

# Onboarding Settings
STARTING_MONEY = 1500
STARTING_LEVEL = 1
STARTING_XP = 0

# Economy caps & earnings
CHAT_CREDITS_PER_MSG = 5
CHAT_DAILY_LIMIT = 200  # max 40 messages/day
VOICE_CREDITS_PER_MIN = 2
VOICE_DAILY_LIMIT = 200  # max 100 minutes/day (100 mins * 2 credits)
DAILY_BONUS = 500
WORK_MIN_CREDITS = 100
WORK_MAX_CREDITS = 500

# Parts & Upgrades configuration
# Upgrade level costs for Engine (Level 1 -> 2, etc.)
ENGINE_UPGRADE_COSTS = {
    2: 200,
    3: 400,
    4: 700,
    5: 1100,
    6: 1600,
    7: 2200,
    8: 2900,
    9: 3700,
    10: 4700,
    11: 5900,
    12: 7300,
    13: 8900,
    14: 10700,
    15: 12700,
    16: 15000,
    17: 17500,
    18: 20300,
    19: 23400,
    20: 26800
}

# Multipliers relative to engine cost
PART_MULTIPLIERS = {
    "engine": 1.0,
    "aerodynamics": 0.8,  # ~2/3
    "ers": 0.8,           # ~2/3
    "tyres": 0.5,         # ~1/2
    "reliability": 0.25,  # ~1/4
    "pit_crew": 0.25      # ~1/4
}

# Repair settings
REPAIR_COST_PER_PCT = 25  # e.g., 20% damage * 25 credits = 500 credits to repair
MAX_DAMAGE = 100

# Stat Caps
MAX_STAT_LEVEL = 20

# Duel Rewards
DUEL_WIN_CREDITS = 200
DUEL_LOSS_CREDITS = 50
DUEL_COOLDOWN_SECONDS = 60  # Anti-spam limit for duels

# Grand Prix Rewards & Settings
GP_ENTRY_FEE = 1000
GP_PODIUM_REWARDS = {
    1: 5000,
    2: 3000,
    3: 1500
}
GP_BASE_PARTICIPATION_REWARD = 500
GP_POINTS_DISTRIBUTION = [8, 7, 6, 5, 4, 3, 2, 1]  # Top 8 Sprint points

def get_upgrade_cost(part_name: str, target_level: int) -> int:
    """Calculate credit cost to upgrade a part to target_level."""
    if part_name not in PART_MULTIPLIERS:
        raise ValueError(f"Invalid part name: {part_name}")
    if target_level not in ENGINE_UPGRADE_COSTS:
        raise ValueError(f"Invalid level for upgrade: {target_level}")
    
    base_cost = ENGINE_UPGRADE_COSTS[target_level]
    multiplier = PART_MULTIPLIERS[part_name]
    return int(base_cost * multiplier)
