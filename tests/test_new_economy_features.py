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
