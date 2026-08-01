<div align="center">

# 🏎️ Discord Grand Prix

**The Ultimate Formula 1 Racing & Team Management Bot for Discord**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-v2.0%2B-blueviolet.svg)](https://github.com/Rapptz/discord.py)
[![SQLite3](https://img.shields.io/badge/database-SQLite3-lightgrey.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Live Tutorial](https://img.shields.io/badge/Live_Tutorial-Online-brightgreen.svg?style=for-the-badge&logo=render)](https://discord-grand-prix.onrender.com/)

---

### 🌐 Live Interactive Academy & Web Simulator
**Try the Interactive Race Simulator & Command Guide Live:**  
👉 **[https://discord-grand-prix.onrender.com/](https://discord-grand-prix.onrender.com/)** 👈

---

</div>

## 📌 Overview

**Discord Grand Prix** is an advanced, immersive Formula 1 management and racing simulator for Discord servers. Players build their own racing teams, train drivers, upgrade 6 distinct car components across 20 tiers, manage tyre compounds, react to live rain and Safety Cars in real-time, and compete in server-wide World Driver Championships (WDC).

---

## ✨ Key Features

### 🚦 Live Race Telemetry & Physics Simulator
* **Dynamic Tyre Degradation**: Choose between **Soft** (Fast, high wear), **Medium** (Balanced), **Hard** (Durable), and **Intermediates** (Rain tyres).
* **Live Weather Engine**: Dynamic rain triggers mid-race! Switch to Intermediates to avoid **15-second per lap time penalties**.
* **Safety Car Deployments**: Random incidents trigger Safety Cars, reducing pit stop time from **11 seconds down to 6 seconds**.
* **Interactive DM Telemetry**: Receive live lap-by-lap updates in DMs with interactive **PIT NEXT LAP** buttons and pacing controls.

### ⚙️ Garage & Car Component Engineering
* **6 Upgradable Components**: Engine, Aerodynamics, Tyres, ERS, Reliability, and Pit Crew (Levels 1 to 20).
* **5 Rarity Tiers**: Common (+0%), Uncommon (+5%), Rare (+12%), Epic (+22%), and Legendary (+35% efficiency).
* **Wear & Damage System**: Engine and tyre wear accumulate over races — use `/repair` to restore performance.

### 👨‍✈️ Driver Skills & Track Mastery
* **6 Trainable Driver Attributes**: Pace, Qualifying, Wet Skill, Consistency, Aggression, and Overtaking (1 to 100).
* **Track Mastery System**: Run `/practice` on official tracks (Monaco, Spa, Silverstone, Monza, etc.) to unlock permanent lap-time bonuses.

### 💰 Deep Economy & Passive Income
* **Active Earnings**: `/daily` (500¢) and `/work` (200 - 800¢ daily rewards).
* **Passive Voice & Text Income**: Earn **25 credits per chat message** and **15 credits per minute** spent in server Voice Channels.
* **Loot Crates System**: Unbox crates (`/open rookie`) to win exclusive car parts, skill boosters, and credit drops.

### 🛡️ Anti-Cheat & Real F1 Constructor Protection
* **Forbidden Team Names**: Built-in anti-evasion filter prevents players from claiming official F1 team names (`Red Bull`, `Ferrari`, `Haas`, `Mercedes`, `McLaren`, etc.).
* **Leetspeak Invariance**: Automatically normalizes and blocks bypass attempts like `f3rr4r1`, `ferr@ri`, `r3dbull`, `R3d Bu11`, `h44s`, and `m3rc3d3s`.
* **Admin Suite**: Comprehensive admin control commands (`/admin deleteuser`, `/admin resetprofile`, `/admin resetstandings`).

---

## 🎮 Command Reference

### 🚀 Getting Started & Economy
| Command | Description |
| :--- | :--- |
| `/start <team_name>` | Create your racing team and claim 1,500 starting credits. |
| `/profile` | Display your team standings, wallet, level, and XP progress. |
| `/daily` | Claim your 500¢ daily login bonus. |
| `/work` | Complete daily engineering work to earn 200 - 800 credits. |
| `/open <crate>` | Unbox loot crates for rare car parts and bonus cash. |

### ⚙️ Garage & Training
| Command | Description |
| :--- | :--- |
| `/garage` | Inspect your car component levels, wear, and stats. |
| `/upgrade <part>` | Upgrade Engine, Aero, Tyres, ERS, Reliability, or Pit Crew. |
| `/train <skill>` | Train Pace, Qualifying, Wet Skill, Consistency, Aggression, or Overtaking (400¢/pt). |
| `/repair` | Repair engine or tyre damage accrued during races. |
| `/practice` | Run practice sessions on official tracks to build permanent Track Mastery. |

### 🏎️ Racing & Strategy
| Command | Description |
| :--- | :--- |
| `/joinrace` | Enter the upcoming server Grand Prix (500¢ entry fee). |
| `/strategy` | Configure tyre selection (Soft/Medium/Hard) and pace mode (Aggressive/Balanced/Conservative). |
| `/pit` | Call your driver into the pit lane on the next lap. |
| `/duel <user>` | Challenge a rival manager to a 1v1 sprint race. |

### 🛡️ Game Admin Commands (Admin Role Required)
| Command | Description |
| :--- | :--- |
| `/admin deleteuser <user>` | Permanently delete a user profile so they can register fresh. |
| `/admin resetprofile <user>` | Reset a user's stats, garage, and money back to default starting levels. |
| `/admin resetstandings` | Reset all WDC championship points for the server. |
| `/admin addadmin <user>` | Grant Game Admin privileges to a team manager. |

---

## 💻 Installation & Setup

### Prerequisites
* **Python 3.10+** installed
* A **Discord Bot Token** (from the [Discord Developer Portal](https://discord.com/developers/applications))

### 1. Clone Repository & Install Dependencies
```bash
git clone https://github.com/your-username/discord-grand-prix.git
cd discord-grand-prix
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the project root directory:
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_target_server_guild_id
ADMIN_ROLE_NAME=Admin
DATABASE_PATH=game.db
```

### 3. Run the Bot
```bash
python bot.py
```

---

## 🧪 Running Unit Tests

The codebase includes a full automated test suite covering database transactions, race physics, credit rewards, and anti-evasion team checks:

```bash
python -m pytest
```

---

## 🌐 Tutorial Web Dashboard

The repository includes a web tutorial dashboard located in the `tutorial/` folder. It features:
* **Step-by-Step Command Guide**: Visual walkthrough for new managers.
* **Stat & Upgrade Calculator**: Interactive slider preview for car components and driver skills.
* **Live Race Physics Simulator**: Real-time canvas simulation with live weather changes, tyre wear, and pit stops.

*Hosted Live on Render:* **[https://discord-grand-prix.onrender.com/](https://discord-grand-prix.onrender.com/)**

---

## 📜 License

This project is open-source under the **MIT License**.
