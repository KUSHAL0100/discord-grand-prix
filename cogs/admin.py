import discord
from discord.ext import commands
from discord import app_commands
import shutil
import os
from datetime import datetime

import config
import database
import utils

def is_admin():
    """Check if the user is an admin or has the configured Admin role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if hasattr(interaction.user, 'roles'):
            role = discord.utils.get(interaction.user.roles, name=config.ADMIN_ROLE_NAME)
            if role is not None:
                return True
        return False
    return app_commands.check(predicate)

class AdminCog(commands.Cog):
    """Cog containing all Administrator and Server Management commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Game administrator controls for economy and stats.")
    season_admin_group = app_commands.Group(name="season", description="Admin controls for World Driver Championship (WDC) Seasons")

    @admin_group.command(name="setstat", description="Set a driver skill level or garage part level for a user.")
    @app_commands.describe(
        target="The user to modify",
        stat_name="Stat to modify (engine, aerodynamics, tyres, ers, reliability, pace, qual, wet_skill, etc.)",
        value="New level (1 to 20 for parts, 1 to 100 for skills)"
    )
    @is_admin()
    @app_commands.guild_only()
    async def admin_setstat(self, interaction: discord.Interaction, target: discord.User, stat_name: str, value: int):
        stat_name = stat_name.lower()
        valid_garage = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
        valid_driver = ["pace", "qual", "wet_skill", "consistency", "aggression", "overtaking"]

        if stat_name not in valid_garage and stat_name not in valid_driver:
            valid_list = ", ".join(valid_garage + valid_driver)
            await interaction.response.send_message(f"❌ Invalid stat name. Must be one of: `{valid_list}`", ephemeral=True)
            return

        if stat_name in valid_garage and (value < 1 or value > config.MAX_STAT_LEVEL):
            await interaction.response.send_message(f"❌ Garage part levels must be between 1 and {config.MAX_STAT_LEVEL}.", ephemeral=True)
            return

        if stat_name in valid_driver and (value < 1 or value > config.MAX_DRIVER_STAT_LEVEL):
            await interaction.response.send_message(f"❌ Driver skill levels must be between 1 and {config.MAX_DRIVER_STAT_LEVEL}.", ephemeral=True)
            return

        success, msg = database.admin_set_user_stat(target.id, interaction.guild_id, stat_name, value)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="⚙️ Admin Stat Modification", description=msg, color=color))

    @admin_group.command(name="resetprofile", description="Completely reset a user's racing profile.")
    @app_commands.describe(target="The user whose profile will be completely reset")
    @is_admin()
    @app_commands.guild_only()
    async def admin_resetprofile(self, interaction: discord.Interaction, target: discord.User):
        prof = database.get_user_by_discord_id(target.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ Target user does not have a profile on this server.", ephemeral=True)
            return

        success, msg = database.reset_user_profile(target.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="⚙️ Admin Profile Reset", description=msg, color=color))

    @season_admin_group.command(name="create", description="Create a new World Driver Championship Season.")
    @app_commands.describe(name="Season name (e.g. Season 1, 2026 Championship)")
    @is_admin()
    @app_commands.guild_only()
    async def admin_season_create(self, interaction: discord.Interaction, name: str):
        success, msg = database.create_season(interaction.guild_id, name)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏆 World Driver Championship Season", description=msg, color=color))

    @season_admin_group.command(name="end", description="Conclude active season and declare the World Driver Champion!")
    @is_admin()
    @app_commands.guild_only()
    async def admin_season_end(self, interaction: discord.Interaction):
        success, msg, season, standings = database.end_active_season(interaction.guild_id)
        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
            
        standings_desc = f"🏆 **FINAL WDC DRIVER STANDINGS — {season['name']}**\n\n"
        for idx, s in enumerate(standings[:10]):
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"**{idx + 1}.**"))
            standings_desc += f"{medal} **{s['team_name']}** ({s['driver_name']}) — **{s['points']} pts** ({s['wins']} wins)\n"
            
        champion = standings[0] if standings else {"team_name": "Unknown Driver"}
        embed = utils.create_embed(
            title=f"👑 {season['name']} — Checkered Flag & World Champion",
            description=f"🎉 **THE SEASON HAS OFFICIALLY CONCLUDED!**\n\n🥇 **World Driver Champion:** **{champion['team_name']}**!\n\n" + standings_desc,
            color=utils.COLOR_GOLD
        )
        await interaction.response.send_message(embed=embed)

    @season_admin_group.command(name="cancel", description="Cancel the active Season.")
    @is_admin()
    @app_commands.guild_only()
    async def admin_season_cancel(self, interaction: discord.Interaction):
        success, msg = database.cancel_active_season(interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏆 Season Cancellation", description=msg, color=color))

    @app_commands.command(name="give", description="Give credits to a player (Admin only).")
    @app_commands.describe(user="The player to receive credits", amount="Amount of credits to award")
    @is_admin()
    @app_commands.guild_only()
    async def admin_give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
            return

        target_prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
        if not target_prof:
            await interaction.response.send_message(f"❌ User {user.mention} does not have a profile. They must run `/start` first.", ephemeral=True)
            return

        database.update_user_balance(target_prof['user_id'], amount)
        embed = utils.create_embed(
            title="💰 Admin Grant",
            description=f"Successfully granted **{amount:,} credits** to {user.mention}!",
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove", description="Deduct credits from a player (Admin only).")
    @app_commands.describe(user="The player to deduct credits from", amount="Amount of credits to deduct")
    @is_admin()
    @app_commands.guild_only()
    async def admin_remove(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
            return

        target_prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
        if not target_prof:
            await interaction.response.send_message(f"❌ User {user.mention} does not have a profile.", ephemeral=True)
            return

        actual_deducted = database.update_user_balance(target_prof['user_id'], -amount)
        embed = utils.create_embed(
            title="💰 Admin Deduction",
            description=f"Successfully deducted **{actual_deducted:,} credits** from {user.mention}.",
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="broadcast", description="Broadcast an announcement message to a designated channel (Admin only).")
    @app_commands.describe(channel="The text channel to post the announcement in", message="The announcement message content")
    @is_admin()
    @app_commands.guild_only()
    async def admin_broadcast(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        embed = utils.create_embed(
            title="📢 Official Announcement",
            description=message,
            color=utils.COLOR_INFO
        )
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send announcement: {str(e)}", ephemeral=True)

    @app_commands.command(name="dbbackup", description="Trigger manual backup copy of SQLite DB (Admin only).")
    @is_admin()
    @app_commands.guild_only()
    async def admin_dbbackup(self, interaction: discord.Interaction):
        if not os.path.exists(config.DATABASE_PATH):
            await interaction.response.send_message("❌ Database file does not exist yet.", ephemeral=True)
            return
            
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{config.DATABASE_PATH}"
        try:
            shutil.copy2(config.DATABASE_PATH, backup_filename)
            await interaction.response.send_message(
                embed=utils.create_embed(
                    title="💾 Database Backup Success",
                    description=f"Successfully backed up **{config.DATABASE_PATH}** to **{backup_filename}**.",
                    color=utils.COLOR_SUCCESS
                )
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Backup failed: {str(e)}", ephemeral=True)

    @app_commands.command(name="debug", description="Toggle verbose terminal logs (Admin only).")
    @app_commands.describe(toggle="Turn debug logs on/off")
    @is_admin()
    @app_commands.guild_only()
    async def admin_debug(self, interaction: discord.Interaction, toggle: bool):
        from bot import set_debug_mode
        set_debug_mode(toggle)
        status = "ON" if toggle else "OFF"
        await interaction.response.send_message(
            embed=utils.create_embed(
                title="⚙️ Debug Mode",
                description=f"Verbose debugging terminal logs have been turned **{status}**.",
                color=utils.COLOR_SUCCESS
            )
        )

async def setup(bot: commands.Bot):
    cog = AdminCog(bot)
    # Remove season group from Cog's top-level app commands to prevent CommandAlreadyRegistered
    cog.__cog_app_commands__ = [cmd for cmd in cog.__cog_app_commands__ if cmd.name != "season"]
    # Add season group as a subcommand under admin group
    cog.admin_group.add_command(cog.season_admin_group)
    # Register the Cog (which automatically registers admin_group and top-level commands)
    await bot.add_cog(cog)
