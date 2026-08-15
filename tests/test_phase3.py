import pytest
import config
import database
import race
import crates

def test_tier_stat_scaling():
    assert config.get_tier_stat_multiplier(3) == 1.0     # Tier 1 (100%)
    assert config.get_tier_stat_multiplier(8) == 1.10    # Tier 2 (110%)
    assert config.get_tier_stat_multiplier(14) == 1.20   # Tier 3 (120%)
    assert config.get_tier_stat_multiplier(18) == 1.30   # Tier 4 (130%)

def test_inventory_and_equipment_system():
    discord_id = 777777
    guild_id = 11111
    database.create_user(discord_id, guild_id, "Inventory Test Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    # 1. Add parts to inventory
    success1, msg1, id1 = database.add_inventory_part(user_id, "engine", "Spec V6", "Common", 5, 5)
    success2, msg2, id2 = database.add_inventory_part(user_id, "engine", "Turbo V10", "Legendary", 15, 15)
    assert success1 and success2
    
    # 2. Equip Legendary part
    equip_ok, equip_msg = database.equip_inventory_part(user_id, id2)
    assert equip_ok is True
    
    equipped = database.get_equipped_inventory(user_id)
    assert "engine" in equipped
    assert equipped["engine"]["item_id"] == id2
    assert equipped["engine"]["rarity"] == "Legendary"

def test_booster_inventory_cap():
    discord_id = 888888
    guild_id = 11111
    database.create_user(discord_id, guild_id, "Booster Test Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    # Clean up
    conn = database.get_db_connection()
    conn.execute("DELETE FROM user_boosters WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # 1. Add 1st booster
    ok1, msg1 = database.add_user_booster(user_id, "quali", "Tyre Blanket Warmer")
    assert ok1 is True
    
    # 2. Add 2nd booster
    ok2, msg2 = database.add_user_booster(user_id, "race", "ERS High-Flow Injector")
    assert ok2 is True
    
    # 3. Add 3rd booster -> SHOULD FAIL (Max 2 Cap)
    ok3, msg3 = database.add_user_booster(user_id, "reliability", "Heavy Duty Radiator")
    assert ok3 is False
    assert "Cap Reached" in msg3

def test_track_practice_daily_limit_and_cap():
    discord_id = 9999991
    guild_id = 11111
    database.create_user(discord_id, guild_id, "Practice Test Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    track = "Monaco (Monte Carlo)"
    
    database.update_user_balance(user_id, 10000)
    
    # 1. Practice 3 times (allowed)
    for i in range(3):
        ok, msg, bonus = database.record_track_practice(user_id, track)
        assert ok is True
        
    # 2. Practice 4th time -> SHOULD FAIL (3 per day limit)
    ok4, msg4, bonus4 = database.record_track_practice(user_id, track)
    assert ok4 is False
    assert "Limit Reached" in msg4

def test_crate_unboxing():
    # Setup test user in database
    discord_id = 999999
    guild_id = 11111
    database.create_user(discord_id, guild_id, "Crate Tester Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    # Give enough credits
    database.update_user_balance(user_id, 10000)
    
    # Unbox Rookie Crate
    ok, msg, summary = crates.unbox_crate(user_id, "rookie")
    assert ok is True
    assert summary["gold_reward"] >= 25
    assert summary["cost"] == 500

def test_rarity_scaling_realism():
    discord_id = 444555
    guild_id = 11111
    database.create_user(discord_id, guild_id, "Rarity Realism Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    # 1. Equip Level 3 Common engine
    ok_c, msg_c, id_c = database.add_inventory_part(user_id, "engine", "Common Spec V6", "Common", 3, 3)
    database.equip_inventory_part(user_id, id_c)
    
    sim_common = race.SimTeam({
        "user_id": user_id, "team_name": "Common Car", "discord_id": discord_id,
        "engine": 3, "aerodynamics": 1, "tyres": 1, "ers": 1, "reliability": 1
    })
    power_common = sim_common.calculate_base_car_power("Monza")
    
    # 2. Equip Level 3 Rare engine
    ok_r, msg_r, id_r = database.add_inventory_part(user_id, "engine", "Rare Turbo V8", "Rare", 3, 3)
    database.equip_inventory_part(user_id, id_r)
    
    sim_rare = race.SimTeam({
        "user_id": user_id, "team_name": "Rare Car", "discord_id": discord_id,
        "engine": 3, "aerodynamics": 1, "tyres": 1, "ers": 1, "reliability": 1
    })
    power_rare = sim_rare.calculate_base_car_power("Monza")
    
    # Verify Level 3 Rare engine power > Level 3 Common engine power
    assert power_rare > power_common, f"Expected Level 3 Rare ({power_rare}) > Level 3 Common ({power_common})"

def test_rarity_upgrade_costs():
    """Verify get_upgrade_cost scales properly based on part rarity."""
    base_engine_lvl2 = config.ENGINE_UPGRADE_COSTS[2] # 200
    
    cost_common = config.get_upgrade_cost("engine", 2, "Common")
    cost_uncommon = config.get_upgrade_cost("engine", 2, "Uncommon")
    cost_rare = config.get_upgrade_cost("engine", 2, "Rare")
    cost_epic = config.get_upgrade_cost("engine", 2, "Epic")
    cost_legendary = config.get_upgrade_cost("engine", 2, "Legendary")
    
    assert cost_common == int(200 * 1.0 * 1.00)     # 200
    assert cost_uncommon == int(200 * 1.0 * 1.10)   # 220
    assert cost_rare == int(200 * 1.0 * 1.20)       # 240
    assert cost_epic == int(200 * 1.0 * 1.30)       # 260
    assert cost_legendary == int(200 * 1.0 * 1.40)  # 280

    # Ensure strictly increasing cost by rarity
    assert cost_common < cost_uncommon < cost_rare < cost_epic < cost_legendary

