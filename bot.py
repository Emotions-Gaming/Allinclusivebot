import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands

# ----------------------------- #
# 1. Logging Setup
# ----------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

# ----------------------------- #
# 2. Lade Umgebungsvariablen
# ----------------------------- #
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID", 0))

if not DISCORD_TOKEN:
    logging.error("DISCORD_TOKEN fehlt in .env oder Railway.")
    exit(1)
if not GUILD_ID:
    logging.warning("GUILD_ID ist nicht gesetzt! Slash-Command-Sync evtl. fehlerhaft.")

# ----------------------------- #
# 3. Intents & Bot-Objekt
# ----------------------------- #
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.presences = True  # Für Online-Status-Checks

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------- #
# 4. Events: Startup & Fehler
# ----------------------------- #
@bot.event
async def on_ready():
    logging.info(f"Bot online als {bot.user} (ID: {bot.user.id})")
    # Optional: Slash-Command Sync (lokal ODER GUILD-spezifisch)
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await bot.tree.sync(guild=guild)
            logging.info(f"Slash-Commands für Guild {GUILD_ID} synchronisiert.")
        else:
            await bot.tree.sync()
            logging.info(f"Slash-Commands global synchronisiert.")
    except Exception as e:
        logging.error(f"Fehler beim Slash-Command-Sync: {e}")

@bot.event
async def on_command_error(ctx, error):
    # Für !-Befehle
    await ctx.send(f"❌ Fehler: {error}")

@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(f"Unbehandelter Fehler im Event {event}:", exc_info=True)

# ----------------------------- #
# 5. Lade Extensions (Module)
# ----------------------------- #
async def load_extensions():
    for ext in [
        "utils",          # Hilfsfunktionen
        "translation",    # Übersetzungs-Modul
        "strike",         # Strike/Verwarnsystem
        "wiki",           # Wiki-System
        "schicht",        # Schichtwechsel/Übergabe
        "alarm",          # Alarm-/Notfall-System
        # "persist"       # Wenn persistente Daten in eigenem Modul (optional)
    ]:
        try:
            await bot.load_extension(ext)
            logging.info(f"Extension '{ext}' geladen.")
        except Exception as e:
            logging.warning(f"Extension '{ext}' konnte nicht geladen werden: {e}")

# ----------------------------- #
# 6. Bot starten
# ----------------------------- #
async def main():
    await load_extensions()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
