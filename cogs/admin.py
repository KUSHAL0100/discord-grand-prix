import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Optional, Tuple, Any
import shutil
import os
from datetime import datetime
import math

import config
import database
import utils

def is_admin():
    """Check if the user is an admin, server owner, has the configured Admin role, or is a game admin."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return utils.is_admin_user(interaction)
    return app_commands.check(predicate)

def is_owner_or_mod():
    """Check if the user can manage game admins (server owner, administrator, or manage_guild perm)."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.user.guild_permissions.manage_guild:
            return True
        return False
    return app_commands.check(predicate)
async def track_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    import race
    choices = []
    for t_name in race.TRACK_PROFILES.keys():
        if current.lower() in t_name.lower():
            choices.append(app_commands.Choice(name=t_name[:100], value=t_name))
        if len(choices) >= 25:
            break
    return choices

class AdminCog(commands.Cog):
    """Cog containing all Administrator and Server Management commands."""
    
    admin_group = app_commands.Group(name="admin", description="Game administrator controls for economy and stats.")
    season_admin_group = app_commands.Group(name="season", description="Admin controls for World Driver Championship (WDC) Seasons")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @admin_group.command(name="stats", description="View server activity statistics & bot impact metrics (Admin only).")
    @app_commands.describe(timeframe="Filter statistics window (Today, Weekly, Monthly, or All-Time)")
    @app_commands.choices(timeframe=[
        app_commands.Choice(name="📅 Today (24 Hours)", value="today"),
        app_commands.Choice(name="🗓️ Weekly (Last 7 Days)", value="weekly"),
        app_commands.Choice(name="📆 Monthly (Last 30 Days)", value="monthly"),
        app_commands.Choice(name="🏆 All-Time Overview", value="all")
    ])
    @is_admin()
    @app_commands.guild_only()
    async def admin_stats(self, interaction: discord.Interaction, timeframe: Optional[app_commands.Choice[str]] = None):
        tf = timeframe.value if timeframe else "today"
        view = AdminStatsView(self.bot, interaction.guild_id, current_tf=tf)
        embed = view.build_embed(interaction.guild.name)
        await interaction.response.send_message(embed=embed, view=view)

    @admin_group.command(name="setstat", description="Set a driver skill level or garage part level for a user.")
    @app_commands.describe(
        target="The user to modify",
        stat_name="Select the garage component or driver skill to modify",
        value="New level (1 to 20 for garage parts, 1 to 100 for driver skills)"
    )
    @app_commands.choices(stat_name=[
        app_commands.Choice(name="🛠️ Engine Level (1 - 20)", value="engine"),
        app_commands.Choice(name="🛠️ Aerodynamics Level (1 - 20)", value="aerodynamics"),
        app_commands.Choice(name="🛠️ Tyres Level (1 - 20)", value="tyres"),
        app_commands.Choice(name="🛠️ ERS System Level (1 - 20)", value="ers"),
        app_commands.Choice(name="🛠️ Reliability Level (1 - 20)", value="reliability"),
        app_commands.Choice(name="🛠️ Pit Crew Level (1 - 20)", value="pit_crew"),
        app_commands.Choice(name="👤 Pace Skill (1 - 100)", value="pace"),
        app_commands.Choice(name="👤 Qualifying Skill (1 - 100)", value="qual"),
        app_commands.Choice(name="👤 Wet Skill (1 - 100)", value="wet_skill"),
        app_commands.Choice(name="👤 Consistency Skill (1 - 100)", value="consistency"),
        app_commands.Choice(name="👤 Aggression Skill (1 - 100)", value="aggression"),
        app_commands.Choice(name="👤 Overtaking Skill (1 - 100)", value="overtaking"),
    ])
    @is_admin()
    @app_commands.guild_only()
    async def admin_setstat(self, interaction: discord.Interaction, target: discord.User, stat_name: app_commands.Choice[str], value: int):
        stat_key = stat_name.value
        valid_garage = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
        valid_driver = ["pace", "qual", "wet_skill", "consistency", "aggression", "overtaking"]

        if stat_key in valid_garage and (value < 1 or value > config.MAX_STAT_LEVEL):
            await interaction.response.send_message(f"❌ Garage part levels must be between 1 and {config.MAX_STAT_LEVEL}.", ephemeral=True)
            return

        if stat_key in valid_driver and (value < 1 or value > config.MAX_DRIVER_STAT_LEVEL):
            await interaction.response.send_message(f"❌ Driver skill levels must be between 1 and {config.MAX_DRIVER_STAT_LEVEL}.", ephemeral=True)
            return

        success, msg = database.admin_set_user_stat(target.id, interaction.guild_id, stat_key, value)
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

    @admin_group.command(name="deleteuser", description="Permanently delete a user's entire profile. They will need to /start again.")
    @app_commands.describe(target="The user whose profile will be permanently deleted")
    @is_admin()
    @app_commands.guild_only()
    async def admin_deleteuser(self, interaction: discord.Interaction, target: discord.User):
        prof = database.get_user_by_discord_id(target.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ Target user does not have a profile on this server.", ephemeral=True)
            return

        success, msg = database.delete_user_profile(target.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🗑️ Admin Profile Deletion", description=msg, color=color))

    @admin_group.command(name="resetstandings", description="Reset all World Driver Championship (WDC) standings/points for the server.")
    @is_admin()
    @app_commands.guild_only()
    async def admin_resetstandings(self, interaction: discord.Interaction):
        success, msg = database.reset_wdc_standings(interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="⚙️ Admin WDC Standings Reset", description=msg, color=color))

    @admin_group.command(name="addadmin", description="Grant a user Game Admin access for bot commands.")
    @app_commands.describe(target="The user to grant Game Admin access to")
    @is_owner_or_mod()
    @app_commands.guild_only()
    async def admin_add_admin(self, interaction: discord.Interaction, target: discord.User):
        if target.bot:
            await interaction.response.send_message("❌ Cannot add a bot as a game admin.", ephemeral=True)
            return
        success, msg = database.add_bot_admin(target.id, interaction.guild_id, interaction.user.id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🛡️ Game Admin Management", description=msg, color=color))

    @admin_group.command(name="removeadmin", description="Revoke a user's Game Admin access.")
    @app_commands.describe(target="The user to revoke Game Admin access from")
    @is_owner_or_mod()
    @app_commands.guild_only()
    async def admin_remove_admin(self, interaction: discord.Interaction, target: discord.User):
        success, msg = database.remove_bot_admin(target.id, interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🛡️ Game Admin Management", description=msg, color=color))

    @admin_group.command(name="listadmins", description="View all users with Game Admin access.")
    @is_owner_or_mod()
    @app_commands.guild_only()
    async def admin_list_admins(self, interaction: discord.Interaction):
        admins = database.get_bot_admins(interaction.guild_id)
        if not admins:
            desc = "No game admins have been added yet.\nUse `/admin addadmin` to grant access."
        else:
            lines = []
            for i, a in enumerate(admins, 1):
                lines.append(f"**{i}.** <@{a['discord_id']}> — added by <@{a['added_by']}>")
            desc = "\n".join(lines)
        await interaction.response.send_message(embed=utils.create_embed(title="🛡️ Game Admins", description=desc, color=utils.COLOR_INFO))

    @admin_group.command(name="transfer_profile", description="Transfer a user's entire team profile and admin rights to another user.")
    @app_commands.describe(from_user="The user profile to transfer from", to_user="The new owner of the profile")
    @is_owner_or_mod()
    @app_commands.guild_only()
    async def admin_transfer_profile(self, interaction: discord.Interaction, from_user: discord.User, to_user: discord.User):
        if from_user.id == to_user.id:
            await interaction.response.send_message("❌ Source and target user cannot be the same.", ephemeral=True)
            return
        if to_user.bot:
            await interaction.response.send_message("❌ Cannot transfer profile to a bot account.", ephemeral=True)
            return
            
        success, msg = database.transfer_user_ownership(from_user.id, to_user.id, guild_id=interaction.guild_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🔄 Profile Ownership Transfer", description=msg, color=color))


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

    @season_admin_group.command(name="add_race", description="Add a normal Grand Prix to the active WDC season calendar.")
    @app_commands.describe(
        track="Select official F1 track to schedule",
        laps="Race distance length (number of laps, default 15)"
    )
    @app_commands.autocomplete(track=track_autocomplete)
    @is_admin()
    @app_commands.guild_only()
    async def add_season_race_cmd(self, interaction: discord.Interaction, track: str, laps: int = 15):
        import race
        active_season = database.get_active_season(interaction.guild_id)
        if not active_season:
            await interaction.response.send_message("❌ There is no active WDC season. Create one first using `/season create`.", ephemeral=True)
            return
        if track not in race.TRACK_PROFILES:
            await interaction.response.send_message("❌ Invalid track selection.", ephemeral=True)
            return
        
        success, msg = database.add_season_race(active_season['season_id'], track, laps, is_sprint=False)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏆 Season Calendar", description=msg, color=color))

    @season_admin_group.command(name="add_sprint_race", description="Add a Sprint race to the active WDC season calendar.")
    @app_commands.describe(
        track="Select official F1 track to schedule",
        laps="Sprint race distance length (number of laps, default 8)"
    )
    @app_commands.autocomplete(track=track_autocomplete)
    @is_admin()
    @app_commands.guild_only()
    async def add_season_sprint_cmd(self, interaction: discord.Interaction, track: str, laps: int = 8):
        import race
        active_season = database.get_active_season(interaction.guild_id)
        if not active_season:
            await interaction.response.send_message("❌ There is no active WDC season. Create one first using `/season create`.", ephemeral=True)
            return
        if track not in race.TRACK_PROFILES:
            await interaction.response.send_message("❌ Invalid track selection.", ephemeral=True)
            return
        
        success, msg = database.add_season_race(active_season['season_id'], track, laps, is_sprint=True)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏆 Season Calendar", description=msg, color=color))

    @season_admin_group.command(name="calendar", description="View and manage the WDC season calendar (Reorder, remove, or start next round).")
    @is_admin()
    @app_commands.guild_only()
    async def season_calendar_cmd(self, interaction: discord.Interaction):
        active_season = database.get_active_season(interaction.guild_id)
        if not active_season:
            await interaction.response.send_message("❌ There is no active WDC season. Create one first using `/season create`.", ephemeral=True)
            return
            
        calendar = database.get_season_calendar(active_season['season_id'])
        view = SeasonCalendarAdminView(active_season, calendar)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)



    @admin_group.command(name="give", description="Give credits to a player (Admin only).")
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

    async def _do_remove_money(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
            return

        target_prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
        if not target_prof:
            await interaction.response.send_message(f"❌ User {user.mention} does not have a profile.", ephemeral=True)
            return

        success = database.update_user_balance(target_prof['user_id'], -amount)
        if not success:
            await interaction.response.send_message(f"❌ Cannot deduct **{amount:,} credits**. User only has **{target_prof['money']:,} credits** in their wallet.", ephemeral=True)
            return

        embed = utils.create_embed(
            title="💰 Admin Deduction",
            description=f"Successfully deducted **{amount:,} credits** from {user.mention}.",
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @admin_group.command(name="remove", description="Deduct credits from a player (Admin only).")
    @app_commands.describe(user="The player to deduct credits from", amount="Amount of credits to deduct")
    @is_admin()
    @app_commands.guild_only()
    async def admin_remove(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await self._do_remove_money(interaction, user, amount)

    @admin_group.command(name="removemoney", description="Deduct credits from a player (Admin only).")
    @app_commands.describe(user="The player to deduct credits from", amount="Amount of credits to deduct")
    @is_admin()
    @app_commands.guild_only()
    async def admin_removemoney(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await self._do_remove_money(interaction, user, amount)

    @app_commands.command(name="removemoney", description="Deduct credits from a player (Admin only).")
    @app_commands.describe(user="The player to deduct credits from", amount="Amount of credits to deduct")
    @is_admin()
    @app_commands.guild_only()
    async def top_removemoney(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await self._do_remove_money(interaction, user, amount)

    @admin_group.command(name="resetdaily", description="Reset daily chat/voice credit trackers for a player (Admin only).")
    @app_commands.describe(user="The player to reset daily credit limits for")
    @is_admin()
    @app_commands.guild_only()
    async def admin_resetdaily(self, interaction: discord.Interaction, user: discord.User):
        target_prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
        if not target_prof:
            await interaction.response.send_message(f"❌ User {user.mention} does not have a profile.", ephemeral=True)
            return

        database.reset_user_daily_activity(target_prof['user_id'])
        await interaction.response.send_message(embed=utils.create_embed(
            title="🔄 Daily Activity Limit Reset",
            description=f"Successfully reset daily chat & voice credit trackers for {user.mention}.",
            color=utils.COLOR_SUCCESS
        ))


    @admin_group.command(name="broadcast", description="Broadcast an announcement message to a channel (Admin only).")
    @app_commands.describe(
        message="The announcement message content (supports \\n for line breaks)",
        channel="Target text channel (optional, defaults to current channel)",
        title="Custom title for announcement embed (optional)",
        ping="Optional ping: 'everyone' or 'here'"
    )
    @app_commands.choices(ping=[
        app_commands.Choice(name="None", value="none"),
        app_commands.Choice(name="@everyone", value="everyone"),
        app_commands.Choice(name="@here", value="here")
    ])
    @is_admin()
    @app_commands.guild_only()
    async def admin_broadcast(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: Optional[discord.TextChannel] = None,
        title: Optional[str] = "📢 Official Announcement",
        ping: Optional[str] = "none"
    ):
        target_channel = channel or interaction.channel
        if not target_channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return

        formatted_message = message.replace("\\n", "\n")
        embed = utils.create_embed(
            title=title or "📢 Official Announcement",
            description=formatted_message,
            color=utils.COLOR_INFO
        )

        content = None
        if ping == "everyone":
            content = "@everyone"
        elif ping == "here":
            content = "@here"

        try:
            await target_channel.send(content=content, embed=embed)
            await interaction.response.send_message(f"✅ Announcement successfully sent to {target_channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send announcement to {target_channel.mention}: {str(e)}", ephemeral=True)

    @admin_group.command(name="dbbackup", description="Trigger manual backup copy of SQLite DB (Admin only).")
    @is_admin()
    @app_commands.guild_only()
    async def admin_dbbackup(self, interaction: discord.Interaction):
        if not os.path.exists(config.DATABASE_PATH):
            await interaction.response.send_message("❌ Database file does not exist yet.", ephemeral=True)
            return
            
        db_filename = os.path.basename(config.DATABASE_PATH)
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{db_filename}"
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

    @admin_group.command(name="gp", description="Manage Grand Prix events (Admin control panel).")
    @app_commands.describe(laps="Specify the race distance length (number of laps, default 15)")
    @is_admin()
    @app_commands.guild_only()
    async def admin_gp_panel(self, interaction: discord.Interaction, laps: int = 15):
        if laps < 1 or laps > 200:
            await interaction.response.send_message("❌ Invalid lap count. Laps must be between 1 and 200.", ephemeral=True)
            return

        active_gp = database.get_active_gp_race(interaction.guild_id)
        if active_gp:
            entries = database.get_gp_entries_full(active_gp['race_id'])
            import json
            weather_raw = active_gp.get('weather', 'Sunny')
            forecast = "Sunny"
            try:
                weather_data = json.loads(weather_raw)
                forecast = weather_data.get('forecast', 'Sunny')
            except Exception:
                forecast = weather_raw

            desc = (
                f"🏁 **Active GP:** **{active_gp['name']}**\n"
                f"🗺️ **Track:** `{active_gp['track']}`\n"
                f"⏱️ **Distance:** `{active_gp['laps']} Laps`\n"
                f"📊 **Stage:** `{active_gp.get('status', 'Created')}`\n"
                f"🌦️ **Forecast:** `{forecast}`\n"
                f"👥 **Entrants:** `{len(entries)} driver(s) registered`"
            )
        else:
            desc = f"❌ **No active Grand Prix scheduled.**\nUse the **Select a Track** dropdown below to schedule a **{laps}-lap** event."

        embed = utils.create_embed(
            title="🏁 Grand Prix Admin Panel",
            description=desc,
            color=utils.COLOR_WARNING
        )

        from cogs.racing import GPAdminView
        view = GPAdminView(interaction.guild_id, laps=laps)
        await interaction.response.send_message(embed=embed, view=view)

    @admin_group.command(name="sprint", description="Schedule a Sprint Race Weekend (Admin control panel).")
    @app_commands.describe(laps="Specify the Sprint race distance length (number of laps, default 8)")
    @is_admin()
    @app_commands.guild_only()
    async def admin_sprint_panel(self, interaction: discord.Interaction, laps: int = 8):
        if laps < 1 or laps > 50:
            await interaction.response.send_message("❌ Invalid Sprint lap count. Laps must be between 1 and 50.", ephemeral=True)
            return

        active_gp = database.get_active_gp_race(interaction.guild_id)
        if active_gp:
            entries = database.get_gp_entries_full(active_gp['race_id'])
            desc = (
                f"⚡ **Active Event:** **{active_gp['name']}**\n"
                f"🗺️ **Track:** `{active_gp['track']}`\n"
                f"⏱️ **Sprint Distance:** `{active_gp['laps']} Laps`\n"
                f"📊 **Stage:** `{active_gp.get('status', 'Created')}`\n"
                f"👥 **Entrants:** `{len(entries)} driver(s) registered`"
            )
        else:
            desc = f"❌ **No active Sprint Race scheduled.**\nUse the **Select an Official F1 Track** dropdown below to schedule a **{laps}-lap** Sprint Weekend."

        embed = utils.create_embed(
            title="⚡ Sprint Race Weekend Admin Panel",
            description=desc,
            color=utils.COLOR_QUALIFYING
        )

        from cogs.racing import GPAdminView, GPTrackSelect
        view = GPAdminView(interaction.guild_id, laps=laps)
        if not active_gp:
            view.clear_items()
            view.add_item(GPTrackSelect(laps=laps, is_sprint=True))

        await interaction.response.send_message(embed=embed, view=view)


class SeasonCalendarAdminView(discord.ui.View):
    def __init__(self, active_season, calendar):
        super().__init__(timeout=180.0)
        self.active_season = active_season
        self.calendar = calendar
        self.selected_index = None
        self.page = 0
        self.update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if utils.is_admin_user(interaction):
            return True
        await interaction.response.send_message("❌ Only server administrators can manage the WDC Season Calendar.", ephemeral=True)
        return False

    def build_embed(self):
        desc = f"📅 **WDC Season:** **{self.active_season['name']}** (`{len(self.calendar)} Rounds`)\n\n"
        if not self.calendar:
            desc += "*No rounds scheduled in the season calendar yet. Use `/season add_race` or `/season add_sprint_race` to add races!*"
        else:
            lines = []
            for idx, item in enumerate(self.calendar):
                icon = "⚡" if item['is_sprint'] else "🏁"
                status = item['status']
                status_emoji = "🟢" if status == 'Running' else ("⚪" if status == 'Scheduled' else "🏁")
                
                prefix = f"👉 **Round {idx+1}:** " if self.selected_index == idx else f"**Round {idx+1}:** "
                lines.append(f"{prefix}{icon} **{item['track']}** ({item['laps']} Laps) — `{status}` {status_emoji}")
                
            full_text = "\n".join(lines)
            if len(full_text) > 3800:
                lines = lines[:35]
                lines.append(f"\n*...and {len(self.calendar) - 35} more rounds scheduled!*")
                full_text = "\n".join(lines)
            desc += full_text
                
        embed = utils.create_embed(
            title=f"📅 WDC Calendar Manager",
            description=desc,
            color=utils.COLOR_QUALIFYING
        )
        return embed

    def update_components(self):
        self.clear_items()
        
        if self.calendar:
            total_items = len(self.calendar)
            max_options = 25
            total_pages = max(1, math.ceil(total_items / max_options))
            
            if self.selected_index is not None:
                self.page = self.selected_index // max_options
            
            self.page = max(0, min(self.page, total_pages - 1))
            start_idx = self.page * max_options
            end_idx = min(start_idx + max_options, total_items)
            
            options = []
            for idx in range(start_idx, end_idx):
                item = self.calendar[idx]
                race_type = "Sprint" if item['is_sprint'] else "GP"
                options.append(discord.SelectOption(
                    label=f"Round {idx+1}: {item['track']} ({race_type})",
                    value=str(idx),
                    default=(self.selected_index == idx)
                ))
            
            placeholder = f"Select Round {start_idx+1}-{end_idx} of {total_items}..."
            if total_pages > 1:
                placeholder = f"Page {self.page+1}/{total_pages}: Select Round {start_idx+1}-{end_idx} of {total_items}..."
                
            select = discord.ui.Select(placeholder=placeholder, options=options, custom_id="season_cal_select")
            select.callback = self.select_callback
            self.add_item(select)
            
            if total_pages > 1:
                prev_page_btn = discord.ui.Button(label="◀️ Prev 25", style=discord.ButtonStyle.primary, disabled=(self.page == 0), custom_id="cal_prev_page")
                prev_page_btn.callback = self.prev_page_callback
                self.add_item(prev_page_btn)
                
                page_info_btn = discord.ui.Button(label=f"Page {self.page+1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True, custom_id="cal_page_info")
                self.add_item(page_info_btn)
                
                next_page_btn = discord.ui.Button(label="▶️ Next 25", style=discord.ButtonStyle.primary, disabled=(self.page >= total_pages - 1), custom_id="cal_next_page")
                next_page_btn.callback = self.next_page_callback
                self.add_item(next_page_btn)
            
            if self.selected_index is not None:
                up_btn = discord.ui.Button(label="Move Up", style=discord.ButtonStyle.secondary, emoji="⬆️", disabled=(self.selected_index == 0))
                up_btn.callback = self.move_up_callback
                self.add_item(up_btn)
                
                down_btn = discord.ui.Button(label="Move Down", style=discord.ButtonStyle.secondary, emoji="⬇️", disabled=(self.selected_index == len(self.calendar) - 1))
                down_btn.callback = self.move_down_callback
                self.add_item(down_btn)
                
                remove_btn = discord.ui.Button(label="Remove", style=discord.ButtonStyle.danger, emoji="❌")
                remove_btn.callback = self.remove_callback
                self.add_item(remove_btn)

        next_race = None
        for item in self.calendar:
            if item['status'] == 'Scheduled':
                next_race = item
                break
                
        start_btn = discord.ui.Button(label="Start Next Round", style=discord.ButtonStyle.success, emoji="🏁", disabled=(next_race is None))
        start_btn.callback = self.start_next_round_callback
        self.add_item(start_btn)

    async def prev_page_callback(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        total_pages = math.ceil(len(self.calendar) / 25)
        if self.page < total_pages - 1:
            self.page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)



    async def select_callback(self, interaction: discord.Interaction):
        self.selected_index = int(interaction.data['values'][0])
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def move_up_callback(self, interaction: discord.Interaction):
        if self.selected_index is None or self.selected_index <= 0:
            await interaction.response.defer()
            return
            
        idx = self.selected_index
        self.calendar[idx], self.calendar[idx-1] = self.calendar[idx-1], self.calendar[idx]
        self.selected_index = idx - 1
        
        cal_ids = [item['calendar_id'] for item in self.calendar]
        database.update_calendar_orders(cal_ids)
        
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def move_down_callback(self, interaction: discord.Interaction):
        if self.selected_index is None or self.selected_index >= len(self.calendar) - 1:
            await interaction.response.defer()
            return
            
        idx = self.selected_index
        self.calendar[idx], self.calendar[idx+1] = self.calendar[idx+1], self.calendar[idx]
        self.selected_index = idx + 1
        
        cal_ids = [item['calendar_id'] for item in self.calendar]
        database.update_calendar_orders(cal_ids)
        
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def remove_callback(self, interaction: discord.Interaction):
        if self.selected_index is None:
            await interaction.response.defer()
            return
            
        target = self.calendar[self.selected_index]
        success, msg = database.remove_season_race(target['calendar_id'])
        if success:
            self.calendar = database.get_season_calendar(self.active_season['season_id'])
            self.selected_index = None
            self.update_components()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def start_next_round_callback(self, interaction: discord.Interaction):
        next_race = None
        for item in self.calendar:
            if item['status'] == 'Scheduled':
                next_race = item
                break
                
        if not next_race:
            await interaction.response.send_message("❌ No scheduled rounds left in this season.", ephemeral=True)
            return
            
        track = next_race['track']
        laps = next_race['laps']
        is_sprint = bool(next_race['is_sprint'])
        event_type = "Sprint Race" if is_sprint else "Grand Prix"
        gp_name = f"{track} {event_type}"
        
        active_gp = database.get_active_gp_race(interaction.guild_id)
        if active_gp:
            await interaction.response.send_message("❌ There is already an active GP running on this server. Complete or cancel it first.", ephemeral=True)
            return
            
        success, msg = database.create_gp_race(
            interaction.guild_id, 
            gp_name, 
            track, 
            laps, 
            is_sprint=is_sprint, 
            season_id=self.active_season['season_id']
        )
        if success:
            database.mark_calendar_race_status(next_race['calendar_id'], 'Running')
            
            announcement = utils.create_embed(
                title=f"🏁 WDC Round Launched: {gp_name}!",
                description=(
                    f"A new WDC Season round has been launched at **{track}** ({laps} laps)!\n\n"
                    f"Type **`/joinrace`** to register and secure your spot on the starting grid!"
                ),
                color=utils.COLOR_SUCCESS
            )
            await interaction.channel.send(embed=announcement)
            
            self.calendar = database.get_season_calendar(self.active_season['season_id'])
            self.selected_index = None
            self.update_components()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)


class AdminStatsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, current_tf: str = "today"):
        super().__init__(timeout=180.0)
        self.bot = bot
        self.guild_id = guild_id
        self.current_tf = current_tf
        self.update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if utils.is_admin_user(interaction):
            return True
        await interaction.response.send_message("❌ Only server administrators can view server engagement telemetry.", ephemeral=True)
        return False

    def build_embed(self, guild: Any = None, guild_name: str = "") -> discord.Embed:
        g_name = "Server"
        g_icon = None
        if isinstance(guild, str):
            g_name = guild
        elif guild and hasattr(guild, 'name'):
            g_name = guild.name
            if hasattr(guild, 'icon') and guild.icon:
                g_icon = guild.icon.url
        elif guild_name:
            g_name = guild_name

        stats = database.get_server_engagement_stats(self.guild_id, self.current_tf)
        
        tf_titles = {
            "today": "Today (24 Hours)",
            "weekly": "Weekly (Last 7 Days)",
            "monthly": "Monthly (Last 30 Days)",
            "all": "All-Time Overview"
        }
        tf_label = tf_titles.get(self.current_tf, "Today (24 Hours)")

        embed = utils.create_embed(
            title=f"📊 Server Activity Telemetry — {g_name}",
            description=f"Showing bot-driven engagement & activity metrics for **{tf_label}**.\nUse the interactive buttons below to switch timeframes.",
            color=utils.COLOR_INFO
        )

        if g_icon:
            embed.set_thumbnail(url=g_icon)

        new_racers_str = f" (`+{stats['new_racers']:,}` new)" if stats['new_racers'] > 0 and self.current_tf != 'all' else ""
        embed.add_field(
            name="👥 Community & Driver Base",
            value=(
                f"• 🏎️ **Total Registered Drivers:** `{stats['total_racers']:,}`{new_racers_str}\n"
                f"• ⚡ **Active Players ({tf_label}):** `{stats['active_today']:,} members`\n"
                f"• 💰 **Server Economy Wealth:** `{stats['total_wealth']:,} credits`\n"
                f"• 🎖️ **Average Driver Level:** `Lvl {stats['avg_level']}`"
            ),
            inline=False
        )

        vc_hours = round(stats['est_voice_minutes_today'] / 60, 1)

        embed.add_field(
            name=f"💬 Text Chat & Voice Activity Driven by Bot ({tf_label})",
            value=(
                f"• 💬 **Text Messages Sent:** `~{stats['est_chat_messages_today']:,} messages` (`{stats['chat_credits_today']:,} credits rewarded`)\n"
                f"• 🎙️ **Voice Channel Time:** `~{stats['est_voice_minutes_today']:,} mins` (`~{vc_hours} hrs active in VC`) (`{stats['voice_credits_today']:,} credits rewarded`)\n"
                f"• 👥 **Active Engaged Members:** `{stats['active_chatters']:,} text chatters` | `{stats['active_voice_members']:,} voice members`"
            ),
            inline=False
        )

        embed.add_field(
            name=f"🏁 Grand Prix & Race Weekends ({tf_label})",
            value=(
                f"• 🏁 **Grand Prix Events:** `{stats['total_gps']:,} hosted` (`{stats['completed_gps']:,}` finished)\n"
                f"• 🏎️ **Driver Grid Entries:** `{stats['total_entries']:,} entries`\n"
                f"• 🏆 **Prize Money Awarded:** `{stats['total_gp_payouts']:,} credits`"
            ),
            inline=False
        )

        embed.add_field(
            name=f"⚔️ Head-to-Head Duels & Championships ({tf_label})",
            value=(
                f"• ⚔️ **1v1 Duels Fought:** `{stats['total_duels']:,} duels`\n"
                f"• 🏆 **WDC Seasons:** `{stats['total_seasons']:,} seasons` (`{stats['completed_seasons']:,}` completed)\n"
                f"• 📅 **Calendar Rounds:** `{stats['completed_season_rounds']:,} rounds finished`"
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ Garage Upgrades & Progression",
            value=(
                f"• 📦 **Car Parts Collected:** `{stats['total_inventory_items']:,} items`\n"
                f"• ⚙️ **Installed Components:** `{stats['equipped_items']:,} active upgrades`"
            ),
            inline=False
        )

        avatar_url = self.bot.user.display_avatar.url if (self.bot and self.bot.user and hasattr(self.bot.user, 'display_avatar')) else None
        embed.set_footer(text=f"Server ID: {self.guild_id} • Click buttons below to change timeframe", icon_url=avatar_url)
        return embed

    def update_components(self):
        self.clear_items()
        
        btn_today = discord.ui.Button(label="Today (24h)", style=discord.ButtonStyle.primary if self.current_tf == "today" else discord.ButtonStyle.secondary, emoji="📅")
        btn_today.callback = self.make_tf_callback("today")
        self.add_item(btn_today)

        btn_weekly = discord.ui.Button(label="Weekly (7D)", style=discord.ButtonStyle.primary if self.current_tf == "weekly" else discord.ButtonStyle.secondary, emoji="🗓️")
        btn_weekly.callback = self.make_tf_callback("weekly")
        self.add_item(btn_weekly)

        btn_monthly = discord.ui.Button(label="Monthly (30D)", style=discord.ButtonStyle.primary if self.current_tf == "monthly" else discord.ButtonStyle.secondary, emoji="📆")
        btn_monthly.callback = self.make_tf_callback("monthly")
        self.add_item(btn_monthly)

        btn_all = discord.ui.Button(label="All-Time", style=discord.ButtonStyle.primary if self.current_tf == "all" else discord.ButtonStyle.secondary, emoji="🏆")
        btn_all.callback = self.make_tf_callback("all")
        self.add_item(btn_all)

    def make_tf_callback(self, tf: str):
        async def callback(interaction: discord.Interaction):
            self.current_tf = tf
            self.update_components()
            embed = self.build_embed(guild=interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback


async def setup(bot: commands.Bot):
    cog = AdminCog(bot)

    # Debug: show what CogMeta detected
    detected = [c.name for c in cog.__cog_app_commands__]
    print(f"[ADMIN COG] CogMeta detected app commands: {detected}")
    print(f"[ADMIN COG] admin_group subcommands: {[c.name for c in cog.admin_group.commands]}")
    print(f"[ADMIN COG] season_admin_group subcommands: {[c.name for c in cog.season_admin_group.commands]}")

    await bot.add_cog(cog, override=True)
    print("[ADMIN COG] [OK] AdminCog added via add_cog")

    # Fallback: if CogMeta didn't register the groups, add them manually
    tree_names = [c.name for c in bot.tree.get_commands()]
    if 'admin' not in tree_names:
        bot.tree.add_command(cog.admin_group)
        print("[ADMIN COG] [WARN] Manually added admin_group (CogMeta missed it)")
    if 'season' not in tree_names:
        bot.tree.add_command(cog.season_admin_group)
        print("[ADMIN COG] [WARN] Manually added season_admin_group (CogMeta missed it)")

    final = [c.name for c in bot.tree.get_commands()]
    print(f"[ADMIN COG] Final tree commands: {final}")
