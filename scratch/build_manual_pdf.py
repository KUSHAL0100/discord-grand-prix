import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # Cover page - dark theme styling
            self.saveState()
            self.setFillColor(colors.HexColor("#0B0E14"))
            self.rect(0, 0, 8.5 * inch, 11 * inch, fill=1, stroke=0)
            
            # Left red accent stripe
            self.setFillColor(colors.HexColor("#FF1801"))
            self.rect(0, 0, 0.4 * inch, 11 * inch, fill=1, stroke=0)
            self.restoreState()
            return

        self.saveState()
        self.setFont("Helvetica-Oblique", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header
        self.drawString(0.75 * inch, 10.3 * inch, "DISCORD GRAND PRIX | MASTER SPECIFICATION & FEATURE GUIDE")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(0.75 * inch, 10.2 * inch, 7.75 * inch, 10.2 * inch)
        
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawCentredString(4.25 * inch, 0.4 * inch, page_str)
        self.restoreState()

def create_manual_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.8 * inch
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=colors.white,
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#00E5FF"),
        spaceAfter=15
    )
    
    cover_body = ParagraphStyle(
        'CoverBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#94A3B8")
    )
    
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor("#E2E8F0"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A")
    )

    story = []

    # ================= COVER PAGE =================
    story.append(Spacer(1, 1.8 * inch))
    story.append(Paragraph("DISCORD<br/>GRAND PRIX", title_style))
    story.append(HRFlowable(width="100%", thickness=3, color=colors.HexColor("#FF1801"), spaceBefore=0, spaceAfter=20))
    story.append(Paragraph("UNIFIED MASTER ENGINE SPECIFICATION & FEATURE GUIDE", subtitle_style))
    story.append(Spacer(1, 0.2 * inch))
    
    meta_text = """
    All Bot Features &nbsp;|&nbsp; Deep Mathematical Models &nbsp;|&nbsp; Physics Equations<br/>
    Admin Suite &nbsp;|&nbsp; 24 Official F1 Track Profiles &nbsp;|&nbsp; 46 Commands
    """
    story.append(Paragraph(meta_text, cover_body))
    story.append(Spacer(1, 0.4 * inch))
    
    subsystems_text = """
    <b>SYSTEM CORE SUB-SYSTEMS:</b><br/>
    -- 6-Part Garage & Upgrade System (Levels 1-20)<br/>
    -- Crate Unboxing, Parts Inventory & 5-Tier Rarity Offsets<br/>
    -- Driver Skills Training & Dynamic Track Mastery familiarization<br/>
    -- 1v1 Duels, High-Stakes Wagers & full 20-Car Grand Prix weekends<br/>
    -- Qualifying Knockouts (Q1 -&gt; Q2 -&gt; Q3) & Live Telemetry<br/>
    -- Advanced Physics Engine (tyre wear, non-linear degradation, mechanical DNFs)<br/>
    -- World Driver Championship (WDC) Season Manager & automated calendar<br/>
    -- Modular Python Cogs architecture built with SQLite WAL-mode databases
    """
    story.append(Paragraph(subsystems_text, cover_body))
    
    story.append(Spacer(1, 1.5 * inch))
    doc_spec = """
    <b>DOCUMENT SPECIFICATION</b><br/>
    Version: 2.1 &nbsp;|&nbsp; Updated: August 2026<br/>
    Database Schema: Active Build V2 &nbsp;|&nbsp; Target: discord.py 2.x API
    """
    story.append(Paragraph(doc_spec, cover_body))
    story.append(PageBreak())

    # ================= TABLE OF CONTENTS =================
    story.append(Paragraph("TABLE OF CONTENTS", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284C7"), spaceBefore=0, spaceAfter=10))

    toc_items = [
        "1. All Gameplay & RPG Features",
        "2. Onboarding & Team Profile Creation",
        "3. 6-Part Garage & Upgrade System",
        "4. Driver Personnel Training",
        "5. Strategist Personnel",
        "6. Crate Unboxing & Inventory System",
        "7. Consumable Boosters Shop",
        "8. Economy & Earning Credits",
        "9. Racing Modes",
        "10. Grand Prix Race Weekend",
        "11. Qualifying System (Q1/Q2/Q3)",
        "12. Race Simulation Physics Engine",
        "13. Track Mastery & Practice Sessions",
        "14. Official 24 F1 Track Profile Matrix",
        "15. AI Grid System (20-Car Grid)",
        "16. WDC Season & Championship Management",
        "17. Admin Suite & Server Management",
        "18. Deep Mathematical Model & Physics Equations",
        "19. Complete Command Registry",
        "20. Database Schema & Architecture"
    ]
    
    for item in toc_items:
        story.append(Paragraph(f"<b>{item}</b>", body_style))
    story.append(Spacer(1, 15))

    # ================= SECTION 1: ALL GAMEPLAY & RPG FEATURES =================
    story.append(Paragraph("1. ALL GAMEPLAY & RPG FEATURES", h1_style))
    story.append(Paragraph("DISCORD GRAND PRIX is an advanced, high-performance Formula 1 esports and team management engine built for Discord. Combining deep RPG progression, realistic telemetry physics equations, a full World Driver Championship (WDC) calendar management system, an item economy with crate unboxing, and automated server activity rewards -- it delivers the ultimate racing simulation experience.", body_style))
    
    feature_table_data = [
        [Paragraph("<b>Feature Subsystem</b>", table_header), Paragraph("<b>Capabilities & Functionality Overview</b>", table_header)],
        [Paragraph("RPG Driver Training", table_cell), Paragraph("Train 6 Driver Skills (Pace, Qual, Wet, Consistency, Aggression, Overtaking) with /train. Each skill ranges from 1 - 100. Training costs 400¢ per session.", table_cell)],
        [Paragraph("6-Part Garage & Damage Engine", table_cell), Paragraph("Upgrade & manage Engine, Aerodynamics, Tyres, ERS, Reliability, & Pit Crew (Levels 1 - 20). Dynamic damage accumulates per race with realistic power loss penalties. Repair with /repair or /repairs.", table_cell)],
        [Paragraph("Crate & Inventory System", table_cell), Paragraph("Unbox Rookie (500¢), Pro (2,500¢), or Champion (6,000¢) crates. Drop parts across 5 rarity tiers (Common -&gt; Legendary) with base level offsets and efficiency multipliers. Equip parts from /inventory.", table_cell)],
        [Paragraph("Consumable Boosters Shop", table_cell), Paragraph("Purchase tactical boosters from /shop -- Tyre Blanket Warmer (1,500¢), ERS High-Flow Injector (2,000¢), or Heavy Duty Radiator (1,200¢). Max 2 active boosters at a time.", table_cell)],
        [Paragraph("Economy & Earning Methods", table_cell), Paragraph("Earn credits through /daily (500¢), /work (250 - 600¢), chat activity (25¢/msg, 1,000¢/day cap), and voice channel time (15¢/min, 1,500¢/day cap).", table_cell)],
        [Paragraph("1v1 Duels & High-Stakes Wagers", table_cell), Paragraph("Challenge rivals to head-to-head duel races (/race) with live lap-by-lap telemetry updates, dynamic overtaking, and real-time strategy. Wager credits using /bet.", table_cell)],
        [Paragraph("Grand Prix Events (20-Car Grid)", table_cell), Paragraph("Admin-scheduled full GP weekends (500¢ entry fee) with Q1/Q2/Q3 qualifying, dynamic weather, Safety Car/VSC, DRS overtaking, and F1-standard points distribution.", table_cell)],
        [Paragraph("Sprint Race Weekends", table_cell), Paragraph("Shorter sprint format races with alternate points distribution (8-7-6-5-4-3-2-1 for Top 8). Official sprint tracks marked in calendar.", table_cell)],
        [Paragraph("Track Mastery & Practice", table_cell), Paragraph("Run solo practice sessions (/practice) on any official F1 track. Earn pace bonus up to -0.15s/lap. Max 3 sessions per day. Costs 500¢ per session.", table_cell)],
        [Paragraph("WDC Season Championship", table_cell), Paragraph("Full World Driver Championship management. Create multi-round seasons, schedule GP & Sprint rounds, view live standings, and crown a World Champion.", table_cell)],
        [Paragraph("Leaderboard System", table_cell), Paragraph("View server-wide rankings sorted by Championship Points, Total Wins, Team Wealth, or Driver Level via /leaderboard.", table_cell)]
    ]

    t_features = Table(feature_table_data, colWidths=[1.8 * inch, 5.2 * inch])
    t_features.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_features)
    story.append(Spacer(1, 15))

    # ================= SECTION 2: ONBOARDING & TEAM PROFILE CREATION =================
    story.append(Paragraph("2. ONBOARDING & TEAM PROFILE CREATION", h1_style))
    story.append(Paragraph("<b>/start -- Initialize Your Racing Team</b>", h2_style))
    story.append(Paragraph("Every player begins their journey by creating a unique team profile.", body_style))
    story.append(Paragraph("• <b>Starting Resources:</b> 1,500¢ Credits, Driver Level 1, 0 XP, All 6 Driver Skills at 50/100, All Garage Parts at Level 1/20 (0% Damage).", bullet_style))
    story.append(Paragraph("• <b>Team Name Rules:</b> 3 - 32 characters, must contain at least one letter, allowed characters: letters, numbers, spaces, hyphens, underscores, apostrophes. Must be unique per server.", bullet_style))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>/profile -- View Your Team Profile Card</b>", h2_style))
    story.append(Paragraph("Renders a premium <b>880x540px F1-style PNG profile card</b> featuring:", body_style))
    story.append(Paragraph("• Carbon-teal header gradient with team name and country flag.", bullet_style))
    story.append(Paragraph("• Driver Level, Overall Power rating, and Equipped Rarity Class.", bullet_style))
    story.append(Paragraph("• Credits balance, XP progress bar, Win/Loss record.", bullet_style))
    story.append(Paragraph("• Left column: 6 Driver skill bars (1 - 100 scale, color-coded).", bullet_style))
    story.append(Paragraph("• Right column: 6 Garage component bars with equipped part rarity tags.", bullet_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<i>[NOTE] The standalone /team command has been integrated into /profile and /garage for a streamlined user experience.</i>", body_style))
    story.append(Spacer(1, 15))

    # ================= SECTION 3: GARAGE & UPGRADES =================
    story.append(Paragraph("3. 6-PART GARAGE & UPGRADE SYSTEM", h1_style))
    story.append(Paragraph("The garage contains 6 upgradeable car components on a Level 1 - 20 scale:", body_style))
    
    garage_table_data = [
        [Paragraph("<b>Component</b>", table_header), Paragraph("<b>Power Weight</b>", table_header), Paragraph("<b>Race Impact</b>", table_header)],
        [Paragraph("Engine", table_cell), Paragraph("1.0x (Highest)", table_cell), Paragraph("Raw straight-line speed. Shaves 0.05s/lap per level.", table_cell)],
        [Paragraph("Aerodynamics", table_cell), Paragraph("0.8x", table_cell), Paragraph("Corner speed & downforce. Shaves 0.04s/lap per level.", table_cell)],
        [Paragraph("Tyres", table_cell), Paragraph("0.5x", table_cell), Paragraph("Grip & tyre longevity. Reduces tyre wear impact.", table_cell)],
        [Paragraph("ERS System", table_cell), Paragraph("0.8x", table_cell), Paragraph("Energy recovery & deployment. Shaves 0.04s/lap per level.", table_cell)],
        [Paragraph("Reliability", table_cell), Paragraph("0.25x", table_cell), Paragraph("Reduces DNF / mechanical failure probability.", table_cell)],
        [Paragraph("Pit Crew", table_cell), Paragraph("0.25x", table_cell), Paragraph("Reduces pit stop stationary duration.", table_cell)]
    ]
    t_garage = Table(garage_table_data, colWidths=[1.5 * inch, 1.3 * inch, 4.2 * inch])
    t_garage.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_garage)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Damage & Repair System</b>", h2_style))
    story.append(Paragraph("Cars accumulate damage after every race session:", body_style))
    story.append(Paragraph("• <b>Finishing Race:</b> Engine +3-10%, Tyres +10-25% damage.", bullet_style))
    story.append(Paragraph("• <b>DNF (Crash):</b> Engine +15-30%, Tyres +30-60% damage.", bullet_style))
    story.append(Paragraph("• <b>Damage Penalty:</b> -1% car power per 10% total damage (capped at -50%).", bullet_style))
    story.append(Paragraph("• <b>Repair Costs:</b> 25¢ per 1% damage. Commands: <code>/repairs</code>, <code>/repair</code>.", bullet_style))
    story.append(Spacer(1, 15))

    # ================= SECTION 4 & 5: DRIVER & STRATEGIST =================
    story.append(Paragraph("4. DRIVER PERSONNEL TRAINING", h1_style))
    story.append(Paragraph("Train 6 driver skills from Level 50 -&gt; 100 with <code>/train &lt;skill&gt;</code>. Each session costs <b>400¢</b> and increases skill by +1:", body_style))
    
    driver_table_data = [
        [Paragraph("<b>Skill</b>", table_header), Paragraph("<b>Race Impact & Mechanics</b>", table_header)],
        [Paragraph("Pace", table_cell), Paragraph("Raw lap time speed. Shaves up to 2.0s/lap at max (100).", table_cell)],
        [Paragraph("Qualifying", table_cell), Paragraph("One-lap qualifying speed bonus. Higher = better grid positions.", table_cell)],
        [Paragraph("Wet Skill", table_cell), Paragraph("Performance in rain. Reduces wet weather lap time penalty significantly.", table_cell)],
        [Paragraph("Consistency", table_cell), Paragraph("Reduces random lap time variance and lowers mistake/lockup probability.", table_cell)],
        [Paragraph("Aggression", table_cell), Paragraph("Increases overtake frequency & minor pace boost, but increases crash risk and tyre wear.", table_cell)],
        [Paragraph("Overtaking", table_cell), Paragraph("Improves DRS pass success rate against defender's Consistency stat.", table_cell)]
    ]
    t_driver = Table(driver_table_data, colWidths=[1.8 * inch, 5.2 * inch])
    t_driver.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_driver)
    story.append(Spacer(1, 15))

    # ================= SECTION 6: CRATE UNBOXING & INVENTORY =================
    story.append(Paragraph("6. CRATE UNBOXING & INVENTORY SYSTEM", h1_style))
    story.append(Paragraph("Unbox parts to gain intrinsic power offsets and rarity efficiency multipliers:", body_style))
    
    crate_table_data = [
        [Paragraph("<b>Crate Tier</b>", table_header), Paragraph("<b>Price</b>", table_header), Paragraph("<b>Gold Refund</b>", table_header), Paragraph("<b>Drop Chance</b>", table_header), Paragraph("<b>Rarities Available</b>", table_header)],
        [Paragraph("Rookie Crate", table_cell), Paragraph("500¢", table_cell), Paragraph("25 - 125¢", table_cell), Paragraph("60%", table_cell), Paragraph("Common (70%), Uncommon (25%), Rare (5%)", table_cell)],
        [Paragraph("Pro Crate", table_cell), Paragraph("2,500¢", table_cell), Paragraph("125 - 625¢", table_cell), Paragraph("85%", table_cell), Paragraph("Uncommon (40%), Rare (45%), Epic (12%), Legendary (3%)", table_cell)],
        [Paragraph("Champion Crate", table_cell), Paragraph("6,000¢", table_cell), Paragraph("300 - 1,500¢", table_cell), Paragraph("100%", table_cell), Paragraph("Rare (35%), Epic (50%), Legendary (15%)", table_cell)]
    ]
    t_crate = Table(crate_table_data, colWidths=[1.4 * inch, 0.9 * inch, 1.1 * inch, 1.0 * inch, 2.6 * inch])
    t_crate.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_crate)
    story.append(Spacer(1, 10))

    rarity_table_data = [
        [Paragraph("<b>Rarity Tier</b>", table_header), Paragraph("<b>Base Level Offset</b>", table_header), Paragraph("<b>Efficiency Multiplier</b>", table_header)],
        [Paragraph("Common", table_cell), Paragraph("+0 levels", table_cell), Paragraph("1.00x (+0%)", table_cell)],
        [Paragraph("Uncommon", table_cell), Paragraph("+3 levels", table_cell), Paragraph("1.05x (+5%)", table_cell)],
        [Paragraph("Rare", table_cell), Paragraph("+6 levels", table_cell), Paragraph("1.12x (+12%)", table_cell)],
        [Paragraph("Epic", table_cell), Paragraph("+10 levels", table_cell), Paragraph("1.22x (+22%)", table_cell)],
        [Paragraph("Legendary", table_cell), Paragraph("+15 levels", table_cell), Paragraph("1.35x (+35%)", table_cell)]
    ]
    t_rarity = Table(rarity_table_data, colWidths=[2.2 * inch, 2.2 * inch, 2.6 * inch])
    t_rarity.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_rarity)
    story.append(Spacer(1, 15))

    # ================= SECTION 7 & 8: BOOSTERS & ECONOMY =================
    story.append(Paragraph("7. CONSUMABLE BOOSTERS SHOP", h1_style))
    story.append(Paragraph("Purchase single-use tactical boosters from <code>/shop</code> and equip via <code>/booster</code> (Max 2 active boosters):", body_style))
    
    booster_table_data = [
        [Paragraph("<b>Booster</b>", table_header), Paragraph("<b>Price</b>", table_header), Paragraph("<b>Tactical Effect</b>", table_header)],
        [Paragraph("Tyre Blanket Warmer", table_cell), Paragraph("1,500¢", table_cell), Paragraph("-0.15s Qualifying Lap Pace advantage", table_cell)],
        [Paragraph("ERS High-Flow Injector", table_cell), Paragraph("2,000¢", table_cell), Paragraph("+1 Lap extra ERS boost during races", table_cell)],
        [Paragraph("Heavy Duty Radiator", table_cell), Paragraph("1,200¢", table_cell), Paragraph("-30% engine thermal heat buildup", table_cell)]
    ]
    t_booster = Table(booster_table_data, colWidths=[2.2 * inch, 1.2 * inch, 3.6 * inch])
    t_booster.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_booster)
    story.append(Spacer(1, 15))

    story.append(Paragraph("8. ECONOMY & EARNING CREDITS", h1_style))
    story.append(Paragraph("• <b>Daily Login Bonus:</b> <code>/daily</code> awards 500¢ flat once per 24h.", bullet_style))
    story.append(Paragraph("• <b>Team Job:</b> <code>/work</code> awards 250 - 600¢ random once per 24h.", bullet_style))
    story.append(Paragraph("• <b>Chat Messages Passive:</b> 25¢ per message (1,000¢ daily cap).", bullet_style))
    story.append(Paragraph("• <b>Voice Channel Passive:</b> 15¢ per minute unmuted & undeafened (1,500¢ daily cap).", bullet_style))
    story.append(Paragraph("• <b>GP Winner / Podium:</b> P1: 5,000¢, P2: 3,000¢, P3: 1,500¢ (500¢ base participation).", bullet_style))
    story.append(Paragraph("• <b>AI Rival Defeat:</b> +500¢ bonus for finishing ahead of designated AI rival.", bullet_style))
    story.append(Spacer(1, 15))

    # ================= SECTION 9 & 10: RACING & GRAND PRIX =================
    story.append(Paragraph("9. RACING MODES & GRAND PRIX EVENTS", h1_style))
    story.append(Paragraph("<b>1v1 Duels & Wagers</b>", h2_style))
    story.append(Paragraph("• <code>/race &lt;opponent&gt;</code> -- Instant head-to-head racing duel with live telemetry updates.", bullet_style))
    story.append(Paragraph("• <code>/bet &lt;opponent&gt; &lt;amount&gt;</code> -- High-stakes duel where winner takes the doubled credit pot.", bullet_style))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Grand Prix Weekend Lifecycle (500¢ Entry Fee)</b>", h2_style))
    story.append(Paragraph("1. <b>Registration:</b> Players join with <code>/joinrace</code> (500¢ entry fee). Leave with <code>/leaverace</code> for a full refund.", bullet_style))
    story.append(Paragraph("2. <b>Qualifying (Q1 -&gt; Q2 -&gt; Q3):</b> Knockout format qualifying determines the starting grid.", bullet_style))
    story.append(Paragraph("3. <b>Race Simulation:</b> Lap-by-lap simulation featuring dynamic weather radar, DRS overtaking, Safety Car/VSC deployments, and live pit strategy management (<code>/strategy</code>, <code>/pit</code>).", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Points Distribution Table</b>", h2_style))
    
    points_table_data = [
        [Paragraph("<b>Position</b>", table_header), Paragraph("<b>GP Points</b>", table_header), Paragraph("<b>Sprint Points</b>", table_header)],
        [Paragraph("P1", table_cell), Paragraph("25", table_cell), Paragraph("8", table_cell)],
        [Paragraph("P2", table_cell), Paragraph("18", table_cell), Paragraph("7", table_cell)],
        [Paragraph("P3", table_cell), Paragraph("15", table_cell), Paragraph("6", table_cell)],
        [Paragraph("P4", table_cell), Paragraph("12", table_cell), Paragraph("5", table_cell)],
        [Paragraph("P5", table_cell), Paragraph("10", table_cell), Paragraph("4", table_cell)],
        [Paragraph("P6", table_cell), Paragraph("8", table_cell), Paragraph("3", table_cell)],
        [Paragraph("P7", table_cell), Paragraph("6", table_cell), Paragraph("2", table_cell)],
        [Paragraph("P8", table_cell), Paragraph("4", table_cell), Paragraph("1", table_cell)],
        [Paragraph("P9 / P10", table_cell), Paragraph("2 / 1", table_cell), Paragraph("--", table_cell)],
        [Paragraph("Fastest Lap", table_cell), Paragraph("+1 (Top 10 only)", table_cell), Paragraph("+1 (Top 10 only)", table_cell)]
    ]
    t_points = Table(points_table_data, colWidths=[2.2 * inch, 2.4 * inch, 2.4 * inch])
    t_points.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_points)
    story.append(Spacer(1, 15))

    # ================= SECTION 17: ADMIN SUITE & COMMAND REGISTRY =================
    story.append(Paragraph("17. ADMIN SUITE & SERVER MANAGEMENT", h1_style))
    story.append(Paragraph("Comprehensive administrative controls auto-granted to Server Owners, Discord Administrators, users with the 'Admin' role, or designated Game Admins:", body_style))
    
    admin_cmd_table = [
        [Paragraph("<b>Command</b>", table_header), Paragraph("<b>Administrative Function & Description</b>", table_header)],
        [Paragraph("<code>/admin gp [laps]</code>", table_cell), Paragraph("Open Grand Prix Admin Control Panel -- schedule track, run Q1/Q2/Q3, launch race, or cancel.", table_cell)],
        [Paragraph("<code>/admin sprint [laps]</code>", table_cell), Paragraph("Open Sprint Race Weekend Admin Panel.", table_cell)],
        [Paragraph("<code>/admin setstat &lt;user&gt; &lt;stat&gt; &lt;val&gt;</code>", table_cell), Paragraph("Set any driver skill (1 - 100) or garage part level (1 - 20).", table_cell)],
        [Paragraph("<code>/admin give &lt;user&gt; &lt;amount&gt;</code>", table_cell), Paragraph("Grant credits to a player profile.", table_cell)],
        [Paragraph("<code>/admin remove &lt;user&gt; &lt;amount&gt;</code>", table_cell), Paragraph("Deduct credits from a player profile.", table_cell)],
        [Paragraph("<code>/admin resetprofile &lt;user&gt;</code>", table_cell), Paragraph("Reset a player profile to default starting values.", table_cell)],
        [Paragraph("<code>/admin deleteuser &lt;user&gt;</code>", table_cell), Paragraph("Permanently delete a player's profile and wipe all DB records. <i>(Fully Operational)</i>", table_cell)],
        [Paragraph("<code>/admin resetstandings</code>", table_cell), Paragraph("Reset server WDC championship points to 0.", table_cell)],
        [Paragraph("<code>/admin broadcast &lt;message&gt;</code>", table_cell), Paragraph("Post announcement embed to channel with optional @everyone / @here.", table_cell)],
        [Paragraph("<code>/admin dbbackup</code>", table_cell), Paragraph("Trigger timestamped backup of the SQLite database.", table_cell)],
        [Paragraph("<code>/admin addadmin / removeadmin / listadmins</code>", table_cell), Paragraph("Manage bot Game Admin permissions for users.", table_cell)]
    ]
    t_admin = Table(admin_cmd_table, colWidths=[2.5 * inch, 4.5 * inch])
    t_admin.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_admin)
    story.append(Spacer(1, 15))

    # ================= SECTION 19: COMPLETE COMMAND REGISTRY =================
    story.append(Paragraph("19. COMPLETE COMMAND REGISTRY (46 COMMANDS)", h1_style))
    story.append(Paragraph("<b>Player Commands (20 Commands)</b>", h2_style))
    story.append(Paragraph("<code>/start</code>, <code>/profile</code>, <code>/garage</code>, <code>/upgradeshop</code>, <code>/upgrade</code>, <code>/inventory</code>, <code>/repairs</code>, <code>/repair</code>, <code>/train</code>, <code>/practice</code>, <code>/daily</code>, <code>/work</code>, <code>/crate</code>, <code>/open</code>, <code>/shop</code>, <code>/booster</code>, <code>/race</code>, <code>/bet</code>, <code>/leaderboard</code>, <code>/help</code>", body_style))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Race Event Commands (7 Commands)</b>", h2_style))
    story.append(Paragraph("<code>/joinrace</code>, <code>/leaverace</code>, <code>/grid</code>, <code>/standings</code>, <code>/results</code>, <code>/strategy</code>, <code>/pit</code>", body_style))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Admin Suite Commands (13 Commands)</b>", h2_style))
    story.append(Paragraph("<code>/admin setstat</code>, <code>/admin give</code>, <code>/admin remove</code>, <code>/admin resetprofile</code>, <code>/admin deleteuser</code>, <code>/admin resetstandings</code>, <code>/admin broadcast</code>, <code>/admin dbbackup</code>, <code>/admin addadmin</code>, <code>/admin removeadmin</code>, <code>/admin listadmins</code>, <code>/admin gp</code>, <code>/admin sprint</code>", body_style))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Season Management Commands (6 Commands)</b>", h2_style))
    story.append(Paragraph("<code>/season create</code>, <code>/season add_race</code>, <code>/season add_sprint_race</code>, <code>/season calendar</code>, <code>/season end</code>, <code>/season cancel</code>", body_style))
    
    story.append(Spacer(1, 15))

    # ================= SECTION 20: DATABASE SCHEMA & ARCHITECTURE =================
    story.append(Paragraph("20. DATABASE SCHEMA & ARCHITECTURE", h1_style))
    story.append(Paragraph("Built on SQLite with WAL-mode concurrency and foreign keys. Modular architecture split into 5 Cogs:", body_style))
    story.append(Paragraph("• <b>AdminCog (cogs/admin.py):</b> Admin controls, season management, GP panels.", bullet_style))
    story.append(Paragraph("• <b>GarageCog (cogs/garage.py):</b> Onboarding, profile cards, garage upgrades, inventory, repairs.", bullet_style))
    story.append(Paragraph("• <b>EconomyCog (cogs/economy.py):</b> Daily/work economy, crates, shop boosters, driver training, leaderboards, bets.", bullet_style))
    story.append(Paragraph("• <b>RacingCog (cogs/racing.py):</b> 1v1 duels, GP lifecycle, Q1/Q2/Q3 qualifying, telemetry views.", bullet_style))
    story.append(Paragraph("• <b>SimulatorCog (cogs/simulator.py):</b> Track mastery practice sessions, help system.", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated manual at: {filename}")

if __name__ == "__main__":
    out_dir = r"C:\Users\kusha\Downloads"
    out_file = os.path.join(out_dir, "GAME MANUAL.pdf")
    create_manual_pdf(out_file)
    
    # Also write copy to workspace root
    local_file = os.path.join(r"c:\Users\kusha\Desktop\DISCORD GRAND PRIX", "DISCORD_GRAND_PRIX_MASTER_GUIDE.pdf")
    create_manual_pdf(local_file)
