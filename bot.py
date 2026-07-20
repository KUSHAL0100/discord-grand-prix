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

# In-memory dict to track when voice members joined: {member_id: join_time}
voice_tracking = {}

# In-memory dict to track when members last earned chat credits: {member_id: last_award_time}
chat_cooldowns = {}

# Keep track of debug mode status
debug_mode = False

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
    except Exception as e:
        print(f"Failed to sync commands: {e}")

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

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
        
    # User joins a voice channel
    if before.channel is None and after.channel is not None:
        voice_tracking[member.id] = datetime.now()
        if debug_mode:
            print(f"{member.name} joined voice channel {after.channel.name}.")
            
    # User leaves a voice channel
    elif before.channel is not None and after.channel is None:
        join_time = voice_tracking.pop(member.id, None)
        if join_time:
            duration = datetime.now() - join_time
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
                        print(f"Awarded {earned}¢ to {member.name} for {int(minutes)} mins in voice.")

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

@bot.tree.command(name="profile", description="View your team profile and overall standings.")
@app_commands.describe(member="Select another team owner to view their profile (optional)")
@app_commands.guild_only()
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    prof = database.get_full_team_profile(target.id, interaction.guild_id)
    
    if not prof:
        if member:
            await interaction.response.send_message("❌ That user does not have a team profile yet in this server.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You haven't registered a profile yet in this server! Run `/start` to begin.", ephemeral=True)
        return
        
    # Calculate overall power
    overall_power = utils.calculate_overall_power(prof, prof["pace"])
    
    # Format embed output mimicking the design specifications (Page 3)
    title = f"🏎️ {prof['team_name']}"
    if prof['country']:
        title = f"{prof['country']} " + title
    title += f" (Level {prof['level']})"
    
    desc = (
        f"💰 **Money:** {prof['money']:,} credits\n"
        f"🏆 **Wins:** {prof['wins']} | 🚫 **Losses:** {prof['losses']}\n"
        f"⚡ **Power:** {overall_power}\n"
        f"📋 **Strategy:** {prof.get('pref_strategy', 'Balanced')} | 🛞 **Tyres:** {prof.get('pref_tyres', 'Medium')} | 🔧 **Stops:** {prof.get('pref_pit_stops', 1)}"
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
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="team", description="Show detailed summary of a team.")
@app_commands.describe(member="Select another team owner (optional)")
@app_commands.guild_only()
async def team_info(interaction: discord.Interaction, member: discord.Member = None):
    # Map to profile command directly as required by PRD
    await profile(interaction, member)

@bot.tree.command(name="garage", description="View your current car component levels and damage.")
@app_commands.guild_only()
async def garage(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
        return
        
    overall_power = utils.calculate_overall_power(prof, prof["pace"])
    
    fields = [
        {"name": "⚙️ Engine", "value": f"Level {prof['engine']}/{config.MAX_STAT_LEVEL} (Damage: {prof['damage_engine']}%)", "inline": True},
        {"name": "✈️ Aerodynamics", "value": f"Level {prof['aerodynamics']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "⭕ Tyres", "value": f"Level {prof['tyres']}/{config.MAX_STAT_LEVEL} (Damage: {prof['damage_tyres']}%)", "inline": True},
        {"name": "🔋 ERS", "value": f"Level {prof['ers']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "🛡️ Reliability", "value": f"Level {prof['reliability']}/{config.MAX_STAT_LEVEL}", "inline": True},
        {"name": "🔧 Pit Crew", "value": f"Level {prof['pit_crew']}/{config.MAX_STAT_LEVEL}", "inline": True}
    ]
    
    embed = utils.create_embed(
        title=f"🛠️ {prof['team_name']}'s Garage",
        description=f"**Overall Car Power Rating:** {overall_power}\n**Total Pending Damage:** {prof['damage_total']}%",
        color=utils.COLOR_INFO,
        fields=fields
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View detailed Driver and Strategist statistics.")
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
            f"• **Overtaking:** {prof['overtaking']}/100\n"
            f"• **XP/Experience:** {prof['experience']}"
        ), "inline": True},
        {"name": "📋 Strategist Stats", "value": (
            f"• **Pit Timing:** {prof['pit_timing']}/100\n"
            f"• **Weather Calls:** {prof['weather_call']}/100\n"
            f"• **Undercut Execution:** {prof['undercut']}/100\n"
            f"• **Safety Car Strategy:** {prof['sc_skill']}/100\n"
            f"• **Risk Tolerance:** {prof['risk']}/100\n"
            f"• **Communication:** {prof['communication']}/100"
        ), "inline": True}
    ]
    
    embed = utils.create_embed(
        title=f"📊 Staff Performance Sheet - {prof['team_name']}",
        description="Your team personnel gain experience and skill ratings after races.",
        color=utils.COLOR_INFO,
        fields=fields
    )
    await interaction.response.send_message(embed=embed)

class AddPitStopModal(discord.ui.Modal, title="Add Pit Stop"):
    lap_num = discord.ui.TextInput(label="Lap Number (e.g. 8)", placeholder="Between 1 and 100", min_length=1, max_length=3)
    tyre_compound = discord.ui.TextInput(label="Tyre Compound (Soft, Medium, Hard)", placeholder="e.g. Hard", min_length=4, max_length=6)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lap = int(self.lap_num.value)
            if lap < 1 or lap > 100:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ Invalid lap number. Must be a number between 1 and 100.", ephemeral=True)
            return

        tyre = self.tyre_compound.value.strip().capitalize()
        if tyre not in ["Soft", "Medium", "Hard"]:
            await interaction.response.send_message("❌ Invalid tyre compound. Must be Soft, Medium, or Hard.", ephemeral=True)
            return

        self.view.stops.append({"lap": lap, "tyre": tyre})
        self.view.stops.sort(key=lambda x: x["lap"])
        
        import json
        strategy_data = {
            "pace": self.view.pace,
            "start_tyre": self.view.start_tyre,
            "stops": self.view.stops
        }
        database.update_user_pit_strategy(self.view.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.view.user_id, self.view.pace, self.view.start_tyre, len(self.view.stops))
        await self.view.update_embed(interaction)

class StrategyPaceSelect(discord.ui.Select):
    def __init__(self, current_pace):
        options = [
            discord.SelectOption(label="Aggressive (+pace, ++wear, +crash)", value="Aggressive", default=(current_pace == "Aggressive")),
            discord.SelectOption(label="Balanced (neutral pace, normal wear)", value="Balanced", default=(current_pace == "Balanced")),
            discord.SelectOption(label="Conservative (-pace, -wear, -crash)", value="Conservative", default=(current_pace == "Conservative"))
        ]
        super().__init__(placeholder="Select Pace Strategy...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.pace = self.values[0]
        import json
        strategy_data = {
            "pace": self.view.pace,
            "start_tyre": self.view.start_tyre,
            "stops": self.view.stops
        }
        database.update_user_pit_strategy(self.view.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.view.user_id, self.view.pace, self.view.start_tyre, len(self.view.stops))
        await self.view.update_embed(interaction)

class StrategyTyresSelect(discord.ui.Select):
    def __init__(self, current_tyres):
        options = [
            discord.SelectOption(label="Soft tyres (++pace, ++wear)", value="Soft", default=(current_tyres == "Soft")),
            discord.SelectOption(label="Medium tyres (+pace, +wear)", value="Medium", default=(current_tyres == "Medium")),
            discord.SelectOption(label="Hard tyres (neutral pace, very low wear)", value="Hard", default=(current_tyres == "Hard"))
        ]
        super().__init__(placeholder="Select Tyre Compound...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.start_tyre = self.values[0]
        import json
        strategy_data = {
            "pace": self.view.pace,
            "start_tyre": self.view.start_tyre,
            "stops": self.view.stops
        }
        database.update_user_pit_strategy(self.view.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.view.user_id, self.view.pace, self.view.start_tyre, len(self.view.stops))
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
        self.stops = self.strategy_data.get("stops", [])
        
        self.add_item(StrategyPaceSelect(self.pace))
        self.add_item(StrategyTyresSelect(self.start_tyre))

    @discord.ui.button(label="➕ Add Pit Stop", style=discord.ButtonStyle.green, custom_id="add_pit_stop")
    async def add_pit_stop_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.stops) >= 4:
            await interaction.response.send_message("❌ Maximum of 4 planned pit stops allowed.", ephemeral=True)
            return
        await interaction.response.send_modal(AddPitStopModal(self))

    @discord.ui.button(label="🧹 Clear Strategy", style=discord.ButtonStyle.red, custom_id="clear_strategy")
    async def clear_strategy_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stops = []
        import json
        strategy_data = {
            "pace": self.pace,
            "start_tyre": self.start_tyre,
            "stops": self.stops
        }
        database.update_user_pit_strategy(self.user_id, json.dumps(strategy_data))
        database.update_user_strategy(self.user_id, self.pace, self.start_tyre, 0)
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        stops_desc = ""
        if self.stops:
            for idx, stop in enumerate(self.stops):
                stops_desc += f"  • Stop {idx + 1}: **Lap {stop['lap']}** ➡️ Switched to `{stop['tyre']}` tyres\n"
        else:
            stops_desc = "  • *No pit stops scheduled (1-stop evenly-spaced fallback if no custom stops)*\n"
            
        embed = utils.create_embed(
            title="⚙️ Racing Strategy Configuration",
            description=(
                f"Customize your racing setup and pit window schedule below:\n\n"
                f"• **Pacing Strategy:** `{self.pace}`\n"
                f"• **Starting Tyres:** `{self.start_tyre}`\n"
                f"• **Planned Pit Stops Strategy:**\n{stops_desc}\n"
                f"*Selections are updated and saved in real-time. This menu is hidden from other players.*"
            ),
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.edit_message(embed=embed, view=self)

@bot.tree.command(name="strategy", description="Configure your preferred race strategy, tyres, and pit stops.")
@app_commands.guild_only()
async def strategy_setup(interaction: discord.Interaction):
    prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
    if not prof:
        await interaction.response.send_message("❌ You do not have a profile. Use `/start` first.", ephemeral=True)
        return
        
    view = StrategyConfigView(interaction.user.id, interaction.guild_id)
    
    stops_desc = ""
    if view.stops:
        for idx, stop in enumerate(view.stops):
            stops_desc += f"  • Stop {idx + 1}: **Lap {stop['lap']}** ➡️ Switched to `{stop['tyre']}` tyres\n"
    else:
        stops_desc = "  • *No pit stops scheduled (1-stop evenly-spaced fallback if no custom stops)*\n"

    embed = utils.create_embed(
        title="⚙️ Racing Strategy Configuration",
        description=(
            f"Customize your racing setup and pit window schedule below:\n\n"
            f"• **Pacing Strategy:** `{view.pace}`\n"
            f"• **Starting Tyres:** `{view.start_tyre}`\n"
            f"• **Planned Pit Stops Strategy:**\n{stops_desc}\n"
            f"*Selections are updated and saved in real-time. This menu is hidden from other players.*"
        ),
        color=utils.COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
    
    # 2. Stream Laps
    for idx, lap_events in enumerate(lap_logs):
        lap_num = idx + 1
        is_last = (lap_num == len(lap_logs))
        
        embed = utils.create_embed(
            title=f"🏎️ Duel Lap {lap_num}/{laps}: {p1_prof['team_name']} vs {p2_prof['team_name']}",
            description="\n".join(lap_events),
            color=utils.COLOR_SUCCESS if is_last else utils.COLOR_QUALIFYING
        )
        await channel.send(embed=embed)
        await asyncio.sleep(5.0)
        
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
            
            # Insert bet record (race_id is nullable, insert NULL for duels to avoid foreign key errors)
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
        # Winner DNF check
        if winner.get("dnf", False):
            w_dmg_eng = random.randint(15, 30)
            w_dmg_tyr = random.randint(30, 60)
        else:
            w_dmg_eng = random.randint(1, 4)
            w_dmg_tyr = random.randint(2, 8)
            
        # Loser DNF check
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
        
        # Post summary ONLY if commit succeeds
        if wager_amount > 0:
            desc = (
                f"🏆 **Winner:** **{winner['team_name']}** takes the pot of **{wager_amount * 2}¢**!\n"
                f"📉 **{loser['team_name']}** loses **{wager_amount}¢**."
            )
        else:
            desc = (
                f"🏆 **Winner:** **{winner['team_name']}** (+{config.DUEL_WIN_CREDITS}¢)\n"
                f"🏎️ **Runner-up:** **{loser['team_name']}** (+{config.DUEL_LOSS_CREDITS}¢)"
            )
            
        final_embed = utils.create_embed(
            title="🏁 Race Duel: Checkered Flag",
            description=desc,
            color=utils.COLOR_SUCCESS
        )
        await channel.send(embed=final_embed)
        
    except Exception as e:
        conn.rollback()
        print(f"Error saving duel results: {e}")
        await channel.send("❌ **Error:** An operational database error occurred while saving the duel results.")
    finally:
        conn.close()


class RaceAcceptView(discord.ui.View):
    """View handling Duel Race requests."""
    def __init__(self, bettor: discord.Member, target: discord.Member, laps: int, bettor_prof: dict, target_prof: dict):
        super().__init__(timeout=60.0)
        self.bettor = bettor
        self.target = target
        self.laps = laps
        self.bettor_prof = bettor_prof
        self.target_prof = target_prof
        
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
            
        if p1['damage_total'] >= 80 or p2['damage_total'] >= 80:
            await interaction.response.send_message("❌ One of the cars is too damaged to race (must be < 80% damage)!", ephemeral=True)
            self.stop()
            return
            
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🟢 The duel was accepted! The race is starting...", view=self)
        self.stop()
        
        # Run simulation in channel
        await run_duel_simulation(interaction.channel, self.bettor, self.target, p1, p2, self.laps, wager_amount=0)

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
@app_commands.describe(opponent="The player you want to challenge", laps="Number of laps (1-20)")
@app_commands.guild_only()
async def race_duel(interaction: discord.Interaction, opponent: discord.Member, laps: int = 1):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot race against yourself!", ephemeral=True)
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
        
    if p1_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Your car is heavily damaged! Run `/repairs` and `/repair` before racing.", ephemeral=True)
        return
    if p2_prof['damage_total'] >= 80:
        await interaction.response.send_message("❌ Opponent's car is too damaged to race.", ephemeral=True)
        return
        
    view = RaceAcceptView(interaction.user, opponent, laps, p1_prof, p2_prof)
    embed = utils.create_embed(
        title="🏎️ Racing Duel Challenge!",
        description=f"**{interaction.user.name}** has challenged **{opponent.name}** to a **{laps}-lap** racing duel!",
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
        "• `/stats` — View detailed driver/strategist personnel stats.\n"
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
    def __init__(self):
        options = [
            discord.SelectOption(label="Monza Grand Prix", value="Monza", description="Fast track, rewards high Engine Power"),
            discord.SelectOption(label="Spa-Francorchamps Grand Prix", value="Spa", description="Medium track, rewards Aerodynamics & ERS"),
            discord.SelectOption(label="Silverstone Grand Prix", value="Silverstone", description="High speed corners, rewards Aerodynamics"),
            discord.SelectOption(label="Monaco Grand Prix", value="Monaco", description="Tight street circuit, rewards Reliability & Pit Crew"),
            discord.SelectOption(label="Suzuka Grand Prix", value="Suzuka", description="Technical track, rewards balanced setups"),
            discord.SelectOption(label="Bahrain Grand Prix", value="Bahrain", description="Heavy braking, rewards ERS & tyres")
        ]
        super().__init__(placeholder="Select a Track to Schedule GP...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        track_choice = self.values[0]
        gp_name = f"{track_choice} Grand Prix"
        laps = 15
        
        success, msg = database.create_gp_race(interaction.guild_id, gp_name, track_choice, laps)
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
                title="🏁 Grand Prix Scheduled!",
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
            results, logs = race.simulate_gp(entries, active_gp['track'], active_gp['laps'])
            
            winner_id = None
            for res in results:
                if res['finish_position'] == 1:
                    winner_id = res['user_id']
                    break
                    
            database.save_gp_results(active_gp['race_id'], results, winner_id)
            database.update_gp_status(active_gp['race_id'], "Finished")
            
            progress_embed = utils.create_embed(
                title=f"🏎️ LIVE: Grand Prix of {active_gp['track']}",
                description="⏱️ **Qualifying and grid setups are initializing...**",
                color=utils.COLOR_QUALIFYING
            )
            live_message = await interaction.followup.send(embed=progress_embed)
            
            qual_logs = []
            race_lap_logs = {}
            finish_logs = []
            
            current_section = "qual"
            for log in logs:
                if "Qualifying" in log or "P1:" in log or "P2:" in log or "P3:" in log or "P4:" in log or "P5:" in log or "P6:" in log or "P7:" in log or "P8:" in log or "P9:" in log or "P10:" in log:
                    qual_logs.append(log)
                elif "Lights Out!" in log:
                    current_section = "race"
                    race_lap_logs["Lights Out"] = [log]
                elif "Lap " in log:
                    import re
                    lap_match = re.search(r"Lap (\d+)", log)
                    if lap_match:
                        lap_num = int(lap_match.group(1))
                        if lap_num not in race_lap_logs:
                            race_lap_logs[lap_num] = []
                        race_lap_logs[lap_num].append(log)
                elif "Checkered Flag!" in log or "P1:" in log or "Points:" in log or "Winner:" in log:
                    current_section = "finish"
                    finish_logs.append(log)
                else:
                    if current_section == "qual":
                        qual_logs.append(log)
                    elif current_section == "finish":
                        finish_logs.append(log)
                        
            grid_desc = "\n".join(qual_logs[:20])
            progress_embed.description = f"⏱️ **Grid Positions Set!**\n\n{grid_desc}"
            await live_message.edit(embed=progress_embed)
            await asyncio.sleep(4)
            
            if "Lights Out" in race_lap_logs:
                lights_embed = utils.create_embed(
                    title=f"🏎️ LIVE: Grand Prix of {active_gp['track']}",
                    description="\n".join(race_lap_logs["Lights Out"]),
                    color=utils.COLOR_QUALIFYING
                )
                await interaction.channel.send(embed=lights_embed)
                await asyncio.sleep(2)
                
            sorted_keys = sorted([k for k in race_lap_logs.keys() if isinstance(k, int)])
            
            for l_num in sorted_keys:
                lap_events = race_lap_logs[l_num]
                lap_embed = utils.create_embed(
                    title=f"🏎️ Grand Prix Lap {l_num}/{active_gp['laps']}",
                    description="\n".join(lap_events),
                    color=utils.COLOR_RACE_RESULTS
                )
                await interaction.channel.send(embed=lap_embed)
                await asyncio.sleep(15.0)
                
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
    def __init__(self, guild_id):
        super().__init__(timeout=300.0)
        self.guild_id = guild_id
        
        active_gp = database.get_active_gp_race(guild_id)
        if not active_gp:
            self.add_item(GPTrackSelect())
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
@is_admin()
@app_commands.guild_only()
async def gp_admin(interaction: discord.Interaction):
    active_gp = database.get_active_gp_race(interaction.guild_id)
    
    if active_gp:
        entries = database.get_gp_entries_full(active_gp['race_id'])
        desc = (
            f"🏁 **Active GP:** **{active_gp['name']}**\n"
            f"🗺️ **Track:** `{active_gp['track']}`\n"
            f"⏱️ **Distance:** `{active_gp['laps']} Laps`\n"
            f"📊 **Stage:** `{active_gp.get('status', 'Created')}`\n"
            f"👥 **Entrants:** `{len(entries)} driver(s) registered`"
        )
    else:
        desc = "❌ **No active Grand Prix scheduled.**\nUse the **Select a Track** dropdown below to schedule one."
        
    embed = utils.create_embed(
        title="🏁 Grand Prix Admin Panel",
        description=desc,
        color=utils.COLOR_WARNING
    )
    
    view = GPAdminView(interaction.guild_id)
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
    desc = f"🏁 **Event:** **{active_gp['name']}** ({active_gp['track']})\n📊 **Stage:** `{status}`\n\n"
    
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
    await interaction.response.send_message(embed=embed)

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

# ----------------- Start Bot -----------------
if __name__ == "__main__":
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        print("Error: DISCORD_TOKEN is missing or not set in environment or .env file.")
    else:
        bot.run(config.DISCORD_TOKEN)
