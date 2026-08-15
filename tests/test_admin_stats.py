import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock
import os
import discord

import config
import database
from cogs.admin import AdminCog

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = str(tmp_path / "test_game.db")
    config.DATABASE_PATH = db_file
    database.init_db()
    yield
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass

def test_get_server_engagement_stats_empty():
    guild_id = 99999
    stats = database.get_server_engagement_stats(guild_id, timeframe="today")
    assert stats["total_racers"] == 0
    assert stats["active_today"] == 0
    assert stats["total_wealth"] == 0
    assert stats["total_gps"] == 0
    assert stats["total_duels"] == 0
    assert stats["total_seasons"] == 0

def test_get_server_engagement_stats_timeframes():
    guild_id = 12345
    # Create test users
    success1, _ = database.create_user(1001, guild_id, "Apex Racing", "USA")
    assert success1
    success2, _ = database.create_user(1002, guild_id, "Bull Racing", "UK")
    assert success2

    # Get user details
    u1 = database.get_user_by_discord_id(1001, guild_id)
    u2 = database.get_user_by_discord_id(1002, guild_id)

    # Award activity credits
    database.award_daily_activity_credits(u1["user_id"], 50, "chat")
    database.award_daily_activity_credits(u2["user_id"], 300, "voice")

    # Record duels
    database.record_duel_history(guild_id, u1["user_id"], u2["user_id"])

    # Create Grand Prix
    database.create_gp_race(guild_id, "Monaco GP", "Monaco GP", 15)

    for tf in ["today", "weekly", "monthly", "all"]:
        stats = database.get_server_engagement_stats(guild_id, timeframe=tf)
        assert stats["total_racers"] == 2
        assert stats["active_today"] >= 1
        assert stats["chat_credits_today"] == 50
        assert stats["est_chat_messages_today"] == 50 // config.CHAT_CREDITS_PER_MSG
        assert stats["voice_credits_today"] == 300
        assert stats["est_voice_minutes_today"] == 300 // config.VOICE_CREDITS_PER_MIN
        assert stats["total_duels"] == 1
        assert stats["total_gps"] == 1

@pytest.mark.asyncio
async def test_admin_stats_command_execution():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.display_avatar.url = "http://example.com/avatar.png"
    cog = AdminCog(bot)

    guild_id = 77777
    database.create_user(2001, guild_id, "Speed Demons", "GER")

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.guild_id = guild_id
    interaction.guild = MagicMock()
    interaction.guild.name = "Test Speed Guild"
    interaction.user = MagicMock()
    interaction.user.id = 2001
    interaction.response = AsyncMock()

    await cog.admin_stats.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in call_kwargs
    embed = call_kwargs["embed"]
    assert "Server Activity Telemetry" in embed.title
    assert "Test Speed Guild" in embed.title
