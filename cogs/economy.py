import discord
from discord.ext import commands
from discord import app_commands

import config
import database
import utils
import crates

class LeaderboardView(discord.ui.View):
    def __init__(self, user_id: int, results: list, criterion: str, title: str, top_10_only: bool = False):
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.results = results
        self.criterion = criterion
        self.title = title
        self.top_10_only = top_10_only
        self.page_size = 10
        self.current_page = 0
        self.update_buttons()

    @property
    def display_results(self):
        if self.top_10_only:
            return self.results[:10]
        return self.results

    @property
    def total_pages(self):
        total = len(self.display_results)
        return max(1, (total + self.page_size - 1) // self.page_size)

    def get_embed(self) -> discord.Embed:
        display = self.display_results
        total_items = len(display)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total_items)
        page_items = display[start_idx:end_idx]

        filter_status = " *(Top 10 Only)*" if self.top_10_only else ""
        desc = f"📊 **Total Server Teams:** `{len(self.results)}`{filter_status}\n\n"

        for idx_offset, row in enumerate(page_items):
            global_rank = start_idx + idx_offset + 1
            medal = "🥇" if global_rank == 1 else ("🥈" if global_rank == 2 else ("🥉" if global_rank == 3 else f"**{global_rank}.**"))
            score_val = row['score']
            unit = "pts" if self.criterion == "points" else ("wins" if self.criterion == "wins" else ("credits" if self.criterion == "money" else "Level"))
            if self.criterion == "money":
                score_str = f"{score_val:,} {unit}"
            else:
                score_str = f"{score_val} {unit}"
            desc += f"{medal} **{row['team_name']}** — {score_str}\n"

        embed = utils.create_embed(title=self.title, description=desc, color=utils.COLOR_INFO)
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages} • Total Entries: {total_items}")
        return embed

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
        self.toggle_top10_button.label = "📋 Show All Teams" if self.top_10_only else "🔝 Top 10 Only"

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.primary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the person who ran `/leaderboard` can use these page controls.", ephemeral=True)
            return
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.primary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the person who ran `/leaderboard` can use these page controls.", ephemeral=True)
            return
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

    @discord.ui.button(label="🔝 Top 10 Only", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_top10_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the person who ran `/leaderboard` can use these page controls.", ephemeral=True)
            return
        await interaction.response.defer()
        self.top_10_only = not self.top_10_only
        self.current_page = 0
        self.update_buttons()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)


class EconomyCog(commands.Cog):
    """Cog containing all Economy, Loot Crates, Personnel Training, Shop and Leaderboard commands."""
    
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

    @app_commands.command(name="weekly", description="Claim your weekly credit login bonus (3,000 credits).")
    @app_commands.guild_only()
    async def weekly(self, interaction: discord.Interaction):
        user = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if not user:
            await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            return

        success, msg = database.claim_weekly_bonus(user['user_id'])
        color = utils.COLOR_SUCCESS if success else utils.COLOR_WARNING
        await interaction.response.send_message(embed=utils.create_embed(title="🎁 Weekly Reward", description=msg, color=color))


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
            "  • **Guaranteed Gold:** `25¢ – 125¢` refund (Max 25% return)\n"
            "  • **Part Drop Chance:** `60%` (⚪ Common 70% | 🟢 Uncommon 25% | 🔵 Rare 5%)\n"
            "  • **Bad Luck Protection:** 3 openings without Uncommon+ guarantees **100% Drop & Uncommon+ part** on your 4th crate!\n"
            "  • Command: `/open crate_tier:rookie`\n\n"
            "💼 **Pro Crate — 2,500¢**\n"
            "  • **Guaranteed Gold:** `125¢ – 625¢` refund (Max 25% return)\n"
            "  • **Part Drop Chance:** `85%` (🟢 Uncommon 40% | 🔵 Rare 45% | 🟣 Epic 12% | 🟡 Legendary 3%)\n"
            "  • **Bad Luck Protection:** 3 openings without Rare+ guarantees **100% Drop & Rare+ part** on your 4th crate!\n"
            "  • Command: `/open crate_tier:pro`\n\n"
            "🏆 **Champion Crate — 6,000¢**\n"
            "  • **Guaranteed Gold:** `300¢ – 1,500¢` refund (Max 25% return)\n"
            "  • **Part Drop Chance:** `100% Guaranteed` (🔵 Rare 35% | 🟣 Epic 50% | 🟡 Legendary 15%)\n"
            "  • **Bad Luck Protection:** 3 openings without Epic+ guarantees **100% Drop & Epic+ part** on your 4th crate!\n"
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
        pity_triggered = summary.get("pity_triggered", False)
        pity_counter = summary.get("pity_counter", 0)
        
        if pity_triggered:
            pity_info = "\n🛡️ **BAD LUCK PROTECTION ACTIVATED!** Guaranteed higher tier drop!"
        else:
            pity_info = f"\n🛡️ **Pity Counter:** `{pity_counter}/3`"
            
        part_desc = (
            f"\n\n✨ **NEW CAR PART UNBOXED!**\n"
            f"{part['emoji']} **{part['rarity']} {part['part_name']}**\n"
            f"⚙️ **Category:** `{part['category'].upper()}` | **Level:** `{part['level']}`\n"
            f"⚡ **Efficiency Bonus:** `{part['efficiency_bonus']}` tuning boost!\n"
            f"*Equip it in `/inventory` to install it onto your car!*"
        ) if part else ""
            
        desc = (
            f"🎉 **{summary['crate_name']} Unboxed!**\n\n"
            f"💰 **Gold Returned:** `+{summary['gold_reward']:,}¢`\n"
            f"📊 **Net Cost:** `{summary['net_cost']:,}¢`"
            f"{pity_info}{part_desc}"
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

    @app_commands.command(name="leaderboard", description="View top racing teams in the server with pagination.")
    @app_commands.describe(
        sort_by="Sort leaderboard by money, level, wins, or points",
        top_10_only="Optional: Show only the top 10 teams"
    )
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="Championship Points", value="points"),
        app_commands.Choice(name="Total Wins", value="wins"),
        app_commands.Choice(name="Team Money", value="money"),
        app_commands.Choice(name="Driver Level", value="level"),
    ])
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction, sort_by: app_commands.Choice[str] = None, top_10_only: bool = False):
        criterion = sort_by.value if sort_by else "points"
        results = database.get_leaderboard(interaction.guild_id, criterion, limit=None)
        
        if not results:
            await interaction.response.send_message("❌ No driver profiles created on this server yet.", ephemeral=True)
            return

        title_map = {
            "points": "🏆 WDC Points Leaderboard",
            "wins": "🏁 Total Wins Leaderboard",
            "money": "💰 Team Wealth Leaderboard",
            "level": "⭐ Driver Level Leaderboard"
        }
        
        view = LeaderboardView(interaction.user.id, results, criterion, title_map[criterion], top_10_only=top_10_only)
        await interaction.response.send_message(embed=view.get_embed(), view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
