import discord
from discord.ext import commands
from discord import app_commands
import os
import shutil
from datetime import datetime
import asyncio

import config
import database
import economy
import race
import utils

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

admin_group = app_commands.Group(name="admin", description="Game administrator controls for economy and stats.")
bot.tree.add_command(admin_group)

# In-memory dict to track when voice members joined: {member_id: join_time}
voice_tracking = {}

# In-memory dict to track when members last earned chat credits: {member_id: last_award_time}
chat_cooldowns = {}

# Keep track of debug mode status
debug_mode = False

# Active live GP race registries for real-time strategy updates
ACTIVE_RACES = {}

# ----------------- DB Initialization -----------------
@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    
    # Sync commands
    try:
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to test guild {config.GUILD_ID}.")
        else:
            # Clear old guild-specific commands to prevent duplicates, then sync globally
            for g in bot.guilds:
                try:
                    bot.tree.clear_commands(guild=g)
                    await bot.tree.sync(guild=g)
                except Exception as guild_err:
                    if debug_mode:
                        print(f"Failed to clear commands for guild {g.id}: {guild_err}")
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} commands globally.")
    if not periodic_voice_credits_check.is_running():
        periodic_voice_credits_check.start()
        print("Started periodic voice credits check background task.")

# ----------------- Economy Activity Trackers -----------------

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not message.guild:
        return
        
    # Check if user has a profile
    user = database.get_user_by_discord_id(message.author.id, message.guild.id)
    if user:
        now = datetime.now()
        last_award = chat_cooldowns.get(message.author.id)
        
        # Only award credits if they haven't earned yet, or it's been >= 60 seconds
        if not last_award or (now - last_award).total_seconds() >= 60.0:
            credits_earned = database.award_daily_activity_credits(
                user['user_id'], 
                config.CHAT_CREDITS_PER_MSG, 
                'chat'
            )
            if credits_earned > 0:
                chat_cooldowns[message.author.id] = now
                if debug_mode:
                    print(f"Awarded {credits_earned}¢ to {message.author.name} for chat activity.")
            
    await bot.process_commands(message)

def is_active_voice(state: discord.VoiceState) -> bool:
    """Check if member is actively in a valid voice channel with mic unmuted and undeafened."""
    if not state or not state.channel:
        return False
    if getattr(state.channel, 'afk', False):
        return False
    if state.self_mute or state.mute:
        return False
    if state.self_deaf or state.deaf:
        return False
    return True

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
        
    was_active = is_active_voice(before)
    is_active = is_active_voice(after)
    
    # 1. State changed from active to inactive (muted, deafened, left channel, or moved to AFK)
    if was_active and not is_active:
        start_time = voice_tracking.pop(member.id, None)
        if start_time:
            duration = datetime.now() - start_time
            minutes = duration.total_seconds() / 60.0
            if minutes >= 1.0:
                user = database.get_user_by_discord_id(member.id, member.guild.id)
                if user:
                    earned = database.award_daily_activity_credits(
                        user['user_id'], 
                        int(minutes) * config.VOICE_CREDITS_PER_MIN, 
                        'voice'
                    )
                    if debug_mode and earned > 0:
                        print(f"Awarded {earned}¢ to {member.name} for {int(minutes)} mins active in voice.")

    # 2. State changed from inactive to active (unmuted & undeafened in valid voice channel)
    elif not was_active and is_active:
        voice_tracking[member.id] = datetime.now()
        if debug_mode:
            print(f"{member.name} is now active in voice channel {after.channel.name}.")

@tasks.loop(minutes=2.0)
async def periodic_voice_credits_check():
    """Periodically award voice activity credits to members active in VC without requiring them to leave."""
    now = datetime.now()
    active_ids = list(voice_tracking.keys())
    for member_id in active_ids:
        start_time = voice_tracking.get(member_id)
        if not start_time:
            continue
        duration = now - start_time
        minutes = duration.total_seconds() / 60.0
        if minutes >= 2.0:
            for guild in bot.guilds:
                member = guild.get_member(member_id)
                if member and member.voice and is_active_voice(member.voice):
                    user = database.get_user_by_discord_id(member.id, guild.id)
                    if user:
                        earned = database.award_daily_activity_credits(
                            user['user_id'],
                            int(minutes) * config.VOICE_CREDITS_PER_MIN,
                            'voice'
                        )
                        voice_tracking[member_id] = now
                        if debug_mode and earned > 0:
                            print(f"Periodic VC credit: awarded {earned}¢ to {member.name}.")
                    break

# ----------------- Check Helpers -----------------

def is_admin():
    """Check if the user is an admin or has the configured Admin role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        role = discord.utils.get(interaction.user.roles, name=config.ADMIN_ROLE_NAME)
        if role is not None:
            return True
        await interaction.response.send_message(
            "❌ You do not have permission to use this command. Requires Administrator or Admin role.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

# ----------------- Admin Commands -----------------

@admin_group.command(name="setstat", description="Set a driver skill level or garage part level for a user.")
@app_commands.describe(
    user="Select the user/driver to edit",
    stat_name="Select the stat or garage part to edit",
    value="Target value (1-100 for driver skills, 1-20 for garage parts)"
)
@app_commands.choices(stat_name=[
    app_commands.Choice(name="🏎️ Driver: Race Pace (1-100)", value="pace"),
    app_commands.Choice(name="🏎️ Driver: Qualifying Skill (1-100)", value="qual"),
    app_commands.Choice(name="🏎️ Driver: Wet Weather Skill (1-100)", value="wet_skill"),
    app_commands.Choice(name="🏎️ Driver: Consistency (1-100)", value="consistency"),
    app_commands.Choice(name="🏎️ Driver: Aggression (1-100)", value="aggression"),
    app_commands.Choice(name="🏎️ Driver: Overtaking (1-100)", value="overtaking"),
    app_commands.Choice(name="🛠️ Garage: Engine Level (1-20)", value="engine"),
    app_commands.Choice(name="🛠️ Garage: Aerodynamics Level (1-20)", value="aerodynamics"),
    app_commands.Choice(name="🛠️ Garage: Tyres Level (1-20)", value="tyres"),
    app_commands.Choice(name="🛠️ Garage: ERS Level (1-20)", value="ers"),
    app_commands.Choice(name="🛠️ Garage: Reliability Level (1-20)", value="reliability"),
    app_commands.Choice(name="🛠️ Garage: Pit Crew Level (1-20)", value="pit_crew"),
])
@is_admin()
@app_commands.guild_only()
async def admin_set_stat(interaction: discord.Interaction, user: discord.Member, stat_name: app_commands.Choice[str], value: int):
    prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message(f"❌ User {user.display_name} does not have a profile.", ephemeral=True)
        return
        
    stat_key = stat_name.value
    driver_stats = ["pace", "qual", "wet_skill", "consistency", "aggression", "overtaking"]
    garage_parts = ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]
    
    if stat_key in driver_stats:
        if value < 1 or value > 100:
            await interaction.response.send_message("❌ Driver skill value must be between 1 and 100.", ephemeral=True)
            return
        table_name = "drivers"
    elif stat_key in garage_parts:
        if value < 1 or value > 20:
            await interaction.response.send_message("❌ Garage part level must be between 1 and 20.", ephemeral=True)
            return
        table_name = "garage"
    else:
        await interaction.response.send_message("❌ Invalid stat selected.", ephemeral=True)
        return
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE {table_name} SET {stat_key} = ? WHERE user_id = ?", (value, prof['user_id']))
        conn.commit()
        await interaction.response.send_message(embed=utils.create_embed(
            title="⚙️ Admin Stat Override",
            description=f"✅ Successfully set **{stat_name.name}** to **{value}** for **{prof['team_name']}** (Driver: {user.mention})!",
            color=utils.COLOR_SUCCESS
        ))
    except Exception as e:
        conn.rollback()
        await interaction.response.send_message(f"❌ Database error: {e}", ephemeral=True)
    finally:
        conn.close()

@admin_group.command(name="resetprofile", description="Completely reset a user's racing profile (reinitializes back to rookie levels).")
@app_commands.describe(user="Select the user to reset")
@is_admin()
@app_commands.guild_only()
async def admin_reset_profile(interaction: discord.Interaction, user: discord.Member):
    prof = database.get_user_by_discord_id(user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message(f"❌ User {user.display_name} does not have a profile.", ephemeral=True)
        return
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete entry records
        cursor.execute("DELETE FROM users WHERE user_id = ?", (prof['user_id'],))
        conn.commit()
        conn.close()
        
        # Recreate profile using standard create_user method
        success, msg = database.create_user(user.id, interaction.guild_id, f"Rookie Team {random.randint(100, 999)}")
        if success:
            await interaction.response.send_message(embed=utils.create_embed(
                title="🔄 Admin Profile Reset",
                description=f"✅ Successfully reset and reinitialized racing profile for {user.mention}!",
                color=utils.COLOR_SUCCESS
            ))
        else:
            await interaction.response.send_message(f"❌ Reset failed on reinitialization: {msg}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error resetting profile: {e}", ephemeral=True)

# Season Admin Controls Subgroup
season_admin_group = app_commands.Group(name="season", description="Admin controls for World Driver Championship (WDC) Seasons")
admin_group.add_command(season_admin_group)

@season_admin_group.command(name="create", description="Create a new World Driver Championship Season (e.g. Season 1, Season 2).")
@app_commands.describe(name="Season Name (e.g. Season 1, 2026 Championship)")
@is_admin()
@app_commands.guild_only()
async def admin_season_create(interaction: discord.Interaction, name: str):
    success, msg = database.create_season(interaction.guild_id, name)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
    await interaction.response.send_message(embed=utils.create_embed(title="🏆 Season Championship Setup", description=msg, color=color))

@season_admin_group.command(name="end", description="Conclude active season and declare the World Driver Champion!")
@is_admin()
@app_commands.guild_only()
async def admin_season_end(interaction: discord.Interaction):
    success, msg, season, standings = database.end_active_season(interaction.guild_id)
    if not success:
        await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        return
        
    standings_text = ""
    for idx, row in enumerate(standings[:10]):
        pos_emoji = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"**P{idx+1}**"))
        standings_text += f"{pos_emoji} **{row['team_name']}** — **{row['total_points']} pts** ({row['races_entered']} races)\n"
        
    champion_name = standings[0]['team_name'] if standings else "No Driver"
    desc = (
        f"🏆 **WORLD DRIVER CHAMPION:** **{champion_name}**!\n\n"
        f"📊 **Final Driver Championship Standings:**\n{standings_text}\n"
        f"🎉 *Congratulations to the World Champion! Admin can award giveaways directly.*"
    )
    embed = utils.create_embed(
        title=f"👑 {season['name']} — Checkered Flag & World Champion",
        description=desc,
        color=utils.COLOR_WARNING
    )
    await interaction.response.send_message(embed=embed)

@season_admin_group.command(name="cancel", description="Cancel the active Season.")
@is_admin()
@app_commands.guild_only()
async def admin_season_cancel(interaction: discord.Interaction):
    success, msg = database.cancel_active_season(interaction.guild_id)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
    await interaction.response.send_message(embed=utils.create_embed(title="🚫 Season Cancelled", description=msg, color=color))

# ----------------- Slash Commands -----------------


@bot.tree.command(name="start", description="Initialize your Discord Grand Prix racing team!")
@app_commands.describe(team_name="Your racing team name", country="Your home country flag or name (optional)")
@app_commands.guild_only()
async def start(interaction: discord.Interaction, team_name: str, country: str = None):
    # Enforce team name length limit
    if len(team_name) > 32:
        await interaction.response.send_message("❌ Team name cannot exceed 32 characters.", ephemeral=True)
        return
        
    success, msg = database.create_user(interaction.user.id, interaction.guild_id, team_name, country)
    if success:
        # Check if there is an active GP scheduled in the server
        active_gp = database.get_active_gp_race(interaction.guild_id)
        gp_suggestion = ""
        if active_gp:
            gp_suggestion = (
                f"\n\n🏁 **Active Event:** The **{active_gp['name']}** is scheduled at **{active_gp['track']}**!\n"
                f"Type **`/joinrace`** to register your team and participate in the championship."
            )
            
        embed = utils.create_embed(
            title=f"🏎️ Welcome to Discord Grand Prix!",
            description=(
                f"Congratulations **{interaction.user.name}**! Your racing team **{team_name}** has been registered.\n\n"
                f"💰 **Starting Balance:** {config.STARTING_MONEY}¢\n"
                f"🛠️ **Garage:** Level 1 components installed\n\n"
                f"Earn credits by text chatting and hanging out in voice. "
                f"Upgrade your car parts using `/upgrade` and duel other players via `/race`!{gp_suggestion}"
            ),
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(
            f"❌ {msg}",
            ephemeral=True
        )

async def _send_profile_embed(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    prof = database.get_full_team_profile(target.id, interaction.guild_id)
    
    if not prof:
        if member:
            await interaction.response.send_message("❌ That user does not have a team profile yet in this server.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You haven't registered a profile yet in this server! Run `/start` to begin.", ephemeral=True)
        return
        
    overall_power = utils.calculate_overall_power(prof, prof["pace"])
    
    title = f"🏎️ {prof['team_name']}"
    if prof['country']:
        title = f"{prof['country']} " + title
    title += f" (Level {prof['level']})"
    
    import json
    strat_json = {}
    strategy_str = prof.get('pit_strategy_json')
    if strategy_str:
        try:
            strat_json = json.loads(strategy_str)
        except Exception:
            pass
            
    pace = strat_json.get("pace", prof.get("pref_strategy", "Balanced"))
    start_tyre = strat_json.get("start_tyre", prof.get("pref_tyres", "Medium"))
    stops = strat_json.get("stops", [])
    
    if stops:
        stops_str = ", ".join([f"L{s['lap']}({s['tyre']})" for s in stops])
    else:
        stops_str = f"{prof.get('pref_pit_stops', 1)} (Auto)"
        
    desc = (
        f"💰 **Money:** {prof['money']:,} credits\n"
        f"⭐ **XP:** {prof['xp']:,} / {prof['level'] * 1000:,} XP\n"
        f"🏆 **Wins:** {prof['wins']} | 🚫 **Losses:** {prof['losses']}\n"
        f"⚡ **Power:** {overall_power}\n"
        f"📋 **Strategy:** `{pace}` | 🛞 **Start Tyres:** `{start_tyre}` | 🔧 **Stops:** `{stops_str}`"
    )
    
    fields = [
        {"name": "Engine", "value": f"Level {prof['engine']}", "inline": True},
        {"name": "Aerodynamics", "value": f"Level {prof['aerodynamics']}", "inline": True},
        {"name": "Tyres", "value": f"Level {prof['tyres']}", "inline": True},
        {"name": "ERS", "value": f"Level {prof['ers']}", "inline": True},
        {"name": "Reliability", "value": f"Level {prof['reliability']}", "inline": True},
        {"name": "Pit Crew", "value": f"Level {prof['pit_crew']}", "inline": True}
    ]
    
    embed = utils.create_embed(
        title=title,
        description=desc,
        color=utils.COLOR_F1_RED,
        fields=fields,
        footer_text=f"Last updated: {datetime.now().strftime('%Y-%m-%d')}"
    )
    
    try:
        card_buf = utils.generate_profile_card(prof)
        card_file = discord.File(card_buf, filename="profile_card.png")
        embed.set_image(url="attachment://profile_card.png")
        await interaction.response.send_message(embed=embed, file=card_file)
    except Exception as e:
        if debug_mode:
            print(f"Failed to render profile card image: {e}")
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="profile", description="View your team profile and overall standings.")
@app_commands.describe(member="Select another team owner to view their profile (optional)")
@app_commands.guild_only()
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    await _send_profile_embed(interaction, member)

@bot.tree.command(name="team", description="Show detailed summary of a team.")
@app_commands.describe(member="Select another team owner (optional)")
@app_commands.guild_only()
async def team_info(interaction: discord.Interaction, member: discord.Member = None):
    await _send_profile_embed(interaction, member)

@bot.tree.command(name="garage", description="View your current car component levels and damage.")
@app_commands.guild_only()
async def garage(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    overall_power = utils.calculate_overall_power(prof, prof["pace"])
    
    engine_bar = utils.make_progress_bar(prof['damage_engine'])
    tyres_bar = utils.make_progress_bar(prof['damage_tyres'])
    total_bar = utils.make_progress_bar(prof['damage_total'])
    
    fields = [
        {"name": "⚙️ Engine", "value": f"Level {prof['engine']}/{config.MAX_STAT_LEVEL}\nWear: {engine_bar}", "inline": True},
        {"name": "✈️ Aerodynamics", "value": f"Level {prof['aerodynamics']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "⭕ Tyres", "value": f"Level {prof['tyres']}/{config.MAX_STAT_LEVEL}\nWear: {tyres_bar}", "inline": True},
        {"name": "🔋 ERS", "value": f"Level {prof['ers']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "🛡️ Reliability", "value": f"Level {prof['reliability']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "🔧 Pit Crew", "value": f"Level {prof['pit_crew']}/{config.MAX_STAT_LEVEL}", "inline": True}
    ]
    
    embed = utils.create_embed(
        title=f"🛠️ {prof['team_name']}'s Garage",
        description=(
            f"**Overall Car Power Rating:** {overall_power}\n"
            f"**Total Car Damage:** {total_bar}"
        ),
        color=utils.COLOR_INFO,
        fields=fields
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View detailed Driver statistics.")
@app_commands.guild_only()
async def stats(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    fields = [
        {"name": "🏎️ Driver Stats", "value": (
            f"• **Race Pace:** {prof['pace']}/100\n"
            f"• **Qualifying Skill:** {prof['qual']}/100\n"
            f"• **Wet Skill:** {prof['wet_skill']}/100\n"
            f"• **Consistency:** {prof['consistency']}/100\n"
            f"• **Aggression:** {prof['aggression']}/100\n"
            f"• **Overtaking:** {prof['overtaking']}/100"
        ), "inline": False}
    ]
    
    embed = utils.create_embed(
        title=f"📊 Driver Performance Sheet - {prof['team_name']}",
        description="Your driver gains direct skill boosts based on GP race results (P1 gets +8 to all skills, P2 gets +7, down to P8 getting +1). You can also spend credits to train them with `/train`.",
        color=utils.COLOR_INFO,
        fields=fields
    )
    await interaction.response.send_message(embed=embed)

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

@bot.tree.command(name="strategy", description="Configure your starting race pacing strategy and tyres.")
@app_commands.guild_only()
async def strategy_setup(interaction: discord.Interaction):
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

@bot.tree.command(name="pit", description="Schedule a pit stop for the very next lap of the active Grand Prix.")
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
async def gp_pit_command(interaction: discord.Interaction, tyre: app_commands.Choice[str]):
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

@bot.tree.command(name="train", description="Spend 400 credits to train a selected Driver skill.")
@app_commands.describe(
    skill="Select the specific Driver skill to train"
)
@app_commands.choices(skill=[
    app_commands.Choice(name="Driver: Race Pace", value="pace"),
    app_commands.Choice(name="Driver: Qualifying Skill", value="qual"),
    app_commands.Choice(name="Driver: Wet Weather Skill", value="wet_skill"),
    app_commands.Choice(name="Driver: Consistency", value="consistency"),
    app_commands.Choice(name="Driver: Aggression", value="aggression"),
    app_commands.Choice(name="Driver: Overtaking", value="overtaking")
])
@app_commands.guild_only()
async def train(interaction: discord.Interaction, skill: app_commands.Choice[str]):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    skill_val = skill.value
    
    success, msg = database.train_personnel_skill(prof['user_id'], "driver", skill_val, cost=400)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
    await interaction.response.send_message(embed=utils.create_embed(title="🏋️ Personnel Training Center", description=msg, color=color))

@bot.tree.command(name="daily", description="Claim your daily credit login bonus (500 credits).")
@app_commands.guild_only()
async def daily(interaction: discord.Interaction):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    success, msg = economy.claim_daily(prof['user_id'])
    color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
    await interaction.response.send_message(embed=utils.create_embed(title="📅 Daily Bonus", description=msg, color=color))

@bot.tree.command(name="work", description="Perform a daily odd-job for your racing team to earn credits.")
@app_commands.guild_only()
async def work(interaction: discord.Interaction):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    success, msg = economy.perform_work(prof['user_id'])
    color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
    await interaction.response.send_message(embed=utils.create_embed(title="🔧 Daily Work", description=msg, color=color))

# ----------------- Duel Command & Betting -----------------

# ----------------- Duel Command & Betting -----------------

async def run_duel_simulation(channel, p1_member: discord.Member, p2_member: discord.Member, p1_prof: dict, p2_prof: dict, laps: int, wager_amount: int = 0):
    # Simulate the duel
    winner, loser, lap_logs, qual_logs = race.simulate_duel(p1_prof, p2_prof, laps)
    
    # 1. Post Qualifying Grid
    embed = utils.create_embed(
        title=f"🏁 Race Duel Setup: {p1_prof['team_name']} vs {p2_prof['team_name']}",
        description="\n".join(qual_logs),
        color=utils.COLOR_QUALIFYING
    )
    await channel.send(embed=embed)
    await asyncio.sleep(4.0)
    
    # 2. Stream Laps - Announce as leader completes each lap
    for idx, lap_events in enumerate(lap_logs):
        lap_num = idx + 1
        is_last = (lap_num == len(lap_logs))
        
        embed = utils.create_embed(
            title=f"🏎️ Duel Lap {lap_num}/{laps}: {p1_prof['team_name']} vs {p2_prof['team_name']}",
            description="\n".join(lap_events),
            color=utils.COLOR_SUCCESS if is_last else utils.COLOR_QUALIFYING
        )
        await channel.send(embed=embed)
        await asyncio.sleep(12.0)
        
    # 3. Apply database updates & rewards
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        w_uid = winner['user_id']
        l_uid = loser['user_id']
        
        if wager_amount > 0:
            # Deduct wager from both
            cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (wager_amount, w_uid))
            cursor.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (wager_amount, l_uid))
            # Award payout to winner
            payout = wager_amount * 2
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (payout, w_uid))
            
            # Insert bet record
            cursor.execute("INSERT INTO bets (race_id, bettor_id, target_id, amount, outcome, payout) VALUES (NULL, ?, ?, ?, ?, ?)",
                           (p1_prof['user_id'], p2_prof['user_id'], wager_amount, "win" if w_uid == p1_prof['user_id'] else "lose", payout))
        else:
            # Standard duel rewards
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (config.DUEL_WIN_CREDITS, w_uid))
            cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (config.DUEL_LOSS_CREDITS, l_uid))
            payout = config.DUEL_WIN_CREDITS
            
        # Update wins/losses
        cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (w_uid,))
        cursor.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (l_uid,))
        
        # Calculate car damage based on whether they crashed (DNF)
        if winner.get("dnf", False):
            w_dmg_eng = random.randint(15, 30)
            w_dmg_tyr = random.randint(30, 60)
        else:
            w_dmg_eng = random.randint(1, 4)
            w_dmg_tyr = random.randint(2, 8)
            
        if loser.get("dnf", False):
            l_dmg_eng = random.randint(15, 30)
            l_dmg_tyr = random.randint(30, 60)
        else:
            l_dmg_eng = random.randint(2, 6)
            l_dmg_tyr = random.randint(4, 12)
            
        cursor.execute("""
            UPDATE garage 
            SET damage_engine = MIN(100, damage_engine + ?),
                damage_tyres = MIN(100, damage_tyres + ?)
            WHERE user_id = ?
        """, (w_dmg_eng, w_dmg_tyr, w_uid))
        
        cursor.execute("""
            UPDATE garage 
            SET damage_engine = MIN(100, damage_engine + ?),
                damage_tyres = MIN(100, damage_tyres + ?)
            WHERE user_id = ?
        """, (l_dmg_eng, l_dmg_tyr, l_uid))
        
        # Recalculate totals
        for uid in [w_uid, l_uid]:
            cursor.execute("SELECT damage_engine, damage_tyres FROM garage WHERE user_id = ?", (uid,))
            d = cursor.fetchone()
            cursor.execute("UPDATE garage SET damage_total = ? WHERE user_id = ?", (d['damage_engine'] + d['damage_tyres'], uid))
            
        conn.commit()

        # Award XP and handle level up via add_user_xp
        w_xp, w_lvl, w_up = database.add_user_xp(w_uid, 150)
        l_xp, l_lvl, l_up = database.add_user_xp(l_uid, 50)
        
        w_lvl_msg = f" ⭐ **LEVEL UP!** Reached Level {w_lvl} (+{w_lvl * 500}¢ reward!)" if w_up else ""
        l_lvl_msg = f" ⭐ **LEVEL UP!** Reached Level {l_lvl} (+{l_lvl * 500}¢ reward!)" if l_up else ""
        
        # Team radio victory quote & Podium Section
        radio_broadcast = utils.get_victory_team_radio(winner['team_name'])
        
        # Post summary ONLY if commit succeeds
        if wager_amount > 0:
            desc = (
                f"{radio_broadcast}\n\n"
                f"🥇 **P1 (Winner):** **{winner['team_name']}** (+150 XP{w_lvl_msg}) — **+{wager_amount * 2}¢**\n"
                f"🥈 **P2 (Runner-up):** **{loser['team_name']}** (+50 XP{l_lvl_msg}) — **-{wager_amount}¢**"
            )
        else:
            desc = (
                f"{radio_broadcast}\n\n"
                f"🥇 **P1 (Winner):** **{winner['team_name']}** (+{config.DUEL_WIN_CREDITS}¢, +150 XP{w_lvl_msg})\n"
                f"🥈 **P2 (Runner-up):** **{loser['team_name']}** (+{config.DUEL_LOSS_CREDITS}¢, +50 XP{l_lvl_msg})"
            )
            
        final_embed = utils.create_embed(
            title="🏁 Race Duel: Checkered Flag & Victory Podium",
            description=desc,
            color=utils.COLOR_SUCCESS
        )

        # Build lap telemetry plot
        lap_history = []
        for i in range(1, laps + 1):
            lap_history.append({"lap": i, "drivers": {winner['team_name']: 1, loser['team_name']: 2}})

        try:
            graph_buf = utils.generate_race_telemetry_graph(lap_history)
            graph_file = discord.File(graph_buf, filename="telemetry_graph.png")
            final_embed.set_image(url="attachment://telemetry_graph.png")
            await channel.send(embed=final_embed, file=graph_file)
        except Exception as e:
            if debug_mode:
                print(f"Failed to generate duel telemetry graph: {e}")
            await channel.send(embed=final_embed)
        
    except Exception as e:
        conn.rollback()
        print(f"Error saving duel results: {e}")
        await channel.send("❌ **Error:** An operational database error occurred while saving the duel results.")
    finally:
        conn.close()


class RaceAcceptView(discord.ui.View):
    """View handling Duel Race requests."""
    def __init__(self, bettor: discord.Member, target: discord.Member, laps: int, bettor_prof: dict, target_prof: dict, wager: int = 0):
        super().__init__(timeout=60.0)
        self.bettor = bettor
        self.target = target
        self.laps = laps
        self.bettor_prof = bettor_prof
        self.target_prof = target_prof
        self.wager = wager
        
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
            
    @discord.ui.button(label="Accept Duel", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
            return
            
        # Re-fetch profiles to ensure they are current
        p1 = database.get_full_team_profile(self.bettor.id, interaction.guild_id)
        p2 = database.get_full_team_profile(self.target.id, interaction.guild_id)
        if not p1 or not p2:
            await interaction.response.send_message("❌ Profile not found.", ephemeral=True)
            self.stop()
            return
            
        # Balance check if there is a wager
        if self.wager > 0:
            if p1['money'] < self.wager or p2['money'] < self.wager:
                await interaction.response.send_message(f"❌ One of you no longer has enough credits to cover the challenge fee of {self.wager}¢!", ephemeral=True)
                self.stop()
                return
            
        if p1['damage_total'] >= 80 or p2['damage_total'] >= 80:
            await interaction.response.send_message("❌ One of the cars is too damaged to race (must be < 80% damage)!", ephemeral=True)
            self.stop()
            return
            
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🟢 The duel was accepted! The race is starting...", view=self)
        self.stop()
        
        # Run simulation in channel
        await run_duel_simulation(interaction.channel, self.bettor, self.target, p1, p2, self.laps, wager_amount=self.wager)

    @discord.ui.button(label="Decline Duel", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
            return
            
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ The duel challenge was declined.", view=self)
        self.stop()


class BetAcceptView(discord.ui.View):
    """View handling Bet requests."""
    def __init__(self, bettor: discord.Member, target: discord.Member, amount: int, laps: int, bettor_prof: dict, target_prof: dict):
        super().__init__(timeout=60.0)
        self.bettor = bettor
        self.target = target
        self.amount = amount
        self.laps = laps
        self.bettor_prof = bettor_prof
        self.target_prof = target_prof
        
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Accept Bet", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
            return
            
        # Re-fetch balances to ensure they have enough money
        p1 = database.get_user_by_id(self.bettor_prof['user_id'])
        p2 = database.get_user_by_id(self.target_prof['user_id'])
        
        if not p1 or not p2 or p1['money'] < self.amount or p2['money'] < self.amount:
            await interaction.response.send_message("❌ One of you no longer has enough credits to cover the bet!", ephemeral=True)
            self.stop()
            return
            
        # Re-fetch profiles
        prof1 = database.get_full_team_profile(self.bettor.id, interaction.guild_id)
        prof2 = database.get_full_team_profile(self.target.id, interaction.guild_id)
        
        if not prof1 or not prof2:
            await interaction.response.send_message("❌ Profile not found.", ephemeral=True)
            self.stop()
            return
            
        if prof1['damage_total'] >= 80 or prof2['damage_total'] >= 80:
            await interaction.response.send_message("❌ One of the cars is too damaged to race (must be < 80% damage)!", ephemeral=True)
            self.stop()
            return
            
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🟢 The bet was accepted! The race is starting...", view=self)
        self.stop()
        
        # Run simulation in channel
        await run_duel_simulation(interaction.channel, self.bettor, self.target, prof1, prof2, self.laps, wager_amount=self.amount)

    @discord.ui.button(label="Decline Bet", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
            return
            
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ The bet challenge was declined.", view=self)
        self.stop()


@bot.tree.command(name="race", description="Challenge another user to a racing duel!")
@app_commands.describe(opponent="The player you want to challenge", wager="Optional credit wager (both players contribute this amount)", laps="Number of laps (1-20)")
@app_commands.guild_only()
async def race_duel(interaction: discord.Interaction, opponent: discord.Member, wager: int = 0, laps: int = 5):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot race against yourself!", ephemeral=True)
        return
    if wager < 0:
        await interaction.response.send_message("❌ Wager amount cannot be negative.", ephemeral=True)
        return
    if laps < 1 or laps > 20:
        await interaction.response.send_message("❌ Laps must be between 1 and 20.", ephemeral=True)
        return
        
    p1_prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    p2_prof = database.get_full_team_profile(opponent.id, interaction.guild_id)
    
    if not p1_prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start` first.", ephemeral=True)
        return
    if not p2_prof:
        await interaction.response.send_message("❌ Your opponent does not have a profile yet.", ephemeral=True)
        return
        
    # Check if either player lacks the wager funds
    if wager > 0:
        if p1_prof['money'] < wager:
            await interaction.response.send_message(f"❌ You do not have enough credits! You need {wager}¢ (You have {p1_prof['money']}¢).", ephemeral=True)
            return
        if p2_prof['money'] < wager:
            await interaction.response.send_message(f"❌ Opponent does not have enough credits to cover the challenge fee of {wager}¢ (They have {p2_prof['money']}¢).", ephemeral=True)
            return
        
    if p1_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Your car is heavily damaged! Run `/repairs` and `/repair` before racing.", ephemeral=True)
        return
    if p2_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Opponent's car is too damaged to race.", ephemeral=True)
        return
        
    view = RaceAcceptView(interaction.user, opponent, laps, p1_prof, p2_prof, wager=wager)
    
    if wager > 0:
        desc = f"**{interaction.user.name}** has challenged **{opponent.name}** to a **{laps}-lap** racing duel for a wager of **{wager}¢** each!\n💰 *Total pool: **{wager * 2}¢** (Winner takes all, loser gets nothing!)*"
    else:
        desc = f"**{interaction.user.name}** has challenged **{opponent.name}** to a friendly **{laps}-lap** racing duel!"
        
    embed = utils.create_embed(
        title="🏎️ Racing Duel Challenge!",
        description=desc,
        color=utils.COLOR_WARNING
    )
    await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)


@bot.tree.command(name="bet", description="Challenge another user to a race with a credit wager!")
@app_commands.describe(opponent="The player you want to wager against", amount="Credits amount to bet", laps="Number of laps (1-20)")
@app_commands.guild_only()
async def race_bet(interaction: discord.Interaction, opponent: discord.Member, amount: int, laps: int = 1):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot bet against yourself!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Bet amount must be positive.", ephemeral=True)
        return
    if laps < 1 or laps > 20:
        await interaction.response.send_message("❌ Laps must be between 1 and 20.", ephemeral=True)
        return
        
    p1_prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    p2_prof = database.get_full_team_profile(opponent.id, interaction.guild_id)
    
    if not p1_prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start` first.", ephemeral=True)
        return
    if not p2_prof:
        await interaction.response.send_message("❌ Your opponent does not have a profile yet.", ephemeral=True)
        return
        
    if p1_prof['money'] < amount:
        await interaction.response.send_message(f"❌ You do not have enough credits! You need {amount}¢ (You have {p1_prof['money']}¢).", ephemeral=True)
        return
    if p2_prof['money'] < amount:
        await interaction.response.send_message(f"❌ Opponent does not have enough credits to cover the bet ({p2_prof['money']}¢).", ephemeral=True)
        return
        
    if p1_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Your car is heavily damaged! Run `/repairs` and `/repair` before racing.", ephemeral=True)
        return
    if p2_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Opponent's car is too damaged to race.", ephemeral=True)
        return
        
    view = BetAcceptView(interaction.user, opponent, amount, laps, p1_prof, p2_prof)
    embed = utils.create_embed(
        title="💸 Racing Wager Challenge!",
        description=f"**{interaction.user.name}** has challenged **{opponent.name}** to a **{laps}-lap** racing duel for **{amount}¢**!",
        color=utils.COLOR_WARNING
    )
    await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)

# ----------------- Upgrades & Shops -----------------

@bot.tree.command(name="shop", description="Browse available upgrades and costs.")
@app_commands.guild_only()
async def shop(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    desc = "**Current Part Levels and Upgrade Costs:**\n\n"
    
    for part, mult in config.PART_MULTIPLIERS.items():
        curr_level = prof.get(part if part != "aerodynamics" else "aerodynamics", 1)
        # Note: 'aerodynamics' column is named 'aerodynamics' in DB but config might differ. Let's make sure they align.
        # Yes, garage column name is 'aerodynamics'
        
        if curr_level >= config.MAX_STAT_LEVEL:
            cost_str = "MAX LEVEL"
        else:
            cost = config.get_upgrade_cost(part, curr_level + 1)
            cost_str = f"{cost:,}¢"
            
        desc += f"• **{part.capitalize()}:** Level {curr_level} → Level {curr_level + 1 if curr_level < config.MAX_STAT_LEVEL else config.MAX_STAT_LEVEL} (Cost: {cost_str})\n"
        
    embed = utils.create_embed(
        title="🛒 The Performance Shop",
        description=desc + "\nUse `/upgrade <part>` to purchase a component upgrade.",
        color=utils.COLOR_INFO
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="upgrade", description="Upgrade a car part to boost its power.")
@app_commands.describe(part="The part you wish to upgrade")
@app_commands.choices(part=[
    app_commands.Choice(name="Engine", value="engine"),
    app_commands.Choice(name="Aerodynamics", value="aerodynamics"),
    app_commands.Choice(name="Tyres", value="tyres"),
    app_commands.Choice(name="ERS", value="ers"),
    app_commands.Choice(name="Reliability", value="reliability"),
    app_commands.Choice(name="Pit Crew", value="pit_crew")
])
@app_commands.guild_only()
async def upgrade(interaction: discord.Interaction, part: app_commands.Choice[str]):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    success, msg = database.upgrade_part(prof['user_id'], part.value)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
    await interaction.response.send_message(embed=utils.create_embed(title="🛒 Shop Upgrade", description=msg, color=color))

@bot.tree.command(name="repairs", description="View damaged components and repair costs.")
@app_commands.guild_only()
async def repairs(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    cost_eng = prof['damage_engine'] * config.REPAIR_COST_PER_PCT
    cost_tyr = prof['damage_tyres'] * config.REPAIR_COST_PER_PCT
    
    desc = (
        f"🛠️ **Repairs Department - {prof['team_name']}**\n\n"
        f"• **Engine Damage:** {prof['damage_engine']}% (Repair cost: **{cost_eng}¢**)\n"
        f"• **Tyre Damage:** {prof['damage_tyres']}% (Repair cost: **{cost_tyr}¢**)\n\n"
        f"**Total Pending Damage:** {prof['damage_total']}%\n"
        f"**Your Balance:** {prof['money']:,}¢\n\n"
        f"Use `/repair <part>` to fix individual parts."
    )
    embed = utils.create_embed(title="🔧 Repairs Desk", description=desc, color=utils.COLOR_WARNING)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="repair", description="Pay credits to repair a damaged component.")
@app_commands.describe(part="The part you wish to repair")
@app_commands.choices(part=[
    app_commands.Choice(name="Engine", value="engine"),
    app_commands.Choice(name="Tyres", value="tyres")
])
@app_commands.guild_only()
async def repair(interaction: discord.Interaction, part: app_commands.Choice[str]):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    success, msg = database.repair_part(prof['user_id'], part.value)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
    await interaction.response.send_message(embed=utils.create_embed(title="🔧 Repairs Desk", description=msg, color=color))

@bot.tree.command(name="leaderboard", description="View the top racing teams in the server.")
@app_commands.describe(sort_by="Choose sorting criteria")
@app_commands.choices(sort_by=[
    app_commands.Choice(name="Championship Points", value="points"),
    app_commands.Choice(name="Money / Balance", value="money")
])
@app_commands.guild_only()
async def leaderboard(interaction: discord.Interaction, sort_by: app_commands.Choice[str] = None):
    criteria = sort_by.value if sort_by else "points"
    results = database.get_leaderboard(interaction.guild_id, criteria)
    
    if not results:
        await interaction.response.send_message("The leaderboard is currently empty.", ephemeral=True)
        return
        
    desc = ""
    for idx, row in enumerate(results):
        score_suffix = "pts" if criteria == "points" else "¢"
        desc += f"**{idx + 1}.** {row['team_name']} (Lvl {row['level']}) — **{row['score']:,}{score_suffix}**\n"
        
    title = "🏆 Championship Standings" if criteria == "points" else "💰 Server Wealth Leaderboard"
    embed = utils.create_embed(title=title, description=desc, color=utils.COLOR_WARNING)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show detailed guide on how to play Discord Grand Prix.")
@app_commands.guild_only()
async def help_command(interaction: discord.Interaction):
    desc = (
        "🏎️ **Discord Grand Prix — Quick Guide**\n\n"
        "**Core Loop:**\n"
        "Earn credits ➡️ Upgrade car parts ➡️ Race & duel players ➡️ Dominate the server Grand Prix!\n\n"
        "**Commands List:**\n"
        "• `/start <team_name>` — Register your racing team profile.\n"
        "• `/profile` — View your team stats and money.\n"
        "• `/garage` — View car part levels and damage.\n"
        "• `/stats` — View detailed driver stats.\n"
        "• `/train` — Spend credits to train driver skills.\n"
        "• `/daily` — Claim free 500¢ every 24 hours.\n"
        "• `/work` — Perform a job once a day to earn extra credits.\n"
        "• `/shop` — View upgrades and levels cost.\n"
        "• `/upgrade <part>` — Purchase part upgrade.\n"
        "• `/repairs` / `/repair <part>` — Repair damaged components.\n"
        "• `/race @opponent` — Challenge a member to a 1-lap duel.\n"
        "• `/bet @opponent <amount>` — Duel a member with a credit wager.\n"
        "• `/joinrace` / `/leaverace` — Participate in the weekly server GP.\n"
        "• `/grid` — View starting grid of upcoming GP.\n"
        "• `/leaderboard` — View server top standings."
    )
    embed = utils.create_embed(title="📚 Racing Guide", description=desc, color=utils.COLOR_INFO)
    await interaction.response.send_message(embed=embed)

# ----------------- Grand Prix Scheduled Event Control -----------------

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

async def send_driver_lap_telemetry(guild_id, driver_discord_id, team_name, lap_num, lap_time, position, gap_to_leader, gap_to_front, tyre_type, tyre_health):
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
            await interaction.followup.send(f"❌ **Error starting GP:** `{e}`")

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
                user = bot.get_user(drv['discord_id']) or await bot.fetch_user(drv['discord_id'])
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

@bot.tree.command(name="gp", description="Manage Grand Prix events (Admin control panel).")
@app_commands.describe(
    laps="Specify the race distance length (number of laps, default 15)"
)
@is_admin()
@app_commands.guild_only()
async def gp_admin(interaction: discord.Interaction, laps: int = 15):
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
    
    view = GPAdminView(interaction.guild_id, laps=laps)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="sprint", description="Schedule a Sprint Race Weekend (Admin control panel).")
@app_commands.describe(
    laps="Specify the Sprint race distance length (number of laps, default 8)"
)
@is_admin()
@app_commands.guild_only()
async def sprint_admin(interaction: discord.Interaction, laps: int = 8):
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
    
    view = GPAdminView(interaction.guild_id, laps=laps)
    if not active_gp:
        view.clear_items()
        view.add_item(GPTrackSelect(laps=laps, is_sprint=True))
        
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="joinrace", description="Register and pay 1000¢ entry fee to join the upcoming Grand Prix.")
@app_commands.guild_only()
async def join_race(interaction: discord.Interaction):
    success, msg = database.register_gp_entry(interaction.user.id, interaction.guild_id)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
    await interaction.response.send_message(embed=utils.create_embed(title="🏁 Race Entry", description=msg, color=color))

@bot.tree.command(name="leaverace", description="Leave the upcoming Grand Prix and receive a refund of your 1000¢ entry fee.")
@app_commands.guild_only()
async def leave_race(interaction: discord.Interaction):
    success, msg = database.unregister_gp_entry(interaction.user.id, interaction.guild_id)
    color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
    await interaction.response.send_message(embed=utils.create_embed(title="🏁 Race Withdrawal", description=msg, color=color))

class GPGridActionView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=600.0)
        self.guild_id = guild_id

    @discord.ui.button(label="🔍 View My Car Specs", style=discord.ButtonStyle.secondary, custom_id="grid_view_specs")
    async def view_specs_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        prof = database.get_full_team_profile(interaction.user.id, self.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start` to join the grid!", ephemeral=True)
            return
            
        overall_power = utils.calculate_overall_power(prof, prof["pace"])
        engine_bar = utils.make_progress_bar(prof['damage_engine'])
        tyres_bar = utils.make_progress_bar(prof['damage_tyres'])
        total_bar = utils.make_progress_bar(prof['damage_total'])
        
        import json
        strat_json = {}
        strategy_str = prof.get('pit_strategy_json')
        if strategy_str:
            try:
                strat_json = json.loads(strategy_str)
            except Exception:
                pass
        pace = strat_json.get("pace", prof.get("pref_strategy", "Balanced"))
        start_tyre = strat_json.get("start_tyre", prof.get("pref_tyres", "Medium"))
        stops = strat_json.get("stops", [])
        
        if stops:
            stops_str = ", ".join([f"L{s['lap']}({s['tyre']})" for s in stops])
        else:
            stops_str = f"{prof.get('pref_pit_stops', 1)} (Auto)"
            
        desc = (
            f"🏎️ **Driver:** {interaction.user.mention} | **Team:** **{prof['team_name']}** (Level {prof['level']})\n\n"
            f"📈 **Ratings & Stats:**\n"
            f"  • **Driver Pace:** `{prof['pace']}/100` | **Qualifying:** `{prof['qual']}/100`\n"
            f"  • **Wet Skill:** `{prof['wet_skill']}/100` | **Consistency:** `{prof['consistency']}/100`\n"
            f"  • **Overall Team Power:** `{overall_power}`\n\n"
            f"⚙️ **Car Specifications & Health:**\n"
            f"  • **Engine Level:** `Level {prof['engine']}` | Wear: {engine_bar}\n"
            f"  • **Aero Level:** `Level {prof['aerodynamics']}`\n"
            f"  • **Tyres Level:** `Level {prof['tyres']}` | Wear: {tyres_bar}\n"
            f"  • **Overall Damage:** {total_bar}\n\n"
            f"📋 **Current Strategy:**\n"
            f"  • **Pacing:** `{pace}` | **Start Tyres:** `{start_tyre}`\n"
            f"  • **Pit Stops:** `{stops_str}`\n\n"
            f"*You can use `/strategy` in any channel to privately update your pit window and tyre setups.*"
        )
        
        embed = utils.create_embed(
            title="🔍 Private Telemetry Dashboard",
            description=desc,
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="grid", description="View the current registration list and qualifying grid.")
@app_commands.guild_only()
async def view_grid(interaction: discord.Interaction):
    active_gp = database.get_active_gp_race(interaction.guild_id)
    if not active_gp:
        await interaction.response.send_message("❌ There is no active Grand Prix scheduled.", ephemeral=True)
        return
        
    entries = database.get_gp_entries_full(active_gp['race_id'])
    if not entries:
        await interaction.response.send_message(f"There are no entrants registered for **{active_gp['name']}** yet. Run `/joinrace` to be the first!", ephemeral=True)
        return
        
    status = active_gp.get("status", "Created")
    
    import json
    weather_raw = active_gp.get('weather', 'Sunny')
    forecast = "Sunny"
    try:
        weather_data = json.loads(weather_raw)
        forecast = weather_data.get('forecast', 'Sunny')
    except Exception:
        forecast = weather_raw
        
    desc = (
        f"🏁 **Event:** **{active_gp['name']}** ({active_gp['track']})\n"
        f"📊 **Stage:** `{status}`\n"
        f"🌦️ **Forecast:** `{forecast}`\n\n"
    )
    
    if status == "Created":
        desc += "**Registered Entrants:**\n"
        for idx, row in enumerate(entries):
            desc += f"• **{row['team_name']}** (level {row['level']})\n"
    else:
        entries.sort(key=lambda x: (x['start_position'] if x['start_position'] is not None else 999))
        
        desc += "**Starting Grid / Qualifying Standings:**\n"
        for idx, row in enumerate(entries):
            q1 = race.format_lap_time(row['quali_q1_time']) if row['quali_q1_time'] else "—"
            q2 = race.format_lap_time(row['quali_q2_time']) if row['quali_q2_time'] else "—"
            q3 = race.format_lap_time(row['quali_q3_time']) if row['quali_q3_time'] else "—"
            
            pos = row['start_position']
            if pos is not None:
                desc += f"**P{pos}.** {row['team_name']} — Q1: `{q1}` | Q2: `{q2}` | Q3: `{q3}`\n"
            else:
                desc += f"• **{row['team_name']}** — Active (Q1: `{q1}` | Q2: `{q2}` | Q3: `{q3}`)\n"
                
    embed = utils.create_embed(
        title=f"📋 Race Entry Grid - {active_gp['name']}",
        description=desc + f"\n*Registration count: {len(entries)}*",
        color=utils.COLOR_INFO
    )
    view = GPGridActionView(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="standings", description="View current overall Grand Prix points championship standings.")
@app_commands.guild_only()
async def standings(interaction: discord.Interaction):
    await leaderboard(interaction)

@bot.tree.command(name="results", description="View final standings of the last completed Grand Prix.")
@app_commands.guild_only()
async def results(interaction: discord.Interaction):
    race_info, results_rows = database.get_last_finished_gp_results(interaction.guild_id)
    if not race_info:
        await interaction.response.send_message("❌ No Grand Prix races have finished yet.", ephemeral=True)
        return
        
    # Split description into chunks of max 20 lines to prevent character limits
    chunks = []
    current_chunk = []
    for row in results_rows:
        dnf_tag = " (DNF)" if row['dnf'] else ""
        line = f"P{row['finish_position']}: **{row['team_name']}**{dnf_tag} — **+{row['points_earned']} pts** (+{row['credits_won']}¢)"
        current_chunk.append(line)
        if len(current_chunk) == 20:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    # Send the first chunk, then followup for the rest
    await interaction.response.send_message(embed=utils.create_embed(
        title=f"🏁 Race Results: {race_info['name']}",
        description=f"**Results for {race_info['name']} at {race_info['track']}:**\n\n" + (chunks[0] if chunks else ""),
        color=utils.COLOR_RACE_RESULTS
    ))
    
    for c in chunks[1:]:
        await interaction.followup.send(embed=utils.create_embed(
            title=f"🏁 Race Results (Continued)",
            description=c,
            color=utils.COLOR_RACE_RESULTS
        ))

# ----------------- Admin Override Commands -----------------

@bot.tree.command(name="give", description="Give credits to a player (Admin only).")
@app_commands.describe(member="The target player", amount="Credits amount to give")
@is_admin()
@app_commands.guild_only()
async def admin_give(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
        
    user = database.get_user_by_discord_id(member.id, interaction.guild_id)
    if not user:
        await interaction.response.send_message("❌ User has no profile.", ephemeral=True)
        return
        
    database.update_user_balance(user['user_id'], amount)
    await interaction.response.send_message(
        embed=utils.create_embed(
            title="💰 Admin Grant",
            description=f"Successfully granted **{amount:,}¢** to **{member.name}**'s team profile.",
            color=utils.COLOR_SUCCESS
        )
    )

@bot.tree.command(name="remove", description="Deduct credits from a player (Admin only).")
@app_commands.describe(member="The target player", amount="Credits amount to deduct")
@is_admin()
@app_commands.guild_only()
async def admin_remove(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
        
    user = database.get_user_by_discord_id(member.id, interaction.guild_id)
    if not user:
        await interaction.response.send_message("❌ User has no profile.", ephemeral=True)
        return
        
    success = database.update_user_balance(user['user_id'], -amount)
    if success:
        await interaction.response.send_message(
            embed=utils.create_embed(
                title="💰 Admin Penalty",
                description=f"Successfully deducted **{amount:,}¢** from **{member.name}**'s balance.",
                color=utils.COLOR_SUCCESS
            )
        )
    else:
        await interaction.response.send_message("❌ Action failed. Deducting this amount would result in a negative balance.", ephemeral=True)

@bot.tree.command(name="reset", description="Reset a player's profile and delete all upgrades/ratings (Admin only).")
@app_commands.describe(member="The target player")
@is_admin()
@app_commands.guild_only()
async def admin_reset(interaction: discord.Interaction, member: discord.Member):
    user = database.get_user_by_discord_id(member.id, interaction.guild_id)
    if not user:
        await interaction.response.send_message("❌ User has no profile to reset.", ephemeral=True)
        return
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user['user_id'],))
        conn.commit()
        await interaction.response.send_message(
            embed=utils.create_embed(
                title="🗑️ Admin Account Reset",
                description=f"Successfully deleted and reset **{member.name}**'s racing profile.",
                color=utils.COLOR_SUCCESS
            )
        )
    except sqlite3.Error as e:
        conn.rollback()
        await interaction.response.send_message(f"❌ Failed to reset user: {e}", ephemeral=True)
    finally:
        conn.close()

@bot.tree.command(name="broadcast", description="Broadcast an announcement message to a designated channel (Admin only).")
@app_commands.describe(message="The announcement message content")
@is_admin()
@app_commands.guild_only()
async def admin_broadcast(interaction: discord.Interaction, message: str):
    channel_id = config.ANNOUNCEMENT_CHANNEL_ID or interaction.channel_id
    channel = bot.get_channel(channel_id)
    
    if not channel:
        await interaction.response.send_message("❌ Could not find announcement channel.", ephemeral=True)
        return
        
    embed = utils.create_embed(
        title="📢 Grand Prix News & Announcements",
        description=message,
        color=utils.COLOR_QUALIFYING
    )
    
    # Send message to broadcast channel
    await channel.send(embed=embed)
    await interaction.response.send_message("Announcement broadcasted successfully.", ephemeral=True)

@bot.tree.command(name="dbbackup", description="Trigger manual backup copy of SQLite DB (Admin only).")
@is_admin()
@app_commands.guild_only()
async def admin_dbbackup(interaction: discord.Interaction):
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

@bot.tree.command(name="debug", description="Toggle verbose terminal logs (Admin only).")
@app_commands.describe(toggle="Turn debug logs on/off")
@is_admin()
@app_commands.guild_only()
async def admin_debug(interaction: discord.Interaction, toggle: bool):
    global debug_mode
    debug_mode = toggle
    status = "ON" if debug_mode else "OFF"
    await interaction.response.send_message(
        embed=utils.create_embed(
            title="⚙️ Debug Mode",
            description=f"Verbose debugging terminal logs have been turned **{status}**.",
            color=utils.COLOR_SUCCESS
        )
    )

# ----------------- Phase 3: Crates, Inventory, Practice & Boosters -----------------

import crates

@bot.tree.command(name="crate", description="View available loot crates, unboxing drop chances, and credit rewards.")
@app_commands.guild_only()
async def view_crates(interaction: discord.Interaction):
    desc = (
        "📦 **DISCORD GRAND PRIX LOOT CRATE STORE**\n"
        "Unbox rare car components, tuning parts, and credit rewards!\n\n"
        "📦 **Rookie Crate — 500¢**\n"
        "  • **Guaranteed Gold:** `100¢ – 400¢` refund!\n"
        "  • **Part Drop Chance:** `60%` (⚪ Common 70% | 🟢 Uncommon 25% | 🔵 Rare 5%)\n"
        "  • Command: `/open crate_tier:rookie`\n\n"
        "💼 **Pro Crate — 2,500¢**\n"
        "  • **Guaranteed Gold:** `500¢ – 1,800¢` refund!\n"
        "  • **Part Drop Chance:** `85%` (🟢 Uncommon 40% | 🔵 Rare 45% | 🟣 Epic 12% | 🟡 Legendary 3%)\n"
        "  • Command: `/open crate_tier:pro`\n\n"
        "🏆 **Champion Crate — 6,000¢**\n"
        "  • **Guaranteed Gold:** `1,500¢ – 5,000¢` refund!\n"
        "  • **Part Drop Chance:** `100% Guaranteed` (🔵 Rare 35% | 🟣 Epic 50% | 🟡 Legendary 15%)\n"
        "  • Command: `/open crate_tier:champion`"
    )
    embed = utils.create_embed(title="🎁 Loot Crates & Unboxing Store", description=desc, color=utils.COLOR_QUALIFYING)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="open", description="Unbox a Rookie, Pro, or Champion Loot Crate.")
@app_commands.describe(crate_tier="Select crate tier to unbox (rookie, pro, champion)")
@app_commands.choices(crate_tier=[
    app_commands.Choice(name="📦 Rookie Crate (500¢)", value="rookie"),
    app_commands.Choice(name="💼 Pro Crate (2,500¢)", value="pro"),
    app_commands.Choice(name="🏆 Champion Crate (6,000¢)", value="champion")
])
@app_commands.guild_only()
async def open_crate_cmd(interaction: discord.Interaction, crate_tier: app_commands.Choice[str]):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile yet. Use `/start`.", ephemeral=True)
        return
        
    success, msg, summary = crates.unbox_crate(prof['user_id'], crate_tier.value)
    if not success:
        await interaction.response.send_message(f"{msg}", ephemeral=True)
        return
        
    part = summary["part_dropped"]
    part_desc = ""
    if part:
        part_desc = (
            f"\n\n✨ **NEW CAR PART UNBOXED!**\n"
            f"{part['emoji']} **{part['rarity']} {part['part_name']}**\n"
            f"⚙️ **Category:** `{part['category'].upper()}` | **Level:** `{part['level']}`\n"
            f"⚡ **Efficiency Bonus:** `{part['efficiency_bonus']}` tuning boost!\n"
            f"*Equip it in `/inventory` to install it onto your car!*"
        )
    else:
        part_desc = "\n\n⚙️ *No car part dropped this time, better luck next crate!*"
        
    desc = (
        f"🎉 **{summary['crate_name']} Unboxed!**\n\n"
        f"💰 **Gold Returned:** `+{summary['gold_reward']:,}¢`\n"
        f"📊 **Net Cost:** `{summary['net_cost']:,}¢`{part_desc}"
    )
    
    embed = utils.create_embed(
        title="🎁 UNBOXING CEREMONY",
        description=desc,
        color=utils.COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

class InventorySelectMenu(discord.ui.Select):
    def __init__(self, user_id, category):
        self.user_id = user_id
        self.category = category
        items = database.get_user_inventory(user_id, category)
        options = []
        if not items:
            options.append(discord.SelectOption(label="No parts in this category", value="none"))
        else:
            for item in items[:25]:
                status = "🟢 [Equipped]" if item['is_equipped'] else "⚪ [Storage]"
                from crates import RARITY_EMOJIS
                emoji_str = RARITY_EMOJIS.get(item['rarity'], '⚪')
                label = f"{emoji_str} {item['part_name'][:25]} (Lvl {item['level']})"
                desc = f"{status} {item['rarity']} | +{item['stat_bonus']} Stat"
                options.append(discord.SelectOption(label=label, value=str(item['item_id']), description=desc))
                
        super().__init__(placeholder=f"Select {category.upper()} part to equip...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ No parts available in this category.", ephemeral=True)
            return
            
        item_id = int(val)
        success, msg = database.equip_inventory_part(self.user_id, item_id)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🔧 Garage Equipment", description=msg, color=color), ephemeral=True)

class InventoryCategorySelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [
            discord.SelectOption(label="Engine Parts", value="engine", description="View stored engine blocks & turbochargers"),
            discord.SelectOption(label="Aerodynamics Parts", value="aerodynamics", description="View wings & floor diffusers"),
            discord.SelectOption(label="Tyre Compounds", value="tyres", description="View tyre tread compounds"),
            discord.SelectOption(label="ERS Hybrid Units", value="ers", description="View MGU-K and battery cells"),
            discord.SelectOption(label="Reliability Parts", value="reliability", description="View coolers & gearboxes"),
            discord.SelectOption(label="Pit Crew Gear", value="pit_crew", description="View wheel guns & jacks")
        ]
        super().__init__(placeholder="Filter Inventory by Category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        view = discord.ui.View(timeout=180.0)
        view.add_item(InventoryCategorySelect(self.user_id))
        view.add_item(InventorySelectMenu(self.user_id, cat))
        
        items = database.get_user_inventory(self.user_id, cat)
        from crates import RARITY_EMOJIS, RARITY_BONUS_MULTIPLIERS
        desc = f"🧰 **GARAGE INVENTORY — {cat.upper()}**\n\n"
        if not items:
            desc += "⚙️ *No parts owned in this category yet. Unbox crates via `/open` to find rare parts!*"
        else:
            for item in items:
                status = "🟢 **[EQUIPPED]**" if item['is_equipped'] else "⚪ *(Storage)*"
                e_emoji = RARITY_EMOJIS.get(item['rarity'], '⚪')
                bonus_pct = f"+{(RARITY_BONUS_MULTIPLIERS.get(item['rarity'], 1.0) - 1.0)*100:.0f}%"
                desc += f"{status} {e_emoji} **{item['rarity']} {item['part_name']}** (Level {item['level']}) — Efficiency: `{bonus_pct}`\n"
                
        embed = utils.create_embed(title="🧰 Part Inventory & Equipment", description=desc, color=utils.COLOR_INFO)
        await interaction.response.edit_message(embed=embed, view=view)

@bot.tree.command(name="inventory", description="View stored car parts and equip preferred setups.")
@app_commands.guild_only()
async def view_inventory(interaction: discord.Interaction):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    view = discord.ui.View(timeout=180.0)
    view.add_item(InventoryCategorySelect(prof['user_id']))
    view.add_item(InventorySelectMenu(prof['user_id'], "engine"))
    
    items = database.get_user_inventory(prof['user_id'], "engine")
    from crates import RARITY_EMOJIS, RARITY_BONUS_MULTIPLIERS
    desc = "🧰 **GARAGE INVENTORY — ENGINE**\n\n"
    if not items:
        desc += "⚙️ *No custom parts in inventory yet. Upgrade your car via `/upgrade` or unbox crates via `/open`!*"
    else:
        for item in items:
            status = "🟢 **[EQUIPPED]**" if item['is_equipped'] else "⚪ *(Storage)*"
            e_emoji = RARITY_EMOJIS.get(item['rarity'], '⚪')
            bonus_pct = f"+{(RARITY_BONUS_MULTIPLIERS.get(item['rarity'], 1.0) - 1.0)*100:.0f}%"
            desc += f"{status} {e_emoji} **{item['rarity']} {item['part_name']}** (Level {item['level']}) — Efficiency: `{bonus_pct}`\n"
            
    embed = utils.create_embed(title="🧰 Part Inventory & Equipment", description=desc, color=utils.COLOR_INFO)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="practice", description="Run a solo practice session on an official F1 track to gain Track Mastery.")
@app_commands.guild_only()
async def practice_track(interaction: discord.Interaction):
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
            "📅 **Daily Limit:** Maximum **3 practice sessions per day** to prevent single-track spamming.\n\n"
            "Select a track below to begin your practice run:"
        ),
        color=utils.COLOR_QUALIFYING
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="shop", description="View consumable race & qualifying boosters (Max 2 boosters cap).")
@app_commands.guild_only()
async def shop_boosters(interaction: discord.Interaction):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    user_boosters = database.get_user_boosters(prof['user_id'])
    booster_list = ""
    if user_boosters:
        for b in user_boosters:
            booster_list += f"  • **{b['booster_name']}** ({b['charges']} charge(s))\n"
    else:
        booster_list = "  • *No active boosters held*\n"
        
    desc = (
        "🛒 **CONSUMABLE BOOSTERS SHOP**\n"
        "Purchase single-use tactical boosters for upcoming qualifying & race sessions.\n"
        "🔒 **Inventory Limit:** Max **2 active boosters** held at a time.\n\n"
        f"🎒 **Your Active Boosters:**\n{booster_list}\n"
        "🔥 **Available Boosters:**\n"
        "1. **🔥 Tyre Blanket Warmer — 1,500¢**\n"
        "   • *Effect:* Adds **`-0.15s` Qualifying Lap Pace** advantage.\n"
        "   • Buy command: `/booster item:tyre_warmer`\n\n"
        "2. **⚡ ERS High-Flow Injector — 2,000¢**\n"
        "   • *Effect:* Grants **+1 Lap extra ERS Boost** during races.\n"
        "   • Buy command: `/booster item:ers_injector`\n\n"
        "3. **🛡️ Heavy Duty Radiator — 1,200¢**\n"
        "   • *Effect:* Reduces engine thermal heat buildup by **-30%**.\n"
        "   • Buy command: `/booster item:radiator`"
    )
    embed = utils.create_embed(title="🛒 Consumable Boosters Shop", description=desc, color=utils.COLOR_QUALIFYING)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="booster", description="Purchase a consumable booster from the shop.")
@app_commands.describe(item="Select booster to purchase")
@app_commands.choices(item=[
    app_commands.Choice(name="🔥 Tyre Blanket Warmer (1,500¢)", value="tyre_warmer"),
    app_commands.Choice(name="⚡ ERS High-Flow Injector (2,000¢)", value="ers_injector"),
    app_commands.Choice(name="🛡️ Heavy Duty Radiator (1,200¢)", value="radiator")
])
@app_commands.guild_only()
async def buy_booster_cmd(interaction: discord.Interaction, item: app_commands.Choice[str]):
    prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    booster_map = {
        "tyre_warmer": ("quali", "Tyre Blanket Warmer", 1500),
        "ers_injector": ("race", "ERS High-Flow Injector", 2000),
        "radiator": ("reliability", "Heavy Duty Radiator", 1200)
    }
    
    b_type, b_name, price = booster_map[item.value]
    if prof['money'] < price:
        await interaction.response.send_message(f"❌ Insufficient funds! **{b_name}** costs **{price:,}¢**, but you have **{prof['money']:,}¢**.", ephemeral=True)
        return
        
    success, msg = database.add_user_booster(prof['user_id'], b_type, b_name)
    if success:
        database.update_user_balance(prof['user_id'], -price)
        color = utils.COLOR_SUCCESS
    else:
        color = utils.COLOR_WARNING
        
    await interaction.response.send_message(embed=utils.create_embed(title="🛒 Booster Purchase", description=msg, color=color))

# ----------------- Start Bot -----------------
if __name__ == "__main__":
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        print("Error: DISCORD_TOKEN is missing or not set in environment or .env file.")
    else:
        bot.run(config.DISCORD_TOKEN)
