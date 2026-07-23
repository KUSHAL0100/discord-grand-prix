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
    def __init__(self, user1_id, user2_id, guild_id):
        super().__init__(timeout=60.0)
        self.user1_id = user1_id
        self.user2_id = user2_id
        self.guild_id = guild_id
        self.p1_strategy = "Balanced"
        self.p2_strategy = "Balanced"
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

class RaceChallengeView(discord.ui.View):
    def __init__(self, challenger_prof, opponent_prof, guild_id, wager=0, laps=3, track_name=None):
        super().__init__(timeout=60.0)
        self.challenger_prof = challenger_prof
        self.opponent_prof = opponent_prof
        self.guild_id = guild_id
        self.wager = max(0, wager)
        self.laps = max(1, min(10, laps))
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
        await interaction.response.edit_message(view=self)

        pace_view = RacePaceView(self.challenger_prof['discord_id'], self.opponent_prof['discord_id'], self.guild_id)
        pace_embed = utils.create_embed(
            title=f"⏱️ Strategy Setup — Choose Your Race Pacing ({self.laps} Laps)!",
            description=(
                f"**{self.challenger_prof['team_name']}** vs **{self.opponent_prof['team_name']}**\n\n"
                f"Click your pace strategy button below before the lights go out!\n"
                f"• **Push (Aggressive):** Maximum speed, higher tyre wear.\n"
                f"• **Standard (Balanced):** Balanced pace & wear.\n"
                f"• **Save (Conservative):** Protects tyres & engine thermals."
            ),
            color=utils.COLOR_QUALIFYING
        )
        msg = await interaction.followup.send(embed=pace_embed, view=pace_view)
        
        # Wait for both drivers to select or max 15 seconds timeout
        try:
            await asyncio.wait_for(pace_view.ready_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            pass

        t1_data = database.get_full_team_profile(self.challenger_prof['discord_id'], self.guild_id)
        t2_data = database.get_full_team_profile(self.opponent_prof['discord_id'], self.guild_id)
        
        t1_data['pref_strategy'] = pace_view.p1_strategy
        t2_data['pref_strategy'] = pace_view.p2_strategy

        winner, loser, lap_logs, qual_logs = race.simulate_duel(t1_data, t2_data, total_laps=self.laps, track_name=self.track_name)

        # --- PHASE 1: Show Qualifying Info ---
        quali_text = "\n".join(qual_logs)
        quali_embed = utils.create_embed(
            title=f"🏁 Race Starting — {self.laps} Laps!",
            description=quali_text,
            color=utils.COLOR_QUALIFYING
        )
        race_msg = await interaction.followup.send(embed=quali_embed)

        # --- PHASE 2: Lap-by-Lap Live Updates (4s delay per lap) ---
        for lap_idx, lap_events in enumerate(lap_logs):
            await asyncio.sleep(4)
            if isinstance(lap_events, list):
                lap_text = "\n".join(lap_events)
            else:
                lap_text = str(lap_events)
            
            lap_embed = utils.create_embed(
                title=f"🏎️ Lap {lap_idx + 1} / {self.laps}",
                description=lap_text,
                color=0xF5A623
            )
            await interaction.followup.send(embed=lap_embed)

        # --- PHASE 3: Final Results & Rewards ---
        await asyncio.sleep(3)

        if self.wager > 0:
            database.update_user_balance(winner['user_id'], self.wager)
            database.update_user_balance(loser['user_id'], -self.wager)
            wager_str = f"\n💰 **Wager Paid:** **+{self.wager:,} credits** won!"
        else:
            wager_str = ""

        database.record_race_result(winner['user_id'], loser['user_id'], self.guild_id)

        telemetry_chart = utils.generate_race_telemetry_graph(lap_logs)
        chart_file = discord.File(telemetry_chart, filename="telemetry_chart.png")

        victory_radio = utils.get_victory_team_radio(winner['team_name'])

        summary_desc = (
            f"🏆 **WINNER:** **{winner['team_name']}**!{wager_str}\n"
            f"{victory_radio}\n\n"
            f"⏱️ **Distance:** `{self.laps} Laps`\n"
            f"📊 **Rewards Earned:**\n"
            f"  • **Winner ({winner['team_name']}):** `+{config.WIN_PRIZE_CREDITS:,}¢` | `+{config.WIN_XP:,} XP`\n"
            f"  • **Runner-up ({loser['team_name']}):** `+{config.LOSS_PRIZE_CREDITS:,}¢` | `+{config.LOSS_XP:,} XP`"
        )

        embed = utils.create_embed(
            title=f"🏁 RACE RESULTS: {winner['team_name']} VICTORY!",
            description=summary_desc,
            color=utils.COLOR_SUCCESS
        )
        embed.set_image(url="attachment://telemetry_chart.png")
        await interaction.followup.send(embed=embed, file=chart_file)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_prof['discord_id']:
            await interaction.response.send_message("❌ Only the challenged opponent can decline this race!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Race challenge declined.", embed=None, view=None)

class RacingCog(commands.Cog):
    """Cog containing all Grand Prix, Duels, Sprints, and Pit Strategy commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def track_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for t_name in race.TRACK_PROFILES.keys():
            if current.lower() in t_name.lower():
                choices.append(app_commands.Choice(name=t_name[:100], value=t_name))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="race", description="Challenge another user to a 1v1 racing duel!")
    @app_commands.describe(
        opponent="The user to challenge to a 1v1 duel",
        wager="Optional credit wager amount (e.g. 500)",
        laps="Race distance in laps (1 to 10 laps, default 3 laps)",
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

        if laps < 1 or laps > 10:
            await interaction.response.send_message("❌ Race distance must be between 1 and 10 laps.", ephemeral=True)
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


    @app_commands.command(name="joinrace", description="Register and pay 1000¢ entry fee to join the upcoming Grand Prix.")
    @app_commands.guild_only()
    async def join_race(self, interaction: discord.Interaction):
        success, msg = database.register_gp_entry(interaction.user.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏁 Race Entry", description=msg, color=color))

    @app_commands.command(name="leaverace", description="Leave the upcoming Grand Prix and receive a refund of your 1000¢ entry fee.")
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

async def setup(bot: commands.Bot):
    await bot.add_cog(RacingCog(bot))
