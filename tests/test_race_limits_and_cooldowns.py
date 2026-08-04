import pytest
import config
import database
from cogs.racing import is_user_in_race, set_user_in_race, clear_user_in_race

def test_free_limits_config():
    assert config.FREE_DUEL_DAILY_LIMIT == 5
    assert config.FREE_RACE_DAILY_LIMIT == 5

def test_active_user_race_locks():
    uid = 777123
    assert not is_user_in_race(uid)
    
    set_user_in_race(uid)
    assert is_user_in_race(uid)
    
    clear_user_in_race(uid)
    assert not is_user_in_race(uid)

def test_daily_free_duel_limit():
    database.init_db()
    discord_id = 99112233
    guild_id = 5544
    database.delete_user_profile(discord_id, guild_id)
    
    ok, _ = database.create_user(discord_id, guild_id, "Free Duel Team")
    assert ok
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    uid = prof['user_id']
    
    # 5 allowed free duels
    for i in range(5):
        can_duel, _ = database.can_user_free_duel(uid)
        assert can_duel, f"Should allow free duel {i+1}"
        database.increment_daily_free_duels(uid)
        
    # 6th attempt should be blocked
    can_duel, msg = database.can_user_free_duel(uid)
    assert not can_duel
    assert "limit of 5 free AI duels" in msg or "daily limit" in msg
    
    database.delete_user_profile(discord_id, guild_id)

def test_daily_free_race_limit():
    database.init_db()
    discord_id = 99112244
    guild_id = 5544
    database.delete_user_profile(discord_id, guild_id)
    
    ok, _ = database.create_user(discord_id, guild_id, "Free Race Team")
    assert ok
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    uid = prof['user_id']
    
    # 5 allowed free 1v1 races
    for i in range(5):
        can_race, _ = database.can_user_free_race(uid)
        assert can_race, f"Should allow free race {i+1}"
        database.increment_daily_free_races(uid)
        
    # 6th attempt should be blocked
    can_race, msg = database.can_user_free_race(uid)
    assert not can_race
    assert "limit of 5 free 1v1 races" in msg or "daily limit" in msg
    
    database.delete_user_profile(discord_id, guild_id)

def test_daily_and_work_cooldown_formatting():
    database.init_db()
    discord_id = 99112255
    guild_id = 5544
    database.delete_user_profile(discord_id, guild_id)
    
    ok, _ = database.create_user(discord_id, guild_id, "Cooldown Test Team")
    assert ok
    prof = database.get_user_by_discord_id(discord_id, guild_id)
    uid = prof['user_id']
    
    # Claim daily bonus
    succ, msg1 = database.claim_daily_bonus(uid)
    assert succ
    
    # Claim daily bonus again -> should show cooldown time
    succ, msg2 = database.claim_daily_bonus(uid)
    assert not succ
    assert "Cooldown:" in msg2
    assert "<t:" in msg2
    
    # Claim work rewards
    succ, wmsg1 = database.claim_work_rewards(uid)
    assert succ
    
    # Claim work rewards again -> should show cooldown time
    succ, wmsg2 = database.claim_work_rewards(uid)
    assert not succ
    assert "Cooldown:" in wmsg2
    assert "<t:" in wmsg2
    
    database.delete_user_profile(discord_id, guild_id)
