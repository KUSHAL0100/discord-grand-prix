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

@pytest.mark.asyncio
async def test_start_duel_cleanup_on_exception():
    from cogs.racing import RaceChallengeView, is_user_in_race, set_user_in_race
    from unittest.mock import AsyncMock, MagicMock

    p1 = {"user_id": 8881, "discord_id": 111, "team_name": "Team A", "pref_strategy": "Balanced"}
    p2 = {"user_id": 8882, "discord_id": 222, "team_name": "Team B", "pref_strategy": "Balanced", "is_ai": True}
    
    view = RaceChallengeView(p1, p2, 5544)
    set_user_in_race(8881)
    set_user_in_race(8882)

    # Mock interaction that raises exception on thread creation
    mock_interaction = MagicMock()
    mock_response = AsyncMock()
    mock_interaction.response = mock_response
    mock_response.is_done = MagicMock(return_value=False)

    mock_msg = AsyncMock()
    mock_msg.create_thread.side_effect = Exception("Discord API error: Cannot create thread in thread")
    mock_response.original_response.return_value = mock_msg

    await view.start_duel(mock_interaction)

    # Assert that despite exception, user race locks were cleared and not deadlocked
    assert not is_user_in_race(8881)
    assert not is_user_in_race(8882)

def test_wager_minimum_and_xp_scaling():
    assert config.MIN_WAGER == 100
    assert config.MIN_XP_WAGER_THRESHOLD == 200
    assert config.FREE_RACE_WIN_XP == 5
    assert config.FREE_RACE_LOSS_XP == 0
    assert config.WIN_XP == 100
    assert config.LOSS_XP == 25


