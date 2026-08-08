import pytest
from unittest.mock import MagicMock, AsyncMock
import discord

import config
import database
import utils
from cogs.racing import GPAdminView
from cogs.admin import SeasonCalendarAdminView

def test_is_admin_user_scenarios(tmp_path):
    # Setup mock interaction
    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = 12345
    mock_guild.owner_id = 99999
    
    mock_interaction.guild = mock_guild
    
    # 1. Server Owner
    mock_user = MagicMock(spec=discord.Member)
    mock_user.id = 99999
    mock_user.guild_permissions = discord.Permissions(administrator=False)
    mock_user.roles = []
    mock_interaction.user = mock_user
    assert utils.is_admin_user(mock_interaction) is True
    
    # 2. Administrator permission
    mock_user.id = 11111
    mock_user.guild_permissions = discord.Permissions(administrator=True)
    assert utils.is_admin_user(mock_interaction) is True
    
    # 3. Admin role
    mock_user.guild_permissions = discord.Permissions(administrator=False)
    role = MagicMock()
    role.name = config.ADMIN_ROLE_NAME
    mock_user.roles = [role]
    assert utils.is_admin_user(mock_interaction) is True
    
    # 4. Non-admin user
    role.name = "Member"
    mock_user.roles = [role]
    assert utils.is_admin_user(mock_interaction) is False

@pytest.mark.asyncio
async def test_gp_admin_view_interaction_check():
    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.response.send_message = AsyncMock()
    
    # Non-admin user
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = 12345
    mock_guild.owner_id = 99999
    mock_interaction.guild = mock_guild
    
    non_admin = MagicMock(spec=discord.Member)
    non_admin.id = 55555
    non_admin.guild_permissions = discord.Permissions(administrator=False)
    non_admin.roles = []
    mock_interaction.user = non_admin
    
    view = GPAdminView(guild_id=12345)
    allowed = await view.interaction_check(mock_interaction)
    assert allowed is False
    mock_interaction.response.send_message.assert_called_once()
    assert "Only bot administrators" in mock_interaction.response.send_message.call_args[0][0]

@pytest.mark.asyncio
async def test_season_calendar_view_pagination():
    active_season = {"season_id": 1, "name": "Test Season 2026"}
    # Create 35 dummy races
    calendar = []
    for i in range(35):
        calendar.append({
            "calendar_id": i + 1,
            "track": f"Track {i+1}",
            "laps": 10,
            "is_sprint": 0,
            "status": "Scheduled"
        })
        
    view = SeasonCalendarAdminView(active_season, calendar)
    
    # Check page 0 components
    assert view.page == 0
    # There should be 1 select, 3 pagination buttons, 1 start round button
    select_items = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(select_items) == 1
    select_options = select_items[0].options
    assert len(select_options) == 25
    assert select_options[0].label == "Round 1: Track 1 (GP)"
    assert select_options[-1].label == "Round 25: Track 25 (GP)"
    
    # Test Next Page callback
    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.response.edit_message = AsyncMock()
    
    await view.next_page_callback(mock_interaction)
    assert view.page == 1
    
    select_items = [item for item in view.children if isinstance(item, discord.ui.Select)]
    select_options = select_items[0].options
    assert len(select_options) == 10
    assert select_options[0].label == "Round 26: Track 26 (GP)"
    assert select_options[-1].label == "Round 35: Track 35 (GP)"
