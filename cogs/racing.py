import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import asyncio

import config
import database
import utils
import race
import crates

# Active Races Registry for Live Telemetry Updates
ACTIVE_RACES = {}

class RacePaceView(discord.ui.View):
    def __init__(self, user1_id, user2_id, guild_id, p1_default="Balanced", p2_default="Balanced"):
        super().__init__(timeout=60.0)
        self.user1_id = user1_id
        self.user2_id = user2_id
        self.guild_id = guild_id
        self.p1_strategy = p1_default
        self.p2_strategy = p2_default
        self.p1_done = False
        self.p2_done = False
        self.ready_event = asyncio.Event()

    def check_done(self):
        if self.p1_done and self.p2_done:
            self.ready_event.set()

    @discord.ui.button(label="🔥 Push", style=discord.ButtonStyle.danger)
    async def push_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user1_id:
            self.p1_strategy = "Push"
            self.p1_done = True
            await interaction.response.send_message("✅ **Driver 1:** Selected **Push (Aggressive)** pace!", ephemeral=True)
            self.check_done()
        elif interaction.user.id == self.user2_id:
            self.p2_strategy = "Push"
            self.p2_done = True
            await interaction.response.send_message("✅ **Driver 2:** Selected **Push (Aggressive)** pace!", ephemeral=True)
            self.check_done()
        else:
            await interaction.response.send_message("❌ You are not a participating driver in this race.", ephemeral=True)

    @discord.ui.button(label="🟡 Standard", style=discord.ButtonStyle.primary)
    async def standard_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user1_id:
            self.p1_strategy = "Balanced"
            self.p1_done = True
            await interaction.response.send_message("✅ **Driver 1:** Selected **Standard (Balanced)** pace!", ephemeral=True)
            self.check_done()
        elif interaction.user.id == self.user2_id:
            self.p2_strategy = "Balanced"
            self.p2_done = True
            await interaction.response.send_message("✅ **Driver 2:** Selected **Standard (Balanced)** pace!", ephemeral=True)
            self.check_done()
        else:
            await interaction.response.send_message("❌ You are not a participating driver in this race.", ephemeral=True)

    @discord.ui.button(label="🟢 Save", style=discord.ButtonStyle.success)
    async def save_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user1_id:
            self.p1_strategy = "Conservative"
            self.p1_done = True
            await interaction.response.send_message("✅ **Driver 1:** Selected **Save (Conservative)** pace!", ephemeral=True)
            self.check_done()
        elif interaction.user.id == self.user2_id:
            self.p2_strategy = "Conservative"
            self.p2_done = True
            await interaction.response.send_message("✅ **Driver 2:** Selected **Save (Conservative)** pace!", ephemeral=True)
            self.check_done()
        else:
            await interaction.response.send_message("❌ You are not a participating driver in this race.", ephemeral=True)

class DuelRematchView(discord.ui.View):
    def __init__(self, challenger_prof, opponent_prof, guild_id, wager=0, laps=3, track_name=None):
        super().__init__(timeout=120.0)
        self.challenger_prof = challenger_prof
        self.opponent_prof = opponent_prof
        self.guild_id = guild_id
        self.wager = wager
        self.laps = laps
        self.track_name = track_name

    @discord.ui.button(label="🔁 Quick Rematch", style=discord.ButtonStyle.primary)
    async def rematch_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger_prof['discord_id'], self.opponent_prof['discord_id']]:
            await interaction.response.send_message("❌ Only the duel competitors can trigger a rematch!", ephemeral=True)
            return

        parent_channel = interaction.channel.parent or interaction.channel
        new_view = RaceChallengeView(self.challenger_prof, self.opponent_prof, self.guild_id, wager=self.wager, laps=self.laps, track_name=self.track_name)
        wager_text = f"\n💰 **Wager Amount:** `{self.wager:,} credits`" if self.wager > 0 else ""
        track_text = f"\n📍 **Track venue:** `{self.track_name}`" if self.track_name else ""
        embed = utils.create_embed(
            title=f"🏁 1v1 Race Rematch ({self.laps} Laps)!",
            description=(
                f"🔁 **REMATCH OFFERED!**\n"
                f"<@{self.challenger_prof['discord_id']}> (**{self.challenger_prof['team_name']}**) vs <@{self.opponent_prof['discord_id']}> (**{self.opponent_prof['team_name']}**)!{track_text}{wager_text}\n\n"
                f"Click **Accept Challenge** to line up on the grid!"
            ),
            color=utils.COLOR_QUALIFYING
        )
        await parent_channel.send(content=f"<@{self.opponent_prof['discord_id']}>", embed=embed, view=new_view)
        await interaction.response.send_message("✅ Rematch challenge issued in main channel!", ephemeral=True)
        self.stop()

class DuelSpectatorCheerView(discord.ui.View):
    def __init__(self, thread_id, p1_id, p1_name, p1_discord_id, p2_id, p2_name, p2_discord_id):
        super().__init__(timeout=86400.0)
        self.thread_id = thread_id
        self.p1_id = p1_id
        self.p1_name = p1_name
        self.p1_discord_id = p1_discord_id
        self.p2_id = p2_id
        self.p2_name = p2_name
        self.p2_discord_id = p2_discord_id
        self.entries_list = [
            {"user_id": p1_id, "discord_id": p1_discord_id, "team_name": p1_name},
            {"user_id": p2_id, "discord_id": p2_discord_id, "team_name": p2_name}
        ]
        self.update_button_labels()

    def update_button_labels(self):
        race_state = ACTIVE_RACES.get(self.thread_id)
        c1 = 0
        c2 = 0
        if race_state and "cheers" in race_state:
            c1 = race_state["cheers"].get(self.p1_id, 0)
            c2 = race_state["cheers"].get(self.p2_id, 0)
        self.cheer_p1.label = f"💙 Cheer Team 1 ({c1})"
        self.cheer_p2.label = f"❤️ Cheer Team 2 ({c2})"

    @discord.ui.button(label="💙 Cheer Team 1", style=discord.ButtonStyle.primary, custom_id="duel_cheer_p1", row=0)
    async def cheer_p1(self, interaction: discord.Interaction, button: discord.ui.Button):
        race_state = ACTIVE_RACES.get(self.thread_id)
        if race_state and "cheers" in race_state:
            cheered_users = race_state.setdefault("cheered_users", set())
            if interaction.user.id in cheered_users:
                await interaction.response.send_message("❌ You have already cheered in this race!", ephemeral=True)
                return
            cheered_users.add(interaction.user.id)
            race_state["cheers"][self.p1_id] = race_state["cheers"].get(self.p1_id, 0) + 1
            count = race_state["cheers"][self.p1_id]
            self.update_button_labels()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"💙 You cheered for **{self.p1_name}**! Total Cheers: `{count}`", ephemeral=True)
        else:
            await interaction.response.send_message("🎉 Thanks for cheering!", ephemeral=True)

    @discord.ui.button(label="❤️ Cheer Team 2", style=discord.ButtonStyle.danger, custom_id="duel_cheer_p2", row=0)
    async def cheer_p2(self, interaction: discord.Interaction, button: discord.ui.Button):
        race_state = ACTIVE_RACES.get(self.thread_id)
        if race_state and "cheers" in race_state:
            cheered_users = race_state.setdefault("cheered_users", set())
            if interaction.user.id in cheered_users:
                await interaction.response.send_message("❌ You have already cheered in this race!", ephemeral=True)
                return
            cheered_users.add(interaction.user.id)
            race_state["cheers"][self.p2_id] = race_state["cheers"].get(self.p2_id, 0) + 1
            count = race_state["cheers"][self.p2_id]
            self.update_button_labels()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"❤️ You cheered for **{self.p2_name}**! Total Cheers: `{count}`", ephemeral=True)
        else:
            await interaction.response.send_message("🎉 Thanks for cheering!", ephemeral=True)

    @discord.ui.button(label="🏎️ Live Standings", style=discord.ButtonStyle.secondary, custom_id="duel_public_standings", row=1)
    async def standings_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        race_state = ACTIVE_RACES.get(self.thread_id)
        if not race_state or not race_state.get("snapshot"):
            await interaction.response.send_message("❌ No standings available for this lap.", ephemeral=True)
            return
            
        lap_num = race_state.get("lap", 0)
        lap_snapshot = race_state.get("snapshot", {})
        
        standings_list = []
        for user_id, state in lap_snapshot.items():
            team_name = "Unknown Team"
            for entry in self.entries_list:
                if str(entry['user_id']) == str(user_id):
                    team_name = entry['team_name']
                    break
            pos_val = state.get("position")
            standings_list.append({
                "position": pos_val,
                "team_name": team_name,
                "gap_to_leader": state.get("gap_to_leader", "Leader"),
                "gap_to_front": state.get("gap_to_front", "—"),
                "tyre_type": state.get("tyre_type", "M"),
                "tyre_health": state.get("tyre_health", 100.0),
                "dnf": state.get("dnf", False)
            })
            
        standings_list.sort(key=lambda x: (1 if (x["dnf"] or x["position"] is None) else 0, x["position"] if x["position"] is not None else 999))
        
        chunks = [standings_list[i:i + 25] for i in range(0, len(standings_list), 25)]
        embeds = []
        
        for idx, chunk in enumerate(chunks):
            table_lines = []
            table_lines.append("```")
            table_lines.append(f"Pos  Team Name            Gap        Tyre")
            table_lines.append(f"-------------------------------------------")
            
            for driver in chunk:
                if driver['dnf'] or driver['position'] is None:
                    pos_str = "DNF ".ljust(4)
                else:
                    pos_str = f"P{driver['position']}".ljust(4)
                team_str = driver['team_name'][:18].ljust(19)
                
                gap_str = driver['gap_to_leader']
                if driver['dnf']:
                    gap_str = "DNF"
                gap_str = str(gap_str).ljust(10)
                
                tyre_name = driver['tyre_type']
                tyre_pct = int(driver['tyre_health'])
                tyre_str = f"{tyre_name} ({tyre_pct}%)"
                if driver['dnf']:
                    tyre_str = "—"
                    
                table_lines.append(f"{pos_str} {team_str} {gap_str} {tyre_str}")
            table_lines.append("```")
            
            page_title = f"📊 Live Standings - Lap {lap_num}" if idx == 0 else f"📊 Live Standings - Page {idx + 1}"
            embeds.append(utils.create_embed(
                title=page_title,
                description="\n".join(table_lines),
                color=utils.COLOR_QUALIFYING
            ))
            
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

    @discord.ui.button(label="📊 My Telemetry & Strategy", style=discord.ButtonStyle.success, custom_id="duel_lap_telemetry", row=1)
    async def telemetry_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        race_state = ACTIVE_RACES.get(self.thread_id)
        if not race_state or not race_state.get("snapshot"):
            await interaction.response.send_message("❌ No telemetry available for this lap.", ephemeral=True)
            return
            
        lap_num = race_state.get("lap", 0)
        lap_snapshot = race_state.get("snapshot", {})
        
        user_id = None
        team_name = None
        for entry in self.entries_list:
            if entry['discord_id'] == interaction.user.id:
                user_id = entry['user_id']
                team_name = entry['team_name']
                break
                
        if not user_id:
            await interaction.response.send_message("❌ You are not participating in this duel.", ephemeral=True)
            return
            
        state = lap_snapshot.get(user_id) or lap_snapshot.get(str(user_id))
        if not state:
            await interaction.response.send_message("❌ Telemetry not found for your team.", ephemeral=True)
            return
            
        if state['dnf']:
            desc = (
                f"🏎️ **Driver:** {interaction.user.mention} | **Team:** **{team_name}**\n"
                f"🛑 **Status:** **DNF (Did Not Finish)**\n"
                f"⭕ **Tyres:** `{state['tyre_type']}`"
            )
            color = utils.COLOR_ERROR
            embed = utils.create_embed(
                title=f"📊 Private Telemetry - Lap {lap_num}",
                description=desc,
                color=color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            current_strategy = "Balanced"
            scheduled_strategy = "None scheduled"
            pit_scheduled = "None scheduled"
            if race_state and "teams" in race_state:
                for t in race_state["teams"]:
                    if t.discord_id == interaction.user.id:
                        current_strategy = t.strategy
                        if getattr(t, 'next_block_strategy', None):
                            stint_start = (lap_num // 10 + 1) * 10 + 1
                            scheduled_strategy = f"**{t.next_block_strategy}** (starts Lap {stint_start})"
                        if getattr(t, 'pit_next_lap', False):
                            pit_scheduled = f"**Box next lap** (fit `{getattr(t, 'pit_next_lap_tyre', t.tyre_type)}`)"
                        break
            
            tyre_bar = utils.make_progress_bar(state['tyre_health'])
            desc = (
                f"🏎️ **Driver:** {interaction.user.mention} | **Team:** **{team_name}**\n\n"
                f"📊 **Lap {lap_num} Live Telemetry:**\n"
                f"  • **Position:** `P{state['position']}`\n"
                f"  • **Gap to Leader:** `{state['gap_to_leader']}`\n"
                f"  • **Gap to Car Ahead:** `{state['gap_to_front']}`\n\n"
                f"⚙️ **Strategy & Health:**\n"
                f"  • **Current Pace:** `{current_strategy}`\n"
                f"  • **Scheduled Pace stint:** `{scheduled_strategy}`\n"
                f"  • **Scheduled Pit Stop:** `{pit_scheduled}`\n"
                f"  • **Tyres:** `{state['tyre_type']}` | Health: {tyre_bar} ({int(state['tyre_health'])}%)\n\n"
                f"*Adjust your pacing strategy or schedule a pit stop below:*"
            )
            color = utils.COLOR_SUCCESS
            
            embed = utils.create_embed(
                title=f"📊 Private Telemetry - Lap {lap_num}",
                description=desc,
                color=color
            )
            view = GPLapTelemetryAdjustmentView(interaction.channel_id, interaction.user.id, embed=embed)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RaceChallengeView(discord.ui.View):
    def __init__(self, challenger_prof, opponent_prof, guild_id, wager=0, laps=3, track_name=None):
        super().__init__(timeout=60.0)
        self.challenger_prof = challenger_prof
        self.opponent_prof = opponent_prof
        self.guild_id = guild_id
        self.wager = max(0, wager)
        self.laps = max(1, min(20, laps))
        self.track_name = track_name

    @discord.ui.button(label="🏁 Accept Challenge", style=discord.ButtonStyle.green)
    async def accept_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_prof['discord_id']:
            await interaction.response.send_message("❌ Only the challenged opponent can accept this race!", ephemeral=True)
            return

        if self.wager > 0:
            c_check = database.get_user_by_discord_id(self.challenger_prof['discord_id'], self.guild_id)
            o_check = database.get_user_by_discord_id(self.opponent_prof['discord_id'], self.guild_id)
            if c_check['money'] < self.wager or o_check['money'] < self.wager:
                await interaction.response.send_message("❌ Race cancelled: One of the players no longer has enough credits for the wager.", ephemeral=True)
                self.stop()
                return

        for item in self.children:
            item.disabled = True

        orig_msg = interaction.message
        thread_name = f"🏎️ Duel: {self.challenger_prof['team_name'][:12]} vs {self.opponent_prof['team_name'][:12]}"
        thread = await orig_msg.create_thread(name=thread_name, auto_archive_duration=60)

        await interaction.response.edit_message(
            content=(
                f"🏁 **Challenge Accepted!** The 1v1 duel between **{self.challenger_prof['team_name']}** and **{self.opponent_prof['team_name']}** is live!\n"
                f"➡️ **Watch live commentary & select strategy in thread:** {thread.mention}"
            ),
            embed=None,
            view=self
        )

        # Lookup Head-to-Head record
        u1_wins, u2_wins = database.get_head_to_head_record(self.challenger_prof['user_id'], self.opponent_prof['user_id'])
        h2h_text = f"⚔️ **Rivalry Head-to-Head:** `{self.challenger_prof['team_name']} ({u1_wins}) — ({u2_wins}) {self.opponent_prof['team_name']}`\n\n"

        pace_view = RacePaceView(
            self.challenger_prof['discord_id'],
            self.opponent_prof['discord_id'],
            self.guild_id,
            p1_default=self.challenger_prof.get('pref_strategy', 'Balanced'),
            p2_default=self.opponent_prof.get('pref_strategy', 'Balanced')
        )
        pace_embed = utils.create_embed(
            title=f"⏱️ Strategy Setup — Choose Your Race Pacing ({self.laps} Laps)!",
            description=(
                f"**{self.challenger_prof['team_name']}** vs **{self.opponent_prof['team_name']}**\n\n"
                f"{h2h_text}"
                f"Click your pace strategy button below before the lights go out!\n"
                f"• **Push (Aggressive):** Maximum speed, higher tyre wear.\n"
                f"• **Standard (Balanced):** Balanced pace & wear.\n"
                f"• **Save (Conservative):** Protects tyres & engine thermals."
            ),
            color=utils.COLOR_QUALIFYING
        )
        await thread.send(embed=pace_embed, view=pace_view)
        
        # Wait for strategy selections
        try:
            await asyncio.wait_for(pace_view.ready_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            pass

        t1_data = database.get_full_team_profile(self.challenger_prof['discord_id'], self.guild_id)
        t2_data = database.get_full_team_profile(self.opponent_prof['discord_id'], self.guild_id)
        
        t1_data['pref_strategy'] = pace_view.p1_strategy
        t2_data['pref_strategy'] = pace_view.p2_strategy

        generator = race.simulate_duel_generator(t1_data, t2_data, total_laps=self.laps, track_name=self.track_name)
        
        setup_event = next(generator)
        teams_list = setup_event[1]
        qual_logs = setup_event[2]
        track_name = setup_event[3]
        
        # Register in ACTIVE_RACES keyed by thread.id
        ACTIVE_RACES[thread.id] = {
            "teams": teams_list,
            "lap": 0,
            "snapshot": {},
            "cheers": {self.challenger_prof['user_id']: 0, self.opponent_prof['user_id']: 0},
            "cheered_users": set()
        }
        
        quali_embed = utils.create_embed(
            title=f"🏁 Race Starting — {self.laps} Laps at {track_name}!",
            description="\n".join(qual_logs),
            color=utils.COLOR_QUALIFYING
        )
        await thread.send(embed=quali_embed)
        
        try:
            lap_logs = []
            lap_telemetry_history = []
            winner = None
            loser = None
            fastest_lap_time = 999.0
            fastest_lap_team = None
            fastest_lap_user_id = None

            cheer_view = DuelSpectatorCheerView(
                thread.id,
                self.challenger_prof['user_id'], self.challenger_prof['team_name'], self.challenger_prof['discord_id'],
                self.opponent_prof['user_id'], self.opponent_prof['team_name'], self.opponent_prof['discord_id']
            )

            for item in generator:
                if item[0] == "lap":
                    l_num = item[1]
                    lap_events = item[2]
                    lap_snapshot = item[3]
                    
                    lap_logs.append(lap_events)
                    ACTIVE_RACES[thread.id]["lap"] = l_num
                    ACTIVE_RACES[thread.id]["snapshot"] = lap_snapshot

                    drivers_pace = {}
                    for t_obj in teams_list:
                        drivers_pace[t_obj.team_name] = round(t_obj.last_lap_time, 2)
                        if t_obj.last_lap_time > 0 and t_obj.last_lap_time < fastest_lap_time:
                            fastest_lap_time = t_obj.last_lap_time
                            fastest_lap_team = t_obj.team_name
                            fastest_lap_user_id = t_obj.user_id

                    lap_telemetry_history.append({"lap": l_num, "drivers": drivers_pace})
                    
                    lap_text = "\n".join(lap_events) if isinstance(lap_events, list) else str(lap_events)
                    
                    lap_embed = utils.create_embed(
                        title=f"🏎️ Lap {l_num} / {self.laps}",
                        description=lap_text,
                        color=0xF5A623
                    )
                    
                    cheer_view.update_button_labels()
                    await thread.send(embed=lap_embed, view=cheer_view)
                    await asyncio.sleep(20.0)
                    
                elif item[0] == "finish":
                    winner = item[1]
                    loser = item[2]
                    
            if thread.id in ACTIVE_RACES:
                del ACTIVE_RACES[thread.id]

            if not winner or not loser:
                await thread.send("❌ Race simulation finished without a clear winner.")
                return

            if self.wager > 0:
                database.update_user_balance(winner['user_id'], self.wager)
                database.update_user_balance(loser['user_id'], -self.wager)
                wager_str = f"\n💰 **Wager Paid:** **+{self.wager:,} credits** won!"
            else:
                wager_str = ""

            fl_str = ""
            if fastest_lap_user_id:
                database.update_user_balance(fastest_lap_user_id, 25)
                fl_str = f"\n⚡ **Fastest Lap Bonus:** **{fastest_lap_team}** (`{fastest_lap_time:.2f}s`) (+25¢ bonus!)"

            database.record_race_result(winner['user_id'], loser['user_id'], self.guild_id)
            database.record_duel_history(self.guild_id, winner['user_id'], loser['user_id'])

            telemetry_chart = utils.generate_race_telemetry_graph(lap_telemetry_history)
            chart_file = discord.File(telemetry_chart, filename="telemetry_chart.png")

            victory_radio = utils.get_victory_team_radio(winner['team_name'])

            summary_desc = (
                f"🏆 **WINNER:** **{winner['team_name']}**!{wager_str}{fl_str}\n"
                f"{victory_radio}\n\n"
                f"⏱️ **Distance:** `{self.laps} Laps`\n"
                f"📊 **Rewards Earned:**\n"
                f"  • **Winner ({winner['team_name']}):** `+{config.WIN_PRIZE_CREDITS:,}¢` | `+{config.WIN_XP:,} XP`\n"
                f"  • **Runner-up ({loser['team_name']}):** `+{config.LOSS_PRIZE_CREDITS:,}¢` | `+{config.LOSS_XP:,} XP`\n\n"
                f"🗑️ *This live duel thread will automatically delete in 2 minutes to keep the channel clean.*"
            )

            embed = utils.create_embed(
                title=f"🏁 RACE RESULTS: {winner['team_name']} VICTORY!",
                description=summary_desc,
                color=utils.COLOR_SUCCESS
            )
            embed.set_image(url="attachment://telemetry_chart.png")
            rematch_view = DuelRematchView(self.challenger_prof, self.opponent_prof, self.guild_id, self.wager, self.laps, self.track_name)
            await thread.send(embed=embed, file=chart_file, view=rematch_view)

            # Update original main channel message with Winner Summary Banner
            await orig_msg.edit(
                content=f"🏆 **DUEL CONCLUDED:** **{winner['team_name']}** defeated **{loser['team_name']}**! (+{config.WIN_PRIZE_CREDITS:,}¢, +{config.WIN_XP} XP){wager_str}",
                embed=None,
                view=None
            )

            # Schedule 120-second thread deletion
            async def delete_thread_later(th, delay=120):
                await asyncio.sleep(delay)
                try:
                    await th.delete()
                except Exception:
                    pass

            asyncio.create_task(delete_thread_later(thread, 120))

        except Exception as e:
            import traceback
            traceback.print_exc()
            if thread.id in ACTIVE_RACES:
                del ACTIVE_RACES[thread.id]
            await thread.send(f"❌ **Race Error:** `{e}`")

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_prof['discord_id']:
            await interaction.response.send_message("❌ Only the challenged opponent can decline this race!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Race challenge declined.", embed=None, view=None)



def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if hasattr(interaction.user, 'roles'):
            import config
            role = discord.utils.get(interaction.user.roles, name=config.ADMIN_ROLE_NAME)
            if role is not None:
                return True
        return False
    return app_commands.check(predicate)


class StrategyPaceSelect(discord.ui.Select):
    def __init__(self, current_pace):
        options = [
            discord.SelectOption(label="🔴 Aggressive (+pace, ++wear, +crash)", value="Aggressive", default=(current_pace == "Aggressive")),
            discord.SelectOption(label="🟡 Balanced (neutral pace, normal wear)", value="Balanced", default=(current_pace == "Balanced")),
            discord.SelectOption(label="🟢 Conservative (-pace, -wear, -crash)", value="Conservative", default=(current_pace == "Conservative"))
        ]
        super().__init__(placeholder="Select Starting Pace...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.pace = self.values[0]
        import json
        strategy_data = {
            "pace": self.view.pace,
            "start_tyre": self.view.start_tyre,
            "stops": []
        }
        database.update_user_pit_strategy(self.view.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.view.user_id, self.view.pace, self.view.start_tyre, 0)
        await self.view.update_embed(interaction)

class StrategyTyresSelect(discord.ui.Select):
    def __init__(self, current_tyres):
        options = [
            discord.SelectOption(label="🟥 Soft tyres (++pace, ++wear)", value="Soft", default=(current_tyres == "Soft")),
            discord.SelectOption(label="🟨 Medium tyres (+pace, +wear)", value="Medium", default=(current_tyres == "Medium")),
            discord.SelectOption(label="⬜ Hard tyres (neutral pace, very low wear)", value="Hard", default=(current_tyres == "Hard"))
        ]
        super().__init__(placeholder="Select Starting Tyre...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.start_tyre = self.values[0]
        import json
        strategy_data = {
            "pace": self.view.pace,
            "start_tyre": self.view.start_tyre,
            "stops": []
        }
        database.update_user_pit_strategy(self.view.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.view.user_id, self.view.pace, self.view.start_tyre, 0)
        await self.view.update_embed(interaction)



class StrategyConfigView(discord.ui.View):
    def __init__(self, user_id, guild_id):
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.guild_id = guild_id
        
        prof = database.get_full_team_profile(user_id, guild_id)
        
        import json
        self.strategy_data = {}
        strategy_str = prof.get('pit_strategy_json')
        if strategy_str:
            try:
                self.strategy_data = json.loads(strategy_str)
            except Exception:
                pass
                
        self.pace = self.strategy_data.get("pace", prof.get("pref_strategy", "Balanced"))
        self.start_tyre = self.strategy_data.get("start_tyre", prof.get("pref_tyres", "Medium"))
        self.stops = []
        
        self.add_item(StrategyPaceSelect(self.pace))
        self.add_item(StrategyTyresSelect(self.start_tyre))

    async def update_embed(self, interaction: discord.Interaction):
        desc = (
            f"🏎️ **Starting Pacing Mode:** `{self.pace}`\n"
            f"🛞 **Starting Tyres:** `{self.start_tyre}`\n\n"
            f"*💡 Selections are saved in real-time. This configuration sheet is private and hidden from other competitors.*"
        )
        embed = utils.create_embed(
            title="⚙️ Racing Strategy Configuration Board",
            description=desc,
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.edit_message(embed=embed, view=self)











class QualiTyresSelectView(discord.ui.View):
    def __init__(self, user_id, race_id):
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.race_id = race_id

    @discord.ui.button(label="Soft tyres (Fastest)", style=discord.ButtonStyle.green, custom_id="q_soft")
    async def soft_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.update_quali_tyre(self.user_id, self.race_id, "Soft")
        await interaction.response.send_message("✅ Selected **Soft** tyres for the upcoming qualifying session!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Medium tyres (Balanced)", style=discord.ButtonStyle.blurple, custom_id="q_medium")
    async def medium_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.update_quali_tyre(self.user_id, self.race_id, "Medium")
        await interaction.response.send_message("✅ Selected **Medium** tyres for the upcoming qualifying session!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Hard tyres (Slowest)", style=discord.ButtonStyle.red, custom_id="q_hard")
    async def hard_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.update_quali_tyre(self.user_id, self.race_id, "Hard")
        await interaction.response.send_message("✅ Selected **Hard** tyres for the upcoming qualifying session!", ephemeral=True)
        self.stop()



class GPTrackSelect(discord.ui.Select):
    def __init__(self, laps=15, is_sprint=False):
        options = []
        for t_name, profile in list(race.TRACK_PROFILES.items())[:25]:
            sprint_tag = "⚡ [Sprint Track] " if profile.get("is_sprint") else ""
            desc = f"{sprint_tag}{profile.get('description', '')}"[:100]
            options.append(discord.SelectOption(
                label=t_name[:100],
                value=t_name,
                description=desc
            ))
        super().__init__(placeholder="Select an Official F1 Track to Schedule...", min_values=1, max_values=1, options=options)
        self.laps = laps
        self.is_sprint = is_sprint

    async def callback(self, interaction: discord.Interaction):
        track_choice = self.values[0]
        event_type = "Sprint Race" if self.is_sprint else "Grand Prix"
        gp_name = f"{track_choice} {event_type}"
        laps = self.laps
        
        success, msg = database.create_gp_race(interaction.guild_id, gp_name, track_choice, laps, is_sprint=self.is_sprint)
        if success:
            active_gp = database.get_active_gp_race(interaction.guild_id)
            view = GPAdminView(interaction.guild_id)
            desc = (
                f"🏁 **Active GP:** **{active_gp['name']}**\n"
                f"🗺️ **Track:** `{active_gp['track']}`\n"
                f"⏱️ **Distance:** `{active_gp['laps']} Laps`\n"
                f"📊 **Stage:** `Created (Registration open)`\n"
                f"👥 **Entrants:** `0 driver(s) registered`"
            )
            embed = utils.create_embed(title="🏁 Grand Prix Admin Panel", description=desc, color=utils.COLOR_WARNING)
            
            announcement = utils.create_embed(
                title=f"🏁 {event_type} Scheduled!",
                description=(
                    f"A new event **{gp_name}** has been scheduled at **{track_choice}** ({laps} laps)!\n\n"
                    f"Type **`/joinrace`** to register and secure your spot on the starting grid!"
                ),
                color=utils.COLOR_SUCCESS
            )
            await interaction.channel.send(embed=announcement)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)



class GPStartQualiButton(discord.ui.Button):
    def __init__(self, session_key: str, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.success, custom_id=f"gp_run_{session_key.lower()}")
        self.session_key = session_key

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_gp = database.get_active_gp_race(interaction.guild_id)
        if not active_gp:
            await interaction.followup.send("❌ No active GP scheduled.", ephemeral=True)
            return
            
        entries = database.get_gp_entries_full(active_gp['race_id'])
        if len(entries) < 2:
            await interaction.followup.send("❌ Cannot run qualifying. Need at least 2 registered entries.", ephemeral=True)
            return

        if self.session_key == "Q1":
            if len(entries) <= 10:
                database.update_gp_status(active_gp['race_id'], "Q3_Ready")
                embed = utils.create_embed(
                    title="⏱️ GP Qualifying Weekend - Q1/Q2 Skipped",
                    description=(
                        f"Only **{len(entries)}** drivers registered.\n"
                        f"Since there are 10 or fewer drivers, all drivers automatically progress to **Q3**!\n\n"
                        f"Admin, use the `/gp` panel to launch the final **Q3 Qualifying** session next."
                    ),
                    color=utils.COLOR_QUALIFYING
                )
                await interaction.channel.send(embed=embed)
            elif len(entries) <= 15:
                database.update_gp_status(active_gp['race_id'], "Q2_Ready")
                embed = utils.create_embed(
                    title="⏱️ GP Qualifying Weekend - Q1 Skipped",
                    description=(
                        f"Only **{len(entries)}** drivers registered.\n"
                        f"Since there are 15 or fewer drivers, all drivers progress to **Q2**!\n\n"
                        f"Admin, use the `/gp` panel to launch **Q2 Qualifying** next."
                    ),
                    color=utils.COLOR_QUALIFYING
                )
                await interaction.channel.send(embed=embed)
            else:
                results = race.simulate_quali_session(entries, active_gp['track'], "Q1")
                for idx, res in enumerate(results):
                    if idx >= 15:
                        res["start_position"] = idx + 1
                    else:
                        res["start_position"] = None
                database.save_quali_results(active_gp['race_id'], results, "Q1")
                database.update_gp_status(active_gp['race_id'], "Q2_Ready")
                
                desc = "⏱️ **Q1 Results Table:**\n"
                for idx, res in enumerate(results):
                    formatted_time = race.format_lap_time(res['quali_time'])
                    tyre_emoji = "🟢" if res['current_q_tyre'] == "Soft" else ("🟡" if res['current_q_tyre'] == "Medium" else "⚪")
                    status_txt = "✅ **Q2**" if idx < 15 else f"❌ **P{idx + 1}**"
                    desc += f"**{idx + 1}.** {res['team_name']} — `{formatted_time}` {tyre_emoji} {status_txt}\n"
                    
                embed = utils.create_embed(
                    title="⏱️ Grand Prix Q1 - Results",
                    description=desc,
                    color=utils.COLOR_QUALIFYING
                )
                await interaction.channel.send(embed=embed)

        elif self.session_key == "Q2":
            q2_entrants = [e for e in entries if e['start_position'] is None or e['start_position'] > 99]
            results = race.simulate_quali_session(q2_entrants, active_gp['track'], "Q2")
            for idx, res in enumerate(results):
                if idx >= 10:
                    res["start_position"] = idx + 11
                else:
                    res["start_position"] = None
            database.save_quali_results(active_gp['race_id'], results, "Q2")
            database.update_gp_status(active_gp['race_id'], "Q3_Ready")
            
            desc = "⏱️ **Q2 Results Table:**\n"
            for idx, res in enumerate(results):
                formatted_time = race.format_lap_time(res['quali_time'])
                tyre_emoji = "🟢" if res['current_q_tyre'] == "Soft" else ("🟡" if res['current_q_tyre'] == "Medium" else "⚪")
                status_txt = "✅ **Q3**" if idx < 10 else f"❌ **P{idx + 11}**"
                desc += f"**{idx + 1}.** {res['team_name']} — `{formatted_time}` {tyre_emoji} {status_txt}\n"
                
            embed = utils.create_embed(
                title="⏱️ Grand Prix Q2 - Results",
                description=desc,
                color=utils.COLOR_QUALIFYING
            )
            await interaction.channel.send(embed=embed)

        elif self.session_key == "Q3":
            q3_entrants = [e for e in entries if e['start_position'] is None]
            results = race.simulate_quali_session(q3_entrants, active_gp['track'], "Q3")
            for idx, res in enumerate(results):
                res["start_position"] = idx + 1
            database.save_quali_results(active_gp['race_id'], results, "Q3")
            database.update_gp_status(active_gp['race_id'], "GridSet")
            
            desc = "⏱️ **Q3 Results (Final Starting Grid):**\n"
            for idx, res in enumerate(results):
                formatted_time = race.format_lap_time(res['quali_time'])
                tyre_emoji = "🟢" if res['current_q_tyre'] == "Soft" else ("🟡" if res['current_q_tyre'] == "Medium" else "⚪")
                if idx == 0:
                    desc += f"**P{idx + 1}.** {res['team_name']} — `{formatted_time}` {tyre_emoji} (Pole Position! 🏆)\n"
                else:
                    desc += f"**P{idx + 1}.** {res['team_name']} — `{formatted_time}` {tyre_emoji}\n"
                
            embed = utils.create_embed(
                title="⏱️ Grand Prix Q3 - Final Grid Standings",
                description=desc,
                color=utils.COLOR_QUALIFYING
            )
            await interaction.channel.send(embed=embed)

        active_gp = database.get_active_gp_race(interaction.guild_id)
        entries = database.get_gp_entries_full(active_gp['race_id'])
        desc = (
            f"🏁 **Active GP:** **{active_gp['name']}**\n"
            f"🗺️ **Track:** `{active_gp['track']}`\n"
            f"⏱️ **Distance:** `{active_gp['laps']} Laps`\n"
            f"📊 **Stage:** `{active_gp['status']}`\n"
            f"👥 **Entrants:** `{len(entries)} driver(s) registered`"
        )
        await interaction.message.edit(embed=utils.create_embed(
            title="🏁 Grand Prix Admin Panel",
            description=desc,
            color=utils.COLOR_WARNING
        ), view=GPAdminView(interaction.guild_id))



class GPLapPitSelectView(discord.ui.View):
    def __init__(self, guild_id, user_discord_id, parent_view):
        super().__init__(timeout=60.0)
        self.guild_id = guild_id
        self.user_discord_id = user_discord_id
        self.parent_view = parent_view

    async def schedule_pit(self, interaction: discord.Interaction, tyre: str):
        race_state = ACTIVE_RACES.get(self.guild_id)
        if not race_state or "teams" not in race_state:
            await interaction.response.send_message("❌ There is no active Grand Prix simulation running right now.", ephemeral=True)
            return
            
        team_obj = None
        for t in race_state["teams"]:
            if t.discord_id == self.user_discord_id:
                team_obj = t
                break
                
        if not team_obj:
            await interaction.response.send_message("❌ You are not on the active entry list for this race.", ephemeral=True)
            return
            
        team_obj.pit_next_lap = True
        team_obj.pit_next_lap_tyre = tyre
        
        await interaction.response.edit_message(content=f"✅ **Pit stop scheduled!** Your driver will pit at the end of the current lap to switch to **{tyre}** tyres.", embed=None, view=None)

    @discord.ui.button(label="🟥 Soft", style=discord.ButtonStyle.danger, custom_id="gp_pit_soft")
    async def soft_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_pit(interaction, "Soft")

    @discord.ui.button(label="🟨 Medium", style=discord.ButtonStyle.primary, custom_id="gp_pit_medium")
    async def medium_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_pit(interaction, "Medium")

    @discord.ui.button(label="⬜ Hard", style=discord.ButtonStyle.secondary, custom_id="gp_pit_hard")
    async def hard_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_pit(interaction, "Hard")

    @discord.ui.button(label="🟩 Intermediates", style=discord.ButtonStyle.success, custom_id="gp_pit_inters")
    async def inter_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_pit(interaction, "Intermediates")

    @discord.ui.button(label="🔙 Cancel", style=discord.ButtonStyle.secondary, custom_id="gp_pit_cancel")
    async def cancel_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=None, embed=self.parent_view.embed, view=self.parent_view)



class GPRetireConfirmView(discord.ui.View):
    def __init__(self, guild_id, user_discord_id, parent_view):
        super().__init__(timeout=60.0)
        self.guild_id = guild_id
        self.user_discord_id = user_discord_id
        self.parent_view = parent_view

    @discord.ui.button(label="✅ Yes, Retire", style=discord.ButtonStyle.danger, custom_id="gp_retire_confirm")
    async def confirm_retire(self, interaction: discord.Interaction, button: discord.ui.Button):
        race_state = ACTIVE_RACES.get(self.guild_id)
        if not race_state or "teams" not in race_state:
            await interaction.response.edit_message(content="❌ There is no active race running.", embed=None, view=None)
            return
            
        team_obj = None
        for t in race_state["teams"]:
            if t.discord_id == self.user_discord_id:
                team_obj = t
                break
                
        if not team_obj:
            await interaction.response.edit_message(content="❌ You are not on the active entry list.", embed=None, view=None)
            return
            
        if team_obj.dnf:
            await interaction.response.edit_message(content="❌ You have already retired or DNF'd from the race.", embed=None, view=None)
            return
            
        team_obj.dnf = True
        team_obj.dnf_reason = "retired by driver request"
        
        await interaction.response.edit_message(content="🛑 **Retirement confirmed.** Your car is DNF. You can close this chat or spectate the remaining laps in the public channel.", embed=None, view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, custom_id="gp_retire_cancel")
    async def cancel_retire(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=None, embed=self.parent_view.embed, view=self.parent_view)

async def send_driver_lap_telemetry(bot, guild_id, driver_discord_id, team_name, lap_num, lap_time, position, gap_to_leader, gap_to_front, tyre_type, tyre_health):
    # Sleep for the actual lap time of this driver!
    await asyncio.sleep(lap_time)
    try:
        user = bot.get_user(driver_discord_id) or await bot.fetch_user(driver_discord_id)
        if user:
            tyre_bar = utils.make_progress_bar(tyre_health)
            
            # Find their scheduled stint strategy and pit stop status
            race_state = ACTIVE_RACES.get(guild_id)
            current_strategy = "Balanced"
            scheduled_strategy = "None scheduled"
            pit_scheduled = "None scheduled"
            if race_state and "teams" in race_state:
                for t in race_state["teams"]:
                    if t.discord_id == driver_discord_id:
                        current_strategy = t.strategy
                        if t.next_block_strategy:
                            stint_start = (lap_num // 10 + 1) * 10 + 1
                            scheduled_strategy = f"**{t.next_block_strategy}** (starts Lap {stint_start})"
                        if t.pit_next_lap:
                            pit_scheduled = f"**Box next lap** (fit `{t.pit_next_lap_tyre}`)"
                        break
            
            embed = utils.create_embed(
                title=f"📊 Live GP Telemetry - Lap {lap_num} Completed",
                description=(
                    f"🏁 You have completed **Lap {lap_num}**!\n"
                    f"⏱️ **Lap Time:** `{lap_time:.3f}s`\n\n"
                    f"📊 **Standings:**\n"
                    f"  • **Position:** `P{position if position is not None else 'DNF'}`\n"
                    f"  • **Gap to Leader:** `{gap_to_leader}`\n"
                    f"  • **Gap to Car Ahead:** `{gap_to_front}`\n\n"
                    f"⚙️ **Strategy & Health:**\n"
                    f"  • **Current Pace:** `{current_strategy}`\n"
                    f"  • **Scheduled Pace stint:** `{scheduled_strategy}`\n"
                    f"  • **Scheduled Pit Stop:** `{pit_scheduled}`\n"
                    f"  • **Tyres:** `{tyre_type}` | Health: {tyre_bar} ({int(tyre_health)}%)\n\n"
                    f"*Adjust your pacing strategy or schedule a pit stop below:*"
                ),
                color=utils.COLOR_QUALIFYING
            )
            view = GPLapTelemetryAdjustmentView(guild_id, driver_discord_id, embed=embed)
            await user.send(embed=embed, view=view)
    except Exception as e:
        print(f"Failed to send lap telemetry DM to {team_name}: {e}")



class GPLapTelemetryAdjustmentView(discord.ui.View):
    def __init__(self, guild_id, user_discord_id, embed=None):
        super().__init__(timeout=120.0)
        self.guild_id = guild_id
        self.user_discord_id = user_discord_id
        self.embed = embed

    async def update_pace(self, interaction: discord.Interaction, pace: str):
        race_state = ACTIVE_RACES.get(self.guild_id)
        if not race_state or "teams" not in race_state:
            await interaction.response.send_message("❌ There is no active Grand Prix simulation running right now.", ephemeral=True)
            return
            
        team_obj = None
        for t in race_state["teams"]:
            if t.discord_id == self.user_discord_id:
                team_obj = t
                break
                
        if not team_obj:
            await interaction.response.send_message("❌ You are not on the active entry list for this race.", ephemeral=True)
            return
            
        # Determine the driver's current running lap based on their completed laps in physics engine
        current_running_lap = team_obj.laps_completed + 1
        
        # If the race hasn't started
        if getattr(team_obj, 'laps_completed', 0) == 0 and race_state.get("lap", 0) == 0:
            team_obj.strategy = pace
            team_obj.next_block_strategy = None
            await interaction.response.send_message(f"✅ Starting pacing strategy set to **{pace}**!", ephemeral=True)
        else:
            if current_running_lap % 10 == 0:
                await interaction.response.send_message(f"❌ Pacing strategy changes are locked on your Lap {current_running_lap} (transition lap) to avoid confusion. You can change your pacing starting next lap.", ephemeral=True)
                return
                
            stint_start = (current_running_lap // 10 + 1) * 10 + 1
            team_obj.next_block_strategy = pace
            await interaction.response.send_message(f"✅ Pacing strategy scheduled to **{pace}** for your stint starting on **Lap {stint_start}** (Laps {stint_start} to {stint_start + 9})!", ephemeral=True)

    @discord.ui.button(label="🔴 Push (Aggressive)", style=discord.ButtonStyle.danger, custom_id="gp_pace_push")
    async def push_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_pace(interaction, "Aggressive")

    @discord.ui.button(label="🟡 Standard (Balanced)", style=discord.ButtonStyle.primary, custom_id="gp_pace_standard")
    async def standard_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_pace(interaction, "Balanced")

    @discord.ui.button(label="🟢 Save (Conservative)", style=discord.ButtonStyle.success, custom_id="gp_pace_save")
    async def save_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_pace(interaction, "Conservative")

    @discord.ui.button(label="🔧 Pit Next Lap", style=discord.ButtonStyle.secondary, custom_id="gp_pace_pit")
    async def pit_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GPLapPitSelectView(self.guild_id, self.user_discord_id, self)
        await interaction.response.edit_message(content="⚙️ **Select tyre compound for your pit stop next lap:**", embed=None, view=view)

    @discord.ui.button(label="🛑 Retire / DNF", style=discord.ButtonStyle.danger, custom_id="gp_retire_race")
    async def retire_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GPRetireConfirmView(self.guild_id, self.user_discord_id, self)
        await interaction.response.edit_message(content="⚠️ **Are you sure you want to retire from the Grand Prix?** This cannot be undone and your car will DNF.", embed=None, view=view)



class GPLapTelemetryView(discord.ui.View):
    def __init__(self, lap_num, lap_snapshot, entries_list):
        super().__init__(timeout=86400.0)
        self.lap_num = lap_num
        self.lap_snapshot = lap_snapshot
        self.entries_list = entries_list

    @discord.ui.button(label="🏎️ Live Standings", style=discord.ButtonStyle.primary, custom_id="gp_public_standings")
    async def standings_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.lap_snapshot:
            await interaction.response.send_message("❌ No standings available for this lap.", ephemeral=True)
            return
            
        standings_list = []
        for user_id, state in self.lap_snapshot.items():
            team_name = "Unknown Team"
            for entry in self.entries_list:
                if str(entry['user_id']) == str(user_id):
                    team_name = entry['team_name']
                    break
            pos_val = state.get("position")
            standings_list.append({
                "position": pos_val,
                "team_name": team_name,
                "gap_to_leader": state.get("gap_to_leader", "Leader"),
                "gap_to_front": state.get("gap_to_front", "—"),
                "tyre_type": state.get("tyre_type", "M"),
                "tyre_health": state.get("tyre_health", 100.0),
                "dnf": state.get("dnf", False)
            })
            
        standings_list.sort(key=lambda x: (1 if (x["dnf"] or x["position"] is None) else 0, x["position"] if x["position"] is not None else 999))
        
        # Paginate results in chunks of 25 to fit within Discord character limits
        chunks = [standings_list[i:i + 25] for i in range(0, len(standings_list), 25)]
        embeds = []
        
        for idx, chunk in enumerate(chunks):
            table_lines = []
            table_lines.append("```")
            table_lines.append(f"Pos  Team Name            Gap        Tyre")
            table_lines.append(f"-------------------------------------------")
            
            for driver in chunk:
                if driver['dnf'] or driver['position'] is None:
                    pos_str = "DNF ".ljust(4)
                else:
                    pos_str = f"P{driver['position']}".ljust(4)
                team_str = driver['team_name'][:18].ljust(19)
                
                gap_str = driver['gap_to_leader']
                if driver['dnf']:
                    gap_str = "DNF"
                gap_str = str(gap_str).ljust(10)
                
                tyre_name = driver['tyre_type']
                tyre_pct = int(driver['tyre_health'])
                tyre_str = f"{tyre_name} ({tyre_pct}%)"
                if driver['dnf']:
                    tyre_str = "—"
                    
                table_lines.append(f"{pos_str} {team_str} {gap_str} {tyre_str}")
            table_lines.append("```")
            
            page_title = f"📊 Live Standings - Lap {self.lap_num}" if idx == 0 else f"📊 Live Standings - Page {idx + 1}"
            embeds.append(utils.create_embed(
                title=page_title,
                description="\n".join(table_lines),
                color=utils.COLOR_QUALIFYING
            ))
            
        # Send up to 10 embeds at once in a single ephemeral message
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

    @discord.ui.button(label="📊 My Telemetry & Strategy", style=discord.ButtonStyle.success, custom_id="gp_lap_telemetry")
    async def telemetry_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = None
        team_name = None
        for entry in self.entries_list:
            if entry['discord_id'] == interaction.user.id:
                user_id = entry['user_id']
                team_name = entry['team_name']
                break
                
        if not user_id:
            await interaction.response.send_message("❌ You are not participating in this Grand Prix.", ephemeral=True)
            return
            
        state = self.lap_snapshot.get(user_id) or self.lap_snapshot.get(str(user_id))
        if not state:
            await interaction.response.send_message("❌ Telemetry not found for your team.", ephemeral=True)
            return
            
        if state['dnf']:
            desc = (
                f"🏎️ **Driver:** {interaction.user.mention} | **Team:** **{team_name}**\n"
                f"🛑 **Status:** **DNF (Did Not Finish)**\n"
                f"⭕ **Tyres:** `{state['tyre_type']}`"
            )
            color = utils.COLOR_ERROR
            embed = utils.create_embed(
                title=f"📊 Private Telemetry - Lap {self.lap_num}",
                description=desc,
                color=color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            race_state = ACTIVE_RACES.get(interaction.guild_id)
            current_strategy = "Balanced"
            scheduled_strategy = "None scheduled"
            pit_scheduled = "None scheduled"
            if race_state and "teams" in race_state:
                for t in race_state["teams"]:
                    if t.discord_id == interaction.user.id:
                        current_strategy = t.strategy
                        if t.next_block_strategy:
                            stint_start = (self.lap_num // 10 + 1) * 10 + 1
                            scheduled_strategy = f"**{t.next_block_strategy}** (starts Lap {stint_start})"
                        if t.pit_next_lap:
                            pit_scheduled = f"**Box next lap** (fit `{t.pit_next_lap_tyre}`)"
                        break
                        
            tyre_bar = utils.make_progress_bar(state['tyre_health'])
            desc = (
                f"🏎️ **Driver:** {interaction.user.mention} | **Team:** **{team_name}**\n\n"
                f"📊 **Lap {self.lap_num} Live Telemetry:**\n"
                f"  • **Position:** `P{state['position']}`\n"
                f"  • **Gap to Leader:** `{state['gap_to_leader']}`\n"
                f"  • **Gap to Car Ahead:** `{state['gap_to_front']}`\n\n"
                f"⚙️ **Strategy & Health:**\n"
                f"  • **Current Pace:** `{current_strategy}`\n"
                f"  • **Scheduled Pace stint:** `{scheduled_strategy}`\n"
                f"  • **Scheduled Pit Stop:** `{pit_scheduled}`\n"
                f"  • **Tyres:** `{state['tyre_type']}` | Health: {tyre_bar} ({int(state['tyre_health'])}%)\n\n"
                f"*Adjust your pacing strategy or schedule a pit stop below:*"
            )
            color = utils.COLOR_SUCCESS
            
            embed = utils.create_embed(
                title=f"📊 Private Telemetry - Lap {self.lap_num}",
                description=desc,
                color=color
            )
            view = GPLapTelemetryAdjustmentView(interaction.guild_id, interaction.user.id, embed=embed)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



class GPStartRaceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏎️ Start Main GP", style=discord.ButtonStyle.blurple, custom_id="gp_start_race")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_gp = database.get_active_gp_race(interaction.guild_id)
        if not active_gp:
            await interaction.followup.send("❌ No active GP scheduled.", ephemeral=True)
            return
            
        entries = database.get_gp_entries_full(active_gp['race_id'])
        if len(entries) < 2:
            await interaction.followup.send("❌ Cannot start the race. Need at least 2 registered entries.", ephemeral=True)
            return

        try:
            import json
            weather_timeline = None
            weather_raw = active_gp.get('weather', 'Sunny')
            try:
                weather_data = json.loads(weather_raw)
                weather_timeline = weather_data.get('timeline')
            except Exception:
                weather_timeline = [weather_raw] * active_gp['laps']
                
            # Initialize generator
            generator = race.simulate_gp_generator(entries, active_gp['track'], active_gp['laps'], weather_timeline=weather_timeline)
            
            # 1. Setup Phase
            setup_event = next(generator)
            teams_list = setup_event[1]
            setup_logs = setup_event[2]
            current_weather = setup_event[3]
            
            # Register active race for real-time strategy updates
            ACTIVE_RACES[interaction.guild_id] = {
                "teams": teams_list,
                "lap": 0,
                "snapshot": {}
            }
            
            progress_embed = utils.create_embed(
                title=f"🏎️ LIVE: Grand Prix of {active_gp['track']}",
                description="⏱️ **Qualifying and grid setups are initializing...**",
                color=utils.COLOR_QUALIFYING
            )
            live_message = await interaction.followup.send(embed=progress_embed)
            
            grid_desc = "\n".join(setup_logs)
            progress_embed.description = grid_desc
            await live_message.edit(embed=progress_embed)
            await asyncio.sleep(6)
            
            lap_states = {}
            results = []
            finish_logs = []
            
            # 2. Lap-by-Lap Simulator Print Loop
            for item in generator:
                if item[0] == "lap":
                    l_num = item[1]
                    lap_events = item[2]
                    lap_snapshot = item[3]
                    current_weather = item[4]
                    
                    lap_states[l_num] = lap_snapshot
                    ACTIVE_RACES[interaction.guild_id]["lap"] = l_num
                    ACTIVE_RACES[interaction.guild_id]["snapshot"] = lap_snapshot
                    
                    # Spawn telemetry DM tasks for all active drivers at their actual lap finish times
                    max_lap_time = 45.0
                    active_lap_times = []
                    for entry in entries:
                        dr_uid = entry['user_id']
                        dr_discord_id = entry['discord_id']
                        dr_state = lap_snapshot.get(dr_uid) or lap_snapshot.get(str(dr_uid))
                        if dr_state and not dr_state.get('dnf', False):
                            # Find the actual last lap time for this driver
                            t_obj = None
                            for t in teams_list:
                                if t.discord_id == dr_discord_id:
                                    t_obj = t
                                    break
                            
                            if t_obj:
                                active_lap_times.append(t_obj.last_lap_time)
                                
                    leader_lap_time = 45.0
                    if active_lap_times:
                        leader_lap_time = min(active_lap_times)
                        
                    lap_embed = utils.create_embed(
                        title=f"🏎️ Grand Prix Lap {l_num}/{active_gp['laps']} | 🌤️ {current_weather}",
                        description="\n".join(lap_events),
                        color=utils.COLOR_RACE_RESULTS
                    )
                    view = GPLapTelemetryView(l_num, lap_snapshot, entries)
                    await interaction.channel.send(embed=lap_embed, view=view)
                    
                    # Sleep for the actual physical duration of the leading driver to sync simulator clock
                    await asyncio.sleep(leader_lap_time)
                    
                elif item[0] == "finish":
                    results = item[1]
                    finish_logs = item[2]
                    
            # Cleanup active GP registry
            if interaction.guild_id in ACTIVE_RACES:
                del ACTIVE_RACES[interaction.guild_id]
                
            # 3. Save results to DB
            winner_id = None
            for res in results:
                if res['finish_position'] == 1:
                    winner_id = res['user_id']
                    break
                    
            database.save_gp_results(active_gp['race_id'], results, winner_id)
            database.update_gp_status(active_gp['race_id'], "Finished")
            if active_gp.get('season_id'):
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE season_calendar SET status = 'Finished' WHERE season_id = ? AND status = 'Running'",
                    (active_gp['season_id'],)
                )
                conn.commit()
                conn.close()
            
            # 4. Print final results
            chunks = []
            current_chunk = []
            for log in finish_logs:
                current_chunk.append(log)
                if len(current_chunk) == 20:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                
            results_embed = utils.create_embed(
                title=f"🏁 RESULTS: Grand Prix of {active_gp['track']} Finished",
                description=f"🏆 **Grand Prix completed successfully!**\n\n" + (chunks[0] if chunks else ""),
                color=utils.COLOR_SUCCESS
            )
            await interaction.channel.send(embed=results_embed)
            
            for c in chunks[1:]:
                await interaction.channel.send(embed=utils.create_embed(
                    title="🏁 Grand Prix Results (Continued)",
                    description=c,
                    color=utils.COLOR_SUCCESS
                ))
                
            leaderboard_results = database.get_leaderboard(interaction.guild_id, "points")
            if leaderboard_results:
                leaderboard_desc = ""
                for idx, row in enumerate(leaderboard_results[:10]):
                    leaderboard_desc += f"**{idx + 1}.** {row['team_name']} — **{row['score']} pts**\n"
                    
                standings_embed = utils.create_embed(
                    title="🏆 Season Championship Standings (Updated)",
                    description=leaderboard_desc,
                    color=utils.COLOR_WARNING
                )
                await interaction.channel.send(embed=standings_embed)
                
            await interaction.message.edit(embed=utils.create_embed(
                title="🏁 Grand Prix Admin Panel",
                description=f"🏁 **Grand Prix Completed!**\n🗺️ **Track:** `{active_gp['track']}`\n📊 **Stage:** `Finished`",
                color=utils.COLOR_SUCCESS
            ), view=None)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ **Error processing GP results:** `{e}`")



class GPCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel GP", style=discord.ButtonStyle.red, custom_id="gp_cancel")

    async def callback(self, interaction: discord.Interaction):
        success, msg = database.cancel_active_gp(interaction.guild_id)
        if success:
            view = GPAdminView(interaction.guild_id)
            desc = "❌ **No active Grand Prix scheduled.**\nUse the **Select a Track** dropdown below to schedule one."
            embed = utils.create_embed(title="🏁 Grand Prix Admin Panel", description=desc, color=utils.COLOR_WARNING)
            
            announcement = utils.create_embed(title="🏁 Grand Prix Cancelled", description="The scheduled Grand Prix event has been cancelled by an administrator.", color=utils.COLOR_ERROR)
            await interaction.channel.send(embed=announcement)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)



class GPPromptDMsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📩 Send DM Tyre Prompts", style=discord.ButtonStyle.secondary, custom_id="gp_prompt_dms")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        active_gp = database.get_active_gp_race(interaction.guild_id)
        if not active_gp:
            await interaction.followup.send("❌ No active GP scheduled.", ephemeral=True)
            return
            
        entries = database.get_gp_entries_full(active_gp['race_id'])
        if not entries:
            await interaction.followup.send("❌ No entrants registered yet.", ephemeral=True)
            return
            
        status = active_gp.get("status", "Created")
        
        if status in ["Created", "Q1_Ready"]:
            active_drivers = entries
            session_name = "Qualifying Q1"
        elif status == "Q2_Ready":
            active_drivers = [e for e in entries if e.get("start_position") is None or e.get("start_position") > 99]
            session_name = "Qualifying Q2"
        elif status == "Q3_Ready":
            active_drivers = [e for e in entries if e.get("start_position") is None]
            session_name = "Qualifying Q3"
        else:
            await interaction.followup.send("❌ DM prompts are only sent during qualifying setup stages.", ephemeral=True)
            return

        sent_count = 0
        failed_drivers = []
        for drv in active_drivers:
            try:
                user = interaction.client.get_user(drv['discord_id']) or await interaction.client.fetch_user(drv['discord_id'])
                if user:
                    embed = utils.create_embed(
                        title=f"🏎️ Qualifying Tyre Selection - {active_gp['name']}",
                        description=(
                            f"Choose your tyre compound for the upcoming **{session_name}** session at **{active_gp['track']}**:\n\n"
                            f"• **Soft:** Maximum qualifying pace (+6.0s), high wear.\n"
                            f"• **Medium:** Balanced pace (+3.0s), medium wear.\n"
                            f"• **Hard:** Minimum pace (+0.0s), low wear.\n\n"
                            f"*If you do not select a tyre, it will default to Soft compound.*"
                        ),
                        color=utils.COLOR_QUALIFYING
                    )
                    view = QualiTyresSelectView(drv['user_id'], active_gp['race_id'])
                    await user.send(embed=embed, view=view)
                    sent_count += 1
            except Exception:
                failed_drivers.append(drv['team_name'])
                
        failed_desc = f"\n⚠️ Failed to DM (DMs closed): {', '.join(failed_drivers)}" if failed_drivers else ""
        await interaction.followup.send(f"✅ Successfully sent qualifying tyre selection DMs to {sent_count} active drivers.{failed_desc}", ephemeral=True)



class GPAdminView(discord.ui.View):
    def __init__(self, guild_id, laps=15):
        super().__init__(timeout=300.0)
        self.guild_id = guild_id
        
        active_gp = database.get_active_gp_race(guild_id)
        if not active_gp:
            self.add_item(GPTrackSelect(laps=laps))
        else:
            status = active_gp.get("status", "Created")
            if status in ["Created", "Q1_Ready", "Q2_Ready", "Q3_Ready"]:
                self.add_item(GPPromptDMsButton())
                
            if status == "Created":
                self.add_item(GPStartQualiButton("Q1", "Start Q1"))
            elif status == "Q1_Ready":
                self.add_item(GPStartQualiButton("Q1", "Run Q1 Session"))
            elif status == "Q2_Ready":
                self.add_item(GPStartQualiButton("Q2", "Run Q2 Session"))
            elif status == "Q3_Ready":
                self.add_item(GPStartQualiButton("Q3", "Run Q3 Session"))
            elif status == "GridSet":
                self.add_item(GPStartRaceButton())
                
            self.add_item(GPCancelButton())










async def track_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    choices = []
    for t_name in race.TRACK_PROFILES.keys():
        if current.lower() in t_name.lower():
            choices.append(app_commands.Choice(name=t_name[:100], value=t_name))
        if len(choices) >= 25:
            break
    return choices


class RacingCog(commands.Cog):
    """Cog containing all Grand Prix, Duels, Sprints, and Pit Strategy commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="race", description="Challenge another user to a 1v1 racing duel!")
    @app_commands.describe(
        opponent="The user to challenge to a 1v1 duel",
        wager="Optional credit wager amount (e.g. 500)",
        laps="Race distance in laps (1 to 20 laps, default 3 laps)",
        track="Select official F1 track (e.g. Monza, Monaco, Silverstone, Spa)"
    )
    @app_commands.autocomplete(track=track_autocomplete)
    @app_commands.guild_only()
    async def race_cmd(self, interaction: discord.Interaction, opponent: discord.User, wager: int = 0, laps: int = 3, track: str = None):
        if opponent.bot or opponent == interaction.user:
            await interaction.response.send_message("❌ Invalid opponent.", ephemeral=True)
            return

        if wager < 0:
            await interaction.response.send_message("❌ Wager amount cannot be negative.", ephemeral=True)
            return

        if laps < 1 or laps > 20:
            await interaction.response.send_message("❌ Race distance must be between 1 and 20 laps.", ephemeral=True)
            return

        if track and track not in race.TRACK_PROFILES:
            await interaction.response.send_message(f"❌ Invalid track profile `{track}`. Please select an official F1 track from the list.", ephemeral=True)
            return

        p1 = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        p2 = database.get_user_by_discord_id(opponent.id, interaction.guild_id)

        if not p1 or not p2:
            msg = "You must create a profile using `/start` first." if not p1 else f"{opponent.mention} has not created a profile yet."
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        if wager > 0:
            if p1['money'] < wager:
                await interaction.response.send_message(f"❌ You do not have `{wager:,} credits` to wager.", ephemeral=True)
                return
            if p2['money'] < wager:
                await interaction.response.send_message(f"❌ {opponent.mention} does not have `{wager:,} credits` to wager.", ephemeral=True)
                return

        view = RaceChallengeView(p1, p2, interaction.guild_id, wager=wager, laps=laps, track_name=track)
        wager_text = f"\n💰 **Wager Amount:** `{wager:,} credits` (Winner takes **{wager * 2:,}¢**!)" if wager > 0 else ""
        track_text = f"\n📍 **Track venue:** `{track}`" if track else ""
        embed = utils.create_embed(
            title=f"🏁 1v1 Race Challenge ({laps} Laps)!",
            description=(
                f"{interaction.user.mention} (**{p1['team_name']}**) has challenged {opponent.mention} (**{p2['team_name']}**) to a {laps}-lap duel!{track_text}{wager_text}\n\n"
                f"Click **Accept Challenge** to line up on the grid!"
            ),
            color=utils.COLOR_QUALIFYING
        )
        await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)


    @app_commands.command(name="joinrace", description="Register and pay 500¢ entry fee to join the upcoming Grand Prix.")
    @app_commands.guild_only()
    async def join_race(self, interaction: discord.Interaction):
        success, msg = database.register_gp_entry(interaction.user.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏁 Race Entry", description=msg, color=color))

    @app_commands.command(name="leaverace", description="Leave the upcoming Grand Prix and receive a refund of your 500¢ entry fee.")

    @app_commands.guild_only()
    async def leave_race(self, interaction: discord.Interaction):
        success, msg = database.unregister_gp_entry(interaction.user.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏁 Race Withdrawal", description=msg, color=color))

    @app_commands.command(name="grid", description="View the current registration list and qualifying grid.")
    @app_commands.guild_only()
    async def grid_cmd(self, interaction: discord.Interaction):
        active_gp = database.get_active_gp_race(interaction.guild_id)
        if not active_gp:
            await interaction.response.send_message("❌ No active Grand Prix scheduled right now.", ephemeral=True)
            return

        entries = database.get_gp_entries_full(active_gp['race_id'])
        if not entries:
            await interaction.response.send_message(f"🏁 **Grand Prix of {active_gp['track']}** is scheduled, but no drivers have registered yet! Use `/joinrace` to join.", ephemeral=True)
            return

        desc = f"🏁 **GRAND PRIX OF {active_gp['track'].upper()} — GRID LIST**\n\n"
        for idx, entry in enumerate(entries):
            pos_str = f"P{entry['start_position']}" if entry.get('start_position') else f"#{idx + 1}"
            desc += f"• **{pos_str}:** {entry['team_name']} (`{entry['country'] or '🏁'}`)\n"

        embed = utils.create_embed(title="🏁 Starting Grid", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="standings", description="View current overall Grand Prix points championship standings.")
    @app_commands.guild_only()
    async def standings_cmd(self, interaction: discord.Interaction):
        results = database.get_leaderboard(interaction.guild_id, "points")
        if not results:
            await interaction.response.send_message("❌ No driver points recorded yet on this server.", ephemeral=True)
            return

        desc = "🏆 **WORLD DRIVER CHAMPIONSHIP (WDC) STANDINGS**\n\n"
        for idx, row in enumerate(results[:15]):
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"**{idx + 1}.**"))
            desc += f"{medal} **{row['team_name']}** — **{row['score']} pts** ({row['wins']} wins)\n"

        embed = utils.create_embed(title="🏆 Championship Standings", description=desc, color=utils.COLOR_GOLD)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="results", description="View final standings of the last completed Grand Prix.")
    @app_commands.guild_only()
    async def results_cmd(self, interaction: discord.Interaction):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT race_id, track, created_at FROM races WHERE guild_id = ? AND status = 'Finished' ORDER BY race_id DESC LIMIT 1", (interaction.guild_id,))
        last_race = cursor.fetchone()
        conn.close()

        if not last_race:
            await interaction.response.send_message("❌ No completed Grand Prix races recorded yet.", ephemeral=True)
            return

        entries = database.get_gp_entries_full(last_race['race_id'])
        desc = f"🏁 **LAST GRAND PRIX — {last_race['track'].upper()}**\n\n"
        entries_sorted = sorted(entries, key=lambda x: (x.get('finish_position') if x.get('finish_position') is not None else 999))

        for entry in entries_sorted:
            pos = f"P{entry['finish_position']}" if entry.get('finish_position') else "DNF"
            pts = entry.get('points_earned', 0)
            desc += f"• **{pos}:** {entry['team_name']} — `+{pts} pts`\n"

        embed = utils.create_embed(title="🏁 Last Grand Prix Results", description=desc, color=utils.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)



    @app_commands.command(name="strategy", description="Configure your starting race pacing strategy and tyres.")
    @app_commands.guild_only()
    async def strategy_setup(self, interaction: discord.Interaction):
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start` first.", ephemeral=True)
            return

        view = StrategyConfigView(interaction.user.id, interaction.guild_id)

        desc = (
            f"🏎️ **Starting Pacing Mode:** `{view.pace}`\n"
            f"🛞 **Starting Tyres:** `{view.start_tyre}`\n\n"
            f"*💡 Selections are saved in real-time. This configuration sheet is private and hidden from other competitors.*"
        )
        embed = utils.create_embed(
            title="⚙️ Racing Strategy Configuration Board",
            description=desc,
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="pit", description="Schedule a pit stop for the very next lap of the active Grand Prix.")
    @app_commands.describe(
        tyre="Select the tyre compound to switch to"
    )
    @app_commands.choices(tyre=[
        app_commands.Choice(name="🟥 Soft Tyres", value="Soft"),
        app_commands.Choice(name="🟨 Medium Tyres", value="Medium"),
        app_commands.Choice(name="⬜ Hard Tyres", value="Hard"),
        app_commands.Choice(name="🟦 Intermediates", value="Intermediates")
    ])
    @app_commands.guild_only()
    async def gp_pit_command(self, interaction: discord.Interaction, tyre: app_commands.Choice[str]):
        race_state = ACTIVE_RACES.get(interaction.guild_id)
        if not race_state or "teams" not in race_state:
            await interaction.response.send_message("❌ There is no active Grand Prix running right now.", ephemeral=True)
            return

        team_obj = None
        for t in race_state["teams"]:
            if t.discord_id == interaction.user.id:
                team_obj = t
                break

        if not team_obj:
            await interaction.response.send_message("❌ You are not participating in the active Grand Prix.", ephemeral=True)
            return

        if team_obj.dnf:
            await interaction.response.send_message("❌ You have already retired from this race.", ephemeral=True)
            return

        team_obj.pit_next_lap = True
        team_obj.pit_next_lap_tyre = tyre.value

        await interaction.response.send_message(f"✅ **Pit stop scheduled!** Your driver will pit at the end of the current lap to switch to **{tyre.name}** tyres.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RacingCog(bot))
