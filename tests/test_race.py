import pytest
import race

def test_simulate_duel(monkeypatch):
    import database
    monkeypatch.setattr(database, "get_equipped_inventory", lambda uid: {})
    # Setup two mock teams
    team1 = {
        "user_id": 1,
        "team_name": "Apex Racing",
        "discord_id": 1001,
        "engine": 10,
        "aerodynamics": 10,
        "tyres": 10,
        "ers": 10,
        "reliability": 10,
        "pace": 99,
        "qual": 90,
        "wet_skill": 80,
        "consistency": 85,
        "aggression": 70,
        "overtaking": 85,
        "damage_engine": 0,
        "damage_tyres": 0,
        "damage_total": 0
    }
    
    team2 = {
        "user_id": 2,
        "team_name": "Backmarker GP",
        "discord_id": 1002,
        "engine": 1,
        "aerodynamics": 1,
        "tyres": 1,
        "ers": 1,
        "reliability": 1,
        "pace": 10,
        "qual": 10,
        "wet_skill": 10,
        "consistency": 10,
        "aggression": 10,
        "overtaking": 10,
        "damage_engine": 0,
        "damage_tyres": 0,
        "damage_total": 0
    }
    
    # Run a single duel
    winner, loser, lap_logs, qual_logs = race.simulate_duel(team1, team2)
    
    assert len(qual_logs) > 0
    assert "Duel Start!" in qual_logs[0]
    
    # Run multiple duels to assert that team1 wins significantly more often (~95% in PRD)
    team1_wins = 0
    runs = 30
    for _ in range(runs):
        winner, _, _, _ = race.simulate_duel(team1, team2)
        if winner["user_id"] == 1:
            team1_wins += 1
            
    # With stats 10/10 vs 1/1, Apex should dominate
    win_rate = team1_wins / runs
    assert win_rate >= 0.85, f"Apex Racing only won {team1_wins}/{runs} races against Backmarker GP (rate: {win_rate:.2%})"

def test_simulate_gp():
    # Create 4 mock entrants
    entries = [
        {
            "user_id": 1, "team_name": "Red Scuderia", "discord_id": 1001,
            "engine": 8, "aerodynamics": 8, "tyres": 6, "ers": 7, "reliability": 8,
            "pace": 80, "qual": 85, "wet_skill": 75, "consistency": 80, "aggression": 65, "overtaking": 75
        },
        {
            "user_id": 2, "team_name": "Blue Arrows", "discord_id": 1002,
            "engine": 7, "aerodynamics": 9, "tyres": 7, "ers": 6, "reliability": 7,
            "pace": 82, "qual": 80, "wet_skill": 85, "consistency": 78, "aggression": 70, "overtaking": 80
        },
        {
            "user_id": 3, "team_name": "Green Bull", "discord_id": 1003,
            "engine": 9, "aerodynamics": 6, "tyres": 8, "ers": 8, "reliability": 9,
            "pace": 78, "qual": 82, "wet_skill": 60, "consistency": 85, "aggression": 55, "overtaking": 70
        },
        {
            "user_id": 4, "team_name": "Yellow Minardi", "discord_id": 1004,
            "engine": 2, "aerodynamics": 2, "tyres": 2, "ers": 2, "reliability": 10,
            "pace": 20, "qual": 20, "wet_skill": 30, "consistency": 40, "aggression": 45, "overtaking": 30
        }
    ]
    
    # Run GP on Monza track (rewards engine power)
    results, logs, lap_states = race.simulate_gp(entries, "Monza", total_laps=5)
    
    assert len(results) == 20, "Should auto-fill grid up to 20 total cars with AI drivers"
    assert len(logs) > 0
    
    # Ensure positions from 1 to 20 are assigned
    finish_positions = [res["finish_position"] for res in results]
    assert sorted(finish_positions) == list(range(1, 21))
    
    # Ensure human drivers received valid points
    human_results = [r for r in results if not r.get("is_ai")]
    for res in human_results:
        pos = res["finish_position"]
        if pos <= 10:
            assert res["points_earned"] > 0

def test_strategy_selection():
    # Verify that a player with custom tyres/strategies initializes properly in SimTeam
    player_data = {
        "user_id": 1,
        "team_name": "Ferrari F1",
        "discord_id": 1001,
        "pref_strategy": "Aggressive",
        "pref_tyres": "Soft",
        "pref_pit_stops": 3,
        "engine": 10,
        "aerodynamics": 10,
        "tyres": 10,
        "ers": 10,
        "reliability": 10,
        "pace": 90,
        "qual": 90,
        "wet_skill": 90,
        "consistency": 90,
        "aggression": 90,
        "overtaking": 90
    }
    
    t = race.SimTeam(player_data)
    assert t.strategy == "Aggressive"
    assert t.tyre_type == "Soft"
    assert t.pref_pit_stops == 3
    
    # Test pit laps calculation for 12 laps
    intervals = 12 / (t.pref_pit_stops + 1)
    t.pit_laps = [int(round(intervals * i)) for i in range(1, t.pref_pit_stops + 1)]
    assert t.pit_laps == [3, 6, 9]

def test_quali_simulation(monkeypatch):
    import database
    monkeypatch.setattr(database, "get_equipped_inventory", lambda uid: {})
    entries = [
        {"user_id": 1, "team_name": "Apex", "discord_id": 1001, "qual": 99, "current_q_tyre": "Soft"},
        {"user_id": 2, "team_name": "Backmarker", "discord_id": 1002, "qual": 10, "current_q_tyre": "Hard"}
    ]
    results = race.simulate_quali_session(entries, "Monza", "Q1")
    assert len(results) == 2
    assert results[0]["user_id"] == 1
    assert "quali_time" in results[0]


def test_custom_pit_strategy():
    player_data = {
        "user_id": 1,
        "team_name": "Ferrari F1",
        "discord_id": 1001,
        "pref_strategy": "Balanced",
        "pref_tyres": "Medium",
        "pref_pit_stops": 1,
        "pit_strategy_json": '{"pace": "Conservative", "start_tyre": "Soft", "stops": [{"lap": 5, "tyre": "Hard"}]}'
    }
    t = race.SimTeam(player_data)
    assert t.strategy == "Conservative"
    assert t.tyre_type == "Soft"
    assert t.pit_laps == [5]
    assert t.pit_tyres_plan == {5: "Hard"}

def test_generator_simulation():
    entries = [
        {
            "user_id": 1, "team_name": "Apex", "discord_id": 1001,
            "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 10,
            "pace": 90, "qual": 90, "wet_skill": 90, "consistency": 90, "aggression": 90, "overtaking": 90
        },
        {
            "user_id": 2, "team_name": "Backmarker", "discord_id": 1002,
            "engine": 1, "aerodynamics": 1, "tyres": 1, "ers": 1, "reliability": 1,
            "pace": 10, "qual": 10, "wet_skill": 10, "consistency": 10, "aggression": 10, "overtaking": 10
        }
    ]
    generator = race.simulate_gp_generator(entries, "Monza", total_laps=3, weather_timeline=["Sunny", "Sunny", "Rain"])
    
    # 1. Setup Event
    setup_event = next(generator)
    assert setup_event[0] == "setup"
    teams = setup_event[1]
    assert len(teams) == 20
    assert teams[0].team_name == "Apex"
    
    apex_team = [t for t in teams if t.team_name == "Apex"][0]
    apex_team.reliability = 20
    apex_team.strategy = "Conservative"
    
    # 2. Lap 1 Event (should log weather radar warnings since Rain is on Lap 3, index 2)
    lap1_event = next(generator)
    assert lap1_event[0] == "lap"
    assert lap1_event[1] == 1
    lap_logs = lap1_event[2]
    
    # Verify weather radar warning logged (Rain is on Lap 3, which is 2 laps from start of Lap 1)
    has_warning = any("approaching" in l for l in lap_logs)
    assert has_warning is True, "Expected weather radar warning for approaching rain."
    
    # Schedule a pit stop for next lap (lap 2)
    apex_team.pit_next_lap = True
    apex_team.pit_next_lap_tyre = "Hard"
    
    # 3. Lap 2 Event - pit should execute
    lap2_event = next(generator)
    assert lap2_event[0] == "lap"
    assert lap2_event[1] == 2
    
    # Verify pit stop was executed during lap 2
    assert apex_team.tyre_type == "Hard"
    assert apex_team.pit_stops_completed >= 1
    
    # Run to finish
    for item in generator:
        if item[0] == "finish":
            results = item[1]
            assert len(results) == 20
            user_ids = [r["user_id"] for r in results]
            assert 1 in user_ids

def test_ai_winner_save_gp_results(tmp_path):
    import database
    import sqlite3
    database.init_db()
    
    # Create a test race in DB
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO races (guild_id, name, date, track, weather, status, laps) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (12345, "Test GP", "2026-07-29", "Monza", "Sunny", "Qualifying", 10)
    )
    race_id = cursor.lastrowid
    
    # Create 1 human user entry
    cursor.execute("INSERT OR IGNORE INTO users (user_id, discord_id, guild_id, team_name) VALUES (?, ?, ?, ?)", (1, 1001, 12345, "Apex Racing"))
    cursor.execute("INSERT INTO race_entries (race_id, user_id) VALUES (?, ?)", (race_id, 1))
    conn.commit()
    conn.close()
    
    # Mock results where AI driver (user_id 9001) finishes P1 and human (user_id 1) finishes P2
    mock_results = [
        {"user_id": 9001, "finish_position": 1, "points_earned": 25, "credits_won": 5000, "dnf": False, "is_ai": True},
        {"user_id": 1, "finish_position": 2, "points_earned": 18, "credits_won": 3000, "dnf": False, "is_ai": False}
    ]
    
    # This should execute without raising FOREIGN KEY constraint failed
    database.save_gp_results(race_id, mock_results, winner_user_id=9001)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, winner_id FROM races WHERE race_id = ?", (race_id,))
    race_row = cursor.fetchone()
    assert race_row["status"] == "Finished"
    assert race_row["winner_id"] is None  # Foreign key set to None for AI driver

def test_human_driver_no_auto_pit_on_weather_change():
    entries = [
        {
            "user_id": 1, "team_name": "Human Team", "discord_id": 1001,
            "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 100,
            "pace": 90, "qual": 90, "wet_skill": 90, "consistency": 90, "aggression": 90, "overtaking": 90,
            "is_ai": False
        }
    ]
    # Weather: Lap 1 Sunny, Lap 2 Rain, Lap 3 Rain
    generator = race.simulate_gp_generator(entries, "Monza", total_laps=3, weather_timeline=["Sunny", "Rain", "Rain"])
    
    setup_event = next(generator)
    teams = setup_event[1]
    human_team = [t for t in teams if t.user_id == 1][0]
    ai_team = [t for t in teams if t.is_ai][0]
    
    # Lap 1: Sunny
    lap1_event = next(generator)
    assert human_team.tyre_type == "Medium"
    
    # Lap 2: Weather changes to Rain
    lap2_event = next(generator)
    lap2_logs = lap2_event[2]
    
    # Human driver should NOT have automatically pitted
    assert human_team.tyre_type == "Medium", "Human driver should NOT auto-pit on rain"
    assert any("Rain has started" in log for log in lap2_logs), "Human driver should receive radio alert about rain"
    
    # AI driver SHOULD have automatically pitted for Intermediates
    assert ai_team.tyre_type == "Intermediates", "AI driver SHOULD auto-pit for Intermediates on rain"

def test_weather_radar_clearing_alert():
    entries = [
        {
            "user_id": 1, "team_name": "Human Team", "discord_id": 1001,
            "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 10,
            "pace": 90, "qual": 90, "wet_skill": 90, "consistency": 90, "aggression": 90, "overtaking": 90
        }
    ]
    # Lap 1 Rain, Lap 2 Rain, Lap 3 Sunny
    generator = race.simulate_gp_generator(entries, "Monza", total_laps=3, weather_timeline=["Rain", "Rain", "Sunny"])
    
    next(generator)  # setup
    lap1_event = next(generator)
    lap1_logs = lap1_event[2]
    
    # At Lap 1, Lap 3 is 2 laps ahead and becomes Sunny -> should log clearing warning
    has_clearing_warning = any("clearing" in l for l in lap1_logs)
    assert has_clearing_warning is True, "Expected weather radar clearing warning for rain stopping in 2 laps."

def test_simulate_duel_generator_lap_telemetry():
    from unittest.mock import patch
    t1 = {"user_id": 1, "team_name": "Team A", "discord_id": 1001, "engine": 5, "pace": 80}
    t2 = {"user_id": 2, "team_name": "Team B", "discord_id": 1002, "engine": 5, "pace": 80}
    
    with patch('random.uniform', return_value=99.9):
        generator = race.simulate_duel_generator(t1, t2, total_laps=3, track_name="Monza")
        setup_event = next(generator)
        assert setup_event[0] == "setup"
        teams_list = setup_event[1]
        
        lap_telemetry_history = []
        for item in generator:
            if item[0] == "lap":
                l_num = item[1]
                drivers_pace = {}
                for t_obj in teams_list:
                    drivers_pace[t_obj.team_name] = round(t_obj.last_lap_time, 2)
                lap_telemetry_history.append({"lap": l_num, "drivers": drivers_pace})
                
        assert len(lap_telemetry_history) == 3
        assert "Team A" in lap_telemetry_history[0]["drivers"]
        assert "Team B" in lap_telemetry_history[0]["drivers"]



