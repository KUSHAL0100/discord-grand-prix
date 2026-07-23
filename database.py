import sqlite3
import os
import random
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
import config

def get_db_connection():
    """Establish a connection to the SQLite database and return it."""
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
        last_credits_reset TEXT DEFAULT (date('now')),
        last_daily_claim TEXT,
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

    # --- Create performance B-Tree indexes for lightning-fast lookups ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_discord_guild ON users(discord_id, guild_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user_cat ON user_inventory(user_id, category, is_equipped);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_boosters_user ON user_boosters(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_guild_status ON races(guild_id, status);")

    # --- Run schema migrations for existing databases ---
    def get_existing_columns(table_name):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    # Users table migrations
    users_cols = get_existing_columns("users")
    if "pit_strategy_json" not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN pit_strategy_json TEXT DEFAULT '{\"pace\":\"Balanced\", \"start_tyre\":\"Medium\", \"stops\":[]}'")

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

        # Insert user
        cursor.execute(
            "INSERT INTO users (discord_id, guild_id, team_name, country) VALUES (?, ?, ?, ?)",
            (discord_id, guild_id, team_name_clean, country)
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
        
        # Deduct money and update skill
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
        cursor.execute(f"UPDATE {table_name} SET {skill_name} = ? WHERE user_id = ?", (new_val, user_id))
        
        conn.commit()
        return True, f"Successfully trained **{skill_name.replace('_', ' ').capitalize()}** from `{current_val}` to `{new_val}`! Spent {cost}¢."
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
        cursor.execute("""
            UPDATE users 
            SET pref_strategy = ?, pref_tyres = ?, pref_pit_stops = ?
            WHERE user_id = ?
        """, (pace, tyres, pit_stops, user_id))
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

def add_user_xp(user_id: int, xp_to_add: int) -> Tuple[int, int, bool]:
    """
    Add XP to user and handle leveling up.
    Returns (new_xp, new_level, leveled_up: bool)
    XP curve: level_threshold = level * 1000
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return (0, 0, False)
        
        current_xp = row['xp']
        current_level = row['level']
        
        new_xp = current_xp + xp_to_add
        new_level = current_level
        leveled_up = False
        
        # Simple progression curve: level * 1000 XP needed to level up
        while new_xp >= new_level * 1000:
            new_xp -= new_level * 1000
            new_level += 1
            leveled_up = True
            # Level up reward: new_level * 500¢
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (new_level * 500, user_id))
            
        cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
        conn.commit()
        return (new_xp, new_level, leveled_up)
    except sqlite3.Error:
        conn.rollback()
        return (0, 0, False)
    finally:
        conn.close()

# ----------------- Daily resets & limit trackers -----------------

def reset_daily_limits_if_new_day(user_id: int) -> None:
    """Reset daily chat and voice credits if the day has changed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_credits_reset FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return
        
        today_str = date.today().isoformat()
        if row['last_credits_reset'] != today_str:
            cursor.execute("""
                UPDATE users 
                SET daily_chat_credits = 0, daily_voice_credits = 0, last_credits_reset = ? 
                WHERE user_id = ?
            """, (today_str, user_id))
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
            SELECT money, daily_chat_credits, daily_voice_credits 
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
        
        conn.commit()
        return credits_awarded
    except sqlite3.Error:
        conn.rollback()
        return 0
    finally:
        conn.close()

# ----------------- Upgrade and Garage Helpers -----------------

def upgrade_part(user_id: int, part_name: str) -> Tuple[bool, str]:
    """
    Upgrade a car part by one level.
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
        
        # Get current part level
        cursor.execute(f"SELECT {part_name} FROM garage WHERE user_id = ?", (user_id,))
        garage_row = cursor.fetchone()
        if not garage_row:
            return False, "Garage record not found."
            
        current_level = garage_row[part_name]
        if current_level >= config.MAX_STAT_LEVEL:
            return False, f"Your {part_name.capitalize()} is already at max level ({config.MAX_STAT_LEVEL})."
            
        target_level = current_level + 1
        cost = config.get_upgrade_cost(part_name, target_level)
        
        if current_money < cost:
            return False, f"Insufficient credits! Upgrading {part_name.capitalize()} to Level {target_level} costs {cost}¢ (You have {current_money}¢)."
            
        # Deduct money and update garage level
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
        cursor.execute(f"UPDATE garage SET {part_name} = ? WHERE user_id = ?", (target_level, user_id))
        
        conn.commit()
        return True, f"Successfully upgraded {part_name.capitalize()} to Level {target_level} for {cost}¢!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def repair_part(user_id: int, part_name: str) -> Tuple[bool, str]:
    """
    Repair a car part. Sets damage to 0 and charges credits.
    Supported parts: 'engine', 'tyres' (from garage damage columns).
    Returns (success: bool, status_message: str)
    """
    damage_col = f"damage_{part_name}"
    if part_name not in ['engine', 'tyres']:
        return False, "Invalid part for repair. You can only repair 'engine' or 'tyres'."
        
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
        cursor.execute(f"SELECT {damage_col} FROM garage WHERE user_id = ?", (user_id,))
        garage_row = cursor.fetchone()
        if not garage_row:
            return False, "Garage not found."
        
        damage_val = garage_row[damage_col]
        if damage_val <= 0:
            return False, f"Your {part_name} is in perfect condition (0% damage)."
            
        cost = damage_val * config.REPAIR_COST_PER_PCT
        if current_money < cost:
            return False, f"Insufficient credits! Repairing your {part_name} costs {cost}¢ (You have {current_money}¢)."
            
        # Deduct money, reset damage
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (cost, user_id))
        cursor.execute(f"UPDATE garage SET {damage_col} = 0 WHERE user_id = ?", (user_id,))
        
        # Recalculate total damage
        cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (user_id,))
        damages = cursor.fetchone()
        new_total = damages['damage_engine'] + damages['damage_tyres']
        cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (new_total, user_id))
        
        conn.commit()
        return True, f"Repaired your {part_name}! Cost: {cost}¢. Damage is now 0%."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

# ----------------- Leaderboard -----------------

def get_leaderboard(guild_id: int, by_type: str = 'points', limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get leaderboard top lists filtered by guild_id.
    by_type can be 'points' (sum of race entries points) or 'money' (user's credit balance).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if by_type == 'money':
        cursor.execute("""
            SELECT team_name, money as score, level
            FROM users
            WHERE guild_id = ?
            ORDER BY money DESC
            LIMIT ?
        """, (guild_id, limit))
    else:  # Default to championship points
        cursor.execute("""
            SELECT u.team_name, COALESCE(SUM(re.points_earned), 0) as score, u.level
            FROM users u
            LEFT JOIN race_entries re ON u.user_id = re.user_id
            WHERE u.guild_id = ?
            GROUP BY u.user_id
            ORDER BY score DESC
            LIMIT ?
        """, (guild_id, limit))
        
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
    """Cancel the active Grand Prix and refund entry fees for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT race_id FROM races WHERE status != 'Finished' AND status != 'Cancelled' AND guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        if not row:
            return False, "There is no active Grand Prix to cancel on this server."
            
        race_id = row['race_id']
        
        # Refund entries
        cursor.execute("SELECT user_id FROM race_entries WHERE race_id = ?", (race_id,))
        entries = cursor.fetchall()
        
        for entry in entries:
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (config.GP_ENTRY_FEE, entry['user_id']))
            
        # Update race status
        cursor.execute("UPDATE races SET status = 'Cancelled' WHERE race_id = ?", (race_id,))
        conn.commit()
        return True, f"Cancelled Grand Prix and refunded {len(entries)} players their entry fee of {config.GP_ENTRY_FEE}¢."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def register_gp_entry(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Register a user for the upcoming Grand Prix in a specific guild. Deducts entry fee."""
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
        cursor.execute("SELECT user_id, money FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        user_row = cursor.fetchone()
        if not user_row:
            return False, "You need to create a profile first! Use `/start`."
            
        user_id = user_row['user_id']
        money = user_row['money']
        
        # Check if already registered
        cursor.execute("SELECT entry_id FROM race_entries WHERE race_id = ? AND user_id = ?", (race_id, user_id))
        if cursor.fetchone():
            return False, "You are already registered for this Grand Prix."
            
        # Check money
        if money < config.GP_ENTRY_FEE:
            return False, f"Insufficient funds! Entry fee is {config.GP_ENTRY_FEE}¢ (You have {money}¢)."
            
        # Deduct entry fee and insert entry record
        cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (config.GP_ENTRY_FEE, user_id))
        cursor.execute("INSERT INTO race_entries (race_id, user_id) VALUES (?, ?)", (race_id, user_id))
        
        conn.commit()
        return True, f"You successfully registered for the Grand Prix! Paid {config.GP_ENTRY_FEE}¢ entry fee."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def unregister_gp_entry(discord_id: int, guild_id: int) -> Tuple[bool, str]:
    """Unregister a user from the upcoming Grand Prix in a specific guild. Refunds entry fee."""
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
            
        # Refund entry fee and delete entry record
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (config.GP_ENTRY_FEE, user_id))
        cursor.execute("DELETE FROM race_entries WHERE race_id = ? AND user_id = ?", (race_id, user_id))
        
        conn.commit()
        return True, f"You successfully left the Grand Prix and have been refunded your {config.GP_ENTRY_FEE}¢ entry fee."
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
               re.current_q_tyre, re.quali_q1_time, re.quali_q2_time, re.quali_q3_time,
               u.team_name, u.discord_id, u.level, u.pref_strategy, u.pref_tyres, u.pref_pit_stops, u.pit_strategy_json,
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
        # Update race winner and status
        cursor.execute(
            "UPDATE races SET status = 'Finished', winner_id = ? WHERE race_id = ?",
            (winner_user_id, race_id)
        )
        
        # Save results for each entrant
        for res in results:
            cursor.execute("""
                UPDATE race_entries 
                SET finish_position = ?, points_earned = ?, credits_won = ?, dnf = ?
                WHERE race_id = ? AND user_id = ?
            """, (res["finish_position"], res["points_earned"], res["credits_won"], res["dnf"], race_id, res["user_id"]))
            
            # Award credits to user profile
            cursor.execute(
                "UPDATE users SET money = money + ? WHERE user_id = ?",
                (res["credits_won"], res["user_id"])
            )
            
            # Record wins/losses and add experience/XP
            if res["finish_position"] == 1:
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (res["user_id"],))
            else:
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (res["user_id"],))
                
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
                """, (stat_boost, stat_boost, stat_boost, stat_boost, stat_boost, stat_boost, res["user_id"]))

            # Add XP using add_user_xp logic (internal transaction, so we update manually here)
            cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (res["user_id"],))
            user_row = cursor.fetchone()
            if user_row:
                new_xp = user_row['xp'] + xp_to_add
                new_level = user_row['level']
                while new_xp >= new_level * 1000:
                    new_xp -= new_level * 1000
                    new_level += 1
                    # Level up reward: new_level * 500¢
                    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (new_level * 500, res["user_id"]))
                cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, res["user_id"]))
                
            # Apply race damage to garage
            # If DNF, damage is high. Otherwise moderate.
            if res["dnf"]:
                dmg_eng = random.randint(15, 30)
                dmg_tyr = random.randint(30, 60)
            else:
                dmg_eng = random.randint(3, 10)
                dmg_tyr = random.randint(10, 25)
                
            cursor.execute("""
                UPDATE garage 
                SET damage_engine = MIN(100, damage_engine + ?),
                    damage_tyres = MIN(100, damage_tyres + ?)
                WHERE user_id = ?
            """, (dmg_eng, dmg_tyr, res["user_id"]))
            
            # Recalculate damage_total
            cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (res["user_id"],))
            damages = cursor.fetchone()
            new_total = damages['damage_engine'] + damages['damage_tyres']
            cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (new_total, res["user_id"]))
        
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
    """Equip a part from inventory onto active car setup."""
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
        
        # Update garage table active level
        valid_categories = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
        if category in valid_categories:
            cursor.execute(f"UPDATE garage SET {category} = MAX({category}, ?) WHERE user_id = ?", (level, user_id))
            
        conn.commit()
        return True, f"✅ Successfully equipped **{part['rarity']} {part['part_name']}** (Level {level})!"
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_equipped_inventory(user_id_or_discord_id: int) -> Dict[str, Dict[str, Any]]:
    """Return dictionary of currently equipped parts per category."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ? OR discord_id = ?", (user_id_or_discord_id, user_id_or_discord_id))
    rows = cursor.fetchall()
    user_ids = [r['user_id'] for r in rows] if rows else [user_id_or_discord_id]
    
    placeholders = ",".join(["?"] * len(user_ids))
    cursor.execute(f"SELECT * FROM user_inventory WHERE user_id IN ({placeholders}) AND is_equipped = 1", user_ids)
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
        # Check user balance for practice fee (500¢)
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
            
        # Deduct practice fee (500¢)
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

def record_race_result(winner_user_id: int, loser_user_id: int, guild_id: int) -> bool:
    """Record 1v1 duel race results: update wins/losses, award XP and prize credits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Update winner: +1 win, +WIN_XP, +WIN_PRIZE_CREDITS
        cursor.execute("""
            UPDATE users
            SET wins = wins + 1,
                xp = xp + ?,
                money = money + ?
            WHERE user_id = ?
        """, (config.WIN_XP, config.WIN_PRIZE_CREDITS, winner_user_id))
        
        # Update loser: +1 loss, +LOSS_XP, +LOSS_PRIZE_CREDITS
        cursor.execute("""
            UPDATE users
            SET losses = losses + 1,
                xp = xp + ?,
                money = money + ?
            WHERE user_id = ?
        """, (config.LOSS_XP, config.LOSS_PRIZE_CREDITS, loser_user_id))

        # Level up checks
        for uid in [winner_user_id, loser_user_id]:
            cursor.execute("SELECT level, xp FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if row:
                needed_xp = row['level'] * 1000
                if row['xp'] >= needed_xp:
                    cursor.execute("UPDATE users SET level = level + 1 WHERE user_id = ?", (uid,))

        conn.commit()
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
    """Delete a user's profile and all associated data on a guild (Admin reset)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, team_name FROM users WHERE discord_id = ? AND guild_id = ?", (discord_id, guild_id))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found on this server."
            
        team_name = row['team_name']
        cursor.execute("DELETE FROM users WHERE user_id = ?", (row['user_id'],))
        conn.commit()
        return True, f"Successfully reset and deleted profile for team **{team_name}**."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
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

def claim_daily_bonus(user_id: int) -> Tuple[bool, str]:
    """Claim daily credit bonus (500 credits)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        today_str = datetime.now().date().isoformat()
        
        if row and row['last_daily_claim'] == today_str:
            return False, "⏳ You have already claimed your daily bonus today! Come back tomorrow."
            
        reward = 500
        cursor.execute("UPDATE users SET money = money + ?, last_daily_claim = ? WHERE user_id = ?", (reward, today_str, user_id))
        conn.commit()
        return True, f"🎉 **Daily Bonus Claimed!** Received **+{reward:,} credits**!"
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
        today_str = datetime.now().date().isoformat()
        
        if row and row['last_work_claim'] == today_str:
            return False, "⏳ You have already completed your team work today! Come back tomorrow."
            
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
