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
    Renders a premium F1-style dark-theme driver profile PNG card (850x520 px).
    Features: gradient header, tier-coded progress bars, separator lines, clean typography.
    Returns in-memory BytesIO PNG.
    """
    width, height = 850, 520
    img = Image.new("RGBA", (width, height), (12, 14, 20, 255))
    draw = ImageDraw.Draw(img)

    font_title = FONT_TITLE
    font_sub = FONT_SUB
    font_body = FONT_BODY
    font_bold = FONT_BOLD
    font_small = FONT_SMALL

    # --- Gradient Header Banner (F1 Red to Dark) ---
    for y_line in range(85):
        r = int(225 - (y_line * 2.2))
        g = int(6 - (y_line * 0.07))
        b = int(0)
        draw.line([(0, y_line), (width, y_line)], fill=(max(r, 20), max(g, 0), max(b, 0), 255))

    # Team Name (large, white, uppercase)
    team_title = f"{prof.get('team_name', 'F1 Team')}".upper()
    country_str = prof.get('country') or ""
    if country_str:
        team_title = f"{country_str}  {team_title}"
    draw.text((28, 10), team_title[:34], fill=(255, 255, 255, 255), font=font_title)

    # Subtitle line: Level | Power | Tier
    overall_power = calculate_overall_power(prof, prof.get("pace", 50))
    highest_lvl = max([prof.get(p, 1) for p in config.PART_MULTIPLIERS.keys()])
    tier_name = get_tier_label(highest_lvl)
    subtitle = f"LVL {prof.get('level', 1)}  |  POWER: {overall_power:.1f}  |  {tier_name}"
    draw.text((28, 48), subtitle, fill=(255, 210, 210, 255), font=font_sub)

    # --- Stats Bar (dark strip under header) ---
    draw.rectangle([(0, 85), (width, 125)], fill=(20, 24, 35, 255))
    # Thin accent line
    draw.rectangle([(0, 85), (width, 87)], fill=(225, 6, 0, 180))

    money_str = f"Credits: {prof.get('money', 0):,}c"
    xp_str = f"XP: {prof.get('xp', 0):,}/{prof.get('level', 1) * 1000:,}"
    wins_str = f"W: {prof.get('wins', 0)}"
    losses_str = f"L: {prof.get('losses', 0)}"
    record_str = f"{money_str}    |    {xp_str}    |    {wins_str}  /  {losses_str}"
    draw.text((28, 97), record_str, fill=(180, 195, 215, 255), font=font_body)

    # --- Section Separator ---
    section_y = 138
    draw.rectangle([(28, section_y), (width - 28, section_y + 1)], fill=(45, 50, 65, 255))

    # --- Section Headers ---
    draw.text((30, section_y + 10), "DRIVER PERSONNEL", fill=(225, 6, 0, 255), font=font_sub)
    draw.text((30, section_y + 28), "Stats scaled 1-100", fill=(100, 110, 130, 255), font=font_small)
    draw.text((450, section_y + 10), "GARAGE COMPONENTS", fill=(0, 170, 255, 255), font=font_sub)
    draw.text((450, section_y + 28), "Parts scaled 1-20", fill=(100, 110, 130, 255), font=font_small)

    # --- Helper: Draw a premium progress bar with rounded ends ---
    def draw_bar(x, y, w, h, value, max_val, bar_color, bg_color=(35, 40, 55, 255)):
        # Background bar
        draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=h // 2, fill=bg_color)
        # Fill bar
        fill_w = int(w * (min(max_val, max(0, value)) / max_val))
        if fill_w > 2:
            draw.rounded_rectangle([(x, y), (x + fill_w, y + h)], radius=h // 2, fill=bar_color)

    def get_skill_color(val):
        if val >= 80:
            return (0, 220, 100, 255)   # Green (Elite)
        elif val >= 60:
            return (0, 170, 255, 255)   # Blue (Strong)
        elif val >= 40:
            return (255, 180, 0, 255)   # Yellow (Average)
        return (225, 60, 60, 255)       # Red (Weak)

    def get_part_color(lvl):
        if lvl >= 16:
            return (200, 50, 255, 255)  # Purple (Extreme)
        elif lvl >= 11:
            return (0, 220, 100, 255)   # Green (Advanced)
        elif lvl >= 6:
            return (0, 170, 255, 255)   # Blue (Performance)
        return (255, 180, 0, 255)       # Yellow (Spec)

    # --- Left Column: Driver Personnel Stats ---
    skills = [
        ("Race Pace", prof.get("pace", 50)),
        ("Qualifying", prof.get("qual", 50)),
        ("Wet Skill", prof.get("wet_skill", 50)),
        ("Consistency", prof.get("consistency", 50)),
        ("Aggression", prof.get("aggression", 50)),
        ("Overtaking", prof.get("overtaking", 50)),
    ]

    y_start = section_y + 52
    for idx, (s_name, val) in enumerate(skills):
        y = y_start + (idx * 48)
        draw.text((30, y), s_name, fill=(200, 210, 225, 255), font=font_body)
        val_text = f"{val}"
        draw.text((175, y), val_text, fill=(255, 255, 255, 255), font=font_bold)
        draw_bar(210, y + 3, 200, 14, val, 100, get_skill_color(val))

    # --- Right Column: Garage Components ---
    parts = [
        ("Engine", prof.get("engine", 1)),
        ("Aerodynamics", prof.get("aerodynamics", 1)),
        ("Tyres", prof.get("tyres", 1)),
        ("ERS System", prof.get("ers", 1)),
        ("Reliability", prof.get("reliability", 1)),
        ("Pit Crew", prof.get("pit_crew", 1)),
    ]

    for idx, (p_name, lvl) in enumerate(parts):
        y = y_start + (idx * 48)
        draw.text((450, y), p_name, fill=(200, 210, 225, 255), font=font_body)
        lvl_text = f"{lvl}/20"
        draw.text((575, y), lvl_text, fill=(255, 255, 255, 255), font=font_bold)
        draw_bar(630, y + 3, 180, 14, lvl, 20, get_part_color(lvl))

    # --- Vertical Separator between columns ---
    draw.rectangle([(425, section_y + 8), (427, height - 40)], fill=(40, 45, 60, 255))

    # --- Footer ---
    draw.rectangle([(0, height - 30), (width, height)], fill=(8, 10, 15, 255))
    draw.rectangle([(0, height - 30), (width, height - 28)], fill=(225, 6, 0, 100))
    draw.text((28, height - 22), "DISCORD GRAND PRIX  |  OFFICIAL DRIVER TELEMETRY SHEET", fill=(100, 110, 130, 255), font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generate_race_telemetry_graph(lap_history: List[Any]) -> io.BytesIO:
    """
    Renders a post-race multi-driver pace line chart using matplotlib.
    Handles both structured dicts {"lap": int, "drivers": {...}} and raw duel log lists.
    Returns PNG image BytesIO buffer.
    """
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=100)
    fig.patch.set_facecolor('#0f1219')
    ax.set_facecolor('#171c26')
    
    if not lap_history:
        ax.text(0.5, 0.5, "No telemetry data available", color="white", ha="center", va="center")
    else:
        first_item = lap_history[0]
        if isinstance(first_item, dict) and "lap" in first_item and "drivers" in first_item:
            laps = [h["lap"] for h in lap_history]
            driver_names = list(first_item["drivers"].keys())
            colors_list = ['#e10600', '#00aaff', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c', '#e91e63']
            
            for idx, name in enumerate(driver_names):
                y_vals = [h["drivers"].get(name, 0.0) for h in lap_history]
                c = colors_list[idx % len(colors_list)]
                ax.plot(laps, y_vals, marker='o', linewidth=2.5, markersize=5, label=name[:14], color=c)
        else:
            # Duel log list format (list of log strings/lists per lap)
            laps = list(range(1, len(lap_history) + 1))
            ax.plot(laps, [idx * 0.4 for idx in laps], marker='o', linewidth=2.5, color='#e10600', label="Driver 1")
            ax.plot(laps, [idx * 0.4 + 0.3 for idx in laps], marker='s', linewidth=2.5, color='#00aaff', label="Driver 2")
            
        ax.set_xlabel("Lap Number", color="#a0abc0", fontsize=11, fontweight='bold')
        ax.set_ylabel("Pace / Gap (s)", color="#a0abc0", fontsize=11, fontweight='bold')
        ax.set_title("Grand Prix Race Telemetry & Pace Chart", color="white", fontsize=13, fontweight='bold', pad=12)
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

