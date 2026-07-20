import pytest
import race

def test_simulate_duel():
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
    results, logs = race.simulate_gp(entries, "Monza", total_laps=5)
    
    assert len(results) == 4
    assert len(logs) > 0
    
    # Ensure positions from 1 to 4 are assigned
    finish_positions = [res["finish_position"] for res in results]
    assert sorted(finish_positions) == [1, 2, 3, 4]
    
    # Ensure points distribution is allocated correctly based on position and DNF status
    import utils
    for res in results:
        pos = res["finish_position"]
        expected_points = utils.get_points_for_position(pos) if not res["dnf"] else 0
        assert res["points_earned"] == expected_points

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

def test_quali_simulation():
    entries = [
        {"user_id": 1, "team_name": "Apex", "discord_id": 1001, "qual": 90, "current_q_tyre": "Soft"},
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
