import discord
from discord.ext import commands
import os
import sys
import asyncio

from dotenv import load_dotenv
load_dotenv()

import logging

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
PURPLE = "\033[95m"
GRAY = "\033[90m"

def log_info(msg):    print(f"{GREEN}[INFO]{RESET} {msg}")
def log_success(msg): print(f"{BOLD}{GREEN}✅ {msg}{RESET}")
def log_warning(msg): print(f"{YELLOW}⚠️ [WARN] {msg}{RESET}")
def log_error(msg):   print(f"{RED}❌ [ERROR] {msg}{RESET}")
def log_event(msg):   print(f"{CYAN}{msg}{RESET}")
def log_header(msg):  print(f"{PURPLE}{BOLD}{msg}{RESET}")

def log_raw(msg):     print(msg)

logging.basicConfig(level=logging.INFO, format='%(message)s')

# ==== WARNUNG für fehlende PyNaCl (Voice Support) ====
try:
    import nacl
except ImportError:
    log_warning("PyNaCl ist NICHT installiert – Voice/Moves/Streams werden NICHT unterstützt!")

if not TOKEN or not GUILD_ID:
    log_error("ENV DISCORD_TOKEN und GUILD_ID müssen gesetzt sein!")
    sys.exit(1)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "persist",
    "permissions",
    "setupbot",
    "translation",
    "strike",
    "wiki",
    "schicht",
    "alarm",
]

async def log_registered_commands():
    # Listet ALLE Commands (guild & global) mit Typ sauber auf!
    guild_obj = discord.Object(id=GUILD_ID)
    try:
        guild_cmds = await bot.tree.fetch_commands(guild=guild_obj)
        global_cmds = await bot.tree.fetch_commands()  # Kein Guild = global!
        if guild_cmds:
            log_header(f"\nRegistrierte Slash-Commands für Guild {GUILD_ID}:")
            for c in guild_cmds:
                log_info(f"  - /{c.name} | {c.description or '(keine Beschreibung)'} | Type: GUILD")
        else:
            log_warning("Keine Slash-Commands auf Guild-Ebene registriert!")
        if global_cmds:
            log_header("Achtung: Global registrierte Slash-Commands:")
            for c in global_cmds:
                log_warning(f"  - /{c.name} | {c.description or '(keine Beschreibung)'} | Type: GLOBAL")
        else:
            log_info("Keine globalen Slash-Commands gefunden.")
    except Exception as e:
        log_error(f"Fehler beim Auflisten der registrierten Commands: {e}")

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    log_header("\n--- SPACE GUIDE BOT START ---")
    log_event(f"🟣 discord.py Version: {discord.__version__}")
    log_info(f"🤖 Bot connected as {bot.user} in guild: {guild.name} ({guild.id})")

    # Extensions laden
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            log_success(f"Extension geladen: {cog}")
        except Exception as e:
            log_error(f"Fehler beim Laden von Extension {cog}: {e}")

    # WICHTIG: Erst jetzt syncen!
    try:
        # NICHT: bot.tree.clear_commands(...)
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        log_success("Slash-Commands neu für Guild registriert!")
    except Exception as e:
        log_error(f"Fehler beim SlashCommand-Sync: {e}")

    await log_registered_commands()
    log_success(f"BOT ONLINE: {bot.user} ({bot.user.id}) – Alle Systeme bereit!\n")


@bot.tree.error
async def on_app_command_error(interaction, error):
    try:
        await interaction.response.send_message(
            f"❌ Fehler: {error}", ephemeral=True
        )
    except Exception:
        pass
    log_error(f"SlashCommand-Error: {error}")

async def shutdown():
    log_info("🔄 Shutdown-Handler: Speichere persistente Daten...")
    await asyncio.sleep(0.5)
    log_info("🔴 BOT STOPPED")

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        asyncio.run(shutdown())
        sys.exit(0)
    except Exception as e:
        log_error(f"BOT CRASHED: {e}")
        sys.exit(1)
