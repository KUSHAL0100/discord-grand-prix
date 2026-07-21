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

    # --- Run schema migrations for existing databases ---
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN pit_strategy_json TEXT DEFAULT '{\"pace\":\"Balanced\", \"start_tyre\":\"Medium\", \"stops\":[]}'")
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN current_q_tyre TEXT DEFAULT 'Soft'")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q1_time REAL")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q2_time REAL")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE race_entries ADD COLUMN quali_q3_time REAL")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE races ADD COLUMN laps INTEGER DEFAULT 15")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

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

def create_gp_race(guild_id: int, name: str, track: str, laps: int) -> Tuple[bool, str]:
    """Create a new Grand Prix race in Created status for a specific guild."""
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
                forecast = f"Wet start. Heavy rain expected for the first {wet_laps} laps, clearing up to Sunny later."
                for i in range(1, laps + 1):
                    timeline.append("Rain" if i <= wet_laps else "Sunny")
            elif sub_choice == "ends_wet":
                wet_start = random.randint(max(2, int(laps * 0.35)), max(3, int(laps * 0.55)))
                forecast = f"Sunny start, with rain clouds moving in around Lap {wet_start} and continuing until the end."
                for i in range(1, laps + 1):
                    timeline.append("Rain" if i >= wet_start else "Sunny")
            else: # wet_spell
                # wet most of the race, but clears up in the middle
                dry_start = random.randint(max(2, int(laps * 0.3)), max(3, int(laps * 0.5)))
                dry_duration = random.randint(3, 6)
                forecast = f"Rainy conditions from the start, with a brief dry sunny window between Lap {dry_start} and {dry_start + dry_duration - 1}."
                for i in range(1, laps + 1):
                    if dry_start <= i < dry_start + dry_duration:
                        timeline.append("Sunny")
                    else:
                        timeline.append("Rain")
                        
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
        cursor.execute(
            "INSERT INTO races (guild_id, name, date, track, weather, status, laps) VALUES (?, ?, ?, ?, ?, 'Created', ?)",
            (guild_id, name, today_str, track, weather_json, laps)
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

