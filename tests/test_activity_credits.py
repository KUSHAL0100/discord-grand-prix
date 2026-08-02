import pytest
from datetime import datetime, timedelta
import config
import database

def test_chat_cooldown_logic():
    """Verify the 60-second cooldown calculation for chat credits."""
    chat_cooldowns = {}
    user_id = 99999
    
    now = datetime.now()
    
    # 1. First message should be eligible (last_awarded is None)
    last_awarded = chat_cooldowns.get(user_id)
    is_eligible = (last_awarded is None or (now - last_awarded).total_seconds() >= 60)
    assert is_eligible is True
    
    # Award and set timestamp
    chat_cooldowns[user_id] = now
    
    # 2. Second message 30 seconds later -> should NOT be eligible
    t_30s = now + timedelta(seconds=30)
    last_awarded = chat_cooldowns.get(user_id)
    is_eligible = (last_awarded is None or (t_30s - last_awarded).total_seconds() >= 60)
    assert is_eligible is False
    
    # 3. Third message 65 seconds later -> SHOULD be eligible again
    t_65s = now + timedelta(seconds=65)
    last_awarded = chat_cooldowns.get(user_id)
    is_eligible = (last_awarded is None or (t_65s - last_awarded).total_seconds() >= 60)
    assert is_eligible is True

def test_voice_duration_calculation():
    """Verify full elapsed minutes calculation for voice credits (15 credits / min)."""
    start_time = datetime.now()
    
    # 45 seconds -> 0 minutes (not enough for 1 min credit)
    t_45s = start_time + timedelta(seconds=45)
    mins = int((t_45s - start_time).total_seconds() // 60)
    assert mins == 0
    
    # 65 seconds -> 1 minute (awards 1 * 15 = 15 credits)
    t_65s = start_time + timedelta(seconds=65)
    mins = int((t_65s - start_time).total_seconds() // 60)
    assert mins == 1
    assert mins * config.VOICE_CREDITS_PER_MIN == 15
    
    # 185 seconds -> 3 minutes (awards 3 * 15 = 45 credits)
    t_185s = start_time + timedelta(seconds=185)
    mins = int((t_185s - start_time).total_seconds() // 60)
    assert mins == 3
    assert mins * config.VOICE_CREDITS_PER_MIN == 45
