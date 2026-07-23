import random
from typing import Dict, Any, Tuple
import database

# Rarity Base Level Offsets (Higher rarity parts carry authentic base power boosts so Level 1 Rare beats Level 3 Common)
RARITY_BASE_OFFSETS = {
    "Common": 0,        # Base level (+0)
    "Uncommon": 3,      # Level 1 Uncommon acts as Level 4 (+3 base levels)
    "Rare": 6,          # Level 1 Rare acts as Level 7 (+6 base levels)
    "Epic": 10,         # Level 1 Epic acts as Level 11 (+10 base levels)
    "Legendary": 15     # Level 1 Legendary acts as Level 16 (+15 base levels)
}

# Legacy efficiency multipliers mapping
RARITY_BONUS_MULTIPLIERS = {
    "Common": 1.00,
    "Uncommon": 1.05,
    "Rare": 1.12,
    "Epic": 1.22,
    "Legendary": 1.35
}

# Rarity Emojis
RARITY_EMOJIS = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡"
}

# Crate Definitions
CRATE_CONFIGS = {
    "rookie": {
        "name": "📦 Rookie Crate",
        "price": 500,
        "gold_min": 25,
        "gold_max": 125,  # 25% max return
        "part_chance": 0.60, # 60% chance to drop part
        "rarities": ["Common", "Uncommon", "Rare"],
        "weights": [70, 25, 5]
    },
    "pro": {
        "name": "💼 Pro Crate",
        "price": 2500,
        "gold_min": 125,
        "gold_max": 625,  # 25% max return
        "part_chance": 0.85, # 85% chance to drop part
        "rarities": ["Uncommon", "Rare", "Epic", "Legendary"],
        "weights": [40, 45, 12, 3]
    },
    "champion": {
        "name": "🏆 Champion Crate",
        "price": 6000,
        "gold_min": 300,
        "gold_max": 1500, # 25% max return
        "part_chance": 1.00, # 100% guaranteed part
        "rarities": ["Rare", "Epic", "Legendary"],
        "weights": [35, 50, 15]
    }
}

PART_NAMES = {
    "engine": ["V6 Turbo Power Unit", "Titanium Spec V8 Engine", "Hybrid E-Power Core", "Quad-Turbo V10 Unit"],
    "aerodynamics": ["Low-Drag Wing Spec A", "Ground Effect Floor V2", "Vortex Generator Sidepods", "Active Aero Rear Wing"],
    "tyres": ["Soft C5 Slick Compound", "Medium Thermal Tread", "Hard Endurance Slicks", "Ultra-Grip Kevlar Tyres"],
    "ers": ["KERS Energy Recov Cell", "MGU-K High Voltage Rotor", "MGU-H Thermal Collector", "Ultra-Capacitor Bank"],
    "reliability": ["Heavy Duty Oil Cooler", "Carbon Brake Assemblies", "Reinforced Wishbone Suspension", "Titanium Gearbox Casing"],
    "pit_crew": ["Fast-Release Wheel Guns", "Laser Alignment Jacks", "Carbon Pit Stop Boom", "Precision Pit Crew Training"]
}

def unbox_crate(user_id: int, crate_tier: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Unboxes a crate for the user:
    1. Deducts price from user money balance.
    2. Rolls Gold / Credits reward (range specified per crate tier).
    3. Rolls Part Drop Chance and Rarity.
    4. Adds part into user inventory if dropped.
    """
    tier_key = crate_tier.lower()
    if tier_key not in CRATE_CONFIGS:
        return False, "❌ Invalid crate tier! Choose `rookie`, `pro`, or `champion`.", {}
        
    cfg = CRATE_CONFIGS[tier_key]
    price = cfg["price"]
    
    # Check user balance
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, money, level FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False, "❌ User profile not found.", {}
        
    if user['money'] < price:
        return False, f"❌ Insufficient funds! **{cfg['name']}** costs **{price:,}¢**, but you only have **{user['money']:,}¢**.", {}
        
    # Deduct price
    database.update_user_balance(user_id, -price)
    
    # 1. Roll Gold / Credits reward
    gold_reward = random.randint(cfg["gold_min"], cfg["gold_max"])
    database.update_user_balance(user_id, gold_reward)
    
    # 2. Roll Part Drop
    part_dropped = None
    if random.random() <= cfg["part_chance"]:
        rarity = random.choices(cfg["rarities"], weights=cfg["weights"], k=1)[0]
        category = random.choice(["engine", "aerodynamics", "tyres", "ers", "reliability", "pit_crew"])
        part_title = random.choice(PART_NAMES[category])
        
        # Determine part level (user level - 1 to user level + 3, capped 1-20)
        part_level = max(1, min(20, random.randint(max(1, user['level'] - 1), user['level'] + 3)))
        stat_bonus = part_level
        
        success, msg, item_id = database.add_inventory_part(
            user_id=user_id,
            category=category,
            part_name=part_title,
            rarity=rarity,
            level=part_level,
            stat_bonus=stat_bonus
        )
        
        if success:
            part_dropped = {
                "item_id": item_id,
                "category": category,
                "part_name": part_title,
                "rarity": rarity,
                "emoji": RARITY_EMOJIS.get(rarity, "⚪"),
                "level": part_level,
                "stat_bonus": stat_bonus,
                "efficiency_bonus": f"+{(RARITY_BONUS_MULTIPLIERS.get(rarity, 1.0) - 1.0)*100:.0f}%"
            }
            
    summary = {
        "crate_name": cfg["name"],
        "cost": price,
        "gold_reward": gold_reward,
        "net_cost": price - gold_reward,
        "part_dropped": part_dropped
    }
    
    return True, "Crate unboxed successfully!", summary
