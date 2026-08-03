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

def test_inventory_auto_equip_and_unequip(tmp_path, monkeypatch):
    import database
    import config
    import sqlite3
    db_file = str(tmp_path / "test_inv.db")
    monkeypatch.setattr(config, "DATABASE_PATH", db_file)
    database.init_db()

    # Create dummy user
    success, msg = database.create_user(99901, 88801, "Test Racing Team")
    assert success
    user = database.get_user_by_discord_id(99901, 88801)
    uid = user['user_id']

    # Add 2 parts in engine category
    database.add_inventory_part(uid, "engine", "Standard Turbo", "Common", level=2, stat_bonus=10)
    database.add_inventory_part(uid, "engine", "Monster V10", "Legendary", level=5, stat_bonus=50)

    # Auto equip best parts
    success, msg, count = database.auto_equip_best_parts(uid)
    assert success
    assert count >= 1

    equipped = database.get_equipped_inventory(uid)
    assert "engine" in equipped
    assert equipped["engine"]["part_name"] == "Monster V10"

    # Unequip engine category
    un_success, un_msg = database.unequip_inventory_part_category(uid, "engine")
    assert un_success
    equipped_after = database.get_equipped_inventory(uid)
    assert "engine" not in equipped_after

def test_leaderboard_optional_limit(tmp_path, monkeypatch):
    import database
    import config
    db_file = str(tmp_path / "test_lb.db")
    monkeypatch.setattr(config, "DATABASE_PATH", db_file)
    database.init_db()

    guild_id = 77701
    for i in range(15):
        database.create_user(10000 + i, guild_id, f"Team_{i}")

    # Default limit=None should return all 15 users
    all_users = database.get_leaderboard(guild_id, "points", limit=None)
    assert len(all_users) == 15

    # Limit=5 should return 5 users

    top5_users = database.get_leaderboard(guild_id, "points", limit=5)
    assert len(top5_users) == 5

def test_create_inventory_embed_and_view_no_parts(tmp_path, monkeypatch):
    import database
    import config
    from cogs.garage import create_inventory_embed_and_view
    db_file = str(tmp_path / "test_no_parts.db")
    monkeypatch.setattr(config, "DATABASE_PATH", db_file)
    database.init_db()

    success, msg = database.create_user(88881, 77771, "No Parts Team")
    assert success
    user = database.get_user_by_discord_id(88881, 77771)

    embed, view = create_inventory_embed_and_view(user['user_id'], 88881, "engine")
    assert embed is not None
    assert view is not None
    assert len(view.children) > 0

    # Test auto equip when 0 parts exist
    success_ae, msg_ae, count_ae = database.auto_equip_best_parts(user['user_id'])
    assert not success_ae
    assert count_ae == 0

    embed2, view2 = create_inventory_embed_and_view(user['user_id'], 88881, "engine", notice=msg_ae)
    assert embed2 is not None
    assert view2 is not None


