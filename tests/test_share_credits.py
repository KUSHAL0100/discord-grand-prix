import pytest
import sqlite3
import database
import config

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_share.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_file))
    database.init_db()
    return db_file

def test_transfer_credits_success():
    guild_id = 999
    u1_disc = 1001
    u2_disc = 1002

    # Create user 1 and user 2 profiles
    database.create_user(u1_disc, guild_id, "Team Alpha", "IND")
    database.create_user(u2_disc, guild_id, "Team Beta", "NLD")

    # Give user 1 extra credits (starting money is 1500)
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET money = 5000 WHERE discord_id = ?", (u1_disc,))
    c.execute("UPDATE users SET money = 1000 WHERE discord_id = ?", (u2_disc,))
    conn.commit()
    conn.close()

    # Transfer 2,000 credits from u1 to u2
    success, msg, sender_new, recipient_new = database.transfer_credits(u1_disc, u2_disc, guild_id, 2000)
    assert success is True
    assert sender_new == 3000
    assert recipient_new == 3000
    assert "Credits Transferred!" in msg
    assert "Team Beta" in msg

def test_transfer_credits_insufficient_funds():
    guild_id = 999
    u1_disc = 1001
    u2_disc = 1002

    database.create_user(u1_disc, guild_id, "Team Alpha", "IND")
    database.create_user(u2_disc, guild_id, "Team Beta", "NLD")

    # Attempt to transfer 10,000 credits when balance is 1500
    success, msg, s_new, r_new = database.transfer_credits(u1_disc, u2_disc, guild_id, 10000)
    assert success is False
    assert "Insufficient balance" in msg

def test_transfer_credits_self_transfer():
    guild_id = 999
    u1_disc = 1001

    database.create_user(u1_disc, guild_id, "Team Alpha", "IND")

    success, msg, s_new, r_new = database.transfer_credits(u1_disc, u1_disc, guild_id, 500)
    assert success is False
    assert "cannot transfer credits to yourself" in msg

def test_transfer_credits_invalid_amount():
    guild_id = 999
    u1_disc = 1001
    u2_disc = 1002

    database.create_user(u1_disc, guild_id, "Team Alpha", "IND")
    database.create_user(u2_disc, guild_id, "Team Beta", "NLD")

    success, msg, s_new, r_new = database.transfer_credits(u1_disc, u2_disc, guild_id, 0)
    assert success is False
    assert "greater than 0" in msg
