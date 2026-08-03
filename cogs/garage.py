import discord
from discord.ext import commands
from discord import app_commands
import io

import config
import database
import utils
import crates

def create_inventory_embed_and_view(user_id: int, discord_id: int, category: str = "engine", notice: str = None):
    try:
        # Fetch equipped inventory and garage component levels across all categories
        equipped = database.get_equipped_inventory(user_id)
        garage_levels = database.get_user_garage_levels(user_id)
        
        cat_icons = {
            "engine": "🏎️",
            "aerodynamics": "🪽",
            "tyres": "🛞",
            "ers": "⚡",
            "reliability": "🛡️",
            "pit_crew": "🔧"
        }
        
        # Active Car Loadout Summary Box
        loadout_lines = []
        for c_key in ["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"]:
            c_title = c_key.replace("_", " ").title()
            icon = cat_icons.get(c_key, "⚙️")
            g_lvl = garage_levels.get(c_key, 1)
            item = equipped.get(c_key)
            if item:
                rarity = item.get('rarity', 'Common')
                r_emoji = crates.RARITY_EMOJIS.get(rarity, '⚪')
                part_name = item.get('part_name', 'Custom Part')
                item_lvl = item.get('level', 1)
                bonus = item.get('stat_bonus', 0)
                loadout_lines.append(f"{icon} **{c_title}:** {r_emoji} **{rarity} {part_name}** (Level `{item_lvl}` | +`{bonus}` Stat)")
            else:
                loadout_lines.append(f"{icon} **{c_title}:** ⚪ **Stock Baseline** (Level `{g_lvl}`)")

                
        loadout_text = "🔧 **ACTIVE CAR LOADOUT & COMPONENT LEVELS**\n" + "\n".join(loadout_lines)
        
        # Storage items in active category
        items = database.get_user_inventory(user_id, category)
        cat_title = category.replace("_", " ").upper()
        cat_icon = cat_icons.get(category, "🧰")
        
        storage_lines = []
        if not items:
            storage_lines.append("⚙️ *No custom parts in storage for this category yet. Upgrade your car via `/upgrade` or unbox crates via `/open`!*")
        else:
            for item in items:
                status = "🟢 **[EQUIPPED]**" if item.get('is_equipped') else "⚪ *(Storage)*"
                rarity = item.get('rarity', 'Common')
                e_emoji = crates.RARITY_EMOJIS.get(rarity, '⚪')
                mult = crates.RARITY_BONUS_MULTIPLIERS.get(rarity, 1.0)
                bonus_pct = f"+{(mult - 1.0)*100:.0f}%"
                part_name = item.get('part_name', 'Custom Part')
                item_lvl = item.get('level', 1)
                bonus = item.get('stat_bonus', 0)
                storage_lines.append(f"{status} {e_emoji} **{rarity} {part_name}** (Level `{item_lvl}`) — Bonus: `+{bonus}` Stat (`{bonus_pct}`) ")
                
        notice_str = f"{notice}\n\n" if notice else ""
        
        desc = (
            f"{notice_str}"
            f"{loadout_text}\n\n"
            f"─────────────────────────────\n"
            f"{cat_icon} **CATEGORY STORAGE — {cat_title}**\n\n"
            + "\n".join(storage_lines)
        )
        
        embed = utils.create_embed(title="🧰 Part Inventory & Equipment Hub", description=desc, color=utils.COLOR_INFO)
        view = InventoryView(user_id, discord_id, active_category=category)
        return embed, view

    except Exception as e:
        import traceback
        traceback.print_exc()
        embed = utils.create_embed(title="🧰 Part Inventory Hub", description=f"⚠️ Error displaying inventory: `{e}`", color=utils.COLOR_ERROR)
        view = InventoryView(user_id, discord_id, active_category=category)
        return embed, view

class CategoryTabButton(discord.ui.Button):
    def __init__(self, label: str, category: str, active_category: str, row: int):
        is_active = (category == active_category)
        style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, row=row)
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            if self.view.discord_id and interaction.user.id != self.view.discord_id:
                await interaction.followup.send("❌ You can only navigate your own inventory menu.", ephemeral=True)
                return
            embed, view = create_inventory_embed_and_view(self.view.user_id, self.view.discord_id, self.category)
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Interaction error: `{e}`", ephemeral=True)
            except Exception:
                pass

class InventorySelectMenu(discord.ui.Select):
    def __init__(self, user_id: int, discord_id: int, category: str):
        self.user_id = user_id
        self.discord_id = discord_id
        self.category = category
        items = database.get_user_inventory(user_id, category)
        
        # Determine equipped status first to guarantee EXACTLY 1 default option
        equipped_item_id = None
        if items:
            for item in items:
                if item.get('is_equipped'):
                    equipped_item_id = item['item_id']
                    break
                    
        options = [
            discord.SelectOption(
                label="⚪ Stock / Unequip Custom Part",
                value="unequip",
                description="Revert to baseline stock component",
                default=(equipped_item_id is None)
            )
        ]
        
        if items:
            for item in items[:24]:
                is_eq = (item['item_id'] == equipped_item_id)
                status = "🟢 [Equipped]" if is_eq else "⚪ [Storage]"
                rarity = item.get('rarity', 'Common')
                emoji_str = crates.RARITY_EMOJIS.get(rarity, '⚪')
                label = f"{emoji_str} {item.get('part_name', 'Part')[:25]} (Lvl {item.get('level', 1)})"
                desc = f"{status} {rarity} | +{item.get('stat_bonus', 0)} Stat"
                options.append(discord.SelectOption(
                    label=label,
                    value=str(item['item_id']),
                    description=desc,
                    default=is_eq
                ))
                
        super().__init__(placeholder=f"Equip a {category.upper()} part...", min_values=1, max_values=1, options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            if self.discord_id and interaction.user.id != self.discord_id:
                await interaction.followup.send("❌ You can only equip parts in your own inventory view.", ephemeral=True)
                return
                
            val = self.values[0]
            if val == "unequip":
                success, msg = database.unequip_inventory_part_category(self.user_id, self.category)
            else:
                item_id = int(val)
                success, msg = database.equip_inventory_part(self.user_id, item_id)
                
            embed, view = create_inventory_embed_and_view(self.user_id, self.discord_id, self.category, notice=msg)
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Interaction error: `{e}`", ephemeral=True)
            except Exception:
                pass

class InventoryView(discord.ui.View):
    def __init__(self, user_id: int, discord_id: int, active_category: str = "engine"):
        super().__init__(timeout=180.0)
        self.user_id = user_id
        self.discord_id = discord_id
        self.active_category = active_category
        
        # Row 0: Top 3 Category Tabs
        self.add_item(CategoryTabButton("🏎️ Engine", "engine", active_category, row=0))
        self.add_item(CategoryTabButton("🪽 Aero", "aerodynamics", active_category, row=0))
        self.add_item(CategoryTabButton("🛞 Tyres", "tyres", active_category, row=0))
        
        # Row 1: Bottom 3 Category Tabs
        self.add_item(CategoryTabButton("⚡ ERS", "ers", active_category, row=1))
        self.add_item(CategoryTabButton("🛡️ Reliability", "reliability", active_category, row=1))
        self.add_item(CategoryTabButton("🔧 Pit Crew", "pit_crew", active_category, row=1))
        
        # Row 2: Part Dropdown Select for Active Category
        self.add_item(InventorySelectMenu(user_id, discord_id, category=active_category))

    @discord.ui.button(label="⚡ Auto-Equip Best Parts", style=discord.ButtonStyle.success, row=3)
    async def auto_equip_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            if self.discord_id and interaction.user.id != self.discord_id:
                await interaction.followup.send("❌ You can only use actions on your own inventory.", ephemeral=True)
                return
                
            success, msg, count = database.auto_equip_best_parts(self.user_id)
            embed, view = create_inventory_embed_and_view(self.user_id, self.discord_id, self.active_category, notice=msg)
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Interaction error: `{e}`", ephemeral=True)
            except Exception:
                pass






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

        success, msg = database.create_user(interaction.user.id, interaction.guild_id, team_name, country)
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
            await interaction.response.send_message(msg if msg else "❌ An error occurred creating your profile.", ephemeral=True)

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
        equipped = database.get_equipped_inventory(prof['user_id'])
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
                f"{parts_desc}"
            ),
            color=utils.COLOR_INFO
        )
        embed.set_image(url="attachment://profile_card.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    @app_commands.command(name="balance", description="View your credit balance or another driver's balance.")
    @app_commands.describe(user="Optional: View another driver's credit balance")
    @app_commands.guild_only()
    async def balance_cmd(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        prof = database.get_full_team_profile(target.id, interaction.guild_id)
        if not prof:
            if target == interaction.user:
                await interaction.response.send_message("❌ You do not have a profile yet. Use `/start` to create one!", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {target.mention} does not have a profile yet.", ephemeral=True)
            return

        embed = utils.create_embed(
            title="💰 Driver Wallet Balance",
            description=(
                f"👤 **Driver:** {target.mention}\n"
                f"🏎️ **Team:** **{prof['team_name']}**\n"
                f"💰 **Current Balance:** `{prof['money']:,} credits`"
            ),
            color=utils.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
            
        equipped = database.get_equipped_inventory(prof['user_id'])
        desc = "**Current Part Levels and Upgrade Costs:**\n\n"
        for part, mult in config.PART_MULTIPLIERS.items():
            curr_level = prof.get(part, 1)
            eq_item = equipped.get(part)
            rarity = eq_item.get('rarity', 'Common') if eq_item else 'Common'
            r_emoji = crates.RARITY_EMOJIS.get(rarity, '⚪')
            
            if curr_level >= config.MAX_STAT_LEVEL:
                cost_str = "MAX LEVEL"
            else:
                cost = config.get_upgrade_cost(part, curr_level + 1, rarity)
                cost_str = f"{cost:,}¢"
                
            desc += f"• **{part.capitalize()}:** Level {curr_level} → Level {curr_level + 1 if curr_level < config.MAX_STAT_LEVEL else config.MAX_STAT_LEVEL} ({r_emoji} {rarity} | Cost: {cost_str})\n"
            
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

        equipped = database.get_equipped_inventory(prof['user_id'])
        eq_item = equipped.get(part_name)
        rarity = eq_item.get('rarity', 'Common') if eq_item else 'Common'
        r_emoji = crates.RARITY_EMOJIS.get(rarity, '⚪')

        next_level = curr_level + 1
        cost = config.get_upgrade_cost(part_name, next_level, rarity)
        if prof['money'] < cost:
            await interaction.response.send_message(
                f"❌ Insufficient funds! Upgrading your {r_emoji} **{rarity} {part_name.capitalize()}** to Level {next_level} costs **{cost:,} credits**, but you have **{prof['money']:,} credits**.",
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
            
        embed, view = create_inventory_embed_and_view(prof['user_id'], interaction.user.id, "engine")
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
