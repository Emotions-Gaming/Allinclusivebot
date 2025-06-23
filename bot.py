import os
import sys
import logging
import discord
from discord.ext import commands
from discord import app_commands
import traceback
from datetime import datetime
from dotenv import load_dotenv
from discord import Interaction
from discord import Interaction



from permissions import has_permission_for

# === Logging Setup ===
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname}] {message}",
    style='{',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("bot")

def log_event(msg, color=""):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "gray": "\033[90m",
        "end": "\033[0m"
    }
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code = colors.get(color, "")
    endc = colors["end"] if code else ""
    print(f"{code}[{ts}] {msg}{endc}")

# === ENV-Laden ===
log_event("🔄 Starte Space Guide Bot Initialisierung...", "blue")
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
if not DISCORD_TOKEN:
    log_event("❌ ENV DISCORD_TOKEN fehlt! Abbruch.", "red")
    sys.exit(1)
if not GUILD_ID:
    log_event("❌ ENV GUILD_ID fehlt! Abbruch.", "red")
    sys.exit(1)
GUILD_ID = int(GUILD_ID)
log_event("✅ ENV OK: TOKEN & GUILD_ID", "green")

try:
    log_event(f"🟣 discord.py v{discord.__version__} detected", "blue")
except Exception:
    log_event("❗ discord.py Version nicht gefunden!", "red")

# === Discord Intents & Bot-Objekt ===
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
log_event("🛡️  Discord Intents aktiviert (members, guilds, message_content)", "gray")

bot = commands.Bot(
    command_prefix="!",  # Nur für eventuelle Notfälle, sonst /-Commands
    intents=intents,
    help_command=None
)

# === Extensions/Cogs ===
COGS = [
    "persist",
    "permissions",
    "setupbot",
    "schicht",
    "strike",
    "translation",
    "alarm",
    "wiki"
]

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    log_event("=================================================", "gray")
    log_event(f"🟢 Bot ready: {bot.user} / ID: {bot.user.id}", "green")
    log_event(f"🌐 Guild-Only: {guild.name if guild else 'NICHT GEFUNDEN'} (ID: {GUILD_ID})", "yellow")
    log_event("📦 Lade Extensions:", "blue")

    # Commands vorher aufräumen (keine Ghosts)
    try:
        log_event("🔄 Entferne alte Slash-Commands auf Guild…", "gray")
        # Wichtig: Das entfernt ALLE Commands für die GUILD und setzt sie neu!
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        log_event("🟢 Slash-Commands nur noch GUILD-basiert!", "green")
    except Exception as ex:
        log_event(f"❌ Fehler beim Command-Sync: {ex}", "red")
        traceback.print_exc()

    # Extensions laden
    loaded = []
    failed = []
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            log_event(f"🧩 Extension geladen: {cog}", "green")
            loaded.append(cog)
        except Exception as ex:
            log_event(f"❌ Fehler beim Laden von {cog}: {ex}", "red")
            traceback.print_exc()
            failed.append(cog)
    log_event("=================================================", "gray")

    # Command-Listing
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        log_event(f"📋 Registrierte Slash-Commands auf diesem Server ({len(synced)}):", "blue")
        for cmd in synced:
            try:
                perms = []
                if hasattr(cmd, "default_member_permissions") and cmd.default_member_permissions:
                    perms = [str(p) for p in cmd.default_member_permissions]
                log_event(f"  - /{cmd.name} | {cmd.description or '-'} | Typ: {cmd.type} | Permissions: {', '.join(perms) if perms else 'Custom'}", "gray")
            except Exception:
                continue
    except Exception as ex:
        log_event(f"❌ Fehler beim Auflisten der Commands: {ex}", "red")
        traceback.print_exc()

    if loaded:
        log_event(f"✅ Alle Extensions geladen: {', '.join(loaded)}", "green")
    if failed:
        log_event(f"⚠️  Fehlerhafte Extensions: {', '.join(failed)}", "red")

    log_event(f"✅ BOT ONLINE: {bot.user}", "green")
    log_event("=================================================", "gray")

# === Global Error-Handler für Commands/Events ===
@bot.event
async def on_command_error(ctx, error):
    log_event(f"❌ Command Error: {error}", "red")
    traceback.print_exc()

@bot.event
async def on_error(event_method, *args, **kwargs):
    log_event(f"❌ Unbehandelter Fehler in {event_method}", "red")
    traceback.print_exc()

# === Start ===
if __name__ == "__main__":
    try:
        log_event("🚀 Starte Bot…", "blue")
        bot.run(DISCORD_TOKEN)
    except Exception as ex:
        log_event(f"❌ Bot konnte nicht gestartet werden: {ex}", "red")
        traceback.print_exc()
        sys.exit(1)
