import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

import config
import database
import utils

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Global debug mode flag
debug_mode = False

def set_debug_mode(val: bool):
    global debug_mode
    debug_mode = val

# ----------------- Extension Loader (Cogs Architecture) -----------------

async def setup_hook():
    print("Loading modular Cogs architecture...")
    cogs_list = ["cogs.admin", "cogs.garage", "cogs.economy", "cogs.simulator", "cogs.racing"]
    for extension in cogs_list:
        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded Cog: {extension}")
        except Exception as e:
            print(f"❌ Failed to load Cog {extension}: {e}")

bot.setup_hook = setup_hook

# ----------------- Event Handlers & Sync Command -----------------

@bot.command(name="sync")
async def sync_prefix_command(ctx: commands.Context):
    """Force sync all slash commands to this Discord server. Admin only."""
    is_owner = ctx.author.id == ctx.guild.owner_id
    is_admin = ctx.author.guild_permissions.administrator
    if not (is_owner or is_admin):
        await ctx.send("❌ Only server administrators can run `!sync`.")
        return

    msg = await ctx.send("⏳ Syncing slash commands...")

    # Snapshot → clear stale global → restore → sync this guild
    cmds = list(bot.tree.get_commands())
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    for cmd in cmds:
        try:
            bot.tree.add_command(cmd)
        except app_commands.CommandAlreadyRegistered:
            pass

    bot.tree.copy_global_to(guild=ctx.guild)
    synced = await bot.tree.sync(guild=ctx.guild)
    names = [c.name for c in synced]
    await msg.edit(content=f"✅ **Synced {len(synced)} commands** to **{ctx.guild.name}**!\nCommands: `{', '.join(names)}`")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Initializing database schema and performance indexes...")
    database.init_db()

    try:
        # Debug: show what the tree contains after cog loading
        all_cmds = bot.tree.get_commands()
        print(f"[SYNC] Tree has {len(all_cmds)} commands: {[c.name for c in all_cmds]}")

        # Step 1: Snapshot all commands from the tree
        cmds_snapshot = list(all_cmds)

        # Step 2: Clear stale GLOBAL registrations from Discord (fixes duplicates)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("[SYNC] Cleared stale global registrations from Discord")

        # Step 3: Restore commands back into the tree
        for cmd in cmds_snapshot:
            try:
                bot.tree.add_command(cmd)
            except app_commands.CommandAlreadyRegistered:
                pass

        # Step 4: Sync per-guild (instant update, zero duplicates)
        for g in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=g)
                synced = await bot.tree.sync(guild=g)
                print(f"[SYNC] [OK] Synced {len(synced)} commands to '{g.name}': {[c.name for c in synced]}")
            except Exception as e:
                print(f"[SYNC] Guild sync error for {g.name}: {e}")
    except Exception as e:
        print(f"[SYNC] Error during command sync: {e}")
        import traceback
        traceback.print_exc()

    try:
        if not periodic_voice_credits_check.is_running():
            periodic_voice_credits_check.start()
            print("Started periodic voice credits check background task.")
    except Exception as task_err:
        if debug_mode:
            print(f"Periodic VC task status: {task_err}")

# ----------------- Economy Activity Trackers -----------------

# Per-user chat credit cooldown: {user_id: datetime}
chat_cooldowns = {}

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
        
    now = datetime.now()
    last_awarded = chat_cooldowns.get(message.author.id)
    
    # Only award credits and 25 XP once every 60 seconds (1 minute) per user
    if last_awarded is None or (now - last_awarded).total_seconds() >= 60:
        user = database.get_user_by_discord_id(message.author.id, message.guild.id)
        if user:
            earned = database.award_daily_activity_credits(user['user_id'], config.CHAT_CREDITS_PER_MSG, 'chat')
            if earned > 0:
                chat_cooldowns[message.author.id] = now
                new_xp, new_lvl, lvl_up, reward = database.add_user_xp(user['user_id'], 25)
                if lvl_up:
                    embed = utils.create_embed(
                        title="🎉 DRIVER LEVEL UP!",
                        description=f"Congratulations {message.author.mention}! Your driver reached **Level {new_lvl}**!\n💰 **Level-Up Reward:** Received **+{reward:,} credits** into your team wallet!",
                        color=utils.COLOR_SUCCESS
                    )
                    await message.channel.send(embed=embed)
            
    await bot.process_commands(message)

# Voice tracking dict: {member_id: datetime}
voice_tracking = {}

def is_active_voice(voice_state: discord.VoiceState) -> bool:
    """Check if member is actively in a voice channel (not self/server muted or deafened)."""
    if not voice_state or not voice_state.channel:
        return False
    if voice_state.self_mute or voice_state.self_deaf or voice_state.mute or voice_state.deaf:
        return False
    return True

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
        
    was_active = is_active_voice(before)
    is_active = is_active_voice(after)
    
    if was_active and not is_active:
        if member.id in voice_tracking:
            start_time = voice_tracking.pop(member.id)
            duration = datetime.now() - start_time
            minutes = int(duration.total_seconds() // 60)
            if minutes >= 1:
                user = database.get_user_by_discord_id(member.id, member.guild.id)
                if user:
                    earned = database.award_daily_activity_credits(user['user_id'], minutes * config.VOICE_CREDITS_PER_MIN, 'voice')
                    if debug_mode and earned > 0:
                        print(f"Voice session ended for {member.name}: awarded {earned} credits for {minutes} mins.")

    elif not was_active and is_active:
        voice_tracking[member.id] = datetime.now()
        if debug_mode:
            print(f"{member.name} is now active in voice channel {after.channel.name}.")

@tasks.loop(seconds=30.0)
async def periodic_voice_credits_check():
    """Periodically award voice activity credits (15 credits per minute) to members active in VC."""
    now = datetime.now()

    # Auto-scan all voice channels to catch members who were already in VC when the bot started
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot:
                    continue
                if is_active_voice(member.voice) and member.id not in voice_tracking:
                    voice_tracking[member.id] = now
                    if debug_mode:
                        print(f"[VC AUTO-TRACK] Detected active member {member.name} in {channel.name}.")

    active_ids = list(voice_tracking.keys())
    for member_id in active_ids:
        start_time = voice_tracking.get(member_id)
        if not start_time:
            continue
        duration = now - start_time
        minutes = int(duration.total_seconds() // 60)
        if minutes >= 1:
            found_active = False
            for guild in bot.guilds:
                member = guild.get_member(member_id)
                if member and member.voice and is_active_voice(member.voice):
                    found_active = True
                    user = database.get_user_by_discord_id(member.id, guild.id)
                    if user:
                        earned = database.award_daily_activity_credits(
                            user['user_id'],
                            minutes * config.VOICE_CREDITS_PER_MIN,
                            'voice'
                        )
                        voice_tracking[member_id] = start_time + timedelta(minutes=minutes)
                        if debug_mode and earned > 0:
                            print(f"Periodic VC credit: awarded {earned} credits to {member.name} for {minutes} min(s).")
                    break
            
            if not found_active:
                voice_tracking.pop(member_id, None)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        msg = "❌ **Permission Denied!** Requires Administrator permissions or the configured Admin role."
    else:
        print(f"App command error: {error}")
        msg = f"❌ An error occurred: {str(error)}"
        
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

# ----------------- Start Bot -----------------
if __name__ == "__main__":
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        print("Error: DISCORD_TOKEN is missing or not set in environment or .env file.")
    else:
        bot.run(config.DISCORD_TOKEN)
