import pytest
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
