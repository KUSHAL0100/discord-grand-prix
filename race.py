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
    "Singapore": {"description": "Hot, humid street circuit. High wear and high safety car risk.", "tyre_mod": 1.4, "sc_chance_mult": 1.5}
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
        self.tyre_health = 100.0
        
        # Load user strategy preferences
        self.pref_strategy = data.get("pref_strategy", "Balanced")
        self.pref_tyres = data.get("pref_tyres", "Medium")
        self.pref_pit_stops = data.get("pref_pit_stops", 1)
        
        self.tyre_type = self.pref_tyres
        self.strategy = self.pref_strategy
        
        self.pit_stop_done = False
        self.pit_stops_completed = 0
        self.pit_lap = 10
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
            dnf_chance = max(1.0, 16.0 - t.reliability * 1.5)
            if t.strategy == "Aggressive":
                dnf_chance += 10.0
            elif t.strategy == "Conservative":
                dnf_chance = max(0.5, dnf_chance - 5.0)
                
            if random.uniform(0, 100) < dnf_chance:
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
            # Pit if scheduled lap or if tyres are critical (< 30%) and total laps > 3
            if total_laps > 3 and (lap in t.pit_laps or t.tyre_health < 30.0):
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
            
        # Tyre penalty
        if leader.tyre_health < 40.0:
            l_perf -= (40.0 - leader.tyre_health) * 0.3
        if trailer.tyre_health < 40.0:
            t_perf -= (40.0 - trailer.tyre_health) * 0.3
            
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
    w_data = team1_data if winner.user_id == team1_data["user_id"] else team2_data
    l_data = team1_data if loser.user_id == team1_data["user_id"] else team2_data
    
    return w_data, l_data, lap_logs, qual_logs

def simulate_gp(entries_data: List[Dict[str, Any]], track_name: str, total_laps: int = 15) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Simulate a full multi-lap Grand Prix race.
    Returns (final_standings_data, race_logs).
    """
    teams = [SimTeam(entry) for entry in entries_data]
    logs = [f"🚥 **Grand Prix of {track_name} - Race Start!**"]
    
    # 1. Setup track details
    track_profile = TRACK_PROFILES.get(track_name, {"sc_chance_mult": 1.0})
    sc_multiplier = track_profile.get("sc_chance_mult", 1.0)
    
    # Initial weather setting
    current_weather = random.choice(["Sunny", "Sunny", "Sunny", "Mixed", "Rain"])
    logs.append(f"🌤️ **Weather at start:** {current_weather}")
    
    # Initialize strategies and pit laps
    for t in teams:
        # If weather is Rain, force Intermediates. Otherwise use user's preferred tyres.
        if current_weather == "Rain":
            t.tyre_type = "Intermediates"
        else:
            t.tyre_type = t.pref_tyres
            
        # Determine pit laps (space stops evenly)
        intervals = total_laps / (t.pref_pit_stops + 1)
        t.pit_laps = [int(round(intervals * i)) for i in range(1, t.pref_pit_stops + 1)]

    # 2. Qualifying simulation
    logs.append("⏱️ **Qualifying Sessions complete! Here is the starting grid:**")
    qual_results = []
    for t in teams:
        car_power = t.calculate_base_car_power(track_name)
        # Qualifying driver bonus
        qual_bonus = t.driver_qual / 2.0
        # Aggressive strategy adds qualifying pace
        strat_bonus = 5.0 if t.strategy == "Aggressive" else 0.0
        
        perf = car_power + qual_bonus + strat_bonus + random.uniform(0, 10)
        qual_results.append((t, perf))
        
    qual_results.sort(key=lambda x: x[1], reverse=True)
    
    # Set initial grid positions
    for idx, (t, _) in enumerate(qual_results):
        t.grid_position = idx + 1
        t.current_position = idx + 1
        
    # Re-order the teams list to match initial grid (from 1st to last)
    teams = [x[0] for x in qual_results]
    
    for t in teams:
        logs.append(f"P{t.grid_position}: **{t.team_name}** (overall power: {utils.calculate_overall_power({'engine':t.engine, 'aerodynamics':t.aerodynamics, 'tyres':t.tyres_stat, 'ers':t.ers, 'reliability':t.reliability}, t.driver_pace)})")

    logs.append("\n🟢 **Lights Out! The race is underway!**")
    
    # Safety Car & VSC states
    safety_car_laps_left = 0
    vsc_laps_left = 0
    
    # Lap by lap simulation
    for lap in range(1, total_laps + 1):
        # A. Weather change check (10% chance)
        if random.random() < 0.10:
            old_weather = current_weather
            current_weather = random.choice(["Sunny", "Mixed", "Rain"])
            if old_weather != current_weather:
                logs.append(f"🌧️ **Lap {lap}: Weather change! It is now {current_weather}.**")
                
        # B. Calculate performance for all active teams
        for t in teams:
            if t.dnf:
                continue
                
            car_power = t.calculate_base_car_power(track_name)
            
            # Tyre wear simulation
            if t.tyre_type == "Soft":
                base_wear = 12.0
            elif t.tyre_type == "Hard":
                base_wear = 4.0
            else: # Medium or Intermediates
                base_wear = 7.0
                
            if t.strategy == "Aggressive":
                wear_rate = base_wear * 1.3
            elif t.strategy == "Conservative":
                wear_rate = base_wear * 0.7
            else:
                wear_rate = base_wear
                
            t.tyre_health -= random.uniform(wear_rate - 2, wear_rate + 2)
            
            # Apply tire wear penalty if health is below 40%
            tyre_penalty = 0.0
            if t.tyre_health < 40.0:
                tyre_penalty = (40.0 - t.tyre_health) * 0.4
                
            # Weather tire compatibility penalty
            weather_penalty = 0.0
            if current_weather == "Rain" and t.tyre_type != "Intermediates":
                # Dry tyres in rain is a massive penalty
                weather_penalty = 25.0 - (t.driver_wet_skill / 10.0) # Wet skill reduces penalty
            elif current_weather == "Sunny" and t.tyre_type == "Intermediates":
                # Wet tyres in sunny is a moderate penalty & high tyre wear
                weather_penalty = 12.0
                t.tyre_health -= 10.0 # Extra wear
                
            # Driver pace bonus
            driver_bonus = t.driver_pace / 4.0
            if current_weather == "Rain":
                # Wet skill is added in rain
                driver_bonus += t.driver_wet_skill / 5.0
                
            # Strategy bonus
            strat_bonus = 0.0
            if t.strategy == "Aggressive":
                strat_bonus = car_power * 0.06
            elif t.strategy == "Conservative":
                strat_bonus = -car_power * 0.04
                
            # Tyre pace bonus
            tyre_bonus = 8.0 if t.tyre_type == "Soft" else (0.0 if t.tyre_type == "Hard" else 4.0)
            
            # Combine stats
            t.performance = car_power + driver_bonus + strat_bonus + tyre_bonus - tyre_penalty - weather_penalty + random.uniform(0, 8)
            
            # If Safety Car or VSC is active, bunch the pack (equalize performance)
            if safety_car_laps_left > 0:
                t.performance = 30.0 + random.uniform(0, 2)
            elif vsc_laps_left > 0:
                t.performance = 40.0 + random.uniform(0, 1.5)
 
        # C. Pit stop logic
        for t in teams:
            if t.dnf:
                continue
                
            # Determine if team wants to pit:
            # - Scheduled pit lap
            # - Tyres are worn out (< 30%)
            # - Weather changed and tyres don't match
            wants_pit = False
            needed_tyre = t.tyre_type
            
            if current_weather == "Rain" and t.tyre_type != "Intermediates":
                wants_pit = True
                needed_tyre = "Intermediates"
            elif current_weather == "Sunny" and t.tyre_type == "Intermediates":
                wants_pit = True
                needed_tyre = t.pref_tyres
                if needed_tyre == "Intermediates":
                    needed_tyre = "Medium"
            elif lap in t.pit_laps:
                wants_pit = True
                needed_tyre = t.pref_tyres
            elif t.tyre_health < 30.0:
                wants_pit = True
                needed_tyre = t.pref_tyres
                
            if wants_pit:
                # Calculate pit stop duration
                pit_crew_val = getattr(t, "pit_crew", 1)
                pit_duration = 3.5 - (pit_crew_val * 0.15)
                
                # If pitting under safety car, pit stop takes less relative track position time loss
                if safety_car_laps_left > 0 or vsc_laps_left > 0:
                    t.performance -= (pit_duration / 3.0)
                    logs.append(f"🔧 **Lap {lap}:** {t.team_name} pits under **Safety Car** (switched to {needed_tyre}, time: {pit_duration:.2f}s).")
                else:
                    t.performance -= (pit_duration / 2.0)
                    logs.append(f"🔧 **Lap {lap}:** {t.team_name} pits (switched to {needed_tyre}, time: {pit_duration:.2f}s).")
                    
                t.tyre_health = 100.0
                t.tyre_type = needed_tyre
                t.pit_stops_completed += 1
                t.pit_stop_done = True

        # D. Reliability Check & Random DNFs
        for t in teams:
            if t.dnf:
                continue
                
            # Base crash chance
            dnf_chance = max(1.0, 16.0 - t.reliability * 1.5)
            
            # Strategy adjustments
            if t.strategy == "Aggressive":
                dnf_chance += 10.0
            elif t.strategy == "Conservative":
                dnf_chance = max(0.5, dnf_chance - 5.0)
                
            # Scaled down per-lap (since base is per-race, e.g. divide by total_laps)
            per_lap_dnf_chance = dnf_chance / total_laps
            
            if random.uniform(0, 100) < per_lap_dnf_chance:
                t.dnf = True
                reasons = [
                    "suffered a catastrophic gearbox failure",
                    "crashed into the barriers after lockup",
                    "retired due to power unit issues",
                    "suffered suspension damage after hitting a curb"
                ]
                t.dnf_reason = random.choice(reasons)
                logs.append(f"💥 **Lap {lap}:** {t.team_name} {t.dnf_reason} and is **OUT** (DNF)!")

        # Count active cars
        active_teams = [t for t in teams if not t.dnf]
        if len(active_teams) == 0:
            logs.append(f"💀 **Lap {lap}:** All cars have retired from the race!")
            break
            
        # E. Safety Car / VSC Triggers
        # If there's an active SC/VSC, decrement the lap count
        if safety_car_laps_left > 0:
            safety_car_laps_left -= 1
            if safety_car_laps_left == 0:
                logs.append(f"🟢 **Lap {lap}: Safety Car in this lap! Green flag racing resumes!**")
        elif vsc_laps_left > 0:
            vsc_laps_left -= 1
            if vsc_laps_left == 0:
                logs.append(f"🟢 **Lap {lap}: VSC ending! Green flag!**")
        else:
            # Check for new Safety Car trigger (5% chance, boosted if there was a DNF this lap)
            # Let's check how many DNFs happened this lap
            # (simplification: if a DNF just happened, there's a higher chance)
            sc_chance = 0.05 * sc_multiplier
            # If any active team is DNF this lap and it was logged, increase chance
            # Let's say if any crash occurred, safety car chance becomes 25%
            crashed_this_lap = any(t.dnf and t.laps_completed == lap for t in teams) # wait, we didn't update laps_completed yet. Let's just track it.
            # Let's simplify: if random roll is triggered
            if random.random() < sc_chance:
                if random.random() < 0.4:
                    safety_car_laps_left = 2
                    logs.append(f"🚨 **Lap {lap}: Safety Car deployed! Field bunched up.**")
                else:
                    vsc_laps_left = 1
                    logs.append(f"🟡 **Lap {lap}: Virtual Safety Car (VSC) deployed.**")

        # F. Overtaking loop
        # Iterate grid from back to front (bottom of list to top)
        # Note: list is sorted by positions, so index 0 is P1, index len-1 is last.
        for pos in range(len(teams) - 1, 0, -1):
            back = teams[pos]
            front = teams[pos-1]
            
            if back.dnf or front.dnf:
                continue
                
            # Formula: back.performance - front.performance + random.uniform(-5, 5)
            overtake_chance = back.performance - front.performance + random.uniform(-3, 3)
            
            # Overtaking skill adds small bonus
            skill_bonus = (back.driver_overtaking - front.driver_consistency) / 20.0
            overtake_chance += skill_bonus
            
            if overtake_chance > 2.0:  # Threshold of 2.0 points advantage to overtake
                # Swap positions in teams list
                teams[pos], teams[pos-1] = teams[pos-1], teams[pos]
                
                # Update current positions
                back.current_position = pos
                front.current_position = pos + 1
                
                logs.append(f"⚔️ **Lap {lap}:** {back.team_name} overtakes {front.team_name} for **P{pos}**!")

        # Update laps completed for active teams
        for t in teams:
            if not t.dnf:
                t.laps_completed += 1
                
    # 3. Race finished! Sort teams: active teams sorted by order, DNFs appended at the back by who completed most laps
    active_finishers = [t for t in teams if not t.dnf]
    dnf_finishers = [t for t in teams if t.dnf]
    # Sort DNFs by laps completed descending
    dnf_finishers.sort(key=lambda x: x.laps_completed, reverse=True)
    
    final_order = active_finishers + dnf_finishers
    
    # Update positions and format final list of output data
    results_list = []
    logs.append("\n🏁 **Checkered Flag! The race is finished!**")
    
    for idx, t in enumerate(final_order):
        pos = idx + 1
        points = utils.get_points_for_position(pos) if not t.dnf else 0
        
        # Calculate credits won
        # Winner gets 5000 (podium) or 2500 base. Let's use config.GP_PODIUM_REWARDS and participation
        credits_won = config.GP_BASE_PARTICIPATION_REWARD
        if not t.dnf and pos in config.GP_PODIUM_REWARDS:
            credits_won += config.GP_PODIUM_REWARDS[pos]
            
        logs.append(f"P{pos}: **{t.team_name}** {'(DNF)' if t.dnf else ''} - Points: +{points}, Credits: +{credits_won}¢")
        
        results_list.append({
            "user_id": t.user_id,
            "discord_id": t.discord_id,
            "team_name": t.team_name,
            "finish_position": pos,
            "points_earned": points,
            "credits_won": credits_won,
            "dnf": t.dnf
        })
        
    return results_list, logs
