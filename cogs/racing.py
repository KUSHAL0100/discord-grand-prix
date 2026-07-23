import discord
from discord.ext import commands
from discord import app_commands
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

    @discord.ui.button(label="🔥 Push (P1)", style=discord.ButtonStyle.danger)
    async def p1_push(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user1_id:
            await interaction.response.send_message("❌ This button is for Driver 1.", ephemeral=True)
            return
        self.p1_strategy = "Push"
        self.p1_done = True
        await interaction.response.send_message("✅ Selected **Push (Aggressive)** pace!", ephemeral=True)

    @discord.ui.button(label="🟡 Standard (P1)", style=discord.ButtonStyle.primary)
    async def p1_standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user1_id:
            await interaction.response.send_message("❌ This button is for Driver 1.", ephemeral=True)
            return
        self.p1_strategy = "Balanced"
        self.p1_done = True
        await interaction.response.send_message("✅ Selected **Standard (Balanced)** pace!", ephemeral=True)

    @discord.ui.button(label="🟢 Save (P1)", style=discord.ButtonStyle.success)
    async def p1_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user1_id:
            await interaction.response.send_message("❌ This button is for Driver 1.", ephemeral=True)
            return
        self.p1_strategy = "Conservative"
        self.p1_done = True
        await interaction.response.send_message("✅ Selected **Save (Conservative)** pace!", ephemeral=True)

    @discord.ui.button(label="🔥 Push (P2)", style=discord.ButtonStyle.danger)
    async def p2_push(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user2_id:
            await interaction.response.send_message("❌ This button is for Driver 2.", ephemeral=True)
            return
        self.p2_strategy = "Push"
        self.p2_done = True
        await interaction.response.send_message("✅ Selected **Push (Aggressive)** pace!", ephemeral=True)

    @discord.ui.button(label="🟡 Standard (P2)", style=discord.ButtonStyle.primary)
    async def p2_standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user2_id:
            await interaction.response.send_message("❌ This button is for Driver 2.", ephemeral=True)
            return
        self.p2_strategy = "Balanced"
        self.p2_done = True
        await interaction.response.send_message("✅ Selected **Standard (Balanced)** pace!", ephemeral=True)

    @discord.ui.button(label="🟢 Save (P2)", style=discord.ButtonStyle.success)
    async def p2_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user2_id:
            await interaction.response.send_message("❌ This button is for Driver 2.", ephemeral=True)
            return
        self.p2_strategy = "Conservative"
        self.p2_done = True
        await interaction.response.send_message("✅ Selected **Save (Conservative)** pace!", ephemeral=True)

class RaceChallengeView(discord.ui.View):
    def __init__(self, challenger_prof, opponent_prof, guild_id, wager=0):
        super().__init__(timeout=60.0)
        self.challenger_prof = challenger_prof
        self.opponent_prof = opponent_prof
        self.guild_id = guild_id
        self.wager = wager

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
            title="⏱️ Strategy Setup — Choose Your Race Pacing!",
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
        await asyncio.sleep(8)

        t1_data = database.get_full_team_profile(self.challenger_prof['discord_id'], self.guild_id)
        t2_data = database.get_full_team_profile(self.opponent_prof['discord_id'], self.guild_id)
        
        t1_data['pref_strategy'] = pace_view.p1_strategy
        t2_data['pref_strategy'] = pace_view.p2_strategy

        winner, loser, lap_logs, qual_logs = race.simulate_duel(t1_data, t2_data)

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
            f"📊 **Rewards Earned:**\n"
            f"  • **Winner ({winner['team_name']}):** `+{config.WIN_PRIZE_CREDITS:,}¢` | `+{config.WIN_XP:,} XP`\n"
            f"  • **Runner-up ({loser['team_name']}):** `+{config.LOSS_PRIZE_CREDITS:,}¢` | `+{config.LOSS_XP:,} XP`\n\n"
            f"⏱️ **Qualifying Order:**\n"
            f"  • P1: **{qual_logs[0]}**\n"
            f"  • P2: **{qual_logs[1]}**\n\n"
            f"🏎️ **Race Lap Telemetry:**\n" + "\n".join(lap_logs[-1]["logs"])
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

    @app_commands.command(name="race", description="Challenge another user to a racing duel!")
    @app_commands.describe(opponent="The user to challenge to a 1v1 duel")
    @app_commands.guild_only()
    async def race_cmd(self, interaction: discord.Interaction, opponent: discord.User):
        if opponent.bot or opponent == interaction.user:
            await interaction.response.send_message("❌ Invalid opponent.", ephemeral=True)
            return

        p1 = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        p2 = database.get_user_by_discord_id(opponent.id, interaction.guild_id)

        if not p1 or not p2:
            msg = "You must create a profile using `/start` first." if not p1 else f"{opponent.mention} has not created a profile yet."
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        view = RaceChallengeView(p1, p2, interaction.guild_id)
        embed = utils.create_embed(
            title="🏁 1v1 Race Duel Challenge!",
            description=f"{interaction.user.mention} (**{p1['team_name']}**) has challenged {opponent.mention} (**{p2['team_name']}**) to a head-to-head Grand Prix duel!\n\nClick **Accept Challenge** to line up on the grid!",
            color=utils.COLOR_QUALIFYING
        )
        await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)

    @app_commands.command(name="duel", description="Alias for /race: Challenge another user to a 1v1 sprint duel.")
    @app_commands.describe(opponent="The user to challenge to a 1v1 duel")
    @app_commands.guild_only()
    async def duel_cmd(self, interaction: discord.Interaction, opponent: discord.User):
        await self.race_cmd.callback(self, interaction, opponent)

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
