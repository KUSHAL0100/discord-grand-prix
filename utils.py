import discord
from datetime import datetime
from typing import Dict, Any, List
import config

# Standard color palette for Discord Grand Prix
COLOR_F1_RED = 0xE10600
COLOR_SUCCESS = 0x2ECC71
COLOR_INFO = 0x3498DB
COLOR_WARNING = 0xF1C40F
COLOR_ERROR = 0xE74C3C
COLOR_QUALIFYING = 0xFF6F00
COLOR_RACE_RESULTS = 0x00AAFF

def calculate_car_power(garage: Dict[str, Any]) -> int:
    """
    Calculate base car power using weighted sum:
    (Engine*3 + Aero*2 + Tyres*2 + ERS*2 + Reliability*1)
    """
    return (
        garage.get("engine", 1) * 3 +
        garage.get("aerodynamics", 1) * 2 +
        garage.get("tyres", 1) * 2 +
        garage.get("ers", 1) * 2 +
        garage.get("reliability", 1) * 1
    )

def calculate_overall_power(garage: Dict[str, Any], driver_pace: int) -> int:
    """
    Calculate overall team power:
    car_power + driver_pace / 3
    """
    car_power = calculate_car_power(garage)
    driver_bonus = driver_pace / 3.0
    return round(car_power + driver_bonus)

def get_points_for_position(position: int) -> int:
    """Return points awarded for a given finishing position (1-indexed)."""
    import config
    points_map = config.GP_POINTS_DISTRIBUTION
    if 1 <= position <= len(points_map):
        return points_map[position - 1]
    return 0

def create_embed(
    title: str,
    description: str = "",
    color: int = COLOR_F1_RED,
    fields: List[Dict[str, Any]] = None,
    footer_text: str = "",
    thumbnail_url: str = None
) -> discord.Embed:
    """Helper function to create a standardized beautiful embed."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", True)
            )
            
    if footer_text:
        embed.set_footer(text=footer_text)
    else:
        embed.set_footer(text=f"Discord Grand Prix • {datetime.now().strftime('%Y-%m-%d')}")
        
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
        
    return embed

def make_progress_bar(percentage: float, length: int = 10) -> str:
    """Render a visual progress bar for damage using emojis."""
    percentage = max(0.0, min(100.0, float(percentage)))
    filled_len = int(round(length * (percentage / 100.0)))
    filled_len = max(0, min(length, filled_len))
    
    if percentage >= 80.0:
        fill_emoji = "🔴"
    elif percentage >= 40.0:
        fill_emoji = "🟡"
    else:
        fill_emoji = "🟩"
        
    empty_emoji = "⚪"
    return f"`[{fill_emoji * filled_len}{empty_emoji * (length - filled_len)}] {percentage:.0f}%`"

# --- Phase 1: Visual Card & Telemetry Generators ---
import io
import random
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use('Agg') # Non-interactive backend for server rendering
import matplotlib.pyplot as plt

VICTORY_RADIOS = [
    "📻 *[Team Radio]*: 'P1! Simply lovely! What a drive!'",
    "📻 *[Team Radio]*: 'Grazie Ragazzi! Grande Macchina! What a race!'",
    "📻 *[Team Radio]*: 'P1 baby, get in there! Superb pace out there today!'",
    "📻 *[Team Radio]*: 'WOOOOO! That is how we do it! Perfect execution!'",
    "📻 *[Team Radio]*: 'P1! Unbelievable effort from everyone at the factory!'",
    "📻 *[Team Radio]*: 'Checkered flag! Absolute masterclass from start to finish!'"
]

def get_victory_team_radio(team_name: str = "") -> str:
    """Return a randomized authentic F1 victory team radio broadcast."""
    return random.choice(VICTORY_RADIOS)

# Load crisp fonts with fallback handling
try:
    FONT_TITLE = ImageFont.truetype("arialbd.ttf", 26)
    FONT_SUB = ImageFont.truetype("arialbd.ttf", 15)
    FONT_BODY = ImageFont.truetype("arial.ttf", 14)
    FONT_BOLD = ImageFont.truetype("arialbd.ttf", 14)
    FONT_SMALL = ImageFont.truetype("arial.ttf", 12)
except Exception:
    FONT_TITLE = FONT_SUB = FONT_BODY = FONT_BOLD = FONT_SMALL = ImageFont.load_default()

def get_tier_label(level: int) -> str:
    if level >= 16:
        return "TIER 4 (EXTREME)"
    elif level >= 11:
        return "TIER 3 (ADVANCED)"
    elif level >= 6:
        return "TIER 2 (PERFORMANCE)"
    return "TIER 1 (SPEC)"

def generate_profile_card(prof: Dict[str, Any]) -> io.BytesIO:
    """
    Renders a high-tech dark-theme F1 driver profile PNG card (800x470 px).
    Fixes font glyph missing boxes, adds component category tier badges, and renders crisp progress bars.
    Returns in-memory BytesIO PNG.
    """
    width, height = 800, 470
    img = Image.new("RGBA", (width, height), (15, 18, 25, 255))
    draw = ImageDraw.Draw(img)
    
    # Header Banner (F1 Red Accent)
    draw.rectangle([(0, 0), (width, 80)], fill=(225, 6, 0, 255))
    
    font_title = FONT_TITLE
    font_sub = FONT_SUB
    font_body = FONT_BODY
    font_bold = FONT_BOLD
    font_small = FONT_SMALL
        
    # Team & Driver Name
    team_title = f"{prof.get('team_name', 'F1 Team')}".upper()
    country_str = prof.get('country') or ""
    if country_str:
        team_title = f"{country_str} {team_title}"
    draw.text((25, 12), team_title[:32], fill=(255, 255, 255, 255), font=font_title)
    
    overall_power = calculate_overall_power(prof, prof.get("pace", 50))
    highest_lvl = max([prof.get(p, 1) for p in config.PART_MULTIPLIERS.keys()])
    tier_name = get_tier_label(highest_lvl)
    
    subtitle = f"LEVEL {prof.get('level', 1)} DRIVER  |  OVERALL POWER: {overall_power:.1f}  |  {tier_name}"
    draw.text((25, 48), subtitle, fill=(255, 220, 220, 255), font=font_sub)
    
    # Financials & Stats Strip below header (clean text formatting, no unrendered emoji glyphs)
    draw.rectangle([(0, 80), (width, 118)], fill=(25, 30, 42, 255))
    stats_text = (
        f"Money: {prof.get('money', 0):,}c   |   "
        f"XP: {prof.get('xp', 0):,}/{prof.get('level', 1)*1000:,} XP   |   "
        f"Wins: {prof.get('wins', 0)}   |   Losses: {prof.get('losses', 0)}"
    )
    draw.text((25, 90), stats_text, fill=(200, 210, 225, 255), font=font_body)
    
    # Section Headers
    draw.text((30, 132), "DRIVER PERSONNEL (1-100)", fill=(225, 6, 0, 255), font=font_sub)
    draw.text((430, 132), "GARAGE COMPONENTS (1-20)", fill=(0, 170, 255, 255), font=font_sub)
    
    # Left Column: Driver Skills
    skills = [
        ("Race Pace", prof.get("pace", 50)),
        ("Qualifying", prof.get("qual", 50)),
        ("Wet Skill", prof.get("wet_skill", 50)),
        ("Consistency", prof.get("consistency", 50)),
        ("Aggression", prof.get("aggression", 50)),
        ("Overtaking", prof.get("overtaking", 50)),
    ]
    
    y_start = 168
    for idx, (s_name, val) in enumerate(skills):
        y = y_start + (idx * 44)
        draw.text((30, y), s_name, fill=(220, 225, 235, 255), font=font_body)
        draw.text((140, y), f"{val}/100", fill=(255, 255, 255, 255), font=font_bold)
        
        # Skill bar background
        draw.rectangle([(220, y + 2), (390, y + 16)], fill=(40, 45, 58, 255))
        # Skill bar fill
        fill_width = 220 + int(170 * (min(100, max(0, val)) / 100.0))
        if fill_width > 220:
            draw.rectangle([(220, y + 2), (fill_width, y + 16)], fill=(225, 6, 0, 255))
        
    # Right Column: Garage Component Levels & Tier Category Badges
    parts = [
        ("Engine", prof.get("engine", 1)),
        ("Aerodynamics", prof.get("aerodynamics", 1)),
        ("Tyres", prof.get("tyres", 1)),
        ("ERS System", prof.get("ers", 1)),
        ("Reliability", prof.get("reliability", 1)),
        ("Pit Crew", prof.get("pit_crew", 1)),
    ]
    
    for idx, (p_name, lvl) in enumerate(parts):
        y = y_start + (idx * 44)
        tier_sub = get_tier_label(lvl).split(" ")[0] + " " + get_tier_label(lvl).split(" ")[1]
        draw.text((430, y), p_name, fill=(220, 225, 235, 255), font=font_body)
        draw.text((545, y), f"Lvl {lvl}/20", fill=(255, 255, 255, 255), font=font_bold)
        
        # Level bar background
        draw.rectangle([(640, y + 2), (770, y + 16)], fill=(40, 45, 58, 255))
        # Level bar fill
        fill_width = 640 + int(130 * (min(20, max(0, lvl)) / 20.0))
        if fill_width > 640:
            draw.rectangle([(640, y + 2), (fill_width, y + 16)], fill=(0, 170, 255, 255))
            
    # Footer strip
    draw.rectangle([(0, height - 25), (width, height)], fill=(10, 12, 18, 255))
    draw.text((25, height - 19), "DISCORD GRAND PRIX  |  OFFICIAL TELEMETRY SHEET", fill=(120, 130, 150, 255), font=font_small)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generate_race_telemetry_graph(lap_history: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Renders a post-race multi-driver pace line chart using matplotlib.
    lap_history format: list of dicts {"lap": int, "drivers": {"Team Name": lap_time_or_gap, ...}}
    Returns PNG image BytesIO buffer.
    """
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=100)
    fig.patch.set_facecolor('#0f1219')
    ax.set_facecolor('#171c26')
    
    if not lap_history:
        ax.text(0.5, 0.5, "No telemetry data available", color="white", ha="center", va="center")
    else:
        laps = [h["lap"] for h in lap_history]
        driver_names = list(lap_history[0]["drivers"].keys())
        
        colors_list = ['#e10600', '#00aaff', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c', '#e91e63']
        
        for idx, name in enumerate(driver_names):
            y_vals = [h["drivers"].get(name, 0.0) for h in lap_history]
            c = colors_list[idx % len(colors_list)]
            ax.plot(laps, y_vals, marker='o', linewidth=2.5, markersize=5, label=name[:14], color=c)
            
        ax.set_xlabel("Lap Number", color="#a0abc0", fontsize=11, fontweight='bold')
        ax.set_ylabel("Position / Gap (s)", color="#a0abc0", fontsize=11, fontweight='bold')
        ax.set_title("Grand Prix Live Lap Telemetry & Pace Chart", color="white", fontsize=13, fontweight='bold', pad=12)
        ax.grid(True, linestyle='--', alpha=0.25, color='#404b5c')
        ax.tick_params(colors='#a0abc0', labelsize=10)
        
        for spine in ax.spines.values():
            spine.set_color('#2a3242')
            
        ax.legend(facecolor='#1b212d', edgecolor='#404b5c', labelcolor='white', loc='upper right', fontsize=9)
        
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    plt.close('all')
    plt.clf()
    buf.seek(0)
    return buf

