import sys
import os
import sqlite3
import database
import config

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def fix_and_restore():
    # Allow passing database path argument, e.g. python restore_rahi_and_miggaruns.py path/to/game.db
    db_path = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else config.DATABASE_PATH
    print(f"Restoring exact pre-3PM stats on database at '{db_path}'...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Rahi profile data (discord_id 880355982872555590)
    rahi_discord_id = 880355982872555590
    cursor.execute("""
        UPDATE users
        SET money = 838, xp = 2185, level = 3, wins = 28, losses = 23
        WHERE discord_id = ?
    """, (rahi_discord_id,))

    cursor.execute("SELECT user_id FROM users WHERE discord_id = ?", (rahi_discord_id,))
    r_user = cursor.fetchone()
    if r_user:
        r_uid = r_user['user_id']
        cursor.execute("""
            UPDATE garage
            SET engine = 9, aerodynamics = 7, tyres = 6, ers = 6, reliability = 7, pit_crew = 6,
                damage_engine = 0, damage_tyres = 0, damage_total = 0
            WHERE user_id = ?
        """, (r_uid,))
        cursor.execute("""
            UPDATE drivers
            SET pace = 57, qual = 57, wet_skill = 53, consistency = 55, aggression = 54, overtaking = 54
            WHERE user_id = ?
        """, (r_uid,))
        print(f"[+] Restored Rahi (ID {rahi_discord_id}): Level 3, 2,185 XP, 838¢, Engine Lvl 9, Aero Lvl 7, Driver stats 57/57/53/55/54/54")

    # MIGGARUNS profile data (discord_id 973109717603856415)
    miggaruns_discord_id = 973109717603856415
    cursor.execute("""
        UPDATE users
        SET money = 591, xp = 1980, level = 2, wins = 29, losses = 13
        WHERE discord_id = ?
    """, (miggaruns_discord_id,))

    cursor.execute("SELECT user_id FROM users WHERE discord_id = ?", (miggaruns_discord_id,))
    m_user = cursor.fetchone()
    if m_user:
        m_uid = m_user['user_id']
        cursor.execute("""
            UPDATE garage
            SET engine = 6, aerodynamics = 4, tyres = 4, ers = 3, reliability = 5, pit_crew = 4,
                damage_engine = 0, damage_tyres = 0, damage_total = 0
            WHERE user_id = ?
        """, (m_uid,))
        cursor.execute("""
            UPDATE drivers
            SET pace = 62, qual = 55, wet_skill = 50, consistency = 53, aggression = 60, overtaking = 60
            WHERE user_id = ?
        """, (m_uid,))
        print(f"[+] Restored MIGGARUNS (ID {miggaruns_discord_id}): Level 2, 1,980 XP, 591¢, Engine Lvl 6, Aero Lvl 4, Driver stats 62/55/50/53/60/60")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_and_restore()
