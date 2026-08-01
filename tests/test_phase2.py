import pytest
import discord
import config
import database
import race


def test_f1_calendar_tracks_count():
    assert len(race.TRACK_PROFILES) >= 24, "Should contain all 24 official F1 calendar tracks"
    monaco = race.TRACK_PROFILES["Monaco (Monte Carlo)"]
    assert monaco["aero_mod"] == 1.7
    assert monaco["engine_mod"] == 0.7
    
    sprint_tracks = [t for t, p in race.TRACK_PROFILES.items() if p.get("is_sprint")]
    assert len(sprint_tracks) >= 6, "Should contain official F1 Sprint tracks"

def test_f1_points_distribution():
    assert config.GP_POINTS_DISTRIBUTION == [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    assert config.SPRINT_POINTS_DISTRIBUTION == [8, 7, 6, 5, 4, 3, 2, 1]

def test_ai_grid_fillers_and_thermal_management():
    sample_human = [{
        "user_id": 1,
        "team_name": "Test Human GP",
        "discord_id": 1001,
        "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 10, "pit_crew": 10,
        "pace": 80, "qual": 80, "wet_skill": 80, "consistency": 80, "aggression": 80, "overtaking": 80
    }]
    
    results, logs, lap_states = race.simulate_gp(sample_human, "Monza (Italy)", total_laps=5)
    
    # Grid should be auto-filled up to 20 cars
    assert len(results) == 20, "Should auto-fill grid up to 20 cars with AI drivers"
    
    # First place result should have valid points
    p1 = results[0]
    assert p1["finish_position"] == 1
    assert p1["points_earned"] in [25, 26] # 25 pts + potential fastest lap

def test_season_database_lifecycle():
    guild_id = 99999
    database.cancel_active_season(guild_id)
    
    # 1. Create season
    success, msg = database.create_season(guild_id, "Test WDC Season 1")
    assert success is True, f"create_season failed: {msg}"
    
    # 2. Get active season
    active = database.get_active_season(guild_id)
    assert active is not None
    assert active["name"] == "Test WDC Season 1"
    
    # 3. End season
    success_end, msg_end, season, standings = database.end_active_season(guild_id)
    assert success_end is True
    assert season["name"] == "Test WDC Season 1"
    
    # 4. Verify no active season remains
    active_after = database.get_active_season(guild_id)
    assert active_after is None

def test_season_calendar_lifecycle():
    guild_id = 88888
    database.cancel_active_season(guild_id)
    
    # 1. Create active season
    success, msg = database.create_season(guild_id, "Calendar Test Season")
    assert success is True
    active = database.get_active_season(guild_id)
    season_id = active['season_id']
    
    # 2. Add races to calendar
    s1, m1 = database.add_season_race(season_id, "Monza (Italy)", 15, is_sprint=False)
    assert s1 is True
    s2, m2 = database.add_season_race(season_id, "Monaco (Monte Carlo)", 8, is_sprint=True)
    assert s2 is True
    s3, m3 = database.add_season_race(season_id, "Silverstone (Great Britain)", 15, is_sprint=False)
    assert s3 is True
    
    # 3. Verify calendar order
    calendar = database.get_season_calendar(season_id)
    assert len(calendar) == 3
    assert calendar[0]['track'] == "Monza (Italy)"
    assert calendar[0]['race_order'] == 1
    assert calendar[1]['is_sprint'] == 1
    assert calendar[2]['track'] == "Silverstone (Great Britain)"
    
    # 4. Remove round 2 (Monaco Sprint)
    cal_id_2 = calendar[1]['calendar_id']
    s_rem, m_rem = database.remove_season_race(cal_id_2)
    assert s_rem is True
    
    calendar_after = database.get_season_calendar(season_id)
    assert len(calendar_after) == 2
    assert calendar_after[0]['track'] == "Monza (Italy)"
    assert calendar_after[1]['track'] == "Silverstone (Great Britain)"
    assert calendar_after[1]['race_order'] == 2

def test_large_calendar_handling():
    """Verify that calendars with 40+ races render Select options within Discord's 25-option limit."""
    from cogs.admin import SeasonCalendarAdminView
    guild_id = 999991
    database.cancel_active_season(guild_id)
    database.create_season(guild_id, "40 Round Season")
    active = database.get_active_season(guild_id)
    season_id = active['season_id']
    
    # Add 40 races to calendar
    for i in range(40):
        database.add_season_race(season_id, f"Track {i+1}", 10, is_sprint=(i%5==0))
        
    calendar = database.get_season_calendar(season_id)
    assert len(calendar) == 40
    
    # Instantiate view and build components
    view = SeasonCalendarAdminView(active, calendar)
    embed = view.build_embed()
    
    # Check that Select menu options length <= 25
    select_items = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(select_items) == 1
    assert len(select_items[0].options) <= 25
    assert embed is not None

    
    # 5. Clean up season
    database.cancel_active_season(guild_id)

def test_gp_entry_fee_and_refund():
    """Verify that GP registration deducts 500¢ and leaving refunds 500¢."""
    guild_id = 77777
    database.create_user(discord_id=8881, guild_id=guild_id, team_name="Refund Test Team")
    user = database.get_user_by_discord_id(8881, guild_id)
    initial_money = user['money']
    
    # Create GP
    database.create_gp_race(guild_id, "Refund GP", "Monza (Italy)", 10)
    
    # Register (costs 500)
    ok_reg, msg_reg = database.register_gp_entry(8881, guild_id)
    assert ok_reg is True
    assert "500" in msg_reg
    
    user_after_reg = database.get_user_by_discord_id(8881, guild_id)
    assert user_after_reg['money'] == initial_money - 500
    
    # Leave/Unregister (refunds 500)
    ok_unreg, msg_unreg = database.unregister_gp_entry(8881, guild_id)
    assert ok_unreg is True
    assert "500" in msg_unreg
    
    user_after_unreg = database.get_user_by_discord_id(8881, guild_id)
    assert user_after_unreg['money'] == initial_money

    database.cancel_active_season(guild_id)
