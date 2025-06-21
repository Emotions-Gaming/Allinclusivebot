# bot.py
import os
import sys
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands

# === ENV & GLOBALS ===
load_dotenv()  # .env für lokale Entwicklung, Railway nimmt Environment-Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID") or "1249813174731931740")  # Sollte als Zahl (ID) gesetzt sein!

if not DISCORD_TOKEN or not GUILD_ID:
    print("Fehlende Environment-Variablen! Bitte DISCORD_TOKEN und GUILD_ID setzen.")
    sys.exit(1)

# === Discord Bot Intents ===
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === Load Extensions (Module/Systems) ===
# Passe diese Namen exakt an deine Dateinamen OHNE .py-Endung an:
EXTENSIONS = [
    "translation",
    "strike",
    "wiki",
    "schicht",
    "alarm",
    # "utils"   # Falls du Hilfsfunktionen hast und als Cog gebaut hast
]

async def load_all_extensions():
    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"Erweiterung {ext} geladen.")
        except Exception as e:
            print(f"Fehler beim Laden von {ext}: {e}")

# === Railway Persistenz (Backup/Restore nach jedem Start/Stop) ===
import shutil

DATA_DIR = "persistent_data"
DATA_FILES = [
    "profiles.json", "translation_log.json", "translator_menu.json",
    "strike_data.json", "strike_list.json", "strike_roles.json", "strike_autorole.json",
    "wiki_pages.json", "wiki_backup.json",
    "schicht_config.json", "schicht_rights.json",
    "alarm_config.json", "alarm_log.json",
    "trans_category.json"
]
def ensure_persistent_data():
    # Alle relevanten JSON-Files sichern & zurückkopieren
    os.makedirs(DATA_DIR, exist_ok=True)
    # Restore (falls im App-Root fehlt, aber im DATA_DIR vorhanden)
    for file in DATA_FILES:
        src = os.path.join(DATA_DIR, file)
        if not os.path.exists(file) and os.path.exists(src):
            shutil.copy2(src, file)
    # Backup (alles im DATA_DIR sichern)
    for file in DATA_FILES:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(DATA_DIR, file))
import atexit
atexit.register(ensure_persistent_data)

# === Slash-Commands einmalig nach Start synchronisieren ===
@bot.event
async def on_ready():
    ensure_persistent_data()
    try:
        await bot.tree.sync()
        print("Slash-Commands synchronisiert!")
    except Exception as e:
        print(f"Fehler bei Command-Sync: {e}")
    print(f"Bot ist online als {bot.user}.")

# === Main Bot Start ===
async def main():
    await load_all_extensions()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
