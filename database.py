import sqlite3
import os
import random
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
import config

def get_db_connection():
    """Establish a connection to the SQLite database and return it."""
    db_dir = os.path.dirname(config.DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initialize database tables according to schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL,
        team_name TEXT NOT NULL,
        country TEXT,
        money INTEGER NOT NULL DEFAULT {config.STARTING_MONEY},
        xp INTEGER NOT NULL DEFAULT {config.STARTING_XP},
        level INTEGER NOT NULL DEFAULT {config.STARTING_LEVEL},
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        daily_chat_credits INTEGER NOT NULL DEFAULT 0,
        daily_voice_credits INTEGER NOT NULL DEFAULT 0,
        daily_free_duels INTEGER NOT NULL DEFAULT 0,
        daily_free_races INTEGER NOT NULL DEFAULT 0,
        last_credits_reset TEXT DEFAULT (date('now')),
        last_daily_claim TEXT,
        last_weekly_claim TEXT,
        last_work_claim TEXT,
        pref_strategy TEXT DEFAULT 'Balanced',
        pref_tyres TEXT DEFAULT 'Medium',
        pref_pit_stops INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(discord_id, guild_id)
    );
    """)

    # Create drivers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drivers (
        driver_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pace INTEGER NOT NULL DEFAULT 50,
        qual INTEGER NOT NULL DEFAULT 50,
        wet_skill INTEGER NOT NULL DEFAULT 50,
        consistency INTEGER NOT NULL DEFAULT 50,
        aggression INTEGER NOT NULL DEFAULT 50,
        overtaking INTEGER NOT NULL DEFAULT 50,
        experience INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create strategists table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategists (
        strat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pit_timing INTEGER NOT NULL DEFAULT 50,
        weather_call INTEGER NOT NULL DEFAULT 50,
        undercut INTEGER NOT NULL DEFAULT 50,
        sc_skill INTEGER NOT NULL DEFAULT 50,
        risk INTEGER NOT NULL DEFAULT 50,
        communication INTEGER NOT NULL DEFAULT 50,
        experience INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create garage table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garage (
        user_id INTEGER PRIMARY KEY,
        engine INTEGER NOT NULL DEFAULT 1,
        aerodynamics INTEGER NOT NULL DEFAULT 1,
        tyres INTEGER NOT NULL DEFAULT 1,
        ers INTEGER NOT NULL DEFAULT 1,
        reliability INTEGER NOT NULL DEFAULT 1,
        pit_crew INTEGER NOT NULL DEFAULT 1,
        damage_engine INTEGER NOT NULL DEFAULT 0,
        damage_tyres INTEGER NOT NULL DEFAULT 0,
        damage_total INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create races table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS races (
        race_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        date TEXT NOT NULL,
        track TEXT NOT NULL,
        weather TEXT NOT NULL,
        status TEXT NOT NULL, -- 'Registration', 'Qualifying', 'Finished', 'Cancelled'
        laps INTEGER DEFAULT 15,
        winner_id INTEGER,
        FOREIGN KEY (winner_id) REFERENCES users (user_id) ON DELETE SET NULL
    );
    """)

    # Create race_entries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS race_entries (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        race_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        qual_time REAL,
        start_position INTEGER,
        finish_position INTEGER,
        points_earned INTEGER DEFAULT 0,
        credits_won INTEGER DEFAULT 0,
        dnf BOOLEAN DEFAULT 0,
        current_q_tyre TEXT DEFAULT 'Soft',
        quali_q1_time REAL,
        quali_q2_time REAL,
        quali_q3_time REAL,
        FOREIGN KEY (race_id) REFERENCES races (race_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        UNIQUE(race_id, user_id)
    );
    """)

    # Create bets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
        race_id INTEGER,
        bettor_id INTEGER NOT NULL,
        target_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        outcome TEXT, -- 'win', 'lose', 'cancelled'
        payout INTEGER DEFAULT 0,
        FOREIGN KEY (race_id) REFERENCES races (race_id) ON DELETE CASCADE,
        FOREIGN KEY (bettor_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create seasons table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seasons (
        season_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active', -- 'Active', 'Finished', 'Cancelled'
        winner_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (winner_id) REFERENCES users (user_id) ON DELETE SET NULL
    );
    """)

    # Create season_calendar table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_calendar (
        calendar_id INTEGER PRIMARY KEY AUTOINCREMENT,
        season_id INTEGER NOT NULL,
        track TEXT NOT NULL,
        laps INTEGER NOT NULL,
        is_sprint BOOLEAN DEFAULT 0,
        race_order INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Scheduled', -- 'Scheduled', 'Running', 'Finished'
        FOREIGN KEY (season_id) REFERENCES seasons (season_id) ON DELETE CASCADE
    );
    """)

    # Create user_inventory table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_inventory (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        part_name TEXT NOT NULL,
        rarity TEXT NOT NULL DEFAULT 'Common',
        level INTEGER NOT NULL DEFAULT 1,
        stat_bonus INTEGER NOT NULL DEFAULT 0,
        is_equipped INTEGER NOT NULL DEFAULT 0,
        acquired_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create user_boosters table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_boosters (
        booster_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        booster_type TEXT NOT NULL,
        booster_name TEXT NOT NULL,
        charges INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)

    # Create duel_history table for Rivalry H2H statistics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS duel_history (
        duel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id BIGINT NOT NULL,
        winner_id INTEGER NOT NULL,
        loser_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (winner_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (loser_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)


    # Create track_mastery table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS track_mastery (
        mastery_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        track_name TEXT NOT NULL,
        practice_count INTEGER NOT NULL DEFAULT 0,
        last_practice_date TEXT,
        pace_bonus REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        UNIQUE(user_id, track_name)
    );
    """)

    # --- Run schema migrations for existing databases ---
    def get_existing_columns(table_name):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    # Users table migrations
    users_cols = get_existing_columns("users")
    if "guild_id" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN guild_id BIGINT DEFAULT 0")
    if "pit_strategy_json" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN pit_strategy_json TEXT DEFAULT '{\"pace\":\"Balanced\", \"start_tyre\":\"Medium\", \"stops\":[]}'")
    if "daily_free_duels" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN daily_free_duels INTEGER NOT NULL DEFAULT 0")
    if "daily_free_races" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN daily_free_races INTEGER NOT NULL DEFAULT 0")
    if "crate_rookie_pity" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN crate_rookie_pity INTEGER NOT NULL DEFAULT 0")
    if "crate_pro_pity" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN crate_pro_pity INTEGER NOT NULL DEFAULT 0")
    if "crate_champion_pity" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN crate_champion_pity INTEGER NOT NULL DEFAULT 0")
    if "last_weekly_claim" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN last_weekly_claim TEXT")

    # Race Entries table migrations
    re_cols = get_existing_columns("race_entries")
    if "current_q_tyre" not in re_cols:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN current_q_tyre TEXT DEFAULT 'Soft'")
    if "quali_q1_time" not in re_cols:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q1_time REAL")
    if "quali_q2_time" not in re_cols:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q2_time REAL")
    if "quali_q3_time" not in re_cols:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q3_time REAL")

    # Races table migrations
    races_cols = get_existing_columns("races")
    if "guild_id" not in races_cols:
        cursor.execute("ALTER TABLE races ADD COLUMN guild_id BIGINT DEFAULT 0")
    if "laps" not in races_cols:
        cursor.execute("ALTER TABLE races ADD COLUMN laps INTEGER DEFAULT 15")
    if "season_id" not in races_cols:
        cursor.execute("ALTER TABLE races ADD COLUMN season_id INTEGER")
    if "is_sprint" not in races_cols:
        cursor.execute("ALTER TABLE races ADD COLUMN is_sprint BOOLEAN DEFAULT 0")
    if "fastest_lap_user_id" not in races_cols:
        cursor.execute("ALTER TABLE races ADD COLUMN fastest_lap_user_id INTEGER")

    # Garage table migrations
    garage_cols = get_existing_columns("garage")
    if "damage_engine" not in garage_cols:
        cursor.execute("ALTER TABLE garage ADD COLUMN damage_engine INTEGER NOT NULL DEFAULT 0")
    if "damage_tyres" not in garage_cols:
        cursor.execute("ALTER TABLE garage ADD COLUMN damage_tyres INTEGER NOT NULL DEFAULT 0")
    if "damage_total" not in garage_cols:
        cursor.execute("ALTER TABLE garage ADD COLUMN damage_total INTEGER NOT NULL DEFAULT 0")

    # --- Create performance B-Tree indexes for lightning-fast lookups ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_discord_guild ON users(discord_id, guild_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user_cat ON user_inventory(user_id, category, is_equipped);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_boosters_user ON user_boosters(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_guild_status ON races(guild_id, status);")

    # Bot admins table (game admins assigned by server owner/mods)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL,
        added_by BIGINT NOT NULL,
        added_at TEXT DEFAULT (datetime('now')),
        UNIQUE(discord_id, guild_id)
    );
    """)

    # Activity logs table for tracking daily/weekly/monthly text and voice engagement
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id BIGINT NOT NULL,
        user_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_guild_date ON activity_logs(guild_id, activity_type, created_at);")

    conn.commit()
    conn.close()

# Auto-initialize database schema on module load
try:
    init_db()
except Exception as _e:
    pass


# ----------------- User and Profile Management Helpers -----------------

def create_user(discord_id: int, guild_id: int, team_name: str, country: Optional[str] = None) -> Tuple[bool, str]:
    """
    Create a new user, initializing their driver, strategist, and garage levels.
    Returns (success, message).
    """
    import re
    team_name_clean = team_name.strip()
    
    # 1. Basic Format Validation
    if len(team_name_clean) < 3:
        return False, "Team name must be at least 3 characters long."
    if len(team_name_clean) > 32:
        return False, "Team name cannot exceed 32 characters."
    
    # Must contain at least one alphabetical letter
    if not any(char.isalpha() for char in team_name_clean):
        return False, "Team name must contain at least one letter."
        
    # 2. Block Official F1 Team Names (handles case, spaces, symbols, and leetspeak like f3rr4r1, ferr@ri, R3d Bu11)
    forbidden_f1_teams = [
        "redbull", "red bull", "ferrari", "haas", "mercedes", "mclaren",
        "astonmartin", "aston martin", "alpine", "williams", "sauber",
        "alfaromeo", "alfa romeo", "alphatauri", "alpha tauri",
        "tororosso", "toro rosso", "vcarb", "racing bulls", "renault"
    ]
    
    # Translate leetspeak to standard letters (1 and ! can represent 'l' or 'i')
    leet_map_base = str.maketrans({'@': 'a', '4': 'a', '3': 'e', '0': 'o', '5': 's', '$': 's', '7': 't'})
    clean_base = team_name_clean.lower().translate(leet_map_base)
    
    # Create normalized variations for '1'/'!'/'|' as 'l' and as 'i'
    norm_variations = [
        re.sub(r"[^a-z]", "", clean_base.replace('1', 'l').replace('!', 'l').replace('|', 'l')),
        re.sub(r"[^a-z]", "", clean_base.replace('1', 'i').replace('!', 'i').replace('|', 'i'))
    ]
    
    for forbidden in forbidden_f1_teams:
        forbidden_norm = re.sub(r"[^a-z]", "", forbidden.lower())
        for norm in norm_variations:
            if forbidden_norm in norm:
                return False, f"❌ You cannot name your team after official F1 constructors like '**{forbidden.title()}**'! Please choose a unique custom team name."

    # Prevent spammy special characters (only allow alphanumeric, spaces, hyphens, underscores, apostrophes)
    if not re.match(r"^[a-zA-Z0-9\s\-_']+$", team_name_clean):
        return False, "Team name can only contain letters, numbers, spaces, hyphens (-), underscores (_), and apostrophes (')."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if user already exists in this guild
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        if cursor.fetchone():
            return False, "You have already created a profile in this server! Use `/profile` to view your team."

        # Check if team name already exists in this guild (case-insensitive)
        cursor.execute("SELECT user_id FROM users WHERE LOWER(team_name) = LOWER(?) AND guild_id = ?", (team_name_clean, guild_id))
        if cursor.fetchone():
            return False, f"The team name '**{team_name_clean}**' is already taken in this server! Please choose a unique team name."

        # Insert user with explicit starting balance, level, and XP from config
        cursor.execute(
            "INSERT INTO users (discord_id, guild_id, team_name, country, money, xp, level) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (discord_id, guild_id, team_name_clean, country, config.STARTING_MONEY, config.STARTING_XP, config.STARTING_LEVEL)
        )
        user_id = cursor.lastrowid

        # Insert default driver
        cursor.execute(
            "INSERT INTO drivers (user_id) VALUES (?)",
            (user_id,)
        )

        # Insert default strategist
        cursor.execute(
            "INSERT INTO strategists (user_id) VALUES (?)",
            (user_id,)
        )

        # Insert default garage
        cursor.execute(
            "INSERT INTO garage (user_id) VALUES (?)",
            (user_id,)
        )

        conn.commit()
        return True, "Success"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_user_by_discord_id(discord_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get user profile details by discord_id and guild_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user profile details by internal user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_crate_pity(user_id: int) -> Dict[str, int]:
    """Get current crate pity counters for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT crate_rookie_pity, crate_pro_pity, crate_champion_pity FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "rookie": row["crate_rookie_pity"] or 0,
            "pro": row["crate_pro_pity"] or 0,
            "champion": row["crate_champion_pity"] or 0
        }
    return {"rookie": 0, "pro": 0, "champion": 0}

def update_crate_pity(user_id: int, crate_tier: str, reset: bool = False) -> int:
    """
    Updates crate pity counter for user.
    If reset is True, sets counter to 0. Otherwise increments counter by 1.
    Returns the new counter value.
    """
    col_map = {
        "rookie": "crate_rookie_pity",
        "pro": "crate_pro_pity",
        "champion": "crate_champion_pity"
    }
    tier_key = crate_tier.lower()
    if tier_key not in col_map:
        return 0
    col = col_map[tier_key]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if reset:
        cursor.execute(f"UPDATE users SET {col} = 0 WHERE user_id = ?", (user_id,))
        new_val = 0
    else:
        cursor.execute(f"UPDATE users SET {col} = COALESCE({col}, 0) + 1 WHERE user_id = ?", (user_id,))
        cursor.execute(f"SELECT {col} FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        new_val = row[col] if row else 0
    conn.commit()
    conn.close()
    return new_val

def get_full_team_profile(discord_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user, driver, strategist, and garage details as a single dictionary."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query with JOINs
    cursor.execute("""
        SELECT u.*, 
               d.pace, d.qual, d.wet_skill, d.consistency, d.aggression, d.overtaking, d.experience,
               s.pit_timing, s.weather_call, s.undercut, s.sc_skill, s.risk, s.communication,
               g.engine, g.aerodynamics, g.tyres, g.ers, g.reliability, g.pit_crew, 
               g.damage_engine, g.damage_tyres, g.damage_total
        FROM users u
        LEFT JOIN drivers d ON u.user_id = d.user_id
        LEFT JOIN strategists s ON u.user_id = s.user_id
        LEFT JOIN garage g ON u.user_id = g.user_id
        WHERE u.discord_id = ? AND u.guild_id = ?
    """, (discord_id, guild_id))
    
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def train_personnel_skill(user_id: int, category: str, skill_name: str, cost: int = 400) -> Tuple[bool, str]:
    """Train a specific driver or strategist skill directly by spending credits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get current balance
        cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "User profile not found."
            
        if user_row['money'] < cost:
            return False, f"Insufficient credits! Training costs {cost}¢ (You have {user_row['money']}¢)."
            
        table_name = "drivers" if category == "driver" else "strategists"
        
        # Select current value
        cursor.execute(f"SELECT {skill_name} FROM {table_name} WHERE user_id = ?", (user_id,))
        skill_row = cursor.fetchone()
        if not skill_row:
            return False, "Personnel profile not found."
            
        current_val = skill_row[skill_name]
        if current_val >= 100:
            return False, f"This skill is already at the maximum level (100)!"
            
        new_val = min(100, current_val + 1)
        remaining_money = user_row['money'] - cost
        
        # Deduct money and update skill
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
        cursor.execute(f"UPDATE {table_name} SET {skill_name} = ? WHERE user_id = ?", (new_val, user_id))
        
        conn.commit()
        return True, f"Successfully trained **{skill_name.replace('_', ' ').capitalize()}** from `{current_val}` to `{new_val}` for **{cost:,} credits**!\n💰 **Remaining Balance:** `{remaining_money:,} credits`"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def update_user_balance(user_id: int, amount: int) -> bool:
    """Adjust user credit balance. Amount can be positive or negative."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get current money
        cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        new_balance = row['money'] + amount
        if new_balance < 0:
            return False # Enforce no negative balances
        
        cursor.execute("UPDATE users SET money = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def update_user_strategy(user_id: int, pace: str, tyres: str, pit_stops: int) -> bool:
    """Update a user's strategy preferences in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        import json
        row = cursor.execute("SELECT pit_strategy_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        strategy_json = {}
        if row and row['pit_strategy_json']:
            try:
                strategy_json = json.loads(row['pit_strategy_json'])
            except Exception:
                pass
        strategy_json['pace'] = pace
        strategy_json['start_tyre'] = tyres

        cursor.execute("""
            UPDATE users 
            SET pref_strategy = ?, pref_tyres = ?, pref_pit_stops = ?, pit_strategy_json = ?
            WHERE user_id = ?
        """, (pace, tyres, pit_stops, json.dumps(strategy_json), user_id))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def update_user_pit_strategy(user_id: int, strategy_json: str) -> bool:
    """Update a user's full pit strategy JSON in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET pit_strategy_json = ?
            WHERE user_id = ?
        """, (strategy_json, user_id))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def update_quali_tyre(user_id: int, race_id: int, tyre: str) -> bool:
    """Update a user's chosen qualifying tyre compound for an active GP."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE race_entries 
            SET current_q_tyre = ?
            WHERE user_id = ? AND race_id = ?
        """, (tyre, user_id, race_id))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def add_user_xp(user_id: int, xp_to_add: int) -> Tuple[int, int, bool, int]:
    """
    Add XP to user and handle leveling up.
    Returns (new_xp, new_level, leveled_up: bool, total_reward: int)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return (0, 0, False, 0)
        
        current_xp = row['xp']
        current_level = row['level']
        
        new_xp = current_xp + xp_to_add
        new_level = current_level
        leveled_up = False
        total_reward = 0
        
        # Simple progression curve: level * 1000 XP needed to level up
        while new_xp >= new_level * 1000:
            new_xp -= new_level * 1000
            new_level += 1
            leveled_up = True
            # Level up reward: (new_level - 1) * 1000¢ (Level 2 = 1,000¢, Level 3 = 2,000¢)
            reward = (new_level - 1) * 1000
            total_reward += reward
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (reward, user_id))
            
        cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
        conn.commit()
        return (new_xp, new_level, leveled_up, total_reward)
    except sqlite3.Error:
        conn.rollback()
        return (0, 0, False, 0)
    finally:
        conn.close()


# ----------------- Daily resets & limit trackers -----------------

def get_ist_date_str() -> str:
    """Return current YYYY-MM-DD date string in Indian Standard Time (IST, UTC+5:30)."""
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist_tz).date().isoformat()

def reset_daily_limits_if_new_day(user_id: int) -> None:
    """Reset daily chat and voice credits if the day has changed (Midnight IST reset)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_credits_reset FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return
        
        today_str = get_ist_date_str()
        if row['last_credits_reset'] != today_str:
            cursor.execute("""
                UPDATE users 
                SET daily_chat_credits = 0, daily_voice_credits = 0, daily_free_duels = 0, daily_free_races = 0, last_credits_reset = ? 
                WHERE user_id = ?
            """, (today_str, user_id))
            conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()

def reset_user_daily_activity(user_id: int) -> bool:
    """Reset daily chat and voice credit trackers to 0 for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET daily_chat_credits = 0, daily_voice_credits = 0, daily_free_duels = 0, daily_free_races = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def can_user_free_duel(user_id: int) -> Tuple[bool, str]:
    """Check if user can participate in a free AI duel today (max config.FREE_DUEL_DAILY_LIMIT)."""
    reset_daily_limits_if_new_day(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT daily_free_duels FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "❌ User profile not found."
        count = row['daily_free_duels']
        if count >= config.FREE_DUEL_DAILY_LIMIT:
            return False, f"❌ You have reached your daily limit of **{config.FREE_DUEL_DAILY_LIMIT} free AI duels**! Try again tomorrow after midnight IST."
        return True, ""
    finally:
        conn.close()

def increment_daily_free_duels(user_id: int) -> None:
    """Increment user's daily free duel count."""
    reset_daily_limits_if_new_day(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET daily_free_duels = daily_free_duels + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()

def can_user_free_race(user_id: int) -> Tuple[bool, str]:
    """Check if user can participate in a free 1v1 human race today (max config.FREE_RACE_DAILY_LIMIT)."""
    reset_daily_limits_if_new_day(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT daily_free_races FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "❌ User profile not found."
        count = row['daily_free_races']
        if count >= config.FREE_RACE_DAILY_LIMIT:
            return False, f"❌ You have reached your daily limit of **{config.FREE_RACE_DAILY_LIMIT} free 1v1 races**! Challenge another driver with a credit wager of at least **{config.MIN_WAGER:,} credits** (`/race wager:amount`) or try again tomorrow after midnight IST."
        return True, ""
    finally:
        conn.close()

def increment_daily_free_races(user_id: int) -> None:
    """Increment user's daily free race count."""
    reset_daily_limits_if_new_day(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET daily_free_races = daily_free_races + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()


def award_daily_activity_credits(user_id: int, amount: int, credit_type: str) -> int:
    """
    Award chat or voice activity credits up to the configured limits.
    credit_type must be either 'chat' or 'voice'.
    Returns the number of credits actually awarded.
    """
    reset_daily_limits_if_new_day(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT guild_id, money, daily_chat_credits, daily_voice_credits 
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return 0
        
        credits_awarded = 0
        if credit_type == 'chat':
            current_daily = row['daily_chat_credits']
            limit = config.CHAT_DAILY_LIMIT
            if current_daily < limit:
                credits_awarded = min(amount, limit - current_daily)
                cursor.execute("""
                    UPDATE users 
                    SET money = money + ?, daily_chat_credits = daily_chat_credits + ? 
                    WHERE user_id = ?
                """, (credits_awarded, credits_awarded, user_id))
                
        elif credit_type == 'voice':
            current_daily = row['daily_voice_credits']
            limit = config.VOICE_DAILY_LIMIT
            if current_daily < limit:
                credits_awarded = min(amount, limit - current_daily)
                cursor.execute("""
                    UPDATE users 
                    SET money = money + ?, daily_voice_credits = daily_voice_credits + ? 
                    WHERE user_id = ?
                """, (credits_awarded, credits_awarded, user_id))
        
        if credits_awarded > 0:
            cursor.execute("""
                INSERT INTO activity_logs (guild_id, user_id, activity_type, amount, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (row['guild_id'], user_id, credit_type, credits_awarded))

        conn.commit()
        return credits_awarded
    except sqlite3.Error:
        conn.rollback()
        return 0
    finally:
        conn.close()

# ----------------- Upgrade and Garage Helpers -----------------

def upgrade_part(user_id: int, part_name: str, cost: int = 0) -> Tuple[bool, str]:
    """
    Upgrade a car part by one level (either equipped inventory item or stock baseline).
    Deducts the cost and checks limits.
    Returns (success: bool, status_message: str)
    """
    if part_name not in config.PART_MULTIPLIERS:
        return False, f"Invalid part name: {part_name}"
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get user money
        cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "User not found."
        
        current_money = user_row['money']
        
        # Check if an inventory item is equipped in this category
        cursor.execute("SELECT * FROM user_inventory WHERE user_id = ? AND category = ? AND is_equipped = 1", (user_id, part_name))
        eq_item = cursor.fetchone()
        
        if eq_item:
            eq_dict = dict(eq_item)
            current_level = eq_dict['level']
            rarity = eq_dict['rarity']
            part_display_name = f"{rarity} {eq_dict['part_name']}"
            item_id = eq_dict['item_id']
        else:
            cursor.execute(f"SELECT {part_name} FROM garage WHERE user_id = ?", (user_id,))
            garage_row = cursor.fetchone()
            if not garage_row:
                return False, "Garage record not found."
            current_level = garage_row[part_name]
            rarity = "Common"
            part_display_name = f"Stock {part_name.capitalize()}"
            item_id = None
            
        if current_level >= config.MAX_STAT_LEVEL:
            return False, f"Your **{part_display_name}** is already at max level ({config.MAX_STAT_LEVEL})."
            
        target_level = current_level + 1
        if cost is None or cost <= 0:
            cost = config.get_upgrade_cost(part_name, target_level, rarity)
        
        if current_money < cost:
            return False, f"Insufficient credits! Upgrading **{part_display_name}** to Level {target_level} costs {cost:,}¢ (You have {current_money:,}¢)."
            
        remaining_money = current_money - cost

        # Deduct money and update part level
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
        if item_id:
            cursor.execute("UPDATE user_inventory SET level = ?, stat_bonus = ? WHERE item_id = ?", (target_level, target_level, item_id))
        else:
            cursor.execute(f"UPDATE garage SET {part_name} = ? WHERE user_id = ?", (target_level, user_id))
        
        conn.commit()
        return True, f"Successfully upgraded **{part_display_name}** to Level **{target_level}** for **{cost:,} credits**!\n💰 **Remaining Balance:** `{remaining_money:,} credits`"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def repair_part(user_id: int, part_name: str) -> Tuple[bool, str]:
    """
    Repair a car part or perform a full overhaul.
    Supported parts: 'engine', 'tyres', 'full', 'all'.
    Returns (success: bool, status_message: str)
    """
    part_name = part_name.lower()
    if part_name not in ['engine', 'tyres', 'full', 'all']:
        return False, "Invalid component for repair. Please select 'engine', 'tyres', or 'full' overhaul."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get user money
        cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "User not found."
        current_money = user_row['money']
        
        # Get current damage
        cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (user_id,))
        garage_row = cursor.fetchone()
        if not garage_row:
            return False, "Garage record not found."
            
        dmg_engine = garage_row['damage_engine']
        dmg_tyres = garage_row['damage_tyres']
        
        if part_name in ['full', 'all']:
            total_dmg = dmg_engine + dmg_tyres
            if total_dmg <= 0:
                return False, "Your car is already in perfect condition with 0% damage!"
                
            cost = int(total_dmg * config.REPAIR_COST_PER_PCT)
            if current_money < cost:
                return False, f"Insufficient credits! A full overhaul costs {cost:,}¢, but you have {current_money:,}¢."
                
            cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
            cursor.execute("UPDATE garage SET damage_engine = 0, damage_tyres = 0, damage_total = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True, f"🛠️ **Full Car Overhaul Complete!** Repaired engine & body to 0% damage for **{cost:,} credits**!"
            
        else:
            damage_col = f"damage_{part_name}"
            damage_val = garage_row[damage_col]
            display_name = "Body" if part_name == "tyres" else part_name.capitalize()
            if damage_val <= 0:
                return False, f"Your **{display_name}** is already in perfect condition (0% damage)."
                
            cost = int(damage_val * config.REPAIR_COST_PER_PCT)
            if current_money < cost:
                return False, f"Insufficient credits! Repairing your **{display_name}** costs {cost:,}¢, but you have {current_money:,}¢."
                
            cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
            cursor.execute(f"UPDATE garage SET {damage_col} = 0 WHERE user_id = ?", (user_id,))
            
            # Recalculate total damage
            cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (user_id,))
            damages = cursor.fetchone()
            new_total = damages['damage_engine'] + damages['damage_tyres']
            cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (new_total, user_id))
            
            conn.commit()
            return True, f"🔧 Repaired your **{display_name}**! Cost: **{cost:,} credits**. Damage is now 0%."
            
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

# ----------------- Leaderboard -----------------

def get_leaderboard(guild_id: int, by_type: str = 'points', limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get leaderboard top lists filtered by guild_id.
    by_type can be 'points', 'wins', 'money', or 'level'.
    If limit is None, returns all entries.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    limit_clause = " LIMIT ?" if limit is not None else ""
    params = (guild_id, limit) if limit is not None else (guild_id,)
    
    if by_type == 'money':
        query = f"SELECT team_name, money as score, level, wins FROM users WHERE guild_id = ? ORDER BY money DESC{limit_clause}"
    elif by_type == 'wins':
        query = f"SELECT team_name, wins as score, level, wins FROM users WHERE guild_id = ? ORDER BY wins DESC{limit_clause}"
    elif by_type == 'level':
        query = f"SELECT team_name, level as score, level, wins FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC{limit_clause}"
    else:  # Default to championship points
        query = f"""
            SELECT u.team_name, COALESCE(SUM(re.points_earned), 0) as score, u.level, u.wins
            FROM users u
            LEFT JOIN race_entries re ON u.user_id = re.user_id
            WHERE u.guild_id = ?
            GROUP BY u.user_id
            ORDER BY score DESC{limit_clause}
        """
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ----------------- Grand Prix & Race Entries Helpers -----------------

def create_gp_race(guild_id: int, name: str, track: str, laps: int, is_sprint: bool = False, season_id: Optional[int] = None) -> Tuple[bool, str]:
    """Create a new Grand Prix or Sprint race in Created status for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if there is already an active race
        cursor.execute("SELECT race_id FROM races WHERE status != 'Finished' AND status != 'Cancelled' AND guild_id = ?", (guild_id,))
        if cursor.fetchone():
            return False, "There is already an active Grand Prix event in progress on this server. Start or cancel it first."
            
        # Generate weather timeline
        import json
        import random
        weather_modes = ["Sunny", "Rain", "Mixed"]
        choice = random.choices(weather_modes, weights=[50, 20, 30], k=1)[0]
        
        timeline = []
        if choice == "Sunny":
            # 85% chance completely sunny, 15% chance of a tiny 2-lap drizzle
            if random.random() < 0.15 and laps > 5:
                rain_start = random.randint(3, laps - 2)
                forecast = f"Mostly sunny, but radar shows a 15% chance of a brief light shower around Lap {rain_start}."
                for i in range(1, laps + 1):
                    if rain_start <= i < rain_start + 2:
                        timeline.append("Rain")
                    else:
                        timeline.append("Sunny")
            else:
                timeline = ["Sunny"] * laps
                forecast = "Sunny and clear conditions expected throughout the race."
                
        elif choice == "Rain":
            # Dynamic rain: starts wet and dries, or starts sunny and gets wet, or is wet most of the race but has dry windows
            sub_choice = random.choice(["starts_wet", "ends_wet", "wet_spell"])
            if sub_choice == "starts_wet":
                wet_laps = random.randint(max(2, int(laps * 0.35)), max(3, int(laps * 0.65)))
                forecast = f"Heavy rain at start, expected to clear around Lap {wet_laps}."
                for i in range(1, laps + 1):
                    if i <= wet_laps:
                        timeline.append("Rain")
                    else:
                        timeline.append("Sunny")
            elif sub_choice == "ends_wet":
                rain_start = max(2, laps - random.randint(2, max(3, int(laps * 0.5))))
                forecast = f"Overcast start, heavy rain expected to arrive on Lap {rain_start}."
                for i in range(1, laps + 1):
                    if i >= rain_start:
                        timeline.append("Rain")
                    else:
                        timeline.append("Sunny")
            else:
                # Wet spell in the middle
                rain_start = random.randint(2, max(3, laps - 3))
                rain_len = random.randint(2, 4)
                forecast = f"Intermittent rain expected between Laps {rain_start} and {rain_start + rain_len}."
                for i in range(1, laps + 1):
                    if rain_start <= i < rain_start + rain_len:
                        timeline.append("Rain")
                    else:
                        timeline.append("Sunny")
                        
        else: # Mixed
            # Mixed conditions: multiple transitions or a standard mixed shower
            rain_start = random.randint(max(2, int(laps * 0.25)), max(3, int(laps * 0.65)))
            rain_duration = random.randint(3, max(4, int(laps * 0.3)))
            forecast = f"Mixed conditions. Dry start, with rain showers expected from Lap {rain_start} to {rain_start + rain_duration - 1}."
            for i in range(1, laps + 1):
                if rain_start <= i < rain_start + rain_duration:
                    timeline.append("Rain")
                else:
                    timeline.append("Sunny")
                    
        weather_data = {
            "start": timeline[0],
            "forecast": forecast,
            "timeline": timeline
        }
        weather_json = json.dumps(weather_data)
        
        today_str = datetime.now().isoformat()
        
        # Do not auto-assign season_id; it must be explicitly passed for season races.

        cursor.execute(
            "INSERT INTO races (guild_id, name, date, track, weather, status, laps, is_sprint, season_id) VALUES (?, ?, ?, ?, ?, 'Created', ?, ?, ?)",
            (guild_id, name, today_str, track, weather_json, laps, 1 if is_sprint else 0, season_id)
        )
        conn.commit()
        return True, f"Grand Prix **{name}** at **{track}** ({laps} laps) has been scheduled! Type `/joinrace` to enter."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_active_gp_race(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get the currently active Grand Prix race (any status other than Finished) for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM races WHERE status != 'Finished' AND status != 'Cancelled' AND guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def cancel_active_gp(guild_id: int) -> Tuple[bool, str]:
    """Cancel the active Grand Prix for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT race_id FROM races WHERE status != 'Finished' AND status != 'Cancelled' AND guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        if not row:
            return False, "There is no active Grand Prix to cancel on this server."
            
        race_id = row['race_id']
        
        cursor.execute("SELECT user_id FROM race_entries WHERE race_id = ?", (race_id,))
        entries = cursor.fetchall()
        
        # Update race status
        cursor.execute("UPDATE races SET status = 'Cancelled' WHERE race_id = ?", (race_id,))
        conn.commit()
        return True, f"Cancelled Grand Prix for {len(entries)} registered players."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def reroll_gp_to_grid(guild_id: int) -> Tuple[bool, str]:
    """
    Resets the most recent Grand Prix (or currently active GP) for a guild back to 'GridSet' status,
    clearing finish results/points/credits/winner while keeping all qualifying grid data (Q1/Q2/Q3 times and start_position).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT race_id, track, status FROM races WHERE guild_id = ? ORDER BY race_id DESC LIMIT 1", (guild_id,))
        race_row = cursor.fetchone()
        if not race_row:
            return False, "No Grand Prix race found for this server."
            
        race_id = race_row['race_id']
        track = race_row['track']
        
        cursor.execute("UPDATE races SET status = 'GridSet', winner_id = NULL WHERE race_id = ?", (race_id,))
        cursor.execute("""
            UPDATE race_entries 
            SET finish_position = NULL, points_earned = 0, credits_won = 0, dnf = 0 
            WHERE race_id = ?
        """, (race_id,))
        
        conn.commit()
        return True, f"Grand Prix of **{track}** (Race ID `{race_id}`) has been reset to **GridSet** status! All qualifying grid positions (P1-P{get_entry_count(race_id)}) preserved. You can now use `/gp_admin` and click **🏎️ Start Main GP** to restart."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_entry_count(race_id: int) -> int:
    """Helper to count entries for a race."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM race_entries WHERE race_id = ?", (race_id,))
    row = cursor.fetchone()
    conn.close()
    return row['cnt'] if row else 0


def register_gp_entry(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Register a user for the upcoming Grand Prix in a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check active race in this guild
        cursor.execute("SELECT race_id, status FROM races WHERE status = 'Created' AND guild_id = ?", (guild_id,))
        race_row = cursor.fetchone()
        if not race_row:
            return False, "There is no Grand Prix currently accepting registrations on this server."
            
        race_id = race_row['race_id']
        
        # Get user details for this guild
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "You need to create a profile first! Use `/start`."
            
        user_id = user_row['user_id']
        
        # Check if already registered
        cursor.execute("SELECT entry_id FROM race_entries WHERE race_id = ? AND user_id = ?", (race_id, user_id))
        if cursor.fetchone():
            return False, "You are already registered for this Grand Prix."
            
        # Insert entry record
        cursor.execute("INSERT INTO race_entries (race_id, user_id) VALUES (?, ?)", (race_id, user_id))
        
        conn.commit()
        return True, "You successfully registered for the Grand Prix!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def unregister_gp_entry(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Unregister a user from the upcoming Grand Prix in a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check active race in this guild (allow leaving before it runs)
        cursor.execute("SELECT race_id, status FROM races WHERE status != 'Finished' AND guild_id = ?", (guild_id,))
        race_row = cursor.fetchone()
        if not race_row:
            return False, "There is no active Grand Prix on this server."
            
        race_id = race_row['race_id']
        race_status = race_row['status']
        if race_status == 'Running':
            return False, "You cannot withdraw from a Grand Prix that has already started running."
        
        # Get user details for this guild
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "You do not have a profile on this server. Use `/start`."
            
        user_id = user_row['user_id']
        
        # Check if registered
        cursor.execute("SELECT entry_id FROM race_entries WHERE race_id = ? AND user_id = ?", (race_id, user_id))
        if not cursor.fetchone():
            return False, "You are not registered for this Grand Prix."
            
        # Delete entry record
        cursor.execute("DELETE FROM race_entries WHERE race_id = ? AND user_id = ?", (race_id, user_id))
        
        conn.commit()
        return True, "You successfully left the Grand Prix."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_gp_entries_full(race_id: int) -> List[Dict[str, Any]]:
    """Retrieve all team data joined for a specific race."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT re.entry_id, re.race_id, re.user_id, re.qual_time, re.start_position, re.finish_position, 
               re.current_q_tyre, re.quali_q1_time, re.quali_q2_time, re.quali_q3_time, re.points_earned,
               u.team_name, u.discord_id, u.level, u.pref_strategy, u.pref_tyres, u.pref_pit_stops, u.pit_strategy_json,
               u.country,
               d.pace, d.qual, d.wet_skill, d.consistency, d.aggression, d.overtaking, d.experience,
               s.pit_timing, s.weather_call, s.undercut, s.sc_skill, s.risk, s.communication,
               g.engine, g.aerodynamics, g.tyres, g.ers, g.reliability, g.pit_crew, 
               g.damage_engine, g.damage_tyres, g.damage_total
        FROM race_entries re
        JOIN users u ON re.user_id = u.user_id
        LEFT JOIN drivers d ON u.user_id = d.user_id
        LEFT JOIN strategists s ON u.user_id = s.user_id
        LEFT JOIN garage g ON u.user_id = g.user_id
        WHERE re.race_id = ?
    """, (race_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_gp_results(race_id: int, results: List[Dict[str, Any]], winner_user_id: int) -> None:
    """Save results of the GP race and update user standings/balances/stats."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify winner exists in users table (AI drivers have user_id like 9001, which is not in users table)
        valid_winner_id = None
        if winner_user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (winner_user_id,))
            if cursor.fetchone():
                valid_winner_id = winner_user_id

        # Update race winner and status
        cursor.execute(
            "UPDATE races SET status = 'Finished', winner_id = ? WHERE race_id = ?",
            (valid_winner_id, race_id)
        )
        
        # Save results for each entrant
        for res in results:
            user_id = res["user_id"]
            
            cursor.execute("""
                UPDATE race_entries 
                SET finish_position = ?, points_earned = ?, credits_won = ?, dnf = ?
                WHERE race_id = ? AND user_id = ?
            """, (res["finish_position"], res["points_earned"], res["credits_won"], res["dnf"], race_id, user_id))
            
            # Check if this user exists in users table (human user)
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            is_human = cursor.fetchone() is not None
            
            if not is_human:
                continue
                
            # Award credits to user profile
            cursor.execute(
                "UPDATE users SET money = money + ? WHERE user_id = ?",
                (res["credits_won"], user_id)
            )
            
            # Record wins/losses and add experience/XP
            if res["finish_position"] == 1:
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (user_id,))
                
            # Award XP (e.g. 500 XP for completing a GP, 1500 XP for podium)
            xp_to_add = 500
            if res["finish_position"] in [1, 2, 3]:
                xp_to_add = 1500
                
            # Calculate F1 Sprint points for direct stat boost: 8, 7, 6, 5, 4, 3, 2, 1
            finish_pos = res["finish_position"]
            if res["dnf"]:
                stat_boost = 0
            else:
                stat_boost = max(0, 9 - finish_pos) if finish_pos <= 8 else 0
            
            if stat_boost > 0:
                # 1. Boost Driver Skills Directly (capped at 100)
                cursor.execute("""
                    UPDATE drivers 
                    SET pace = MIN(100, pace + ?),
                        qual = MIN(100, qual + ?),
                        wet_skill = MIN(100, wet_skill + ?),
                        consistency = MIN(100, consistency + ?),
                        aggression = MIN(100, aggression + ?),
                        overtaking = MIN(100, overtaking + ?)
                    WHERE user_id = ?
                """, (stat_boost, stat_boost, stat_boost, stat_boost, stat_boost, stat_boost, user_id))

            # Add XP using add_user_xp logic (internal transaction, so we update manually here)
            cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                new_xp = user_row['xp'] + xp_to_add
                new_level = user_row['level']
                while new_xp >= new_level * 1000:
                    new_xp -= new_level * 1000
                    new_level += 1
                    # Level up reward: new_level * 500¢
                    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (new_level * 500, user_id))
                cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
                
            # Apply race damage to garage
            # If DNF, damage is high. Otherwise moderate.
            if res["dnf"]:
                dmg_eng = random.randint(10, 20)
                dmg_tyr = random.randint(20, 35)
            else:
                dmg_eng = random.randint(2, 5)
                dmg_tyr = random.randint(4, 10)
                
            cursor.execute("""
                UPDATE garage 
                SET damage_engine = MIN(100, damage_engine + ?),
                    damage_tyres = MIN(100, damage_tyres + ?)
                WHERE user_id = ?
            """, (dmg_eng, dmg_tyr, user_id))
            
            # Recalculate damage_total
            cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (user_id,))
            damages = cursor.fetchone()
            if damages:
                new_total = damages['damage_engine'] + damages['damage_tyres']
                cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (new_total, user_id))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving GP results: {e}")
        raise e
    finally:
        conn.close()

def save_quali_results(race_id: int, results: List[Dict[str, Any]], session: str) -> None:
    """Save qualifying times and starting/elimination positions in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for entry in results:
            user_id = entry["user_id"]
            time_val = entry["quali_time"]
            start_pos = entry.get("start_position")
            
            if session == "Q1":
                cursor.execute("""
                    UPDATE race_entries 
                    SET quali_q1_time = ?, start_position = COALESCE(?, start_position)
                    WHERE race_id = ? AND user_id = ?
                """, (time_val, start_pos, race_id, user_id))
            elif session == "Q2":
                cursor.execute("""
                    UPDATE race_entries 
                    SET quali_q2_time = ?, start_position = COALESCE(?, start_position)
                    WHERE race_id = ? AND user_id = ?
                """, (time_val, start_pos, race_id, user_id))
            elif session == "Q3":
                cursor.execute("""
                    UPDATE race_entries 
                    SET quali_q3_time = ?, start_position = COALESCE(?, start_position)
                    WHERE race_id = ? AND user_id = ?
                """, (time_val, start_pos, race_id, user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving qualifying results: {e}")
        conn.rollback()
    finally:
        conn.close()

def update_gp_status(race_id: int, status: str) -> bool:
    """Update status of a Grand Prix race in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE races SET status = ? WHERE race_id = ?", (status, race_id))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_last_finished_gp_results(guild_id: int) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve details of the last completed Grand Prix and its results for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM races WHERE status = 'Finished' AND guild_id = ? ORDER BY race_id DESC LIMIT 1", (guild_id,))
    race_row = cursor.fetchone()
    if not race_row:
        conn.close()
        return None, []
        
    race = dict(race_row)
    cursor.execute("""
        SELECT re.finish_position, re.points_earned, re.credits_won, re.dnf, u.team_name
        FROM race_entries re
        JOIN users u ON re.user_id = u.user_id
        WHERE re.race_id = ?
        ORDER BY re.finish_position ASC
    """, (race['race_id'],))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return race, results


# ----------------- Season & Driver Championship Helpers -----------------

def create_season(guild_id: int, name: str) -> Tuple[bool, str]:
    """Create a new active Season for the guild."""
    try:
        init_db()
    except Exception:
        pass
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT season_id FROM seasons WHERE status = 'Active' AND guild_id = ?", (guild_id,))
        if cursor.fetchone():
            return False, "An active Season is already in progress on this server! End or cancel it first."
            
        today_str = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO seasons (guild_id, name, status, created_at) VALUES (?, ?, 'Active', ?)",
            (guild_id, name, today_str)
        )
        conn.commit()
        return True, f"🏆 **{name}** has been officially created! Schedule GPs and Sprints to build the Driver Championship standings."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_active_season(guild_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve active season for a guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seasons WHERE status = 'Active' AND guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def cancel_active_season(guild_id: int) -> Tuple[bool, str]:
    """Cancel active season for a guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT season_id, name FROM seasons WHERE status = 'Active' AND guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        if not row:
            return False, "No active season to cancel."
            
        cursor.execute("UPDATE seasons SET status = 'Cancelled' WHERE season_id = ?", (row['season_id'],))
        conn.commit()
        return True, f"🚫 Season **{row['name']}** has been cancelled."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def end_active_season(guild_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Conclude the active season, determine Driver Champion, and return final standings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM seasons WHERE status = 'Active' AND guild_id = ?", (guild_id,))
        season_row = cursor.fetchone()
        if not season_row:
            return False, "No active season to end.", None, []
            
        season = dict(season_row)
        season_id = season['season_id']
        
        # Calculate driver points total across all finished races in this season
        cursor.execute("""
            SELECT u.user_id, u.team_name, u.discord_id, SUM(re.points_earned) as total_points, COUNT(re.entry_id) as races_entered
            FROM race_entries re
            JOIN races r ON re.race_id = r.race_id
            JOIN users u ON re.user_id = u.user_id
            WHERE r.season_id = ? AND r.status = 'Finished'
            GROUP BY u.user_id
            ORDER BY total_points DESC, races_entered ASC
        """, (season_id,))
        
        standings = [dict(row) for row in cursor.fetchall()]
        
        champion = standings[0] if standings else None
        champion_id = champion['user_id'] if champion else None
        
        cursor.execute("UPDATE seasons SET status = 'Finished', winner_id = ? WHERE season_id = ?", (champion_id, season_id))
        conn.commit()
        
        msg = f"🏆 **{season['name']}** has concluded!"
        if champion:
            msg += f" Congratulations to **{champion['team_name']}** — World Driver Champion!"
        return True, msg, season, standings
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", None, []
    finally:
        conn.close()


# ----------------- Inventory, Boosters & Practice Helpers -----------------

def add_inventory_part(user_id: int, category: str, part_name: str, rarity: str, level: int, stat_bonus: int) -> Tuple[bool, str, int]:
    """Add a new part to user's storage inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        today_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO user_inventory (user_id, category, part_name, rarity, level, stat_bonus, is_equipped, acquired_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (user_id, category, part_name, rarity, level, stat_bonus, today_str))
        item_id = cursor.lastrowid
        conn.commit()
        return True, "Part added to inventory.", item_id
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", 0
    finally:
        conn.close()

def get_user_inventory(user_id: int, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve items in user's inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if category:
        cursor.execute("SELECT * FROM user_inventory WHERE user_id = ? AND category = ? ORDER BY is_equipped DESC, level DESC", (user_id, category))
    else:
        cursor.execute("SELECT * FROM user_inventory WHERE user_id = ? ORDER BY category, is_equipped DESC, level DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def equip_inventory_part(user_id: int, item_id: int) -> Tuple[bool, str]:
    """Equip a part from inventory onto active car setup while keeping exact item level."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM user_inventory WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        part = cursor.fetchone()
        if not part:
            return False, "Part not found in inventory."
            
        category = part['category']
        level = part['level']
        
        # Unequip current part in same category
        cursor.execute("UPDATE user_inventory SET is_equipped = 0 WHERE user_id = ? AND category = ?", (user_id, category))
        # Equip new part
        cursor.execute("UPDATE user_inventory SET is_equipped = 1 WHERE item_id = ?", (item_id,))
        
        conn.commit()
        return True, f"✅ Successfully equipped **{part['rarity']} {part['part_name']}** (Level {level})!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_user_garage_levels(user_id: int) -> Dict[str, int]:
    """Retrieve current garage component levels for user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT engine, aerodynamics, tyres, ers, reliability, pit_crew FROM garage WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return {"engine": 1, "aerodynamics": 1, "tyres": 1, "ers": 1, "reliability": 1, "pit_crew": 1}

def unequip_inventory_part_category(user_id: int, category: str) -> Tuple[bool, str]:

    """Unequip any custom equipped part for a specific category, reverting to baseline."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE user_inventory SET is_equipped = 0 WHERE user_id = ? AND category = ?", (user_id, category))
        conn.commit()
        cat_title = category.replace('_', ' ').title()
        return True, f"✅ Unequipped custom **{cat_title}** part (reverted to stock baseline)."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def sell_inventory_part(user_id: int, item_id: int) -> Tuple[bool, str, int]:
    """
    Sell an unequipped inventory part for 60% of its upgrade cost value.
    Returns (success, message, credits_earned)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM user_inventory WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        part = cursor.fetchone()
        if not part:
            return False, "❌ Part not found in your inventory.", 0
            
        if part['is_equipped']:
            return False, "❌ You cannot sell a part that is currently equipped! Unequip or equip another part first.", 0
            
        category = part['category']
        level = part['level']
        rarity = part['rarity']
        part_name = part['part_name']
        
        if level in config.ENGINE_UPGRADE_COSTS:
            full_val = config.get_upgrade_cost(category, level, rarity)
        else:
            base_cost = config.ENGINE_UPGRADE_COSTS.get(2, 200)
            full_val = int(base_cost * config.PART_MULTIPLIERS.get(category, 1.0) * config.RARITY_PRICE_MULTIPLIERS.get(rarity, 1.0) * 0.5)
            
        sell_price = max(50, int(full_val * config.PART_SELL_RATIO))
        
        cursor.execute("DELETE FROM user_inventory WHERE item_id = ?", (item_id,))
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (sell_price, user_id))
        conn.commit()
        
        msg = f"💰 **Part Salvaged!** Sold **{rarity} {part_name}** (Lvl {level} {category.capitalize()}) for **+{sell_price:,} credits** (60% value)!"
        return True, msg, sell_price
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", 0
    finally:
        conn.close()

def auto_equip_best_parts(user_id: int) -> Tuple[bool, str, int]:
    """
    Automatically equip the highest quality/level part in each category for the user.
    Returns (success, summary_message, count_equipped)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    valid_categories = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
    equipped_count = 0
    equipped_details = []
    
    try:
        for cat in valid_categories:
            cursor.execute("""
                SELECT item_id, part_name, rarity, level, stat_bonus 
                FROM user_inventory 
                WHERE user_id = ? AND category = ?
                ORDER BY stat_bonus DESC, level DESC
                LIMIT 1
            """, (user_id, cat))
            best = cursor.fetchone()
            if best:
                cursor.execute("UPDATE user_inventory SET is_equipped = 0 WHERE user_id = ? AND category = ?", (user_id, cat))
                cursor.execute("UPDATE user_inventory SET is_equipped = 1 WHERE item_id = ?", (best['item_id'],))
                equipped_count += 1
                cat_title = cat.replace('_', ' ').title()
                equipped_details.append(f"• **{cat_title}:** {best['rarity']} {best['part_name']} (Lvl {best['level']})")


                
        conn.commit()
        if equipped_count == 0:
            return False, "⚠️ No custom parts found in inventory to equip.", 0
        msg = f"⚡ **Auto-Equipped Best Parts ({equipped_count} categories updated):**\n" + "\n".join(equipped_details)
        return True, msg, equipped_count
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", 0
    finally:
        conn.close()


def get_equipped_inventory(user_id_or_discord_id: int) -> Dict[str, Dict[str, Any]]:
    """Return dictionary of currently equipped parts per category."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id_or_discord_id,))
    row = cursor.fetchone()
    if row:
        target_uid = row['user_id']
    else:
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ?", (user_id_or_discord_id,))
        row2 = cursor.fetchone()
        target_uid = row2['user_id'] if row2 else user_id_or_discord_id
    
    cursor.execute("SELECT * FROM user_inventory WHERE user_id = ? AND is_equipped = 1", (target_uid,))
    rows = cursor.fetchall()
    conn.close()
    res = {}
    for r in rows:
        d = dict(r)
        res[d['category']] = d
    return res

def add_user_booster(user_id: int, booster_type: str, booster_name: str) -> Tuple[bool, str]:
    """Add a consumable booster while enforcing MAX 2 BOOSTERS cap."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SUM(charges) as total_charges FROM user_boosters WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        current_count = row['total_charges'] if row and row['total_charges'] else 0
        
        if current_count >= 2:
            return False, "❌ **Booster Cap Reached!** You can only hold a maximum of 2 active boosters at a time. Use one before buying another!"
            
        cursor.execute("SELECT booster_id, charges FROM user_boosters WHERE user_id = ? AND booster_name = ?", (user_id, booster_name))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE user_boosters SET charges = charges + 1 WHERE booster_id = ?", (existing['booster_id'],))
        else:
            cursor.execute("INSERT INTO user_boosters (user_id, booster_type, booster_name, charges) VALUES (?, ?, ?, 1)",
                           (user_id, booster_type, booster_name))
        conn.commit()
        return True, f"✅ Acquired **{booster_name}**!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_user_boosters(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve active boosters for user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_boosters WHERE user_id = ? AND charges > 0", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def consume_user_booster(user_id: int, booster_name: str) -> bool:
    """Deduct 1 charge of a booster."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE user_boosters SET charges = charges - 1 WHERE user_id = ? AND booster_name = ? AND charges > 0", (user_id, booster_name))
        cursor.execute("DELETE FROM user_boosters WHERE user_id = ? AND charges <= 0", (user_id,))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def record_track_practice(user_id: int, track_name: str) -> Tuple[bool, str, float]:
    """
    Record solo practice session on a track.
    Enforces max 3 practice sessions PER DAY across all tracks.
    Caps track pace bonus at -0.15s max (20% Track Familiarity).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    try:
        # Check user balance for practice fee (400¢)
        cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        user_money = user_row['money'] if user_row else 0
        if user_money < config.PRACTICE_SESSION_COST:
            return False, f"❌ **Insufficient Funds!** A track practice session costs **{config.PRACTICE_SESSION_COST:,}¢**, but you only have **{user_money:,}¢**.", 0.0

        # Check total daily practice count for user
        cursor.execute("SELECT SUM(practice_count) as daily_count FROM track_mastery WHERE user_id = ? AND last_practice_date = ?", (user_id, today_str))
        row = cursor.fetchone()
        daily_count = row['daily_count'] if row and row['daily_count'] else 0
        if daily_count >= 3:
            return False, "❌ **Daily Practice Limit Reached!** You have already completed 3 practice sessions today. Come back tomorrow!", 0.0
            
        cursor.execute("SELECT * FROM track_mastery WHERE user_id = ? AND track_name = ?", (user_id, track_name))
        existing = cursor.fetchone()
        
        if existing:
            current_bonus = existing['pace_bonus']
            if current_bonus >= 0.15:
                return False, f"🎯 **Track Mastery Maxed!** You have achieved 100% mastery on **{track_name}** (Max `-0.15s` pace bonus).", 0.15
                
            new_bonus = min(0.15, current_bonus + 0.04)
            new_count = existing['practice_count'] + 1
            cursor.execute("""
                UPDATE track_mastery 
                SET practice_count = ?, last_practice_date = ?, pace_bonus = ?
                WHERE mastery_id = ?
            """, (new_count, today_str, new_bonus, existing['mastery_id']))
        else:
            new_bonus = 0.04
            new_count = 1
            cursor.execute("""
                INSERT INTO track_mastery (user_id, track_name, practice_count, last_practice_date, pace_bonus)
                VALUES (?, ?, 1, ?, 0.04)
            """, (user_id, track_name, today_str))
            
        # Deduct practice fee (400¢)
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (config.PRACTICE_SESSION_COST, user_id))

        conn.commit()
        return True, f"🏎️ Practice complete at **{track_name}**! (Cost: `{config.PRACTICE_SESSION_COST:,}¢`). Track Familiarity increased. Pace bonus: **-{new_bonus:.2f}s/lap**.", new_bonus
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", 0.0
    finally:
        conn.close()

def get_track_mastery_bonus(user_id: int, track_name: str) -> float:
    """Return track pace bonus in seconds (0.0 to 0.15)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT pace_bonus FROM track_mastery WHERE user_id = ? AND track_name = ?", (user_id, track_name))
        row = cursor.fetchone()
        return float(row['pace_bonus']) if row else 0.0
    finally:
        conn.close()

def apply_race_damage(user_id: int, is_dnf: bool = False) -> None:
    """Apply engine and tyre damage to a user's garage after a race."""
    if user_id is None or user_id == 0 or user_id >= 999900:
        return  # Skip AI drivers
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if is_dnf:
            dmg_eng = random.randint(10, 20)
            dmg_tyr = random.randint(20, 35)
        else:
            dmg_eng = random.randint(2, 5)
            dmg_tyr = random.randint(4, 10)

        cursor.execute("""
            UPDATE garage
            SET damage_engine = MIN(100, damage_engine + ?),
                damage_tyres = MIN(100, damage_tyres + ?)
            WHERE user_id = ?
        """, (dmg_eng, dmg_tyr, user_id))

        cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            new_total = row['damage_engine'] + row['damage_tyres']
            cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (new_total, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error applying race damage: {e}")
    finally:
        conn.close()

def record_race_result(winner_user_id: int, loser_user_id: int, guild_id: int, win_prize: int = None, loss_prize: int = None, win_xp: int = None, loss_xp: int = None, winner_dnf: bool = False, loser_dnf: bool = False) -> bool:
    """Record 1v1 duel race results: update wins/losses, award XP, prize credits, and apply garage damage."""
    conn = get_db_connection()
    cursor = conn.cursor()
    w_prize = config.WIN_PRIZE_CREDITS if win_prize is None else win_prize
    l_prize = config.LOSS_PRIZE_CREDITS if loss_prize is None else loss_prize
    w_xp = config.WIN_XP if win_xp is None else win_xp
    l_xp = config.LOSS_XP if loss_xp is None else loss_xp
    try:
        # Update winner: +1 win, +w_xp, +w_prize
        cursor.execute("""
            UPDATE users
            SET wins = wins + 1,
                xp = xp + ?,
                money = money + ?
            WHERE user_id = ?
        """, (w_xp, w_prize, winner_user_id))
        
        # Update loser: +1 loss, +l_xp, +l_prize
        cursor.execute("""
            UPDATE users
            SET losses = losses + 1,
                xp = xp + ?,
                money = money + ?
            WHERE user_id = ?
        """, (l_xp, l_prize, loser_user_id))

        # Level up checks
        for uid in [winner_user_id, loser_user_id]:
            cursor.execute("SELECT level, xp FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if row:
                needed_xp = row['level'] * 1000
                if row['xp'] >= needed_xp:
                    cursor.execute("UPDATE users SET level = level + 1 WHERE user_id = ?", (uid,))

        conn.commit()

        # Apply car wear/damage to garage
        apply_race_damage(winner_user_id, is_dnf=winner_dnf)
        apply_race_damage(loser_user_id, is_dnf=loser_dnf)

        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

# ----------------- WDC Season Calendar Helpers -----------------

def get_season_calendar(season_id: int) -> List[Dict[str, Any]]:
    """Get all scheduled races in the season's calendar ordered by race_order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM season_calendar WHERE season_id = ? ORDER BY race_order ASC", (season_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_season_race(season_id: int, track: str, laps: int, is_sprint: bool) -> Tuple[bool, str]:
    """Add a race or sprint to the WDC Season calendar."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Find next race order index
        cursor.execute("SELECT MAX(race_order) as max_order FROM season_calendar WHERE season_id = ?", (season_id,))
        row = cursor.fetchone()
        next_order = (row['max_order'] + 1) if (row and row['max_order'] is not None) else 1
        
        cursor.execute(
            "INSERT INTO season_calendar (season_id, track, laps, is_sprint, race_order, status) VALUES (?, ?, ?, ?, ?, 'Scheduled')",
            (season_id, track, laps, 1 if is_sprint else 0, next_order)
        )
        conn.commit()
        race_type = "Sprint" if is_sprint else "Grand Prix"
        return True, f"Successfully added **{track} {race_type}** ({laps} Laps) as Round {next_order} to the WDC season calendar!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def remove_season_race(calendar_id: int) -> Tuple[bool, str]:
    """Remove a race from the WDC Season calendar and shift orders."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get season_id and current race_order
        cursor.execute("SELECT season_id, race_order, track FROM season_calendar WHERE calendar_id = ?", (calendar_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Race not found in calendar."
        
        season_id = row['season_id']
        removed_order = row['race_order']
        track = row['track']
        
        cursor.execute("DELETE FROM season_calendar WHERE calendar_id = ?", (calendar_id,))
        
        # Shift orders of subsequent races
        cursor.execute(
            "UPDATE season_calendar SET race_order = race_order - 1 WHERE season_id = ? AND race_order > ?",
            (season_id, removed_order)
        )
        conn.commit()
        return True, f"Successfully removed **{track}** from the WDC season calendar."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def update_calendar_orders(calendar_id_orders: List[int]) -> None:
    """Reorder season calendar items based on list of calendar_ids."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for idx, cal_id in enumerate(calendar_id_orders):
            cursor.execute("UPDATE season_calendar SET race_order = ? WHERE calendar_id = ?", (idx + 1, cal_id))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()

def get_next_scheduled_calendar_race(season_id: int) -> Optional[Dict[str, Any]]:
    """Return the next Scheduled or Running race in the WDC calendar."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM season_calendar WHERE season_id = ? AND status IN ('Scheduled', 'Running') ORDER BY race_order ASC LIMIT 1",
        (season_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_calendar_race_status(calendar_id: int, status: str) -> None:
    """Mark a calendar race status ('Scheduled', 'Running', 'Finished')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE season_calendar SET status = ? WHERE calendar_id = ?", (status, calendar_id))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()

def reset_user_profile(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Reset a user's stats, credits, skills, garage parts, and inventory back to starting defaults without deleting their profile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found on this server."
            
        uid = row['user_id']
        team_name = row['team_name']
        
        # Reset users table baseline
        cursor.execute("""
            UPDATE users 
            SET money = ?, 
                xp = ?, 
                level = ?, 
                wins = 0, 
                losses = 0,
                daily_chat_credits = 0,
                daily_voice_credits = 0,
                pref_strategy = 'Balanced',
                pref_tyres = 'Medium',
                pref_pit_stops = 1
            WHERE user_id = ?
        """, (config.STARTING_MONEY, config.STARTING_XP, config.STARTING_LEVEL, uid))
        
        # Reset driver skills
        cursor.execute("""
            UPDATE drivers
            SET pace = 50, qual = 50, wet_skill = 50, consistency = 50, aggression = 50, overtaking = 50, experience = 0
            WHERE user_id = ?
        """, (uid,))
        
        # Reset garage component levels and damage
        cursor.execute("""
            UPDATE garage
            SET engine = 1, aerodynamics = 1, tyres = 1, ers = 1, reliability = 1, pit_crew = 1,
                damage_engine = 0, damage_tyres = 0
            WHERE user_id = ?
        """, (uid,))
        
        # Clear custom inventory, boosters, and track mastery
        cursor.execute("DELETE FROM user_inventory WHERE user_id = ?", (uid,))
        cursor.execute("DELETE FROM user_boosters WHERE user_id = ?", (uid,))
        cursor.execute("DELETE FROM track_mastery WHERE user_id = ?", (uid,))
        
        conn.commit()
        return True, f"Successfully reset all stats, credits, garage parts, and inventory for **{team_name}** back to default starting levels!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def rollback_user_profile_to_timestamp(
    discord_id: int, 
    guild_id: int, 
    cutoff_iso: str, 
    target_money: Optional[int] = None, 
    target_xp: Optional[int] = None, 
    target_level: Optional[int] = None,
    reset_upgrades: bool = False,
    reset_driver_skills: bool = False
) -> Tuple[bool, str]:
    """Roll back inventory parts (deleting only crate drops acquired after cutoff_iso), duel history, and subtract post-cutoff XP/credits while preserving pre-cutoff parts & XP."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name, money, xp, level, wins, losses FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found on this server."
            
        uid = row['user_id']
        team_name = row['team_name']
        current_money = row['money']
        current_xp = row['xp']
        current_level = row['level']
        current_wins = row['wins']
        current_losses = row['losses']
        
        # Parse cutoff to construct both IST and UTC strings for robust SQLite matching
        from datetime import datetime, timezone, timedelta
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        try:
            cutoff_dt = datetime.fromisoformat(cutoff_iso)
        except Exception:
            cutoff_dt = datetime.now(ist_tz).replace(hour=15, minute=0, second=0, microsecond=0)

        if cutoff_dt.tzinfo is None:
            cutoff_dt = cutoff_dt.replace(tzinfo=ist_tz)
        
        ist_str1 = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')
        ist_str2 = cutoff_dt.strftime('%Y-%m-%dT%H:%M:%S')
        utc_dt = cutoff_dt.astimezone(timezone.utc)
        utc_str1 = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
        utc_str2 = utc_dt.strftime('%Y-%m-%dT%H:%M:%S')

        # 1. Delete ONLY inventory parts acquired on or after cutoff (leaving pre-cutoff Common & other parts intact!)
        cursor.execute("""
            DELETE FROM user_inventory 
            WHERE user_id = ? AND (
                acquired_at >= ? OR acquired_at >= ? OR acquired_at >= ? OR acquired_at >= ?
            )
        """, (uid, ist_str1, ist_str2, utc_str1, utc_str2))
        inv_removed = cursor.rowcount

        # 2. Count & delete post-cutoff duel history records
        cursor.execute("""
            SELECT winner_id, loser_id FROM duel_history 
            WHERE (winner_id = ? OR loser_id = ?) AND (
                created_at >= ? OR created_at >= ? OR created_at >= ? OR created_at >= ?
            )
        """, (uid, uid, ist_str1, ist_str2, utc_str1, utc_str2))
        recent_duels = cursor.fetchall()
        duels_removed = len(recent_duels)
        
        # Calculate wins/losses after cutoff to deduct
        recent_wins = sum(1 for d in recent_duels if d['winner_id'] == uid)
        recent_losses = sum(1 for d in recent_duels if d['loser_id'] == uid)

        cursor.execute("""
            DELETE FROM duel_history 
            WHERE (winner_id = ? OR loser_id = ?) AND (
                created_at >= ? OR created_at >= ? OR created_at >= ? OR created_at >= ?
            )
        """, (uid, uid, ist_str1, ist_str2, utc_str1, utc_str2))
        
        cursor.execute("DELETE FROM bets WHERE bettor_id = ? OR target_id = ?", (uid, uid))

        # 3. Reset crate pity counters
        cursor.execute("""
            UPDATE users 
            SET crate_rookie_pity = 0, crate_pro_pity = 0, crate_champion_pity = 0
            WHERE user_id = ?
        """, (uid,))

        # 4. Optionally revert garage component upgrades if requested
        if reset_upgrades:
            cursor.execute("""
                UPDATE garage 
                SET engine = 1, aerodynamics = 1, tyres = 1, ers = 1, reliability = 1, pit_crew = 1,
                    damage_engine = 0, damage_tyres = 0, damage_total = 0
                WHERE user_id = ?
            """, (uid,))

        # 5. Optionally revert driver & strategist trained skills back to 50 (starting baseline)
        if reset_driver_skills:
            cursor.execute("""
                UPDATE drivers
                SET pace = 50, qual = 50, wet_skill = 50, consistency = 50, aggression = 50, overtaking = 50, experience = 0
                WHERE user_id = ?
            """, (uid,))
            cursor.execute("""
                UPDATE strategists
                SET pit_timing = 50, weather_call = 50, undercut = 50, sc_skill = 50, risk = 50, communication = 50, experience = 0
                WHERE user_id = ?
            """, (uid,))

        # 6. Re-equip the highest level remaining part acquired BEFORE 3:00 PM IST per category (e.g. pre-existing Common part)
        categories = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
        for cat in categories:
            cursor.execute("SELECT item_id FROM user_inventory WHERE user_id = ? AND category = ? AND is_equipped = 1", (uid, cat))
            equipped_row = cursor.fetchone()
            if not equipped_row:
                cursor.execute("SELECT item_id FROM user_inventory WHERE user_id = ? AND category = ? ORDER BY level DESC LIMIT 1", (uid, cat))
                best_remaining = cursor.fetchone()
                if best_remaining:
                    cursor.execute("UPDATE user_inventory SET is_equipped = 1 WHERE item_id = ?", (best_remaining['item_id'],))

        # 7. Calculate rolled back Money, XP, and Level
        xp_gained_after_cutoff = (recent_wins * config.WIN_XP) + (recent_losses * config.LOSS_XP)
        
        new_xp = target_xp if target_xp is not None else max(0, current_xp - xp_gained_after_cutoff)
        new_level = target_level if target_level is not None else max(1, (new_xp // 1000) + 1)
        new_money = target_money if target_money is not None else current_money

        new_wins = max(0, current_wins - recent_wins)
        new_losses = max(0, current_losses - recent_losses)

        cursor.execute("""
            UPDATE users 
            SET money = ?, xp = ?, level = ?, wins = ?, losses = ?
            WHERE user_id = ?
        """, (new_money, new_xp, new_level, new_wins, new_losses, uid))
        
        conn.commit()
        return True, (
            f"Successfully rolled back **{team_name}** to state prior to `{cutoff_iso}`!\n"
            f"• **Inventory Restored:** `{inv_removed}` crate drops unboxed after 3:00 PM IST removed. Pre-existing inventory (e.g. Common parts) re-equipped!\n"
            f"• **XP Rolled Back:** `{current_xp:,} XP` ➡️ `{new_xp:,} XP` (Level `{new_level}`)\n"
            f"• **Credits Rolled Back:** `{current_money:,}¢` ➡️ `{new_money:,}¢`\n"
            f"• **Duels & Pity Purged:** `{duels_removed}` recent duels removed (Wins: {new_wins}, Losses: {new_losses})."
        )
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def admin_set_full_user_profile(
    discord_id: int,
    guild_id: int,
    money: Optional[int] = None,
    xp: Optional[int] = None,
    level: Optional[int] = None,
    engine: Optional[int] = None,
    aerodynamics: Optional[int] = None,
    tyres: Optional[int] = None,
    ers: Optional[int] = None,
    reliability: Optional[int] = None,
    pit_crew: Optional[int] = None,
    driver_skills: Optional[int] = None
) -> Tuple[bool, str]:
    """Admin tool to explicitly set a user's level, XP, money, garage component levels, and driver skills."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found."

        uid = row['user_id']
        team_name = row['team_name']

        # Update users table
        updates = []
        params = []
        if money is not None:
            updates.append("money = ?")
            params.append(money)
        if xp is not None:
            updates.append("xp = ?")
            params.append(xp)
        if level is not None:
            updates.append("level = ?")
            params.append(level)

        if updates:
            params.append(uid)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", tuple(params))

        # Update garage table
        g_updates = []
        g_params = []
        if engine is not None:
            g_updates.append("engine = ?")
            g_params.append(engine)
        if aerodynamics is not None:
            g_updates.append("aerodynamics = ?")
            g_params.append(aerodynamics)
        if tyres is not None:
            g_updates.append("tyres = ?")
            g_params.append(tyres)
        if ers is not None:
            g_updates.append("ers = ?")
            g_params.append(ers)
        if reliability is not None:
            g_updates.append("reliability = ?")
            g_params.append(reliability)
        if pit_crew is not None:
            g_updates.append("pit_crew = ?")
            g_params.append(pit_crew)

        if g_updates:
            g_params.append(uid)
            cursor.execute(f"UPDATE garage SET {', '.join(g_updates)} WHERE user_id = ?", tuple(g_params))

        # Update driver skills
        if driver_skills is not None:
            cursor.execute("""
                UPDATE drivers 
                SET pace = ?, qual = ?, wet_skill = ?, consistency = ?, aggression = ?, overtaking = ?
                WHERE user_id = ?
            """, (driver_skills, driver_skills, driver_skills, driver_skills, driver_skills, driver_skills, uid))

        conn.commit()
        return True, f"Successfully updated profile stats for **{team_name}**!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def restore_user_from_backup_db(backup_path: str, discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Restore a user's exact profile, garage, drivers, and inventory from a pre-rollback database backup file."""
    if not os.path.exists(backup_path):
        return False, f"Backup file '{backup_path}' does not exist on host server."

    b_conn = sqlite3.connect(backup_path)
    b_conn.row_factory = sqlite3.Row
    b_cursor = b_conn.cursor()

    b_cursor.execute("SELECT * FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
    b_user = b_cursor.fetchone()
    if not b_user:
        b_conn.close()
        return False, f"User ID `{discord_id}` not found in backup database."

    b_uid = b_user['user_id']
    b_user_dict = dict(b_user)

    # Fetch backup garage, drivers, strategists, inventory
    b_cursor.execute("SELECT * FROM garage WHERE user_id = ?", (b_uid,))
    b_garage = b_cursor.fetchone()

    b_cursor.execute("SELECT * FROM drivers WHERE user_id = ?", (b_uid,))
    b_driver = b_cursor.fetchone()

    b_cursor.execute("SELECT * FROM user_inventory WHERE user_id = ?", (b_uid,))
    b_inv = b_cursor.fetchall()
    b_conn.close()

    # Active DB
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        active_user = cursor.fetchone()
        if not active_user:
            return False, "Target user profile not found in active database."

        uid = active_user['user_id']

        # Restore users table fields
        cursor.execute("""
            UPDATE users
            SET money = ?, xp = ?, level = ?, wins = ?, losses = ?
            WHERE user_id = ?
        """, (b_user_dict['money'], b_user_dict['xp'], b_user_dict['level'], b_user_dict['wins'], b_user_dict['losses'], uid))

        # Restore garage
        if b_garage:
            bg = dict(b_garage)
            cursor.execute("""
                UPDATE garage
                SET engine = ?, aerodynamics = ?, tyres = ?, ers = ?, reliability = ?, pit_crew = ?
                WHERE user_id = ?
            """, (bg['engine'], bg['aerodynamics'], bg['tyres'], bg['ers'], bg['reliability'], bg['pit_crew'], uid))

        # Restore drivers
        if b_driver:
            bd = dict(b_driver)
            cursor.execute("""
                UPDATE drivers
                SET pace = ?, qual = ?, wet_skill = ?, consistency = ?, aggression = ?, overtaking = ?, experience = ?
                WHERE user_id = ?
            """, (bd['pace'], bd['qual'], bd['wet_skill'], bd['consistency'], bd['aggression'], bd['overtaking'], bd['experience'], uid))

        # Restore pre-existing inventory items
        cursor.execute("DELETE FROM user_inventory WHERE user_id = ?", (uid,))
        for item in b_inv:
            it = dict(item)
            cursor.execute("""
                INSERT INTO user_inventory (user_id, category, part_name, rarity, level, stat_bonus, is_equipped, acquired_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, it['category'], it['part_name'], it['rarity'], it['level'], it['stat_bonus'], it['is_equipped'], it['acquired_at']))

        conn.commit()
        return True, f"Successfully restored **{b_user_dict['team_name']}** from backup! (Level {b_user_dict['level']}, {b_user_dict['money']:,}¢, {b_user_dict['xp']:,} XP)"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def _delete_user_data_by_uid(cursor: sqlite3.Cursor, uid: int) -> None:
    """Internal helper to delete all profile data for a given user_id."""
    cursor.execute("DELETE FROM race_entries WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM drivers WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM strategists WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM garage WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM user_inventory WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM user_boosters WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM track_mastery WHERE user_id = ?", (uid,))
    cursor.execute("DELETE FROM duel_history WHERE winner_id = ? OR loser_id = ?", (uid, uid))
    cursor.execute("DELETE FROM bets WHERE bettor_id = ? OR target_id = ?", (uid, uid))
    cursor.execute("UPDATE races SET winner_id = NULL WHERE winner_id = ?", (uid,))
    cursor.execute("UPDATE seasons SET winner_id = NULL WHERE winner_id = ?", (uid,))
    cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))


def delete_user_profile(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Permanently delete a user's entire profile and all associated data from the database.
    The user will need to use /start again to create a new profile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found on this server."

        uid = row['user_id']
        team_name = row['team_name']

        _delete_user_data_by_uid(cursor, uid)

        conn.commit()
        return True, f"Permanently deleted the profile for **{team_name}** (<@{discord_id}>). All stats, garage, inventory, race history, and track mastery have been wiped. They will need to use `/start` to create a new profile."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def reset_wdc_standings(guild_id: int) -> Tuple[bool, str]:
    """Reset all championship points (points_earned in race_entries) for the guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Reset points_earned to 0 in race_entries for all races in this guild
        cursor.execute("""
            UPDATE race_entries 
            SET points_earned = 0 
            WHERE race_id IN (SELECT race_id FROM races WHERE guild_id = ?)
        """, (guild_id,))
        
        conn.commit()
        return True, "Championship standings and WDC points have been successfully reset to 0 for this server."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def transfer_user_ownership(old_discord_id: int, new_discord_id: int, guild_id: Optional[int] = None, overwrite: bool = False) -> Tuple[bool, str]:
    """Transfer ownership of a user profile and admin rights from old_discord_id to new_discord_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if guild_id is not None:
            cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (old_discord_id, guild_id))
            rows = cursor.fetchall()
        else:
            cursor.execute("SELECT user_id, team_name, guild_id FROM users WHERE discord_id = ?", (old_discord_id,))
            rows = cursor.fetchall()

        if not rows:
            return False, f"Transfer failed: Source user <@{old_discord_id}> does not have an active profile on this server."

        # Check if new_discord_id already has a profile
        if guild_id is not None:
            cursor.execute("SELECT user_id FROM users WHERE discord_id = ? AND guild_id = ?", (new_discord_id, guild_id))
            dest_rows = cursor.fetchall()
        else:
            cursor.execute("SELECT user_id FROM users WHERE discord_id = ?", (new_discord_id,))
            dest_rows = cursor.fetchall()

        if dest_rows:
            if overwrite:
                for dest_row in dest_rows:
                    _delete_user_data_by_uid(cursor, dest_row['user_id'])
            else:
                return False, f"Transfer failed: Destination user <@{new_discord_id}> already has an existing profile on this server. Set `overwrite: True` in the transfer command or delete <@{new_discord_id}>'s profile first using `/admin deleteuser`."

        if guild_id is not None:
            cursor.execute("UPDATE users SET discord_id = ? WHERE discord_id = ? AND guild_id = ?", (new_discord_id, old_discord_id, guild_id))
            cursor.execute("UPDATE bot_admins SET discord_id = ? WHERE discord_id = ? AND guild_id = ?", (new_discord_id, old_discord_id, guild_id))
        else:
            cursor.execute("UPDATE users SET discord_id = ? WHERE discord_id = ?", (new_discord_id, old_discord_id))
            cursor.execute("UPDATE bot_admins SET discord_id = ? WHERE discord_id = ?", (new_discord_id, old_discord_id))

        cursor.execute("UPDATE bot_admins SET added_by = ? WHERE added_by = ?", (new_discord_id, old_discord_id))

        conn.commit()
        return True, f"Successfully transferred ownership of {len(rows)} user profile(s) from <@{old_discord_id}> to <@{new_discord_id}>."
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, f"Transfer failed: Destination user <@{new_discord_id}> already has an existing profile."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error during ownership transfer: {e}"
    finally:
        conn.close()




def admin_set_user_stat(discord_id: int, guild_id: int, stat_name: str, value: int) -> Tuple[bool, str]:
    """Set a driver skill or garage part level for a target user on a guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "Target user profile not found."
            
        uid = user_row['user_id']
        team = user_row['team_name']
        
        valid_garage = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
        valid_driver = ["pace", "qual", "wet_skill", "consistency", "aggression", "overtaking"]
        
        if stat_name in valid_garage:
            cursor.execute(f"UPDATE garage SET {stat_name} = ? WHERE user_id = ?", (value, uid))
            
            # If user has an equipped custom inventory part, update its level & bonus as well
            cursor.execute("SELECT item_id, part_name, rarity FROM user_inventory WHERE user_id = ? AND category = ? AND is_equipped = 1", (uid, stat_name))
            eq_item = cursor.fetchone()
            if eq_item:
                cursor.execute("UPDATE user_inventory SET level = ?, stat_bonus = ? WHERE item_id = ?", (value, value, eq_item['item_id']))
                conn.commit()
                return True, f"Successfully set **{eq_item['rarity']} {eq_item['part_name']}** (and Garage Baseline) to **Lvl {value}** for **{team}**!"
                
            conn.commit()
            return True, f"Successfully set **{stat_name.capitalize()}** to **Lvl {value}** for **{team}**!"
        elif stat_name in valid_driver:
            cursor.execute(f"UPDATE drivers SET {stat_name} = ? WHERE user_id = ?", (value, uid))
            conn.commit()
            return True, f"Successfully set **{stat_name.capitalize()}** to **Lvl {value}** for **{team}**!"
        else:
            return False, f"Invalid stat name `{stat_name}`."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def get_daily_reset_cooldown_str() -> Tuple[str, int]:
    """Returns formatted remaining time string (e.g. '2h 15m 30s') and target Unix timestamp for next midnight IST."""
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    tomorrow_midnight = datetime.combine(now_ist.date() + timedelta(days=1), datetime.min.time(), tzinfo=ist_tz)
    rem_seconds = max(0, int((tomorrow_midnight - now_ist).total_seconds()))
    hours = rem_seconds // 3600
    mins = (rem_seconds % 3600) // 60
    secs = rem_seconds % 60
    ts = int(tomorrow_midnight.timestamp())
    return f"**{hours}h {mins}m {secs}s** (<t:{ts}:R>)", ts

def get_ist_week_str() -> str:
    """Return current YYYY-Www ISO week string in Indian Standard Time (IST, UTC+5:30)."""
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    year, week, _ = now_ist.isocalendar()
    return f"{year}-W{week:02d}"

def get_weekly_reset_cooldown_str() -> Tuple[str, int]:
    """Returns formatted remaining time string (e.g. '4d 12h 15m 30s') and target Unix timestamp for next Monday 00:00 IST."""
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    days_until_monday = 7 - now_ist.weekday()
    next_monday = datetime.combine(now_ist.date() + timedelta(days=days_until_monday), datetime.min.time(), tzinfo=ist_tz)
    rem_seconds = max(0, int((next_monday - now_ist).total_seconds()))
    days = rem_seconds // 86400
    hours = (rem_seconds % 86400) // 3600
    mins = (rem_seconds % 3600) // 60
    secs = rem_seconds % 60
    ts = int(next_monday.timestamp())
    time_fmt = f"{days}d {hours}h {mins}m {secs}s" if days > 0 else f"{hours}h {mins}m {secs}s"
    return f"**{time_fmt}** (<t:{ts}:R>)", ts

def claim_daily_bonus(user_id: int) -> Tuple[bool, str]:
    """Claim daily credit bonus (500 credits)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        today_str = get_ist_date_str()
        
        if row and row['last_daily_claim'] == today_str:
            cd_str, _ = get_daily_reset_cooldown_str()
            return False, f"⏳ You have already claimed your daily bonus today! Cooldown: {cd_str}."
            
        reward = 500
        cursor.execute("UPDATE users SET money = money + ?, last_daily_claim = ? WHERE user_id = ?", (reward, today_str, user_id))
        conn.commit()
        return True, f"🎉 **Daily Bonus Claimed!** Received **+{reward:,} credits**!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def claim_weekly_bonus(user_id: int) -> Tuple[bool, str]:
    """Claim weekly credit bonus (3,000 credits)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_weekly_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        current_week_str = get_ist_week_str()
        
        if row and row['last_weekly_claim'] == current_week_str:
            cd_str, _ = get_weekly_reset_cooldown_str()
            return False, f"⏳ You have already claimed your weekly bonus for this week! Cooldown: {cd_str}."
            
        reward = config.WEEKLY_BONUS
        cursor.execute("UPDATE users SET money = money + ?, last_weekly_claim = ? WHERE user_id = ?", (reward, current_week_str, user_id))
        conn.commit()
        return True, f"🎁 **Weekly Bonus Claimed!** Received **+{reward:,} credits**!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def claim_work_rewards(user_id: int) -> Tuple[bool, str]:
    """Perform team work for daily credits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_work_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        today_str = get_ist_date_str()
        
        if row and row['last_work_claim'] == today_str:
            cd_str, _ = get_daily_reset_cooldown_str()
            return False, f"⏳ You have already completed your team work today! Cooldown: {cd_str}."
            
        import random
        reward = random.randint(250, 600)
        jobs = [
            "cleaned and polished the pit garage",
            "serviced the team transporter truck",
            "calibrated the tyre temperature sensors",
            "assisted the chief mechanic with engine telemetry",
            "managed sponsorship hospitality in the paddock"
        ]
        job = random.choice(jobs)
        cursor.execute("UPDATE users SET money = money + ?, last_work_claim = ? WHERE user_id = ?", (reward, today_str, user_id))
        conn.commit()
        return True, f"🛠️ You **{job}** and earned **+{reward:,} credits**!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def train_personnel_stat(user_id: int, skill_name: str, cost: int = 400) -> Tuple[bool, str]:
    """Alias for train_personnel_skill for driver attributes."""
    return train_personnel_skill(user_id, "driver", skill_name, cost)

def upgrade_garage_part(user_id: int, part_name: str, cost: int = 0) -> Tuple[bool, str]:
    """Alias for upgrade_part."""
    return upgrade_part(user_id, part_name)

def repair_user_car(user_id: int, part_name: str, cost: int = 0) -> Tuple[bool, str]:
    """Alias for repair_part."""
    return repair_part(user_id, part_name)

# ======================== Bot Admin Management ========================

def add_bot_admin(discord_id: int, guild_id: int, added_by: int) -> Tuple[bool, str]:
    """Add a user as a game admin for this server."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO bot_admins (discord_id, guild_id, added_by) VALUES (?, ?, ?)",
            (discord_id, guild_id, added_by)
        )
        conn.commit()
        return True, f"<@{discord_id}> has been granted **Game Admin** access."
    except Exception as e:
        return False, f"Failed to add admin: {str(e)}"
    finally:
        conn.close()

def remove_bot_admin(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Remove a user's game admin access for this server."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM bot_admins WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id)
        )
        conn.commit()
        if cursor.rowcount > 0:
            return True, f"<@{discord_id}>'s **Game Admin** access has been revoked."
        else:
            return False, f"<@{discord_id}> is not a game admin."
    except Exception as e:
        return False, f"Failed to remove admin: {str(e)}"
    finally:
        conn.close()

def is_bot_admin(discord_id: int, guild_id: int) -> bool:
    """Check if a user is a game admin for this server."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM bot_admins WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id)
        ).fetchone()
        return row is not None
    finally:
        conn.close()

def get_bot_admins(guild_id: int) -> list:
    """Get all game admins for this server."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT discord_id, added_by, added_at FROM bot_admins WHERE guild_id = ? ORDER BY added_at",
            (guild_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def record_duel_history(guild_id: int, winner_id: int, loser_id: int) -> None:
    """Record a 1v1 duel victory in duel_history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        today_str = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO duel_history (guild_id, winner_id, loser_id, created_at) VALUES (?, ?, ?, ?)",
            (guild_id, winner_id, loser_id, today_str)
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error recording duel history: {e}")
    finally:
        conn.close()

def get_head_to_head_record(user1_id: int, user2_id: int) -> Tuple[int, int]:
    """Returns (user1_wins, user2_wins) between user1 and user2."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM duel_history WHERE winner_id = ? AND loser_id = ?",
            (user1_id, user2_id)
        )
        row1 = cursor.fetchone()
        u1_wins = row1[0] if row1 else 0
        
        cursor.execute(
            "SELECT COUNT(*) FROM duel_history WHERE winner_id = ? AND loser_id = ?",
            (user2_id, user1_id)
        )
        row2 = cursor.fetchone()
        u2_wins = row2[0] if row2 else 0
        
        return (u1_wins, u2_wins)
    except sqlite3.Error:
        return (0, 0)
    finally:
        conn.close()

def get_server_engagement_stats(guild_id: int, timeframe: str = 'today') -> Dict[str, Any]:
    """
    Retrieve real, accurate engagement & activity statistics for a Discord server (guild_id).
    timeframe can be 'today', 'weekly' (7 days), 'monthly' (30 days), or 'all' (all-time).
    Returns a dictionary of metrics showing how much the bot has engaged server members.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        tf = (timeframe or 'today').lower()
        if tf == 'today':
            date_param = "-1 day"
        elif tf == 'weekly':
            date_param = "-7 days"
        elif tf == 'monthly':
            date_param = "-30 days"
        else: # 'all'
            date_param = None

        if date_param:
            date_filter = f"substr(created_at, 1, 10) >= date('now', '{date_param}')"
            race_date_filter = f"substr(date, 1, 10) >= date('now', '{date_param}')"
            duel_date_filter = f"substr(created_at, 1, 10) >= date('now', '{date_param}')"
            user_date_filter = f"substr(created_at, 1, 10) >= date('now', '{date_param}')"
        else:
            date_filter = None
            race_date_filter = None
            duel_date_filter = None
            user_date_filter = None

        # 1. Driver Base & Economy
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(money), 0), COALESCE(AVG(level), 1.0) FROM users WHERE guild_id = ?", (guild_id,))
        u_row = cursor.fetchone()
        total_racers = u_row[0] if u_row else 0
        total_wealth = u_row[1] if u_row else 0
        avg_level = round(u_row[2] if u_row else 1.0, 1)

        # New drivers registered in timeframe
        if user_date_filter:
            cursor.execute(f"SELECT COUNT(*) FROM users WHERE guild_id = ? AND {user_date_filter}", (guild_id,))
            new_row = cursor.fetchone()
            new_racers = new_row[0] if new_row else 0
        else:
            new_racers = total_racers

        # Today's daily activity snapshot from users table
        cursor.execute("""
            SELECT 
                COALESCE(SUM(daily_chat_credits), 0),
                COALESCE(SUM(daily_voice_credits), 0),
                COUNT(CASE WHEN daily_chat_credits > 0 THEN 1 END),
                COUNT(CASE WHEN daily_voice_credits > 0 THEN 1 END),
                COUNT(CASE WHEN daily_chat_credits > 0 OR daily_voice_credits > 0 THEN 1 END)
            FROM users WHERE guild_id = ?
        """, (guild_id,))
        fb_row = cursor.fetchone()
        fb_chat_credits = fb_row[0] if fb_row else 0
        fb_voice_credits = fb_row[1] if fb_row else 0
        fb_active_chatters = fb_row[2] if fb_row else 0
        fb_active_voice = fb_row[3] if fb_row else 0
        fb_active_members = fb_row[4] if fb_row else 0

        # 2. Text Chat & Voice Channel Activity from activity_logs
        chat_credits = 0
        voice_credits = 0
        active_chatters = 0
        active_voice_members = 0
        active_members_count = 0

        if date_filter:
            cursor.execute(f"""
                SELECT activity_type, COALESCE(SUM(amount), 0)
                FROM activity_logs
                WHERE guild_id = ? AND {date_filter}
                GROUP BY activity_type
            """, (guild_id,))
            for row in cursor.fetchall():
                if row[0] == 'chat':
                    chat_credits = row[1]
                elif row[0] == 'voice':
                    voice_credits = row[1]

            cursor.execute(f"""
                SELECT COUNT(DISTINCT user_id)
                FROM activity_logs
                WHERE guild_id = ? AND activity_type = 'chat' AND {date_filter}
            """, (guild_id,))
            ac_row = cursor.fetchone()
            active_chatters = ac_row[0] if ac_row else 0

            cursor.execute(f"""
                SELECT COUNT(DISTINCT user_id)
                FROM activity_logs
                WHERE guild_id = ? AND activity_type = 'voice' AND {date_filter}
            """, (guild_id,))
            av_row = cursor.fetchone()
            active_voice_members = av_row[0] if av_row else 0

            cursor.execute(f"""
                SELECT COUNT(DISTINCT user_id)
                FROM activity_logs
                WHERE guild_id = ? AND {date_filter}
            """, (guild_id,))
            act_row = cursor.fetchone()
            active_members_count = act_row[0] if act_row else 0
        else:
            cursor.execute("""
                SELECT activity_type, COALESCE(SUM(amount), 0)
                FROM activity_logs WHERE guild_id = ?
                GROUP BY activity_type
            """, (guild_id,))
            for row in cursor.fetchall():
                if row[0] == 'chat':
                    chat_credits = row[1]
                elif row[0] == 'voice':
                    voice_credits = row[1]

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM activity_logs WHERE guild_id = ? AND activity_type = 'chat'", (guild_id,))
            ac_row = cursor.fetchone()
            active_chatters = ac_row[0] if ac_row else 0

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM activity_logs WHERE guild_id = ? AND activity_type = 'voice'", (guild_id,))
            av_row = cursor.fetchone()
            active_voice_members = av_row[0] if av_row else 0

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM activity_logs WHERE guild_id = ?", (guild_id,))
            act_row = cursor.fetchone()
            active_members_count = act_row[0] if act_row else 0

        # REAL baseline integration: Use max of activity_logs or today's snapshot
        chat_credits = max(chat_credits, fb_chat_credits)
        voice_credits = max(voice_credits, fb_voice_credits)
        active_chatters = max(active_chatters, fb_active_chatters)
        active_voice_members = max(active_voice_members, fb_active_voice)
        active_members_count = max(active_members_count, fb_active_members)

        chat_per_msg = getattr(config, 'CHAT_CREDITS_PER_MSG', 25)
        est_chat_messages = chat_credits // chat_per_msg if chat_per_msg > 0 else 0

        vc_per_min = getattr(config, 'VOICE_CREDITS_PER_MIN', 15)
        est_vc_minutes = voice_credits // vc_per_min if vc_per_min > 0 else 0

        # 3. Grand Prix Events
        if race_date_filter:
            cursor.execute(f"SELECT COUNT(*), SUM(CASE WHEN status = 'Finished' THEN 1 ELSE 0 END) FROM races WHERE guild_id = ? AND {race_date_filter}", (guild_id,))
        else:
            cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'Finished' THEN 1 ELSE 0 END) FROM races WHERE guild_id = ?", (guild_id,))
        r_row = cursor.fetchone()
        total_gps = r_row[0] if r_row else 0
        completed_gps = r_row[1] if (r_row and r_row[1]) else 0

        if race_date_filter:
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(SUM(re.credits_won), 0)
                FROM race_entries re
                JOIN races r ON re.race_id = r.race_id
                WHERE r.guild_id = ? AND {race_date_filter}
            """, (guild_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(re.credits_won), 0)
                FROM race_entries re
                JOIN races r ON re.race_id = r.race_id
                WHERE r.guild_id = ?
            """, (guild_id,))
        re_row = cursor.fetchone()
        total_entries = re_row[0] if re_row else 0
        total_gp_payouts = re_row[1] if re_row else 0

        # 4. Head-to-Head Duels
        if duel_date_filter:
            cursor.execute(f"SELECT COUNT(*) FROM duel_history WHERE guild_id = ? AND {duel_date_filter}", (guild_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM duel_history WHERE guild_id = ?", (guild_id,))
        d_row = cursor.fetchone()
        total_duels = d_row[0] if d_row else 0

        # 5. Seasons & Rounds
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'Finished' THEN 1 ELSE 0 END) FROM seasons WHERE guild_id = ?", (guild_id,))
        s_row = cursor.fetchone()
        total_seasons = s_row[0] if s_row else 0
        completed_seasons = s_row[1] if (s_row and s_row[1]) else 0

        cursor.execute("SELECT COUNT(*) FROM season_calendar sc JOIN seasons s ON sc.season_id = s.season_id WHERE s.guild_id = ? AND sc.status = 'Finished'", (guild_id,))
        sc_row = cursor.fetchone()
        completed_season_rounds = sc_row[0] if sc_row else 0

        # 6. Inventory Items
        cursor.execute("""
            SELECT COUNT(*), SUM(CASE WHEN is_equipped = 1 THEN 1 ELSE 0 END)
            FROM user_inventory ui JOIN users u ON ui.user_id = u.user_id WHERE u.guild_id = ?
        """, (guild_id,))
        i_row = cursor.fetchone()
        total_inventory_items = i_row[0] if i_row else 0
        equipped_items = i_row[1] if (i_row and i_row[1]) else 0

        return {
            "timeframe": tf,
            "total_racers": total_racers,
            "new_racers": new_racers,
            "active_today": active_members_count,
            "active_chatters": active_chatters,
            "active_voice_members": active_voice_members,
            "total_wealth": total_wealth,
            "avg_level": avg_level,
            "chat_credits_today": chat_credits,
            "est_chat_messages_today": est_chat_messages,
            "voice_credits_today": voice_credits,
            "est_voice_minutes_today": est_vc_minutes,
            "total_gps": total_gps,
            "completed_gps": completed_gps,
            "total_entries": total_entries,
            "total_gp_payouts": total_gp_payouts,
            "total_duels": total_duels,
            "total_seasons": total_seasons,
            "completed_seasons": completed_seasons,
            "completed_season_rounds": completed_season_rounds,
            "total_inventory_items": total_inventory_items,
            "equipped_items": equipped_items,
        }
    except sqlite3.Error as e:
        print(f"Error in get_server_engagement_stats: {e}")
        return {
            "timeframe": timeframe, "total_racers": 0, "new_racers": 0, "active_today": 0,
            "active_chatters": 0, "active_voice_members": 0, "total_wealth": 0, "avg_level": 1.0,
            "chat_credits_today": 0, "est_chat_messages_today": 0, "voice_credits_today": 0, "est_voice_minutes_today": 0,
            "total_gps": 0, "completed_gps": 0, "total_entries": 0, "total_gp_payouts": 0, "total_duels": 0,
            "total_seasons": 0, "completed_seasons": 0, "completed_season_rounds": 0,
            "total_inventory_items": 0, "equipped_items": 0
        }
    finally:
        conn.close()



