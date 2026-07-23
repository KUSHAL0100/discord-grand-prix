import discord
from discord.ext import commands
from discord import app_commands

import database
import utils
import race

class SimulatorCog(commands.Cog):
    """Cog containing Track Practice Simulator and Help documentation commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="practice", description="Run a solo practice session on an official F1 track to gain Track Mastery.")
    @app_commands.guild_only()
    async def practice_track(self, interaction: discord.Interaction):
        prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return
            
        class PracticeTrackSelect(discord.ui.Select):
            def __init__(self, user_id):
                self.user_id = user_id
                options = []
                for t_name, profile in list(race.TRACK_PROFILES.items())[:25]:
                    options.append(discord.SelectOption(label=t_name[:100], value=t_name, description=profile.get('description', '')[:100]))
                super().__init__(placeholder="Select an Official F1 Track to Practice...", min_values=1, max_values=1, options=options)

            async def callback(self, interaction: discord.Interaction):
                track_choice = self.values[0]
                success, msg, bonus = database.record_track_practice(self.user_id, track_choice)
                color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
                await interaction.response.send_message(embed=utils.create_embed(title="🏎️ Track Simulator Practice Session", description=msg, color=color))

        view = discord.ui.View(timeout=180.0)
        view.add_item(PracticeTrackSelect(prof['user_id']))
        embed = utils.create_embed(
            title="🏎️ Track Practice & Simulator",
            description=(
                "Run a solo practice session on any official F1 calendar track to build **Track Mastery**.\n\n"
                "⏱️ **Mastery Benefit:** Up to **`-0.15s` lap time bonus** per track (+4% Track Familiarity per session).\n"
                "💰 **Session Fee:** **`500¢`** per practice session.\n"
                "📅 **Daily Limit:** Maximum **3 practice sessions per day** to prevent single-track spamming.\n\n"
                "Select a track below to begin your practice run:"
            ),
            color=utils.COLOR_QUALIFYING
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="help", description="Show detailed guide on how to play Discord Grand Prix.")
    @app_commands.guild_only()
    async def help_cmd(self, interaction: discord.Interaction):
        desc = (
            "🏎️ **DISCORD GRAND PRIX — DRIVER & ADMIN GUIDE**\n\n"
            "🏁 **1. Getting Started**\n"
            "• `/start <team_name>` — Register your racing team & claim starting funds.\n"
            "• `/profile` — View PNG profile card, XP, balance, and car stats.\n"
            "• `/inventory` — View stored parts and equip preferred setups.\n\n"
            "🛠️ **2. Upgrades & Garage Management**\n"
            "• `/upgradeshop` — View part levels and upgrade prices.\n"
            "• `/upgrade <part>` — Boost Engine, Aero, Tyres, ERS, Reliability, or Pit Crew.\n"
            "• `/train <skill>` — Train Driver Pace, Quali, Wet Skill, and Overtaking.\n\n"
            "📦 **3. Loot Crates, Practice & Boosters**\n"
            "• `/crate` & `/open` — Unbox Rookie, Pro, or Champion Loot Crates.\n"
            "• `/practice` — Solo practice sessions for Track Mastery (-0.15s max bonus).\n"
            "• `/shop` & `/booster` — Buy consumable Tyre Warmers, ERS Injectors, or Radiators.\n\n"
            "🏎️ **4. Race Events & Competitions**\n"
            "• `/race <user>` — Challenge another user to a 1v1 sprint duel.\n"
            "• `/joinrace` — Register for the server Grand Prix event (1,000¢ entry fee).\n"
            "• `/strategy` — Set starting tyre compounds and pacing strategy.\n"
            "• `/sprint` & `/gp` — Scheduled Sprint and Grand Prix race weekend controls."
        )
        embed = utils.create_embed(title="📚 Racing Guide", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
