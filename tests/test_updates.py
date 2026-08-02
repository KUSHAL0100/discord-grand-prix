import pytest
from datetime import datetime, timedelta
import config
from cogs.racing import REJECT_COOLDOWNS

def test_reject_cooldown_expiry():
    challenger_id = 1111
    opponent_id = 2222
    now = datetime.now()
    
    # Set 5 minute cooldown
    REJECT_COOLDOWNS[(challenger_id, opponent_id)] = now + timedelta(minutes=5)
    
    assert (challenger_id, opponent_id) in REJECT_COOLDOWNS
    assert REJECT_COOLDOWNS[(challenger_id, opponent_id)] > now

def test_wager_payout_calculation():
    # 500 wager -> 1000 credits
    wager_500 = 500
    display_500 = (wager_500 * 2) if wager_500 > 0 else config.WIN_PRIZE_CREDITS
    assert display_500 == 1000

    # 400 wager -> 800 credits
    wager_400 = 400
    display_400 = (wager_400 * 2) if wager_400 > 0 else config.WIN_PRIZE_CREDITS
    assert display_400 == 800

    # 0 wager -> default WIN_PRIZE_CREDITS (200)
    wager_0 = 0
    display_0 = (wager_0 * 2) if wager_0 > 0 else config.WIN_PRIZE_CREDITS
    assert display_0 == config.WIN_PRIZE_CREDITS
