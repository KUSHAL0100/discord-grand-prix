import discord
from discord.ext import commands
from discord import app_commands
import io

import config
import database
import utils
import crates

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
                emoji_str = crates.RARITY_EMOJIS.get(item['rarity'], '⚪')
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
        desc = f"🧰 **GARAGE INVENTORY — {cat.upper()}**\n\n"
        if not items:
            desc += "⚙️ *No parts owned in this category yet. Unbox crates via `/open` to find rare parts!*"
        else:
            for item in items:
                status = "🟢 **[EQUIPPED]**" if item['is_equipped'] else "⚪ *(Storage)*"
                e_emoji = crates.RARITY_EMOJIS.get(item['rarity'], '⚪')
                bonus_pct = f"+{(crates.RARITY_BONUS_MULTIPLIERS.get(item['rarity'], 1.0) - 1.0)*100:.0f}%"
                desc += f"{status} {e_emoji} **{item['rarity']} {item['part_name']}** (Level {item['level']}) — Efficiency: `{bonus_pct}`\n"
                
        embed = utils.create_embed(title="🧰 Part Inventory & Equipment", description=desc, color=utils.COLOR_INFO)
        await interaction.response.edit_message(embed=embed, view=view)

class GarageCog(commands.Cog):
    """Cog containing all Garage, Profile, Upgrades and Equipment commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="start", description="Initialize your Discord Grand Prix racing team!")
    @app_commands.describe(
        team_name="Your racing team name",
        country="Optional country code or flag emoji (e.g. 🇮🇹 Italy, 🇬🇧 UK)"
    )
    @app_commands.guild_only()
    async def start(self, interaction: discord.Interaction, team_name: str, country: str = None):
        user = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if user:
            await interaction.response.send_message("❌ You already have a profile created! Use `/profile` to view your team.", ephemeral=True)
            return

        success = database.create_user(interaction.user.id, interaction.guild_id, team_name, country)
        if success:
            embed = utils.create_embed(
                title="🏎️ Welcome to Discord Grand Prix!",
                description=(
                    f"🎉 **{team_name}** has officially joined the grid!\n\n"
                    f"💰 **Starting Balance:** `{config.STARTING_MONEY:,} credits`\n"
                    f"⚙️ **Base Car Specs:** Level 1 across all components.\n"
                    f"🏎️ **Driver Rating:** Level 1 (50 Pace / 50 Quali / 50 Consistency)\n\n"
                    f"Use `/profile` to inspect your PNG profile card or `/upgrade` to research car parts!"
                ),
                color=utils.COLOR_SUCCESS
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ An error occurred creating your profile.", ephemeral=True)

    @app_commands.command(name="profile", description="View your team profile card or another driver's profile.")
    @app_commands.describe(user="Optional: View another driver's profile card")
    @app_commands.guild_only()
    async def profile_cmd(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        prof = database.get_full_team_profile(target.id, interaction.guild_id)
        if not prof:
            if target == interaction.user:
                await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {target.mention} does not have a profile yet.", ephemeral=True)
            return

        card_buf = utils.generate_profile_card(prof)
        file = discord.File(card_buf, filename="profile_card.png")
        
        overall_power = utils.calculate_overall_power(prof, prof["pace"])
        country_prefix = f"{prof['country']} " if prof.get('country') else ""
        
        # Fetch equipped inventory parts
        equipped = database.get_equipped_inventory(target.id)
        overall_rarity = utils.get_team_category(equipped)

        # Build detailed equipped parts description
        parts_list = []
        for cat_label, key in [
            ("Engine", "engine"),
            ("Aero", "aerodynamics"),
            ("Tyres", "tyres"),
            ("ERS", "ers"),
            ("Reliability", "reliability"),
            ("Pit Crew", "pit_crew")
        ]:
            lvl = prof.get(key, 1)
            item = equipped.get(key)
            if item:
                rarity = item.get('rarity', 'Common')
                name = item.get('part_name', 'Stock Block')
                parts_list.append(f"• **{cat_label}:** Lvl `{lvl}` | **{rarity}** (*{name}*)")
            else:
                parts_list.append(f"• **{cat_label}:** Lvl `{lvl}` | **Common** (*Stock*)")
        
        parts_desc = "\n".join(parts_list)

        embed = utils.create_embed(
            title=f"🏎️ {country_prefix}{prof['team_name']}",
            description=(
                f"👤 **Driver:** {target.mention}\n"
                f"⭐ **Level:** `{prof['level']}` | **XP:** `{prof['xp']:,}/{prof['level']*1000:,}`\n"
                f"💰 **Credits:** `{prof['money']:,}¢`\n"
                f"🏎️ **Overall Power:** `{overall_power:.1f}` | **Category:** `{overall_rarity}`\n"
                f"🏆 **W:** `{prof['wins']}` / **L:** `{prof['losses']}`\n\n"
                f"🏋️ **Driver Personnel**\n"
                f"💰 **Training Fee:** `{config.TRAINING_BASE_COST:,} credits` per skill level upgrade.\n"
                f"Use `/train <skill>` to train driver skill attributes!\n"
                f"> Pace `{prof['pace']}` · Quali `{prof['qual']}` · Wet `{prof['wet_skill']}`\n"
                f"> Consistency `{prof['consistency']}` · Aggression `{prof['aggression']}` · Overtaking `{prof['overtaking']}`\n\n"
                f"🔧 **Garage Components** — Use `/upgrade <part>` to upgrade\n"
                f"{parts_desc}\n\n"
                f"⚙️ **Upgrade Rules:** Spec: Lvl 1-5 | Performance: Lvl 6-10 | Advanced: Lvl 11-15 | Extreme: Lvl 16-20"
            ),
            color=utils.COLOR_INFO
        )
        embed.set_image(url="attachment://profile_card.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="team", description="Show detailed summary of a team.")
    @app_commands.describe(user="User whose team summary you want to inspect")
    @app_commands.guild_only()
    async def team_cmd(self, interaction: discord.Interaction, user: discord.User = None):
        target_user = user or interaction.user
        prof = database.get_full_team_profile(target_user.id, interaction.guild_id)
        if not prof:
            msg = "You do not have a profile. Use `/start`!" if target_user == interaction.user else f"{target_user.mention} does not have a profile."
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        card_buf = utils.generate_profile_card(prof)
        file = discord.File(card_buf, filename="profile_card.png")
        
        overall_power = utils.calculate_overall_power(prof, prof["pace"])
        country_prefix = f"{prof['country']} " if prof.get('country') else ""
        
        embed = utils.create_embed(
            title=f"🏎️ {country_prefix}{prof['team_name']}",
            description=(
                f"👤 **Owner:** {target_user.mention}\n"
                f"⭐ **Level:** `{prof['level']}` | **XP:** `{prof['xp']:,}`\n"
                f"💰 **Money:** `{prof['money']:,} credits`\n"
                f"🏎️ **Overall Car Rating:** `{overall_power:.1f}`\n"
                f"🏆 **Wins:** `{prof['wins']}` | **Losses:** `{prof['losses']}`"
            ),
            color=utils.COLOR_INFO
        )
        embed.set_image(url="attachment://profile_card.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="garage", description="View your current car component levels and damage.")
    @app_commands.guild_only()
    async def garage_cmd(self, interaction: discord.Interaction):
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            return

        overall_power = utils.calculate_overall_power(prof, prof["pace"])
        engine_bar = utils.make_progress_bar(prof['damage_engine'])
        tyres_bar = utils.make_progress_bar(prof['damage_tyres'])
        total_bar = utils.make_progress_bar(prof['damage_total'])

        desc = (
            f"🏎️ **Overall Power Rating:** `{overall_power:.1f}`\n\n"
            f"⚙️ **Component Levels:**\n"
            f"  • **Engine:** Level `{prof['engine']}`/{config.MAX_STAT_LEVEL}\n"
            f"  • **Aerodynamics:** Level `{prof['aerodynamics']}`/{config.MAX_STAT_LEVEL}\n"
            f"  • **Tyres:** Level `{prof['tyres']}`/{config.MAX_STAT_LEVEL}\n"
            f"  • **ERS System:** Level `{prof['ers']}`/{config.MAX_STAT_LEVEL}\n"
            f"  • **Reliability:** Level `{prof['reliability']}`/{config.MAX_STAT_LEVEL}\n"
            f"  • **Pit Crew:** Level `{prof['pit_crew']}`/{config.MAX_STAT_LEVEL}\n\n"
            f"🔧 **Component Wear & Damage:**\n"
            f"  • Engine Wear: {engine_bar} ({prof['damage_engine']:.1f}%)\n"
            f"  • Tyre Wear: {tyres_bar} ({prof['damage_tyres']:.1f}%)\n"
            f"  • Overall Damage: {total_bar} ({prof['damage_total']:.1f}%)\n\n"
            f"*Use `/upgrade` to research parts or `/repairs` to service your car!*"
        )
        embed = utils.create_embed(title="🛠️ Team Garage", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="upgradeshop", description="Browse available car component upgrade levels and costs.")
    @app_commands.guild_only()
    async def upgrade_shop_cmd(self, interaction: discord.Interaction):
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return
            
        desc = "**Current Part Levels and Upgrade Costs:**\n\n"
        for part, mult in config.PART_MULTIPLIERS.items():
            curr_level = prof.get(part, 1)
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

    @app_commands.command(name="upgrade", description="Upgrade a car part to boost its power.")
    @app_commands.describe(part="The car component to upgrade (engine, aerodynamics, tyres, ers, reliability, pit_crew)")
    @app_commands.choices(part=[
        app_commands.Choice(name="Engine", value="engine"),
        app_commands.Choice(name="Aerodynamics", value="aerodynamics"),
        app_commands.Choice(name="Tyres", value="tyres"),
        app_commands.Choice(name="ERS System", value="ers"),
        app_commands.Choice(name="Reliability", value="reliability"),
        app_commands.Choice(name="Pit Crew", value="pit_crew"),
    ])
    @app_commands.guild_only()
    async def upgrade_part_cmd(self, interaction: discord.Interaction, part: app_commands.Choice[str]):
        part_name = part.value
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return

        curr_level = prof.get(part_name, 1)
        if curr_level >= config.MAX_STAT_LEVEL:
            await interaction.response.send_message(f"❌ Your **{part_name.capitalize()}** is already at maximum level ({config.MAX_STAT_LEVEL})!", ephemeral=True)
            return

        next_level = curr_level + 1
        cost = config.get_upgrade_cost(part_name, next_level)
        if prof['money'] < cost:
            await interaction.response.send_message(
                f"❌ Insufficient funds! Upgrading **{part_name.capitalize()}** to Level {next_level} costs **{cost:,} credits**, but you have **{prof['money']:,} credits**.",
                ephemeral=True
            )
            return

        success, msg = database.upgrade_garage_part(prof['user_id'], part_name, cost)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🛠️ Part Upgrade", description=msg, color=color))

    @app_commands.command(name="inventory", description="View stored car parts and equip preferred setups.")
    @app_commands.guild_only()
    async def view_inventory(self, interaction: discord.Interaction):
        prof = database.get_user_by_discord_id(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return
            
        view = discord.ui.View(timeout=180.0)
        view.add_item(InventoryCategorySelect(prof['user_id']))
        view.add_item(InventorySelectMenu(prof['user_id'], "engine"))
        
        items = database.get_user_inventory(prof['user_id'], "engine")
        desc = "🧰 **GARAGE INVENTORY — ENGINE**\n\n"
        if not items:
            desc += "⚙️ *No custom parts in inventory yet. Upgrade your car via `/upgrade` or unbox crates via `/open`!*"
        else:
            for item in items:
                status = "🟢 **[EQUIPPED]**" if item['is_equipped'] else "⚪ *(Storage)*"
                e_emoji = crates.RARITY_EMOJIS.get(item['rarity'], '⚪')
                bonus_pct = f"+{(crates.RARITY_BONUS_MULTIPLIERS.get(item['rarity'], 1.0) - 1.0)*100:.0f}%"
                desc += f"{status} {e_emoji} **{item['rarity']} {item['part_name']}** (Level {item['level']}) — Efficiency: `{bonus_pct}`\n"
                
        embed = utils.create_embed(title="🧰 Part Inventory & Equipment", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="repairs", description="View damaged components and repair costs.")
    @app_commands.guild_only()
    async def repairs_cmd(self, interaction: discord.Interaction):
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return

        cost_engine = int(prof['damage_engine'] * config.REPAIR_COST_PER_PCT)
        cost_tyres = int(prof['damage_tyres'] * config.REPAIR_COST_PER_PCT)
        cost_total = cost_engine + cost_tyres

        desc = (
            f"🔧 **Repair Assessment & Costs:**\n\n"
            f"  • **Engine Damage:** `{prof['damage_engine']:.1f}%` (Cost: `{cost_engine:,}¢`)\n"
            f"  • **Tyre Wear:** `{prof['damage_tyres']:.1f}%` (Cost: `{cost_tyres:,}¢`)\n\n"
            f"💰 **Total Overhaul Cost:** `{cost_total:,} credits`\n"
            f"💳 **Your Balance:** `{prof['money']:,} credits`\n\n"
            f"*Use `/repair component:<engine/tyres/full>` to service your car!*"
        )
        embed = utils.create_embed(title="🔧 Pit Crew Repair Shop", description=desc, color=utils.COLOR_INFO)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="repair", description="Pay credits to repair a damaged component.")
    @app_commands.describe(component="Component to repair (engine, tyres, or full overhaul)")
    @app_commands.choices(component=[
        app_commands.Choice(name="Engine", value="engine"),
        app_commands.Choice(name="Tyres", value="tyres"),
        app_commands.Choice(name="Full Overhaul (Both)", value="full"),
    ])
    @app_commands.guild_only()
    async def repair_cmd(self, interaction: discord.Interaction, component: app_commands.Choice[str]):
        comp = component.value
        prof = database.get_full_team_profile(interaction.user.id, interaction.guild_id)
        if not prof:
            await interaction.response.send_message("❌ You do not have a profile. Use `/start`.", ephemeral=True)
            return

        if comp == "engine":
            damage_pct = prof['damage_engine']
        elif comp == "tyres":
            damage_pct = prof['damage_tyres']
        else:
            damage_pct = prof['damage_total']

        if damage_pct <= 0:
            await interaction.response.send_message(f"❌ Your car's **{comp.capitalize()}** has no damage to repair!", ephemeral=True)
            return

        cost = int(damage_pct * config.REPAIR_COST_PER_PCT)
        if prof['money'] < cost:
            await interaction.response.send_message(
                f"❌ Insufficient funds! Repairing **{comp.capitalize()}** costs **{cost:,} credits**, but you have **{prof['money']:,} credits**.",
                ephemeral=True
            )
            return

        success, msg = database.repair_user_car(prof['user_id'], comp, cost)
        color = utils.COLOR_SUCCESS if success else utils.COLOR_ERROR
        await interaction.response.send_message(embed=utils.create_embed(title="🔧 Car Repair", description=msg, color=color))

async def setup(bot: commands.Bot):
    await bot.add_cog(GarageCog(bot))
