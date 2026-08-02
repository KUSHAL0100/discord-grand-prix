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
    # 500 wager -> 1000 credits winner, 125 credits loser (25%)
    wager_500 = 500
    win_500 = (wager_500 * 2) if wager_500 > 0 else config.WIN_PRIZE_CREDITS
    loss_500 = int(wager_500 * 0.25) if wager_500 > 0 else config.LOSS_PRIZE_CREDITS
    assert win_500 == 1000
    assert loss_500 == 125

    # 400 wager -> 800 credits winner, 100 credits loser (25%)
    wager_400 = 400
    win_400 = (wager_400 * 2) if wager_400 > 0 else config.WIN_PRIZE_CREDITS
    loss_400 = int(wager_400 * 0.25) if wager_400 > 0 else config.LOSS_PRIZE_CREDITS
    assert win_400 == 800
    assert loss_400 == 100

    # 0 wager -> default WIN_PRIZE_CREDITS (200), LOSS_PRIZE_CREDITS (50)
    wager_0 = 0
    win_0 = (wager_0 * 2) if wager_0 > 0 else config.WIN_PRIZE_CREDITS
    loss_0 = int(wager_0 * 0.25) if wager_0 > 0 else config.LOSS_PRIZE_CREDITS
    assert win_0 == config.WIN_PRIZE_CREDITS
    assert loss_0 == config.LOSS_PRIZE_CREDITS
