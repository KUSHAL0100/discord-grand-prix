import pytest
import config
import database

def test_part_sell_ratio_config():
    assert config.PART_SELL_RATIO == 0.60
    assert config.AI_DUEL_WIN_CREDITS == 150
    assert config.AI_DUEL_LOSS_CREDITS == 40
    assert config.DUEL_WIN_CREDITS == 50
    assert config.DUEL_LOSS_CREDITS == 25
    assert config.FREE_RACE_WIN_XP == 5
    assert config.FREE_RACE_LOSS_XP == 0
    assert config.MIN_WAGER == 100
    assert config.MIN_XP_WAGER_THRESHOLD == 200

def test_sell_inventory_part():
    database.init_db()
    # Setup test profile
    discord_id = 88887777
    guild_id = 9999
    database.delete_user_profile(discord_id, guild_id)
    
    success, msg = database.create_user(discord_id, guild_id, "Apex Motorsport")
    assert success, f"create_user failed: {msg}"
    
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = prof['user_id']
    starting_money = prof['money']
    
    # Add an unequipped part (Level 3 Engine Rare)
    ok, msg, item_id = database.add_inventory_part(user_id, "engine", "V6 Turbo Core", "Rare", 3, 3)
    assert ok
    assert item_id > 0
    
    # Sell part
    sold, sell_msg, earned = database.sell_inventory_part(user_id, item_id)
    assert sold
    assert earned > 0
    
    # Verify balance updated
    prof_after = database.get_user_by_id(user_id)
    assert prof_after['money'] == starting_money + earned
    
    # Clean up
    database.delete_user_profile(discord_id, guild_id)

def test_weekly_bonus_claim():
    database.init_db()
    discord_id = 77776666
    guild_id = 9999
    database.delete_user_profile(discord_id, guild_id)
    
    success, msg = database.create_user(discord_id, guild_id, "Weekly Test Team")
    assert success
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = prof['user_id']
    starting_money = prof['money']
    
    # Claim weekly bonus
    succ, claim_msg = database.claim_weekly_bonus(user_id)
    assert succ
    assert "Weekly Bonus Claimed" in claim_msg
    assert "3,000" in claim_msg
    
    prof_after = database.get_user_by_id(user_id)
    assert prof_after['money'] == starting_money + 3000
    
    # Try claiming again in same week -> should fail with cooldown
    succ2, claim_msg2 = database.claim_weekly_bonus(user_id)
    assert not succ2
    assert "already claimed" in claim_msg2
    
    database.delete_user_profile(discord_id, guild_id)

def test_legendary_pit_crew_effective_stat():
    import race
    database.init_db()
    discord_id = 66665555
    guild_id = 9999
    database.delete_user_profile(discord_id, guild_id)
    
    success, msg = database.create_user(discord_id, guild_id, "Legendary Pit Team")
    assert success
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = prof['user_id']
    
    # Ensure clean inventory for test user_id
    conn = database.get_db_connection()
    conn.cursor().execute("DELETE FROM user_inventory WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    driver_data = {
        "user_id": user_id,
        "discord_id": discord_id,
        "team_name": "Legendary Pit Team",
        "engine": 1,
        "aerodynamics": 1,
        "tyres": 1,
        "ers": 1,
        "reliability": 1,
        "pit_crew": 1,
        "is_ai": False
    }
    driver = race.SimTeam(driver_data)
    # Default common pit crew level 1
    assert driver.effective_pit_crew == 1.0
    stop_time_common = max(1.8, round(3.5 - (driver.effective_pit_crew * 0.10), 2))
    assert stop_time_common == 3.40
    
    # Add and equip a Legendary Pit Crew part (Level 1)
    ok, msg, item_id = database.add_inventory_part(user_id, "pit_crew", "Laser Alignment Jacks", "Legendary", 1, 1)
    assert ok
    eq_ok, eq_msg = database.equip_inventory_part(user_id, item_id)
    assert eq_ok
    
    # Legendary Pit Crew has base level offset +15 and multiplier 1.25 -> (1 + 15) * 1.25 = 20.0
    assert driver.effective_pit_crew == 20.0
    stop_time_legendary = max(1.8, round(3.5 - (driver.effective_pit_crew * 0.10), 2))
    assert stop_time_legendary == 1.80
    assert stop_time_legendary < stop_time_common
    
    database.delete_user_profile(discord_id, guild_id)

