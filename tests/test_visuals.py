import pytest
import io
import utils

def test_generate_profile_card():
    mock_profile = {
        "team_name": "Apex Racing GP",
        "country": "🇮🇳",
        "level": 5,
        "money": 12500,
        "xp": 3400,
        "wins": 12,
        "losses": 3,
        "pace": 85,
        "qual": 78,
        "wet_skill": 92,
        "consistency": 80,
        "aggression": 75,
        "overtaking": 88,
        "engine": 12,
        "aerodynamics": 10,
        "tyres": 11,
        "ers": 9,
        "reliability": 14,
        "pit_crew": 8
    }
    
    card_buf = utils.generate_profile_card(mock_profile)
    assert isinstance(card_buf, io.BytesIO)
    assert card_buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n', "Output buffer should be a valid PNG image file"

def test_generate_race_telemetry_graph():
    mock_history = [
        {"lap": 1, "drivers": {"Apex Racing": 45.2, "Red Bull": 45.6}},
        {"lap": 2, "drivers": {"Apex Racing": 44.8, "Red Bull": 45.1}},
        {"lap": 3, "drivers": {"Apex Racing": 44.9, "Red Bull": 44.7}}
    ]
    
    graph_buf = utils.generate_race_telemetry_graph(mock_history)
    assert isinstance(graph_buf, io.BytesIO)
    assert graph_buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n', "Output buffer should be a valid PNG image file"

def test_victory_team_radio():
    radio = utils.get_victory_team_radio("Apex Racing")
    assert "Team Radio" in radio
    assert len(radio) > 10
