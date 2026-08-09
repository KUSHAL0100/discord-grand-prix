import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import crates
import config

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = str(tmp_path / "test_pity.db")
    config.DATABASE_PATH = db_file
    database.init_db()
    yield

def test_champion_crate_guaranteed_part_drop():
    """Verify Champion crate always has 100% part drop rate."""
    discord_id = 888111
    guild_id = 999
    database.create_user(discord_id, guild_id, "Guaranteed Drop Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    database.update_user_balance(user_id, 100000)
    
    for _ in range(5):
        ok, msg, summary = crates.unbox_crate(user_id, "champion")
        assert ok is True
        assert summary["part_dropped"] is not None
        assert summary["part_dropped"]["rarity"] in ["Rare", "Epic", "Legendary"]

def test_rookie_crate_pity_system():
    """Verify Rookie crate pity: after setting pity to 3, 4th crate guarantees Uncommon or higher."""
    discord_id = 888222
    guild_id = 999
    database.create_user(discord_id, guild_id, "Rookie Pity Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    database.update_user_balance(user_id, 100000)
    
    # Manually set rookie pity to 3
    database.update_crate_pity(user_id, "rookie", reset=True)
    for _ in range(3):
        database.update_crate_pity(user_id, "rookie", reset=False)
        
    pity_data = database.get_crate_pity(user_id)
    assert pity_data["rookie"] == 3
    
    # Unbox crate with pity triggered
    ok, msg, summary = crates.unbox_crate(user_id, "rookie")
    assert ok is True
    assert summary["pity_triggered"] is True
    assert summary["part_dropped"]["rarity"] in ["Uncommon", "Rare"]
    assert summary["pity_counter"] == 0

def test_pro_crate_pity_system():
    """Verify Pro crate pity: after setting pity to 3, 4th crate guarantees Rare or higher."""
    discord_id = 888333
    guild_id = 999
    database.create_user(discord_id, guild_id, "Pro Pity Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    database.update_user_balance(user_id, 100000)
    
    # Force pity to 3
    database.update_crate_pity(user_id, "pro", reset=True)
    for _ in range(3):
        database.update_crate_pity(user_id, "pro", reset=False)
        
    ok, msg, summary = crates.unbox_crate(user_id, "pro")
    assert ok is True
    assert summary["pity_triggered"] is True
    assert summary["part_dropped"]["rarity"] in ["Rare", "Epic", "Legendary"]
    assert summary["pity_counter"] == 0

def test_champion_crate_pity_system():
    """Verify Champion crate pity: after setting pity to 3, 4th crate guarantees Epic or higher."""
    discord_id = 888444
    guild_id = 999
    database.create_user(discord_id, guild_id, "Champion Pity Team")
    user = database.get_user_by_discord_id(discord_id, guild_id)
    user_id = user['user_id']
    
    database.update_user_balance(user_id, 100000)
    
    # Force pity to 3
    database.update_crate_pity(user_id, "champion", reset=True)
    for _ in range(3):
        database.update_crate_pity(user_id, "champion", reset=False)
        
    ok, msg, summary = crates.unbox_crate(user_id, "champion")
    assert ok is True
    assert summary["pity_triggered"] is True
    assert summary["part_dropped"]["rarity"] in ["Epic", "Legendary"]
    assert summary["pity_counter"] == 0

def test_rarity_price_multipliers():
    """Verify updated rarity price and efficiency bonus multipliers."""
    assert config.RARITY_PRICE_MULTIPLIERS["Common"] == 1.00
    assert config.RARITY_PRICE_MULTIPLIERS["Uncommon"] == 1.10
    assert config.RARITY_PRICE_MULTIPLIERS["Rare"] == 1.20
    assert config.RARITY_PRICE_MULTIPLIERS["Epic"] == 1.30
    assert config.RARITY_PRICE_MULTIPLIERS["Legendary"] == 1.40
    
    assert crates.RARITY_PRICE_MULTIPLIERS["Uncommon"] == 1.10
    assert crates.RARITY_PRICE_MULTIPLIERS["Rare"] == 1.20
    assert crates.RARITY_PRICE_MULTIPLIERS["Epic"] == 1.30
    assert crates.RARITY_PRICE_MULTIPLIERS["Legendary"] == 1.40

    assert crates.RARITY_BONUS_MULTIPLIERS["Epic"] == 1.17
    assert crates.RARITY_BONUS_MULTIPLIERS["Legendary"] == 1.25
