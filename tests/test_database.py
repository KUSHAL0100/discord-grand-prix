import pytest
import os
import sqlite3
import config
import database

# Override DB path for testing
config.DATABASE_PATH = "test_game.db"

@pytest.fixture(autouse=True)
def setup_teardown_db():
    """Setup and teardown a clean test database file before and after each test."""
    # Ensure starting clean
    if os.path.exists(config.DATABASE_PATH):
        try:
            os.remove(config.DATABASE_PATH)
        except PermissionError:
            pass
            
    database.init_db()
    yield
    
    # Cleanup
    if os.path.exists(config.DATABASE_PATH):
        # Close connection if any remains open by force-closing in WAL mode
        try:
            os.remove(config.DATABASE_PATH)
        except PermissionError:
            pass
        # Also clean up WAL journals
        for ext in ['-shm', '-wal']:
            if os.path.exists(config.DATABASE_PATH + ext):
                try:
                    os.remove(config.DATABASE_PATH + ext)
                except PermissionError:
                    pass

def test_user_creation():
    # Test new user creation (guild_id = 9999)
    success, msg = database.create_user(discord_id=12345, guild_id=9999, team_name="Test Racing", country="US")
    assert success is True
    
    # Try duplicate user in same guild
    success_duplicate, msg = database.create_user(discord_id=12345, guild_id=9999, team_name="Other Name")
    assert success_duplicate is False
    assert "already created a profile" in msg
    
    # Try duplicate team name in same guild (case-insensitive)
    success_dup_name, msg = database.create_user(discord_id=67890, guild_id=9999, team_name="TEST RACING")
    assert success_dup_name is False
    assert "already taken" in msg
    
    # Try invalid team name: too short
    success_short, msg = database.create_user(discord_id=67890, guild_id=9999, team_name="Go")
    assert success_short is False
    assert "at least 3 characters" in msg
    
    # Try invalid team name: no letters
    success_no_letters, msg = database.create_user(discord_id=67890, guild_id=9999, team_name="123456")
    assert success_no_letters is False
    assert "contain at least one letter" in msg
    
    # Try invalid team name: illegal symbols
    success_symbols, msg = database.create_user(discord_id=67890, guild_id=9999, team_name="Ferrari#$@")
    assert success_symbols is False
    assert "can only contain letters" in msg
    
    # Verify profile contents
    profile = database.get_full_team_profile(12345, guild_id=9999)
    assert profile is not None
    assert profile["team_name"] == "Test Racing"
    assert profile["country"] == "US"
    assert profile["money"] == config.STARTING_MONEY
    assert profile["engine"] == 1
    assert profile["aerodynamics"] == 1

def test_balance_update():
    database.create_user(discord_id=12345, guild_id=9999, team_name="Test Racing")
    user = database.get_user_by_discord_id(12345, guild_id=9999)
    
    # Add money
    success = database.update_user_balance(user["user_id"], 1000)
    assert success is True
    updated_user = database.get_user_by_discord_id(12345, guild_id=9999)
    assert updated_user["money"] == config.STARTING_MONEY + 1000
    
    # Deduct money (success case)
    success = database.update_user_balance(user["user_id"], -500)
    assert success is True
    updated_user = database.get_user_by_discord_id(12345, guild_id=9999)
    assert updated_user["money"] == config.STARTING_MONEY + 500
    
    # Deduct money (failure case - negative balance)
    success = database.update_user_balance(user["user_id"], -10000)
    assert success is False
    updated_user = database.get_user_by_discord_id(12345, guild_id=9999)
    assert updated_user["money"] == config.STARTING_MONEY + 500  # unchanged

def test_part_upgrades():
    database.create_user(discord_id=12345, guild_id=9999, team_name="Test Racing")
    user = database.get_user_by_discord_id(12345, guild_id=9999)
    
    # Upgrade engine: level 1 -> 2 (costs 500)
    success, msg = database.upgrade_part(user["user_id"], "engine")
    assert success is True
    
    profile = database.get_full_team_profile(12345, guild_id=9999)
    assert profile["engine"] == 2
    assert profile["money"] == config.STARTING_MONEY - 500
    
    # Artificially set money to 0 to test insufficient funds
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET money = 0 WHERE user_id = ?", (user["user_id"],))
    conn.commit()
    conn.close()
    
    # Attempting to upgrade again should fail due to lack of credits
    success, msg = database.upgrade_part(user["user_id"], "engine")
    assert success is False
    assert "Insufficient credits" in msg

def test_multi_guild_isolation():
    # User 12345 registers team "RedBull" in Guild A (1111)
    success, msg = database.create_user(discord_id=12345, guild_id=1111, team_name="RedBull")
    assert success is True
    
    # User 12345 registers team "Ferrari" in Guild B (2222)
    success, msg = database.create_user(discord_id=12345, guild_id=2222, team_name="Ferrari")
    assert success is True
    
    # Verify profiles are isolated
    prof_a = database.get_full_team_profile(12345, guild_id=1111)
    assert prof_a is not None
    assert prof_a["team_name"] == "RedBull"
    
    prof_b = database.get_full_team_profile(12345, guild_id=2222)
    assert prof_b is not None
    assert prof_b["team_name"] == "Ferrari"
    
    # Check that another user can register "RedBull" in Guild B (since it is only taken in Guild A)
    success, msg = database.create_user(discord_id=67890, guild_id=2222, team_name="RedBull")
    assert success is True
    
    # Check that trying to register "RedBull" in Guild A fails (already taken in Guild A)
    success, msg = database.create_user(discord_id=67890, guild_id=1111, team_name="RedBull")
    assert success is False
    assert "already taken" in msg

def test_personnel_training():
    success, msg = database.create_user(discord_id=12345, guild_id=9999, team_name="Test Racing", country="US")
    assert success is True
    prof = database.get_full_team_profile(12345, 9999)
    
    success_train, msg_train = database.train_personnel_skill(prof['user_id'], "driver", "pace", cost=400)
    assert success_train is True
    assert "trained" in msg_train
    
    prof_updated = database.get_full_team_profile(12345, 9999)
    assert prof_updated['money'] == 4600
    assert prof_updated['pace'] == prof['pace'] + 1
