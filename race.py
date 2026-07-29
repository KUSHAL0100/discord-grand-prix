import random
from typing import List, Dict, Any, Tuple
import config
import utils
import database

# Complete 24 Official F1 Calendar Tracks + Traits & Performance Modifiers
TRACK_PROFILES = {
    "Bahrain (Sakhir)": {
        "description": "Heavy braking & traction zones. Severe rear tyre wear.",
        "engine_mod": 1.25, "tyre_mod": 1.4, "aero_mod": 0.9, "heat_mod": 1.2, "is_sprint": False
    },
    "Jeddah (Saudi Arabia)": {
        "description": "Ultra-fast high-speed street circuit. Extreme barrier crash risk.",
        "engine_mod": 1.4, "aero_mod": 1.2, "sc_chance_mult": 1.7, "heat_mod": 1.1, "is_sprint": False
    },
    "Melbourne (Albert Park)": {
        "description": "High-speed flowing street layout with tricky braking zones.",
        "engine_mod": 1.2, "aero_mod": 1.1, "tyre_mod": 1.1, "is_sprint": False
    },
    "Suzuka (Japan)": {
        "description": "Legendary figure-8 circuit. Demands extreme aero & driver consistency.",
        "aero_mod": 1.5, "consistency_mod": 1.3, "engine_mod": 1.1, "is_sprint": False
    },
    "Shanghai (China)": {
        "description": "Official Sprint Track. Monster 1.2km straight & technical hairpins.",
        "engine_mod": 1.35, "tyre_mod": 1.25, "ers_mod": 1.3, "is_sprint": True
    },
    "Miami (USA)": {
        "description": "Official Sprint Track. High heat street circuit around Hard Rock Stadium.",
        "tyre_mod": 1.3, "heat_mod": 1.4, "engine_mod": 1.2, "is_sprint": True
    },
    "Imola (Emilia Romagna)": {
        "description": "Historic narrow track. High downforce and difficult overtaking.",
        "aero_mod": 1.4, "overtake_diff": 1.4, "engine_mod": 1.1, "is_sprint": False
    },
    "Monaco (Monte Carlo)": {
        "description": "The Crown Jewel. Ultra-narrow street track where Aero & Quali are king.",
        "aero_mod": 1.7, "overtake_diff": 2.0, "engine_mod": 0.7, "qual_mod": 1.5, "is_sprint": False
    },
    "Montreal (Canada)": {
        "description": "Stop-and-go circuit with the famous Wall of Champions.",
        "engine_mod": 1.35, "ers_mod": 1.3, "sc_chance_mult": 1.6, "is_sprint": False
    },
    "Barcelona (Catalunya)": {
        "description": "The ultimate aerodynamic testbed. High tyre thermal degradation.",
        "aero_mod": 1.5, "tyre_mod": 1.4, "engine_mod": 1.1, "is_sprint": False
    },
    "Red Bull Ring (Austria)": {
        "description": "Official Sprint Track. Short, power-heavy track in the Styrian mountains.",
        "engine_mod": 1.45, "ers_mod": 1.3, "overtake_bonus": 1.3, "is_sprint": True
    },
    "Silverstone (Great Britain)": {
        "description": "High-speed sweeping curves Maggotts & Becketts. Extreme tyre load.",
        "aero_mod": 1.5, "tyre_mod": 1.5, "engine_mod": 1.2, "is_sprint": False
    },
    "Hungaroring (Hungary)": {
        "description": "Twisty, technical 'Monaco without walls'. High downforce required.",
        "aero_mod": 1.5, "overtake_diff": 1.5, "heat_mod": 1.3, "is_sprint": False
    },
    "Spa-Francorchamps (Belgium)": {
        "description": "Eau Rouge & Pouhon. Legendary power track with high rain chaos.",
        "engine_mod": 1.45, "aero_mod": 1.25, "rain_prob_mult": 2.2, "is_sprint": False
    },
    "Zandvoort (Netherlands)": {
        "description": "Banked corners & coastal dunes. Demands high aerodynamic grip.",
        "aero_mod": 1.45, "tyre_mod": 1.3, "sc_chance_mult": 1.3, "is_sprint": False
    },
    "Monza (Italy)": {
        "description": "The Temple of Speed. Ultra-low downforce where Engine power dominates.",
        "engine_mod": 1.75, "aero_mod": 0.6, "ers_mod": 1.4, "is_sprint": False
    },
    "Baku (Azerbaijan)": {
        "description": "Monster 2.2km main straight meets tight Castle Section.",
        "engine_mod": 1.5, "sc_chance_mult": 1.8, "overtake_bonus": 1.4, "is_sprint": False
    },
    "Singapore (Marina Bay)": {
        "description": "Humid night street race. Extreme thermal engine heat & 100% SC rate.",
        "heat_mod": 1.8, "tyre_mod": 1.5, "sc_chance_mult": 1.8, "is_sprint": False
    },
    "Austin (COTA, USA)": {
        "description": "Official Sprint Track. Turn 1 steep elevation climb & sweeping S-curves.",
        "aero_mod": 1.35, "engine_mod": 1.25, "tyre_mod": 1.2, "is_sprint": True
    },
    "Mexico City (Mexico)": {
        "description": "High altitude thin air (2,200m). Reduced cooling & low downforce air density.",
        "heat_mod": 1.6, "engine_mod": 1.35, "aero_mod": 0.8, "is_sprint": False
    },
    "Interlagos (Brazil)": {
        "description": "Official Sprint Track. High elevation change, overtaking & rain volatility.",
        "overtake_bonus": 1.4, "rain_prob_mult": 2.0, "engine_mod": 1.3, "is_sprint": True
    },
    "Las Vegas (USA)": {
        "description": "Cold night strip straight. Long 1.9km straight with low tyre thermal warmup.",
        "engine_mod": 1.55, "aero_mod": 0.7, "tyre_mod": 1.2, "is_sprint": False
    },
    "Qatar (Lusail)": {
        "description": "Official Sprint Track. Ultra high-speed flowing curves & intense G-force heat.",
        "tyre_mod": 1.6, "heat_mod": 1.5, "aero_mod": 1.4, "is_sprint": True
    },
    "Abu Dhabi (Yas Marina)": {
        "description": "Twilight season finale. Balanced sector 1 & technical hotel sector 3.",
        "engine_mod": 1.2, "aero_mod": 1.2, "tyre_mod": 1.1, "is_sprint": False
    }
}

# 20-Car Grid AI Driver Roster
AI_GRID_DRIVERS = [
    {"user_id": 9001, "team_name": "Red Bull (Verstappen)", "discord_id": 9001, "engine": 16, "aerodynamics": 16, "tyres": 15, "ers": 15, "reliability": 16, "pit_crew": 16, "pace": 96, "qual": 96, "wet_skill": 95, "consistency": 94, "aggression": 90, "overtaking": 92, "is_ai": True},
    {"user_id": 9002, "team_name": "Mercedes (Hamilton)", "discord_id": 9002, "engine": 15, "aerodynamics": 15, "tyres": 15, "ers": 15, "reliability": 15, "pit_crew": 15, "pace": 94, "qual": 94, "wet_skill": 96, "consistency": 95, "aggression": 85, "overtaking": 90, "is_ai": True},
    {"user_id": 9003, "team_name": "Ferrari (Leclerc)", "discord_id": 9003, "engine": 16, "aerodynamics": 15, "tyres": 14, "ers": 15, "reliability": 14, "pit_crew": 14, "pace": 93, "qual": 97, "wet_skill": 88, "consistency": 88, "aggression": 88, "overtaking": 89, "is_ai": True},
    {"user_id": 9004, "team_name": "McLaren (Norris)", "discord_id": 9004, "engine": 15, "aerodynamics": 16, "tyres": 15, "ers": 14, "reliability": 15, "pit_crew": 15, "pace": 93, "qual": 92, "wet_skill": 90, "consistency": 91, "aggression": 86, "overtaking": 89, "is_ai": True},
    {"user_id": 9005, "team_name": "Aston Martin (Alonso)", "discord_id": 9005, "engine": 14, "aerodynamics": 14, "tyres": 15, "ers": 13, "reliability": 14, "pit_crew": 13, "pace": 91, "qual": 90, "wet_skill": 94, "consistency": 92, "aggression": 91, "overtaking": 91, "is_ai": True},
    {"user_id": 9006, "team_name": "McLaren (Piastri)", "discord_id": 9006, "engine": 14, "aerodynamics": 15, "tyres": 14, "ers": 14, "reliability": 14, "pit_crew": 14, "pace": 90, "qual": 91, "wet_skill": 86, "consistency": 89, "aggression": 84, "overtaking": 87, "is_ai": True},
    {"user_id": 9007, "team_name": "Mercedes (Russell)", "discord_id": 9007, "engine": 14, "aerodynamics": 14, "tyres": 14, "ers": 14, "reliability": 14, "pit_crew": 14, "pace": 89, "qual": 92, "wet_skill": 85, "consistency": 87, "aggression": 87, "overtaking": 86, "is_ai": True},
    {"user_id": 9008, "team_name": "Ferrari (Sainz)", "discord_id": 9008, "engine": 14, "aerodynamics": 14, "tyres": 13, "ers": 14, "reliability": 13, "pit_crew": 14, "pace": 89, "qual": 91, "wet_skill": 87, "consistency": 86, "aggression": 88, "overtaking": 88, "is_ai": True},
    {"user_id": 9009, "team_name": "Williams (Albon)", "discord_id": 9009, "engine": 14, "aerodynamics": 11, "tyres": 12, "ers": 13, "reliability": 13, "pit_crew": 12, "pace": 85, "qual": 88, "wet_skill": 82, "consistency": 84, "aggression": 82, "overtaking": 84, "is_ai": True},
    {"user_id": 9010, "team_name": "Alpine (Gasly)", "discord_id": 9010, "engine": 12, "aerodynamics": 12, "tyres": 12, "ers": 12, "reliability": 11, "pit_crew": 12, "pace": 84, "qual": 83, "wet_skill": 86, "consistency": 82, "aggression": 86, "overtaking": 83, "is_ai": True},
    {"user_id": 9011, "team_name": "Alpine (Ocon)", "discord_id": 9011, "engine": 12, "aerodynamics": 12, "tyres": 12, "ers": 12, "reliability": 11, "pit_crew": 12, "pace": 83, "qual": 82, "wet_skill": 85, "consistency": 80, "aggression": 88, "overtaking": 84, "is_ai": True},
    {"user_id": 9012, "team_name": "RB (Tsunoda)", "discord_id": 9012, "engine": 12, "aerodynamics": 12, "tyres": 12, "ers": 12, "reliability": 12, "pit_crew": 12, "pace": 82, "qual": 84, "wet_skill": 83, "consistency": 79, "aggression": 85, "overtaking": 83, "is_ai": True},
    {"user_id": 9013, "team_name": "Haas (Hulkenberg)", "discord_id": 9013, "engine": 12, "aerodynamics": 11, "tyres": 11, "ers": 11, "reliability": 12, "pit_crew": 11, "pace": 81, "qual": 84, "wet_skill": 80, "consistency": 82, "aggression": 83, "overtaking": 81, "is_ai": True},
    {"user_id": 9014, "team_name": "Aston Martin (Stroll)", "discord_id": 9014, "engine": 11, "aerodynamics": 11, "tyres": 11, "ers": 11, "reliability": 11, "pit_crew": 11, "pace": 78, "qual": 79, "wet_skill": 78, "consistency": 80, "aggression": 79, "overtaking": 78, "is_ai": True},
    {"user_id": 9015, "team_name": "Sauber (Bottas)", "discord_id": 9015, "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 10, "pit_crew": 10, "pace": 77, "qual": 78, "wet_skill": 80, "consistency": 81, "aggression": 75, "overtaking": 76, "is_ai": True},
    {"user_id": 9016, "team_name": "Haas (Magnussen)", "discord_id": 9016, "engine": 10, "aerodynamics": 10, "tyres": 10, "ers": 10, "reliability": 10, "pit_crew": 10, "pace": 76, "qual": 76, "wet_skill": 77, "consistency": 78, "aggression": 80, "overtaking": 77, "is_ai": True},
    {"user_id": 9017, "team_name": "Sauber (Zhou)", "discord_id": 9017, "engine": 9, "aerodynamics": 9, "tyres": 9, "ers": 9, "reliability": 9, "pit_crew": 9, "pace": 74, "qual": 75, "wet_skill": 76, "consistency": 76, "aggression": 74, "overtaking": 74, "is_ai": True},
    {"user_id": 9018, "team_name": "Williams (Sargeant)", "discord_id": 9018, "engine": 9, "aerodynamics": 9, "tyres": 9, "ers": 9, "reliability": 9, "pit_crew": 9, "pace": 73, "qual": 74, "wet_skill": 74, "consistency": 74, "aggression": 75, "overtaking": 73, "is_ai": True},
    {"user_id": 9019, "team_name": "Williams (Colapinto)", "discord_id": 9019, "engine": 8, "aerodynamics": 8, "tyres": 8, "ers": 8, "reliability": 8, "pit_crew": 8, "pace": 71, "qual": 72, "wet_skill": 72, "consistency": 72, "aggression": 76, "overtaking": 72, "is_ai": True},
    {"user_id": 9020, "team_name": "Haas (Bearman)", "discord_id": 9020, "engine": 8, "aerodynamics": 8, "tyres": 8, "ers": 8, "reliability": 8, "pit_crew": 8, "pace": 70, "qual": 71, "wet_skill": 71, "consistency": 71, "aggression": 75, "overtaking": 70, "is_ai": True}
]

class SimTeam:
    """Class to wrap team, driver, strategist, and car stats for the race simulation."""
    def __init__(self, data: Dict[str, Any]):
        self.user_id = data["user_id"]
        self.team_name = data["team_name"]
        self.discord_id = data["discord_id"]
        self.is_ai = data.get("is_ai", False)
        self.ai_rival = None
        self.engine_temp = 85.0
        
        # Car Stats
        self.engine = data.get("engine", 1)
        self.aerodynamics = data.get("aerodynamics", 1)
        self.tyres_stat = data.get("tyres", 1)
        self.ers = data.get("ers", 1)
        self.reliability = data.get("reliability", 1)
        self.pit_crew = data.get("pit_crew", 1)
        self.aerodynamics = data.get("aerodynamics", 1)
        self.tyres_stat = data.get("tyres", 1)
        self.ers = data.get("ers", 1)
        self.reliability = data.get("reliability", 1)
        self.pit_crew = data.get("pit_crew", 1)
        
        # Driver Stats
        self.driver_pace = data.get("pace", 50)
        self.driver_qual = data.get("qual", 50)
        self.driver_wet_skill = data.get("wet_skill", 50)
        self.driver_consistency = data.get("consistency", 50)
        self.driver_aggression = data.get("aggression", 50)
        self.driver_overtaking = data.get("overtaking", 50)
        
        # Strategist Stats
        self.strat_pit_timing = data.get("pit_timing", 50)
        self.strat_weather_call = data.get("weather_call", 50)
        self.strat_undercut = data.get("undercut", 50)
        self.strat_sc_skill = data.get("sc_skill", 50)
        
        # Garage Damage
        self.damage_engine = data.get("damage_engine", 0)
        self.damage_tyres = data.get("damage_tyres", 0)
        self.damage_total = data.get("damage_total", 0)
        
        # Simulation Runtime States
        self.performance = 0.0
        self.dnf = False
        self.dnf_reason = ""
        self.dnf_announced = False
        self.tyre_health = 100.0
        self.total_time = 0.0
        self.last_lap_time = 0.0
        self.gap_to_leader = 0.0
        self.gap_to_front = 0.0
        
        self.next_block_strategy = None
        self.pit_next_lap = False
        self.pit_next_lap_tyre = "Medium"
        
        # Load user strategy preferences
        self.pref_strategy = data.get("pref_strategy", "Balanced")
        self.pref_tyres = data.get("pref_tyres", "Medium")
        self.pref_pit_stops = data.get("pref_pit_stops", 1)
        self.start_position = data.get("start_position")
        self.current_q_tyre = data.get("current_q_tyre", "Soft")
        
        # Parse custom pit strategy JSON
        import json
        self.pit_strategy = {}
        strategy_str = data.get("pit_strategy_json")
        if strategy_str:
            try:
                self.pit_strategy = json.loads(strategy_str)
            except Exception:
                pass
                
        self.strategy = self.pit_strategy.get("pace") or data.get("pref_strategy") or "Balanced"
        self.tyre_type = self.pit_strategy.get("start_tyre") or data.get("pref_tyres") or "Medium"
        
        self.pit_laps = []
        self.pit_tyres_plan = {}
        stops_plan = self.pit_strategy.get("stops", [])
        if stops_plan:
            for stop in stops_plan:
                l_num = int(stop.get("lap", 0))
                compound = stop.get("tyre", "Medium")
                if l_num > 0:
                    self.pit_laps.append(l_num)
                    self.pit_tyres_plan[l_num] = compound
        
        self.pit_stop_done = False
        self.pit_stops_completed = 0
        self.grid_position = 0
        self.current_position = 0
        self.laps_completed = 0
        self.fastest_lap_time = 999.9
        
    def calculate_base_car_power(self, track_name: str) -> float:
        """Calculate car power adjusted for rarity base level offsets, tier scaling, track profiles and damage."""
        profile = TRACK_PROFILES.get(track_name, {"aero_mod": 1.0, "engine_mod": 1.0, "tyre_mod": 1.0})
        aero_mult = profile.get("aero_mod", 1.0)
        eng_mult = profile.get("engine_mod", 1.0)
        tyre_mult = profile.get("tyre_mod", 1.0)
        
        equipped = database.get_equipped_inventory(self.user_id) if not self.is_ai else {}
        from crates import RARITY_BASE_OFFSETS, RARITY_BONUS_MULTIPLIERS
        
        def calculate_effective_stat(category: str, base_level: int) -> float:
            item = equipped.get(category)
            rarity = item.get('rarity', 'Common') if item else 'Common'
            offset = RARITY_BASE_OFFSETS.get(rarity, 0)
            effective_level = base_level + offset
            tier_mult = config.get_tier_stat_multiplier(effective_level)
            bonus_mult = RARITY_BONUS_MULTIPLIERS.get(rarity, 1.0)
            return effective_level * tier_mult * bonus_mult

        engine_contrib = calculate_effective_stat('engine', self.engine) * 3.0 * eng_mult
        aero_contrib = calculate_effective_stat('aerodynamics', self.aerodynamics) * 2.0 * aero_mult
        tyre_contrib = calculate_effective_stat('tyres', self.tyres_stat) * 2.0 * tyre_mult
        ers_contrib = calculate_effective_stat('ers', self.ers) * 2.0
        reliability_contrib = calculate_effective_stat('reliability', self.reliability) * 1.0
        
        base_power = engine_contrib + aero_contrib + tyre_contrib + ers_contrib + reliability_contrib
        
        # Apply damage penalty: e.g. -1% power per 10% damage_total
        damage_penalty = (self.damage_total / 10.0) / 100.0
        base_power *= (1.0 - min(0.5, damage_penalty))
        
        return base_power

def simulate_duel_generator(team1_data: Dict[str, Any], team2_data: Dict[str, Any], total_laps: int = 1, track_name: str = None):
    """
    Generator that simulates a 1v1 duel lap-by-lap, yielding intermediate states to allow interactive strategy updates.
    """
    t1 = SimTeam(team1_data)
    t2 = SimTeam(team2_data)
    
    qual_logs = ["🏁 **Duel Start!** Lights out and away we go!"]
    
    # Select track (specified or random)
    if track_name and track_name in TRACK_PROFILES:
        track = track_name
    else:
        track = random.choice(list(TRACK_PROFILES.keys()))
    qual_logs.append(f"📍 Track: **{track}** - {TRACK_PROFILES[track]['description']}")
    
    # Setup initial pit stops
    for t in [t1, t2]:
        if total_laps > 3:
            intervals = total_laps / (t.pref_pit_stops + 1)
            t.pit_laps = [int(round(intervals * i)) for i in range(1, t.pref_pit_stops + 1)]
        else:
            t.pit_laps = []
            
        t.pit_next_lap = False
        t.pit_next_lap_tyre = None
        t.next_block_strategy = None
        t.last_lap_time = 45.0  # default lap time

    qual_logs.append(f"📋 Strategist for '{t1.team_name}' chose **{t1.strategy}** strategy and **{t1.tyre_type}** tyres.")
    qual_logs.append(f"📋 Strategist for '{t2.team_name}' chose **{t2.strategy}** strategy and **{t2.tyre_type}** tyres.")
    
    # Qualifying simulation
    t1_qual = t1.calculate_base_car_power(track) + (t1.driver_qual / 2.0) + random.uniform(0, 10)
    t2_qual = t2.calculate_base_car_power(track) + (t2.driver_qual / 2.0) + random.uniform(0, 10)
    
    if t1_qual >= t2_qual:
        leader, trailer = t1, t2
        qual_logs.append(f"⏱️ **Qualifying:** **{t1.team_name}** takes pole position! **{t2.team_name}** starts P2.")
    else:
        leader, trailer = t2, t1
        qual_logs.append(f"⏱️ **Qualifying:** **{t2.team_name}** takes pole position! **{t1.team_name}** starts P2.")
        
    qual_logs.append("\n🟢 **Lights Out! The duel is underway!**")
    
    yield "setup", [t1, t2], qual_logs, track
    
    gap = 1.0
    finish_logs = []
    
    for lap in range(1, total_laps + 1):
        current_lap_events = []
        
        # Apply scheduled pacing or pit stops
        for t in [t1, t2]:
            if t.dnf:
                continue
            if getattr(t, 'next_block_strategy', None):
                t.strategy = t.next_block_strategy
                t.next_block_strategy = None
                current_lap_events.append(f"📻 **{t.team_name}:** Pacing strategy changed to **{t.strategy}**.")
            
            if getattr(t, 'pit_next_lap', False):
                new_tyre = getattr(t, 'pit_next_lap_tyre', t.tyre_type) or t.tyre_type
                t.tyre_type = new_tyre
                t.tyre_health = 100.0
                t.pit_next_lap = False
                t.pit_stops_completed += 1
                
                pit_duration = 3.5 - (t.pit_crew * 0.15)
                if t == leader:
                    gap -= pit_duration
                else:
                    gap += pit_duration
                current_lap_events.append(f"🔧 **Lap {lap}:** {t.team_name} pits for fresh **{t.tyre_type}** tyres (time: {pit_duration:.2f}s)!")
                
        # Check DNF for both active drivers
        for t in [leader, trailer]:
            if t.dnf:
                continue
            dnf_chance = max(0.2, 6.5 - t.reliability * 0.25)
            if t.strategy == "Aggressive":
                dnf_chance += 3.0
            elif t.strategy == "Conservative":
                dnf_chance = max(0.05, dnf_chance - 2.0)
                
            per_lap_dnf_chance = dnf_chance / total_laps
            if random.uniform(0, 100) < per_lap_dnf_chance:
                t.dnf = True
                reasons = ["spun off into the barriers", "suffered an engine blowup", "had a gearbox failure", "collided with a competitor"]
                t.dnf_reason = random.choice(reasons)
                current_lap_events.append(f"💥 **CRASH!** {t.team_name} {t.dnf_reason} and is out of the race!")
                
        # Handle DNFs
        if leader.dnf and trailer.dnf:
            if random.random() < 0.5:
                winner, loser = leader, trailer
                current_lap_events.append(f"Both crashed! But {leader.team_name} is classified ahead.")
            else:
                winner, loser = trailer, leader
                current_lap_events.append(f"Both crashed! But {trailer.team_name} is classified ahead.")
            finish_logs.extend(current_lap_events)
            yield "lap", lap, current_lap_events, {}, track
            break
        elif leader.dnf:
            winner, loser = trailer, leader
            current_lap_events.append(f"🏆 **Checkered Flag!** {trailer.team_name} wins the duel!")
            finish_logs.extend(current_lap_events)
            yield "lap", lap, current_lap_events, {}, track
            break
        elif trailer.dnf:
            winner, loser = leader, trailer
            current_lap_events.append(f"🏆 **Checkered Flag!** {leader.team_name} wins the duel!")
            finish_logs.extend(current_lap_events)
            yield "lap", lap, current_lap_events, {}, track
            break
            
        # Pitting logic (automatic if not manual)
        for t in [leader, trailer]:
            if t.dnf:
                continue
            if total_laps > 3 and (lap in t.pit_laps) and t.tyre_health < 50.0:
                pit_duration = 3.5 - (t.pit_crew * 0.15)
                if t == leader:
                    gap -= pit_duration
                else:
                    gap += pit_duration
                    
                t.tyre_health = 100.0
                t.pit_stops_completed += 1
                current_lap_events.append(f"🔧 **Lap {lap}:** {t.team_name} pits for fresh {t.tyre_type} tyres (time: {pit_duration:.2f}s)!")
                
        # Calculate tyre wear based on compound choice
        for t in [leader, trailer]:
            if t.tyre_type == "Soft":
                base_wear = 12.0
            elif t.tyre_type == "Hard":
                base_wear = 4.0
            else: # Medium
                base_wear = 7.0
                
            if t.strategy == "Aggressive":
                wear = base_wear * 1.3
            elif t.strategy == "Conservative":
                wear = base_wear * 0.7
            else:
                wear = base_wear
                
            t.tyre_health -= random.uniform(wear - 1, wear + 1)
            t.tyre_health = max(0.0, t.tyre_health)
            
        # Calculate performance for this lap
        l_tyre_bonus = 8.0 if leader.tyre_type == "Soft" else (0.0 if leader.tyre_type == "Hard" else 4.0)
        t_tyre_bonus = 8.0 if trailer.tyre_type == "Soft" else (0.0 if trailer.tyre_type == "Hard" else 4.0)
        
        l_perf = leader.calculate_base_car_power(track) + (leader.driver_pace / 4.0) + l_tyre_bonus + random.uniform(0, 8)
        t_perf = trailer.calculate_base_car_power(track) + (trailer.driver_pace / 4.0) + t_tyre_bonus + random.uniform(0, 8)
        
        # Strategy bonuses
        if leader.strategy == "Aggressive":
            l_perf += 5.0
        elif leader.strategy == "Conservative":
            l_perf -= 3.0
            
        if trailer.strategy == "Aggressive":
            t_perf += 5.0
        elif trailer.strategy == "Conservative":
            t_perf -= 3.0
            
        # Tyre penalty
        if leader.tyre_health < 40.0:
            l_perf -= (40.0 - leader.tyre_health) * 0.8
        if trailer.tyre_health < 40.0:
            t_perf -= (40.0 - trailer.tyre_health) * 0.8
            
        # Shift gap
        perf_diff = (l_perf - t_perf) * 0.25
        gap += perf_diff
        
        if gap <= 0:
            gap = abs(gap)
            if gap < 0.2:
                gap = 0.5
            leader, trailer = trailer, leader
            current_lap_events.append(f"🔄 **Lap {lap}:** **{leader.team_name}** makes a brilliant overtake on **{trailer.team_name}** to take the lead!")
        else:
            if gap > 3.0:
                current_lap_events.append(f"🏎️ **Lap {lap}:** **{leader.team_name}** is pulling away, leading **{trailer.team_name}** by **{gap:.2f}s**.")
            else:
                current_lap_events.append(f"⚔️ **Lap {lap}:** **{leader.team_name}** defends hard! **{trailer.team_name}** is right on their gearbox (+**{gap:.2f}s**).")
                
        current_lap_events.append(
            f"📊 **Tyre Health:** {leader.team_name}: {max(0, int(leader.tyre_health))}% | {trailer.team_name}: {max(0, int(trailer.tyre_health))}%"
        )
        
        # End of race checks
        if lap == total_laps:
            winner, loser = leader, trailer
            current_lap_events.append(f"\n🏁 **Checkered Flag!** **{winner.team_name}** crosses the line to win the duel!")
            
        leader.laps_completed = lap
        trailer.laps_completed = lap
        
        # Build lap snapshot dictionary for telemetry views:
        lap_snapshot = {
            t1.user_id: {
                "position": 1 if leader == t1 else 2,
                "gap_to_leader": "Leader" if leader == t1 else f"+{gap:.2f}s",
                "gap_to_front": "—" if leader == t1 else f"+{gap:.2f}s",
                "tyre_type": t1.tyre_type,
                "tyre_health": t1.tyre_health,
                "dnf": t1.dnf
            },
            t2.user_id: {
                "position": 1 if leader == t2 else 2,
                "gap_to_leader": "Leader" if leader == t2 else f"+{gap:.2f}s",
                "gap_to_front": "—" if leader == t2 else f"+{gap:.2f}s",
                "tyre_type": t2.tyre_type,
                "tyre_health": t2.tyre_health,
                "dnf": t2.dnf
            }
        }
        
        yield "lap", lap, current_lap_events, lap_snapshot, track
        
    # Map back SimTeam object dicts
    w_data = team1_data.copy() if winner.user_id == team1_data["user_id"] else team2_data.copy()
    l_data = team1_data.copy() if loser.user_id == team1_data["user_id"] else team2_data.copy()
    w_data["dnf"] = winner.dnf
    l_data["dnf"] = loser.dnf
    w_data["tyre_health"] = winner.tyre_health
    l_data["tyre_health"] = loser.tyre_health
    
    yield "finish", w_data, l_data, finish_logs

def simulate_duel(team1_data: Dict[str, Any], team2_data: Dict[str, Any], total_laps: int = 1, track_name: str = None) -> Tuple[Dict[str, Any], Dict[str, Any], List[List[str]], List[str]]:
    """
    Simulate a multi-lap head-to-head race duel. Consumes the generator.
    """
    generator = simulate_duel_generator(team1_data, team2_data, total_laps, track_name)
    setup_event = next(generator)
    qual_logs = setup_event[2]
    
    lap_logs = []
    winner = None
    loser = None
    
    for item in generator:
        if item[0] == "lap":
            lap_logs.append(item[2])
        elif item[0] == "finish":
            winner = item[1]
            loser = item[2]
            
    return winner, loser, lap_logs, qual_logs
def simulate_gp_generator(entries_data: List[Dict[str, Any]], track_name: str, total_laps: int = 15, weather_timeline: List[str] = None, is_sprint: bool = False):
    """
    Generator that simulates a Grand Prix lap-by-lap, yielding intermediate states.
    Yields:
      ('setup', teams, setup_logs, current_weather)
      ('lap', lap_number, lap_logs, lap_snapshot, current_weather)
      ('finish', results_list, finish_logs)
    """
    entries_copy = [dict(e) for e in entries_data]
    human_count = len(entries_copy)
    ai_needed = max(0, 20 - human_count)
    if ai_needed > 0:
        human_names = {e.get("team_name", "").lower() for e in entries_copy}
        available_ais = [ai for ai in AI_GRID_DRIVERS if ai["team_name"].lower() not in human_names]
        selected_ais = available_ais[:ai_needed]
        entries_copy.extend(selected_ais)
        
    teams = [SimTeam(entry) for entry in entries_copy]
    
    # Assign AI Rival to each human driver
    ai_drivers = [t for t in teams if t.is_ai]
    for idx, t in enumerate(teams):
        if not t.is_ai and ai_drivers:
            t.ai_rival = ai_drivers[idx % len(ai_drivers)]

    setup_logs = [f"🚥 **Grand Prix of {track_name} - Race Start!**"]
    
    # 1. Setup track details
    track_profile = TRACK_PROFILES.get(track_name, {"sc_chance_mult": 1.0})
    sc_multiplier = track_profile.get("sc_chance_mult", 1.0)
    T_base = TRACK_BASE_LAP_TIMES.get(track_name, 45.0)
    
    # Initial weather setting
    if weather_timeline and len(weather_timeline) > 0:
        current_weather = weather_timeline[0]
    else:
        current_weather = "Sunny"
    setup_logs.append(f"🌤️ **Weather at start:** {current_weather}")
    
    # Initialize strategies and pit laps
    for t in teams:
        if current_weather == "Rain":
            t.tyre_type = "Intermediates"
            
        # Determine pit laps (space stops evenly only if no custom strategy is set)
        if not t.pit_laps:
            intervals = total_laps / (t.pref_pit_stops + 1)
            t.pit_laps = [int(round(intervals * i)) for i in range(1, t.pref_pit_stops + 1)]

    # 2. Setup starting grid positions from qualifying
    teams.sort(key=lambda x: (x.start_position if x.start_position is not None else 999))
    
    setup_logs.append("⏱️ **Qualifying grid has been established:**")
    for idx, t in enumerate(teams):
        t.grid_position = idx + 1
        t.current_position = idx + 1
        t.total_time = idx * 0.4  # Cars start with a minor staggered gap (0.4s)
        setup_logs.append(f"P{t.grid_position}: **{t.team_name}**")
        
    setup_logs.append("\n🟢 **Lights Out! The race is underway!**")
    
    # Safety Car & VSC states
    safety_car_laps_left = 0
    vsc_laps_left = 0
    
    yield ("setup", teams, setup_logs, current_weather)
    
    # Lap by lap simulation
    for lap in range(1, total_laps + 1):
        lap_logs = []
        
        # Stint strategy update check (runs at start of laps 1, 11, 21, etc.)
        if (lap - 1) % 10 == 0:
            for t in teams:
                if t.dnf:
                    continue
                if lap > 1 and t.next_block_strategy:
                    t.strategy = t.next_block_strategy
                    lap_logs.append(f"📻 *[Radio - {t.team_name}]: Stint update! Switching pacing mode to {t.strategy}.*")
        
        # Weather Radar Alerts (runs at start of lap)
        if weather_timeline:
            if lap + 1 < len(weather_timeline):
                next_weather_2 = weather_timeline[lap + 1]
                next_weather_1 = weather_timeline[lap]
                if next_weather_2 == "Rain" and next_weather_1 != "Rain" and current_weather != "Rain":
                    lap_logs.append(f"⛈️ **WEATHER RADAR:** Radar indicates rain clouds approaching! Expected to hit the track in 2 laps (Lap {lap + 2}).")
                elif next_weather_1 == "Rain" and current_weather != "Rain" and (lap == 1 or weather_timeline[lap - 2] != "Rain"):
                    lap_logs.append(f"⛈️ **WEATHER RADAR:** Rain clouds are directly overhead! Expected to hit the track next lap (Lap {lap + 1}).")
        
        # A. Weather change check
        if weather_timeline and lap <= len(weather_timeline):
            new_weather = weather_timeline[lap - 1]
            if new_weather != current_weather:
                lap_logs.append(f"🌧️ **Lap {lap}: Weather change! It is now {new_weather}.**")
                current_weather = new_weather
        else:
            if random.random() < 0.10:
                old_weather = current_weather
                current_weather = random.choice(["Sunny", "Mixed", "Rain"])
                if old_weather != current_weather:
                    lap_logs.append(f"🌧️ **Lap {lap}: Weather change! It is now {current_weather}.**")
                
        # Check for external manual DNFs set during the sleep period
        for t in teams:
            if t.dnf and not getattr(t, "dnf_announced", False):
                t.dnf_announced = True
                lap_logs.append(f"🛑 **Lap {lap}:** {t.team_name} has retired from the race (retired by driver).")

        # B. Calculate lap times for active teams
        for t in teams:
            if t.dnf:
                continue
                
            # Base lap time: T_base
            lap_time = T_base
            
            # Car upgrades bonus (shaves time)
            car_bonus = (t.engine * 0.12) + (t.aerodynamics * 0.08) + (t.ers * 0.08)
            lap_time -= car_bonus
            
            # Driver pace bonus (shaves time)
            driver_bonus = (t.driver_pace / 100.0) * 2.0
            lap_time -= driver_bonus
            
            # Tyre wear rate & simulation
            if t.tyre_type == "Soft":
                base_wear = 12.0
            elif t.tyre_type == "Hard":
                base_wear = 4.0
            else: # Medium or Intermediates
                base_wear = 7.0
                
            # Pace strategy multipliers
            strategy_wear_mult = 1.0
            strategy_lap_delta = 0.0
            
            # Safety Car / VSC pace override and wear reduction
            if safety_car_laps_left > 0:
                lap_time = T_base * 1.6 + random.uniform(-0.1, 0.1)
                strategy_wear_mult = 0.1
            elif vsc_laps_left > 0:
                lap_time = T_base * 1.3 + random.uniform(-0.15, 0.15)
                strategy_wear_mult = 0.3
            else:
                if t.strategy == "Aggressive":
                    strategy_wear_mult = 1.4
                    strategy_lap_delta = -0.8
                elif t.strategy == "Conservative":
                    strategy_wear_mult = 0.7
                    strategy_lap_delta = 1.0
                    
                lap_time += strategy_lap_delta
                
                # Driver aggression boost
                aggression_pace_boost = (t.driver_aggression - 50.0) / 10.0
                lap_time -= aggression_pace_boost
                
                # Consistency random variance
                variance_range = 0.4 * (1.5 - (t.driver_consistency / 100.0))
                lap_time += random.uniform(-variance_range, variance_range)
                
                # Driver mistake (spin)
                if random.random() < 0.02 * (1.5 - (t.driver_consistency / 100.0)):
                    spin_loss = random.uniform(8.0, 15.0)
                    lap_time += spin_loss
                    lap_logs.append(f"⚠️ **Lap {lap}:** {t.team_name} made a lockup and went wide! Lost {spin_loss:.1f}s.")
                
            # Visual progression driver aggression wear scaling
            aggression_wear_mult = 1.0 + (t.driver_aggression - 50.0) / 250.0
            t.tyre_health -= random.uniform(base_wear - 1.5, base_wear + 1.5) * strategy_wear_mult * aggression_wear_mult
            t.tyre_health = max(0.0, t.tyre_health)
            
            # Tyre wear penalty (slower as tyres degrade, bypassed during SC/VSC speed limit)
            wear_penalty = 0.0
            if t.tyre_health < 80.0 and safety_car_laps_left == 0 and vsc_laps_left == 0:
                wear_penalty = ((80.0 - t.tyre_health) ** 1.5) * 0.005
            lap_time += wear_penalty
            
            if t.tyre_health < 40.0 and random.random() < 0.15:
                lap_logs.append(f"📻 *[Radio - {t.team_name}]: Bono, my tyres are dead!*")
                
            # Weather tire compatibility penalty (bypassed during SC/VSC speed limit)
            weather_penalty = 0.0
            if safety_car_laps_left == 0 and vsc_laps_left == 0:
                if current_weather == "Rain" and t.tyre_type != "Intermediates":
                    weather_penalty = 15.0 - (t.driver_wet_skill / 10.0)
                elif current_weather == "Sunny" and t.tyre_type == "Intermediates":
                    weather_penalty = 5.0
                    t.tyre_health -= 15.0  # Extra wear
            lap_time += weather_penalty
            
            t.last_lap_time = round(lap_time, 3)

        # C. Pit stop logic
        for t in teams:
            if t.dnf:
                continue
                
            wants_pit = False
            needed_tyre = t.tyre_type
            
            if current_weather == "Rain" and t.tyre_type != "Intermediates":
                wants_pit = True
                needed_tyre = "Intermediates"
            elif current_weather == "Sunny" and t.tyre_type == "Intermediates":
                wants_pit = True
                needed_tyre = t.pref_tyres
            elif t.pit_next_lap:
                wants_pit = True
                needed_tyre = t.pit_next_lap_tyre
                t.pit_next_lap = False  # Reset scheduled flag
                
            if wants_pit:
                # Scaled pit stop cost (8s base + crew time for 45s laps)
                pit_crew_val = getattr(t, "pit_crew", 1)
                pit_duration = 3.5 - (pit_crew_val * 0.15)
                
                if safety_car_laps_left > 0 or vsc_laps_left > 0:
                    pit_loss = 3.0 + pit_duration
                    t.last_lap_time += pit_loss
                    lap_logs.append(f"🔧 **Lap {lap}:** {t.team_name} pits under **Safety Car** (switched to {needed_tyre}, pit duration: {pit_duration:.2f}s).")
                    lap_logs.append(f"📻 *[Radio - {t.team_name}]: Safety Car is deployed. Pit now for a cheap stop!*")
                else:
                    pit_loss = 8.0 + pit_duration
                    t.last_lap_time += pit_loss
                    lap_logs.append(f"🔧 **Lap {lap}:** {t.team_name} pits (switched to {needed_tyre}, pit duration: {pit_duration:.2f}s).")
                    lap_logs.append(f"📻 *[Radio - {t.team_name}]: Box, box, box! Fitting {needed_tyre} tyres.*")
                
                t.tyre_health = 100.0
                t.tyre_type = needed_tyre
                t.pit_stops_completed += 1

        # D. Reliability & DNF Checks (Disabled behind Safety Car)
        if safety_car_laps_left == 0 and vsc_laps_left == 0:
            for t in teams:
                if t.dnf:
                    continue
                    
                dnf_chance = max(0.2, 6.5 - t.reliability * 0.25)
                aggression_mult = 1.0 + (t.driver_aggression - 50.0) / 100.0
                dnf_chance *= aggression_mult
                
                if t.strategy == "Aggressive":
                    dnf_chance += 3.0
                elif t.strategy == "Conservative":
                    dnf_chance = max(0.05, dnf_chance - 2.0)
                    
                # Rain crash risk multiplier
                is_slipping = False
                if current_weather == "Rain":
                    if t.tyre_type != "Intermediates":
                        # Dry slicks on wet track: 3.5x crash chance!
                        dnf_chance *= 3.5
                        is_slipping = True
                    else:
                        # Correct wet weather tyres: 1.5x crash chance
                        dnf_chance *= 1.5
                    
                per_lap_dnf_chance = dnf_chance / total_laps
                
                if random.uniform(0, 100) < per_lap_dnf_chance:
                    t.dnf = True
                    if is_slipping:
                        reason = "spun out on dry slick tyres in the wet and hit the barrier"
                    else:
                        reasons = [
                            "suffered a catastrophic gearbox failure",
                            "crashed into the barriers after lockup",
                            "retired due to power unit issues",
                            "suffered suspension damage after hitting a curb"
                        ]
                        reason = random.choice(reasons)
                    t.dnf_reason = reason
                    lap_logs.append(f"💥 **Lap {lap}:** {t.team_name} {reason} and is **DNF**!")
                    if "crash" in reason or "barrier" in reason or "curb" in reason:
                        lap_logs.append(f"📻 *[Radio - {t.team_name}]: I've crashed! Suspension is broken, I'm out.*")
                    else:
                        lap_logs.append(f"📻 *[Radio - {t.team_name}]: Engine is losing power! I have lost power, retiring the car.*")

        # E. Accumulated time update and Safety Car / VSC Compression
        active_teams = [t for t in teams if not t.dnf]
        if len(active_teams) == 0:
            lap_logs.append(f"💀 **Lap {lap}:** All cars have retired from the race!")
            yield ("lap", lap, lap_logs, {}, current_weather)
            break
            
        for t in active_teams:
            t.total_time += t.last_lap_time
            
        # Sort by total time elapsed to establish position order
        teams.sort(key=lambda x: (x.total_time if not x.dnf else 9999999.0))
        
        # Recalculate active teams reference after sorting
        active_teams = [t for t in teams if not t.dnf]
        
        # Check if DNF occurred this lap
        dnf_this_lap_teams = [t for t in teams if t.dnf and t.laps_completed == lap]
        
        # Handle SC / VSC timers
        if safety_car_laps_left > 0:
            safety_car_laps_left -= 1
            # Pack compression: Cars are bunched up behind safety car (maximum 0.5s gaps)
            for idx in range(1, len(active_teams)):
                gap = active_teams[idx].total_time - active_teams[idx-1].total_time
                if gap > 0.5:
                    active_teams[idx].total_time = active_teams[idx-1].total_time + 0.5
            if safety_car_laps_left == 0:
                lap_logs.append(f"🟢 **Lap {lap}: Safety Car in this lap! Green flag racing resumes!**")
        elif vsc_laps_left > 0:
            vsc_laps_left -= 1
            if vsc_laps_left == 0:
                lap_logs.append(f"🟢 **Lap {lap}: Virtual Safety Car (VSC) ending! Green flag!**")
        else:
            # Trigger VSC/SC logic
            if dnf_this_lap_teams:
                # Check if it was a crash or mechanical failure
                any_crash = any("crash" in getattr(t, 'dnf_reason', '') or "barrier" in getattr(t, 'dnf_reason', '') or "curb" in getattr(t, 'dnf_reason', '') for t in dnf_this_lap_teams)
                if any_crash:
                    # Crash always triggers Safety Car (60% chance) or VSC (40% chance)
                    if random.random() < 0.6:
                        safety_car_laps_left = 4
                        lap_logs.append(f"🚨 **Lap {lap}: Safety Car deployed due to track blockage! Field bunching up.**")
                    else:
                        vsc_laps_left = 3
                        lap_logs.append(f"🟡 **Lap {lap}: Virtual Safety Car (VSC) deployed to clear debris.**")
                else:
                    # Mechanical failure has 25% chance of VSC
                    if random.random() < 0.25:
                        vsc_laps_left = 3
                        lap_logs.append(f"🟡 **Lap {lap}: Virtual Safety Car (VSC) deployed to recover stranded car.**")
                    else:
                        lap_logs.append(f"🟨 **Lap {lap}: Local Yellow Flags deployed while marshals recover the retired car.**")
            else:
                # Random incident/debris can trigger VSC/SC (5% base chance)
                if random.random() < 0.05 * sc_multiplier:
                    if random.random() < 0.4:
                        safety_car_laps_left = 4
                        lap_logs.append(f"🚨 **Lap {lap}: Safety Car deployed! Debris on track.**")
                    else:
                        vsc_laps_left = 3
                        lap_logs.append(f"🟡 **Lap {lap}: Virtual Safety Car (VSC) deployed.**")

        # F. DRS zone and Overtaking passes (Disabled under SC/VSC)
        if safety_car_laps_left == 0 and vsc_laps_left == 0:
            for pos in range(len(active_teams) - 1, 0, -1):
                back = active_teams[pos]
                front = active_teams[pos-1]
                
                gap = back.total_time - front.total_time
                
                # Within 0.6s dirty air/DRS window
                if gap <= 0.6:
                    # Calculate tyre health advantage
                    tyre_adv = max(-0.25, min(0.4, (back.tyre_health - front.tyre_health) / 100.0))
                    
                    # Calculate raw car power delta
                    power_back = back.engine * 1.5 + back.aerodynamics * 1.0 + back.ers * 1.0
                    power_front = front.engine * 1.5 + front.aerodynamics * 1.0 + front.ers * 1.0
                    power_adv = max(-0.2, min(0.3, (power_back - power_front) / 50.0))
                    
                    # DRS slipstream base is 0.45
                    overtake_chance = 0.45 + (back.driver_overtaking - front.driver_consistency) / 200.0 + (back.driver_aggression / 250.0) + tyre_adv + power_adv
                    overtake_chance = max(0.1, min(0.95, overtake_chance))
                    
                    # Check for successful pass
                    if random.random() < overtake_chance:
                        # Swap positions in sorted array
                        active_teams[pos], active_teams[pos-1] = active_teams[pos-1], active_teams[pos]
                        
                        # Adjust times: overtaking car is placed 0.2s ahead of the overtaken car
                        back.total_time = front.total_time - 0.2
                        lap_logs.append(f"⚔️ **Lap {lap}:** {back.team_name} overtakes {front.team_name} for **P{pos}**!")
                    else:
                        # Dirty air restriction: back car cannot finish ahead, cap time behind front car
                        if back.total_time < front.total_time + 0.2:
                            back.total_time = front.total_time + 0.2

        # Re-sort list after overtaking adjustments
        teams.sort(key=lambda x: (x.total_time if not x.dnf else 9999999.0))
        active_teams = [t for t in teams if not t.dnf]
        leader_time = active_teams[0].total_time if active_teams else 0.0
        
        # G. Update gap statistics and write lap snapshot
        lap_snapshot = {}
        for idx, t in enumerate(teams):
            if t.dnf:
                t.gap_to_leader = 999.9
                t.gap_to_front = 999.9
                lap_snapshot[t.user_id] = {
                    "position": None,
                    "tyre_health": 0.0,
                    "tyre_type": t.tyre_type,
                    "dnf": True,
                    "gap_to_leader": "DNF",
                    "gap_to_front": "DNF"
                }
            else:
                pos = idx + 1
                t.current_position = pos
                t.gap_to_leader = t.total_time - leader_time
                if idx == 0:
                    t.gap_to_front = 0.0
                else:
                    t.gap_to_front = t.total_time - active_teams[idx-1].total_time
                    
                lap_snapshot[t.user_id] = {
                    "position": pos,
                    "tyre_health": max(0.0, t.tyre_health),
                    "tyre_type": t.tyre_type,
                    "dnf": False,
                    "gap_to_leader": f"+{t.gap_to_leader:.3f}s" if pos > 1 else "Leader",
                    "gap_to_front": f"+{t.gap_to_front:.3f}s" if pos > 1 else "—"
                }
                
        # Increment lap counter
        for t in active_teams:
            t.laps_completed += 1
            
        yield ("lap", lap, lap_logs, lap_snapshot, current_weather)
        
    # 3. Race finished! Sort teams: active finishers first
    active_finishers = [t for t in teams if not t.dnf]
    dnf_finishers = [t for t in teams if t.dnf]
    dnf_finishers.sort(key=lambda x: x.laps_completed, reverse=True)
    
    final_order = active_finishers + dnf_finishers
    
    # Find fastest lap driver
    fastest_driver = None
    min_fl_time = 999.9
    for t in teams:
        if getattr(t, 'fastest_lap_time', 999.9) < min_fl_time:
            min_fl_time = t.fastest_lap_time
            fastest_driver = t
            
    is_sprint_event = is_sprint or track_profile.get("is_sprint", False)
    points_distribution = config.SPRINT_POINTS_DISTRIBUTION if is_sprint_event else config.GP_POINTS_DISTRIBUTION
    
    results_list = []
    finish_logs = ["\n🏁 **Checkered Flag! The race is finished!**"]
    
    if fastest_driver and min_fl_time < 900.0:
        finish_logs.append(f"⚡ **Fastest Lap:** **{fastest_driver.team_name}** (`{min_fl_time:.3f}s`)")
        
    for idx, t in enumerate(final_order):
        pos = idx + 1
        
        # Base points distribution
        if not t.dnf and pos <= len(points_distribution):
            points = points_distribution[pos - 1]
        else:
            points = 0
            
        # Fastest lap bonus point (must finish in top 10 and not DNF)
        if fastest_driver and t.user_id == fastest_driver.user_id and not t.dnf and pos <= 10:
            points += 1
            finish_logs.append(f"🟣 **{t.team_name}** earned **+1 Bonus Point** for Fastest Lap!")
            
        credits_won = config.GP_BASE_PARTICIPATION_REWARD
        if not t.dnf and pos in config.GP_PODIUM_REWARDS:
            credits_won += config.GP_PODIUM_REWARDS[pos]
            
        # AI Rival defeat bonus for human drivers
        rival_msg = ""
        if not t.is_ai and t.ai_rival:
            # Check if human finished ahead of AI rival
            if not t.dnf and (t.ai_rival.dnf or pos < t.ai_rival.current_position):
                credits_won += 500
                rival_msg = f" ⚔️ *(Defeated AI Rival {t.ai_rival.team_name}: +500¢!)*"
                
        if not t.is_ai:
            finish_logs.append(f"P{pos}: **{t.team_name}** {'(DNF)' if t.dnf else ''} — Points: +{points}, Credits: +{credits_won}¢{rival_msg}")
        else:
            finish_logs.append(f"P{pos}: 🤖 **{t.team_name}** {'(DNF)' if t.dnf else ''} — Points: +{points}")
            
        results_list.append({
            "user_id": t.user_id,
            "discord_id": t.discord_id,
            "team_name": t.team_name,
            "finish_position": pos,
            "points_earned": points,
            "credits_won": credits_won if not t.is_ai else 0,
            "dnf": t.dnf,
            "is_ai": t.is_ai
        })
        
    yield ("finish", results_list, finish_logs)

def simulate_gp(entries_data: List[Dict[str, Any]], track_name: str, total_laps: int = 15, weather_timeline: List[str] = None, is_sprint: bool = False) -> Tuple[List[Dict[str, Any]], List[str], Dict[int, Any]]:
    """
    Backward-compatible wrapper around simulate_gp_generator.
    """
    generator = simulate_gp_generator(entries_data, track_name, total_laps, weather_timeline, is_sprint=is_sprint)
    
    setup_event = next(generator)
    setup_logs = setup_event[2]
    
    all_logs = []
    all_logs.extend(setup_logs)
    
    lap_states = {}
    results_list = []
    
    for item in generator:
        if item[0] == "lap":
            lap_num = item[1]
            lap_logs = item[2]
            lap_snapshot = item[3]
            lap_states[lap_num] = lap_snapshot
            all_logs.extend(lap_logs)
        elif item[0] == "finish":
            results_list = item[1]
            finish_logs = item[2]
            all_logs.extend(finish_logs)
            
    return results_list, all_logs, lap_states

# --- F1 Qualifying Weekend Simulation ---
TRACK_BASE_LAP_TIMES = {
    "Monaco": 47.0,
    "Monza": 43.0,
    "Spa": 49.0,
    "Silverstone": 45.0,
    "Singapore": 48.0,
    "Suzuka": 46.0,
    "Bahrain": 44.0
}

def format_lap_time(seconds: float) -> str:
    """Format lap time in seconds into F1 standard format MM:SS.mmm"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}:{secs:06.3f}"
    return f"{secs:.3f}"

def simulate_quali_session(entries: List[Dict[str, Any]], track_name: str, session_name: str) -> List[Dict[str, Any]]:
    """
    Simulate a qualifying session (Q1, Q2, or Q3).
    Returns the list of entries with simulated lap times sorted from fastest to slowest.
    """
    base_time = TRACK_BASE_LAP_TIMES.get(track_name, 90.0)
    results = []
    
    for entry in entries:
        t = SimTeam(entry)
        car_power = t.calculate_base_car_power(track_name)
        
        # Qual driver rating bonus
        qual_bonus = t.driver_qual / 2.0
        
        # Tyre compound bonus (Soft/Medium/Hard)
        q_tyre = entry.get("current_q_tyre", "Soft")
        if q_tyre == "Soft":
            tyre_bonus = 6.0
        elif q_tyre == "Hard":
            tyre_bonus = 0.0
        else: # Medium
            tyre_bonus = 3.0
            
        perf = car_power + qual_bonus + tyre_bonus
        
        # Base time minus performance reduction plus minor variance
        lap_time = base_time - (perf * 0.12) + random.uniform(-0.3, 0.3)
        lap_time = round(lap_time, 3)
        
        res_entry = entry.copy()
        res_entry["quali_time"] = lap_time
        res_entry["current_q_tyre"] = q_tyre
        results.append(res_entry)
        
    results.sort(key=lambda x: x["quali_time"])
    return results
