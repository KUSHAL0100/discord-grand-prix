import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from datetime import datetime

import config
import database
import utils

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

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

# ----------------- Event Handlers -----------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Initializing database schema and performance indexes...")
    database.init_db()
    
    try:
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to test guild {config.GUILD_ID}.")
        else:
            for g in bot.guilds:
                try:
                    bot.tree.copy_global_to(guild=g)
                    synced = await bot.tree.sync(guild=g)
                    print(f"Synced {len(synced)} commands to guild: {g.name} ({g.id})")
                except Exception as guild_err:
                    print(f"Guild sync notice for {g.id}: {guild_err}")
    except Exception as sync_err:
        print(f"Command sync notice: {sync_err}")

    try:
        if not periodic_voice_credits_check.is_running():
            periodic_voice_credits_check.start()
            print("Started periodic voice credits check background task.")
    except Exception as task_err:
        if debug_mode:
            print(f"Periodic VC task status: {task_err}")

# ----------------- Economy Activity Trackers -----------------

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
        
    user = database.get_user_by_discord_id(message.author.id, message.guild.id)
    if user:
        earned = database.award_daily_activity_credits(user['user_id'], config.CHAT_CREDITS_PER_MSG, 'chat')
        if debug_mode and earned > 0:
            print(f"Awarded {earned} chat credits to {message.author.name}.")
            
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
            minutes = duration.total_seconds() / 60.0
            if minutes >= 1.0:
                user = database.get_user_by_discord_id(member.id, member.guild.id)
                if user:
                    earned = database.award_daily_activity_credits(user['user_id'], int(minutes) * config.VOICE_CREDITS_PER_MIN, 'voice')
                    if debug_mode and earned > 0:
                        print(f"Voice session ended for {member.name}: awarded {earned} credits for {int(minutes)} mins.")

    elif not was_active and is_active:
        voice_tracking[member.id] = datetime.now()
        if debug_mode:
            print(f"{member.name} is now active in voice channel {after.channel.name}.")

@tasks.loop(minutes=5.0)
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

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ **Permission Denied!** Requires Administrator permissions or the configured Admin role.", ephemeral=True)
    else:
        print(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)

# ----------------- Start Bot -----------------
if __name__ == "__main__":
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        print("Error: DISCORD_TOKEN is missing or not set in environment or .env file.")
    else:
        bot.run(config.DISCORD_TOKEN)
