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
    # Test new user creation
    success = database.create_user(discord_id=12345, team_name="Test Racing", country="US")
    assert success is True
    
    # Try duplicate user
    success_duplicate = database.create_user(discord_id=12345, team_name="Other Name")
    assert success_duplicate is False
    
    # Verify profile contents
    profile = database.get_full_team_profile(12345)
    assert profile is not None
    assert profile["team_name"] == "Test Racing"
    assert profile["country"] == "US"
    assert profile["money"] == config.STARTING_MONEY
    assert profile["engine"] == 1
    assert profile["aerodynamics"] == 1

def test_balance_update():
    database.create_user(discord_id=12345, team_name="Test Racing")
    user = database.get_user_by_discord_id(12345)
    
    # Add money
    success = database.update_user_balance(user["user_id"], 1000)
    assert success is True
    updated_user = database.get_user_by_discord_id(12345)
    assert updated_user["money"] == config.STARTING_MONEY + 1000
    
    # Deduct money (success case)
    success = database.update_user_balance(user["user_id"], -500)
    assert success is True
    updated_user = database.get_user_by_discord_id(12345)
    assert updated_user["money"] == config.STARTING_MONEY + 500
    
    # Deduct money (failure case - negative balance)
    success = database.update_user_balance(user["user_id"], -10000)
    assert success is False
    updated_user = database.get_user_by_discord_id(12345)
    assert updated_user["money"] == config.STARTING_MONEY + 500  # unchanged

def test_part_upgrades():
    database.create_user(discord_id=12345, team_name="Test Racing")
    user = database.get_user_by_discord_id(12345)
    
    # Upgrade engine: level 1 -> 2 (costs 500)
    success, msg = database.upgrade_part(user["user_id"], "engine")
    assert success is True
    
    profile = database.get_full_team_profile(12345)
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
