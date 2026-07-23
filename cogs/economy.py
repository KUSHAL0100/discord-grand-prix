import discord
from discord.ext import commands
from discord import app_commands

import config
import database
import utils
import crates

class EconomyCog(commands.Cog):
    """Cog containing all Economy, Loot Crates, Personnel Training and Shop commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Claim your daily credit login bonus (500 credits).")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction):
        user = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if not user:
            await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            return

        success, msg = database.claim_daily_bonus(user['user_id'])
        color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
        await interaction.response.send_message(embed=utils.create_embed(title="🎁 Daily Reward", description=msg, color=color))

    @app_commands.command(name="work", description="Perform a daily odd-job for your racing team to earn credits.")
    @app_commands.guild_only()
    async def work(self, interaction: discord.Interaction):
        user = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if not user:
            await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            return

        success, msg = database.claim_work_rewards(user['user_id'])
        color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
        await interaction.response.send_message(embed=utils.create_embed(title="💼 Team Work", description=msg, color=color))

    @app_commands.command(name="crate", description="View available loot crates, unboxing drop chances, and credit rewards.")
    @app_commands.guild_only()
    async def view_crates(self, interaction: discord.Interaction):
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

    @app_commands.command(name="open", description="Unbox a Rookie, Pro, or Champion Loot Crate.")
    @app_commands.describe(crate_tier="Select crate tier to unbox (rookie, pro, champion)")
    @app_commands.choices(crate_tier=[
        app_commands.Choice(name="📦 Rookie Crate (500¢)", value="rookie"),
        app_commands.Choice(name="💼 Pro Crate (2,500¢)", value="pro"),
        app_commands.Choice(name="🏆 Champion Crate (6,000¢)", value="champion")
    ])
    @app_commands.guild_only()
    async def open_crate_cmd(self, interaction: discord.Interaction, crate_tier: app_commands.Choice[str]):
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

    @app_commands.command(name="shop", description="View consumable race & qualifying boosters (Max 2 boosters cap).")
    @app_commands.guild_only()
    async def shop_boosters(self, interaction: discord.Interaction):
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

    @app_commands.command(name="booster", description="Purchase a consumable booster from the shop.")
    @app_commands.describe(item="Select booster to purchase")
    @app_commands.choices(item=[
        app_commands.Choice(name="🔥 Tyre Blanket Warmer (1,500¢)", value="tyre_warmer"),
        app_commands.Choice(name="⚡ ERS High-Flow Injector (2,000¢)", value="ers_injector"),
        app_commands.Choice(name="🛡️ Heavy Duty Radiator (1,200¢)", value="radiator")
    ])
    @app_commands.guild_only()
    async def buy_booster_cmd(self, interaction: discord.Interaction, item: app_commands.Choice[str]):
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

    @app_commands.command(name="train", description="Spend credits to train a selected Driver skill.")
    @app_commands.describe(skill="The driver skill attribute to train")
    @app_commands.choices(skill=[
        app_commands.Choice(name="Pace (Race speed & lap times)", value="pace"),
        app_commands.Choice(name="Quali (One-lap qualifying speed)", value="qual"),
        app_commands.Choice(name="Wet Skill (Wet weather speed)", value="wet_skill"),
        app_commands.Choice(name="Consistency (Fewer mistakes/lockups)", value="consistency"),
        app_commands.Choice(name="Aggression (Overtaking attempt frequency)", value="aggression"),
        app_commands.Choice(name="Overtaking (Defense & attack success)", value="overtaking"),
    ])
    @app_commands.guild_only()
    async def train(self, interaction: discord.Interaction, skill: app_commands.Choice[str]):
        skill_name = skill.value
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            return

        curr_level = prof.get(skill_name, 50)
        if curr_level >= config.MAX_DRIVER_STAT_LEVEL:
            await interaction.response.send_message(f"❌ Your driver's **{skill_name.capitalize()}** is already at maximum level ({config.MAX_DRIVER_STAT_LEVEL})!", ephemeral=True)
            return

        cost = config.TRAINING_BASE_COST
        if prof['money'] < cost:
            await interaction.response.send_message(
                f"❌ Insufficient funds! Driver training costs **{cost:,} credits**, but you have **{prof['money']:,} credits**.",
                ephemeral=True
            )
            return

        success, msg = database.train_personnel_stat(prof['user_id'], skill_name, cost)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🏎️ Driver Training", description=msg, color=color))

    @app_commands.command(name="personnel", description="View driver skill ratings and training options.")
    @app_commands.guild_only()
    async def personnel_cmd(self, interaction: discord.Interaction):
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return

        desc = (
            f"🏎️ **Driver Ratings & Skill Attributes:**\n\n"
            f"  • **Pace:** Level `{prof['pace']}`/{config.MAX_DRIVER_STAT_LEVEL}\n"
            f"  • **Quali:** Level `{prof['qual']}`/{config.MAX_DRIVER_STAT_LEVEL}\n"
            f"  • **Wet Skill:** Level `{prof['wet_skill']}`/{config.MAX_DRIVER_STAT_LEVEL}\n"
            f"  • **Consistency:** Level `{prof['consistency']}`/{config.MAX_DRIVER_STAT_LEVEL}\n"
            f"  • **Aggression:** Level `{prof['aggression']}`/{config.MAX_DRIVER_STAT_LEVEL}\n"
            f"  • **Overtaking:** Level `{prof['overtaking']}`/{config.MAX_DRIVER_STAT_LEVEL}\n\n"
            f"💰 **Training Fee:** `{config.TRAINING_BASE_COST:,} credits` per skill level upgrade.\n"
            f"*Use `/train <skill>` to train driver skill attributes!*"
        )
        embed = utils.create_embed(title="🏋️ Driver Personnel Training", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View top racing teams in the server.")
    @app_commands.describe(sort_by="Sort leaderboard by money, level, wins, or points")
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="Championship Points", value="points"),
        app_commands.Choice(name="Total Wins", value="wins"),
        app_commands.Choice(name="Team Money", value="money"),
        app_commands.Choice(name="Driver Level", value="level"),
    ])
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction, sort_by: app_commands.Choice[str] = None):
        criterion = sort_by.value if sort_by else "points"
        results = database.get_leaderboard(interaction.guild_id, criterion)
        
        if not results:
            await interaction.response.send_message("❌ No driver profiles created on this server yet.", ephemeral=True)
            return

        title_map = {
            "points": "🏆 WDC Points Leaderboard",
            "wins": "🏁 Total Wins Leaderboard",
            "money": "💰 Team Wealth Leaderboard",
            "level": "⭐ Driver Level Leaderboard"
        }
        
        desc = ""
        for idx, row in enumerate(results):
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"**{idx + 1}.**"))
            score_val = row['score']
            unit = "pts" if criterion == "points" else ("wins" if criterion == "wins" else ("credits" if criterion == "money" else "Level"))
            if criterion == "money":
                score_str = f"{score_val:,} {unit}"
            else:
                score_str = f"{score_val} {unit}"
                
            desc += f"{medal} **{row['team_name']}** — {score_str}\n"

        embed = utils.create_embed(title=title_map[criterion], description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bet", description="Challenge another user to a race with a credit wager!")
    @app_commands.describe(opponent="The user to wager against", amount="Credit wager amount")
    @app_commands.guild_only()
    async def bet(self, interaction: discord.Interaction, opponent: discord.User, amount: int):
        from cogs.racing import RaceChallengeView
        if opponent.bot or opponent == interaction.user:
            await interaction.response.send_message("❌ Invalid opponent.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Wager amount must be positive.", ephemeral=True)
            return

        p1 = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        p2 = database.get_user_by_discord_id(opponent.id, interaction.guild_id)

        if not p1 or not p2:
            await interaction.response.send_message("❌ Both users must have created profiles using `/start`.", ephemeral=True)
            return

        if p1['money'] < amount:
            await interaction.response.send_message(f"❌ You do not have `{amount:,} credits` to wager.", ephemeral=True)
            return

        if p2['money'] < amount:
            await interaction.response.send_message(f"❌ {opponent.mention} does not have `{amount:,} credits` to wager.", ephemeral=True)
            return

        view = RaceChallengeView(p1, p2, interaction.guild_id, wager=amount)
        embed = utils.create_embed(
            title="🏁 High-Stakes Wager Race Challenge!",
            description=(
                f"{interaction.user.mention} (**{p1['team_name']}**) has challenged {opponent.mention} (**{p2['team_name']}**) to a 1v1 Race Duel!\n\n"
                f"💰 **Wager Amount:** `{amount:,} credits`\n"
                f"Winner takes **{amount * 2:,} credits**!"
            ),
            color=utils.COLOR_WARNING
        )
        await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
