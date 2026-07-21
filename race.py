import random
from typing import List, Dict, Any, Tuple
import config
import utils

# Track definitions with modifiers
TRACK_PROFILES = {
    "Monaco": {"description": "Tight street circuit, aerodynamics is king.", "aero_mod": 1.5, "engine_mod": 0.8},
    "Monza": {"description": "The Temple of Speed, engine power dominates.", "aero_mod": 0.8, "engine_mod": 1.5},
    "Spa": {"description": "Legendary fast corners and long straights, balanced requirements.", "aero_mod": 1.2, "engine_mod": 1.2},
    "Silverstone": {"description": "High speed sweeping corners, tests tyres and aerodynamics.", "aero_mod": 1.3, "tyre_mod": 1.3},
    "Singapore": {"description": "Hot, humid street circuit. High wear and high safety car risk.", "tyre_mod": 1.4, "sc_chance_mult": 1.5},
    "Suzuka": {"description": "Technical track, rewards balanced setups.", "aero_mod": 1.1, "engine_mod": 1.1, "tyre_mod": 1.1},
    "Bahrain": {"description": "Heavy braking, rewards ERS & tyres.", "engine_mod": 1.2, "tyre_mod": 1.3}
}

class SimTeam:
    """Class to wrap team, driver, strategist, and car stats for the race simulation."""
    def __init__(self, data: Dict[str, Any]):
        self.user_id = data["user_id"]
        self.team_name = data["team_name"]
        self.discord_id = data["discord_id"]
        
        # Car Stats
        self.engine = data.get("engine", 1)
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
                
        self.strategy = self.pit_strategy.get("pace", self.pref_strategy)
        self.tyre_type = self.pit_strategy.get("start_tyre", self.pref_tyres)
        
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
        """Calculate car power adjusted for track profiles and existing damage."""
        # Get track modifiers
        profile = TRACK_PROFILES.get(track_name, {"aero_mod": 1.0, "engine_mod": 1.0, "tyre_mod": 1.0})
        aero_mult = profile.get("aero_mod", 1.0)
        eng_mult = profile.get("engine_mod", 1.0)
        tyre_mult = profile.get("tyre_mod", 1.0)
        
        # Weighted car power
        engine_contrib = self.engine * 3.0 * eng_mult
        aero_contrib = self.aerodynamics * 2.0 * aero_mult
        tyre_contrib = self.tyres_stat * 2.0 * tyre_mult
        ers_contrib = self.ers * 2.0
        reliability_contrib = self.reliability * 1.0
        
        base_power = engine_contrib + aero_contrib + tyre_contrib + ers_contrib + reliability_contrib
        
        # Apply damage penalty: e.g. -1% power per 10% damage_total
        damage_penalty = (self.damage_total / 10.0) / 100.0 # percentage penalty
        base_power *= (1.0 - min(0.5, damage_penalty)) # cap damage penalty at 50%
        
        return base_power

def simulate_duel(team1_data: Dict[str, Any], team2_data: Dict[str, Any], total_laps: int = 1) -> Tuple[Dict[str, Any], Dict[str, Any], List[List[str]], List[str]]:
    """
    Simulate a multi-lap head-to-head race duel.
    Returns (winner_data, loser_data, lap_logs, qual_logs).
    """
    t1 = SimTeam(team1_data)
    t2 = SimTeam(team2_data)
    
    qual_logs = ["🏁 **Duel Start!** Lights out and away we go!"]
    
    # Randomly select a track for the duel
    track = random.choice(list(TRACK_PROFILES.keys()))
    qual_logs.append(f"📍 Track: **{track}** - {TRACK_PROFILES[track]['description']}")
    
    # Space pit stops evenly if total laps > 3
    for t in [t1, t2]:
        if total_laps > 3:
            intervals = total_laps / (t.pref_pit_stops + 1)
            t.pit_laps = [int(round(intervals * i)) for i in range(1, t.pref_pit_stops + 1)]
        else:
            t.pit_laps = []
            
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
    
    # We will track the gap (in seconds). Let's start the gap at 1.0s.
    gap = 1.0
    lap_logs = []
    
    for lap in range(1, total_laps + 1):
        current_lap_events = []
        
        # Check DNF for both active drivers
        for t in [leader, trailer]:
            if t.dnf:
                continue
            # Scaled crashes: base of 6.5% scaled by reliability
            dnf_chance = max(0.2, 6.5 - t.reliability * 0.25)
            if t.strategy == "Aggressive":
                dnf_chance += 3.0
            elif t.strategy == "Conservative":
                dnf_chance = max(0.05, dnf_chance - 2.0)
                
            # Scaled down per-lap (since dnf_chance is per-race)
            per_lap_dnf_chance = dnf_chance / total_laps
                
            if random.uniform(0, 100) < per_lap_dnf_chance:
                t.dnf = True
                reasons = ["spun off into the barriers", "suffered an engine blowup", "had a gearbox failure", "collided with a competitor"]
                t.dnf_reason = random.choice(reasons)
                current_lap_events.append(f"💥 **CRASH!** {t.team_name} {t.dnf_reason} and is out of the race!")
                
        # Handle DNFs
        if leader.dnf and trailer.dnf:
            # Both crashed, random classification
            if random.random() < 0.5:
                winner, loser = leader, trailer
                current_lap_events.append(f"Both crashed! But {leader.team_name} is classified ahead.")
            else:
                winner, loser = trailer, leader
                current_lap_events.append(f"Both crashed! But {trailer.team_name} is classified ahead.")
            lap_logs.append(current_lap_events)
            break
        elif leader.dnf:
            winner, loser = trailer, leader
            current_lap_events.append(f"🏆 **Checkered Flag!** {trailer.team_name} wins the duel!")
            lap_logs.append(current_lap_events)
            break
        elif trailer.dnf:
            winner, loser = leader, trailer
            current_lap_events.append(f"🏆 **Checkered Flag!** {leader.team_name} wins the duel!")
            lap_logs.append(current_lap_events)
            break
            
        # Pitting logic in Duels
        for t in [leader, trailer]:
            if t.dnf:
                continue
            # Pit ONLY if scheduled lap and total laps > 3
            if total_laps > 3 and (lap in t.pit_laps):
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
            
        # Tyre penalty (Steeper penalty when tyres are worn)
        if leader.tyre_health < 40.0:
            l_perf -= (40.0 - max(0.0, leader.tyre_health)) * 0.8
        if trailer.tyre_health < 40.0:
            t_perf -= (40.0 - max(0.0, trailer.tyre_health)) * 0.8
            
        # Performance difference shifts the gap
        # If leader was faster, gap increases. If trailer was faster, gap decreases.
        perf_diff = (l_perf - t_perf) * 0.25 # scaling factor
        gap += perf_diff
        
        if gap <= 0:
            # Trailer overtakes!
            gap = abs(gap)
            if gap < 0.2:
                gap = 0.5 # keep some minimal gap
            leader, trailer = trailer, leader
            current_lap_events.append(f"🔄 **Lap {lap}:** **{leader.team_name}** makes a brilliant overtake on **{trailer.team_name}** to take the lead!")
        else:
            # No overtake, describe state
            if gap > 3.0:
                current_lap_events.append(f"🏎️ **Lap {lap}:** **{leader.team_name}** is pulling away, leading **{trailer.team_name}** by **{gap:.2f}s**.")
            else:
                current_lap_events.append(f"⚔️ **Lap {lap}:** **{leader.team_name}** defends hard! **{trailer.team_name}** is right on their gearbox (+**{gap:.2f}s**).")
                
        # Tyre status stats string
        current_lap_events.append(
            f"📊 **Tyre Health:** {leader.team_name}: {max(0, int(leader.tyre_health))}% | {trailer.team_name}: {max(0, int(trailer.tyre_health))}%"
        )
        
        # End of race checks
        if lap == total_laps:
            winner, loser = leader, trailer
            current_lap_events.append(f"\n🏁 **Checkered Flag!** **{winner.team_name}** crosses the line to win the duel!")
            
        lap_logs.append(current_lap_events)
        
    # Map back SimTeam object dicts
    w_data = team1_data.copy() if winner.user_id == team1_data["user_id"] else team2_data.copy()
    l_data = team1_data.copy() if loser.user_id == team1_data["user_id"] else team2_data.copy()
    
    w_data["dnf"] = winner.dnf
    l_data["dnf"] = loser.dnf
    w_data["tyre_health"] = winner.tyre_health
    l_data["tyre_health"] = loser.tyre_health
    
    return w_data, l_data, lap_logs, qual_logs
def simulate_gp_generator(entries_data: List[Dict[str, Any]], track_name: str, total_laps: int = 15, weather_timeline: List[str] = None):
    """
    Generator that simulates a Grand Prix lap-by-lap, yielding intermediate states.
    Yields:
      ('setup', teams, setup_logs, current_weather)
      ('lap', lap_number, lap_logs, lap_snapshot, current_weather)
      ('finish', results_list, finish_logs)
    """
    teams = [SimTeam(entry) for entry in entries_data]
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
    
    results_list = []
    finish_logs = ["\n🏁 **Checkered Flag! The race is finished!**"]
    
    for idx, t in enumerate(final_order):
        pos = idx + 1
        points = utils.get_points_for_position(pos) if not t.dnf else 0
        
        credits_won = config.GP_BASE_PARTICIPATION_REWARD
        if not t.dnf and pos in config.GP_PODIUM_REWARDS:
            credits_won += config.GP_PODIUM_REWARDS[pos]
            
        finish_logs.append(f"P{pos}: **{t.team_name}** {'(DNF)' if t.dnf else ''} - Points: +{points}, Credits: +{credits_won}¢")
        
        results_list.append({
            "user_id": t.user_id,
            "discord_id": t.discord_id,
            "team_name": t.team_name,
            "finish_position": pos,
            "points_earned": points,
            "credits_won": credits_won,
            "dnf": t.dnf
        })
        
    yield ("finish", results_list, finish_logs)

def simulate_gp(entries_data: List[Dict[str, Any]], track_name: str, total_laps: int = 15, weather_timeline: List[str] = None) -> Tuple[List[Dict[str, Any]], List[str], Dict[int, Any]]:
    """
    Backward-compatible wrapper around simulate_gp_generator.
    """
    generator = simulate_gp_generator(entries_data, track_name, total_laps, weather_timeline)
    
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
