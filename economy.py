import database
import config
import random
from datetime import date, datetime
from typing import Tuple

def claim_daily(user_id: int) -> Tuple[bool, str]:
    """
    Claim daily credit bonus of 500.
    Checks if already claimed today.
    Returns (success: bool, message: str)
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found. Please type `/start` first."
        
        today_str = date.today().isoformat()
        if row['last_daily_claim'] == today_str:
            return False, "You have already claimed your daily bonus today! Come back tomorrow."
        
        # Award credits and update last_daily_claim
        cursor.execute("""
            UPDATE users 
            SET money = money + ?, last_daily_claim = ? 
            WHERE user_id = ?
        """, (config.DAILY_BONUS, today_str, user_id))
        
        conn.commit()
        return True, f"You successfully claimed your daily bonus and received **{config.DAILY_BONUS}¢**!"
    except Exception as e:
        conn.rollback()
        return False, f"An error occurred: {str(e)}"
    finally:
        conn.close()

def perform_work(user_id: int) -> Tuple[bool, str]:
    """
    Perform a daily work job.
    Earns between 100 and 500 credits.
    Returns (success: bool, message: str)
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_work_claim FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "User profile not found. Please type `/start` first."
        
        today_str = date.today().isoformat()
        if row['last_work_claim'] == today_str:
            return False, "You have already worked today! You can work again tomorrow."
        
        # Choose a random job and pay
        jobs = [
            ("cleaned the pit lane", random.randint(100, 200)),
            ("assisted the tyre technician", random.randint(150, 300)),
            ("polished the team's wind tunnel", random.randint(200, 400)),
            ("sponsored a local go-karting event", random.randint(300, 500)),
            ("analyzed telemetry data for the race engineer", random.randint(250, 450)),
            ("promoted your team merchandise on social media", random.randint(100, 300))
        ]
        
        job_desc, pay = random.choice(jobs)
        
        # Award credits and update last_work_claim
        cursor.execute("""
            UPDATE users 
            SET money = money + ?, last_work_claim = ? 
            WHERE user_id = ?
        """, (pay, today_str, user_id))
        
        conn.commit()
        return True, f"You **{job_desc}** and earned **{pay}¢**!"
    except Exception as e:
        conn.rollback()
        return False, f"An error occurred: {str(e)}"
    finally:
        conn.close()
