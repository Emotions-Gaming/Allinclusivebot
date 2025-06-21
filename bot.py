import os
import sys
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands

# ------------- ENV Variablen laden -------------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ------------- Intents / Bot-Objekt -------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------- Extension-Liste -------------
COGS = [
    "utils",
    "strike",
    "schicht",
    "translation",
    "wiki",
    "alarm"
]

# ------------- Railway Persistent Volume Support -------------
DATA_DIR = "persistent_data"
if not os.path.isdir(DATA_DIR):
    os.makedirs(DATA_DIR)

def backup_data():
    # Beispiel-Backup (ggf. mit shutil oder ähnlichem erweitern)
    pass

def restore_data():
    # Beispiel-Restore (ggf. mit shutil oder ähnlichem erweitern)
    pass

# ------------- Startup-Handler -------------
@bot.event
async def on_ready():
    print(f"[Bot Online] Angemeldet als: {bot.user}")
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            await bot.tree.sync(guild=guild)
            print("[Slash Commands] Mit Guild-Scope synchronisiert!")
        else:
            await bot.tree.sync()
            print("[Slash Commands] Global synchronisiert!")
    except Exception as e:
        print(f"[Error] Slash-Command-Sync: {e}")

    # Backup/Restore-Daten, falls nötig (optional)
    restore_data()

# ------------- Error Handling (global für alle Commands) -------------
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"❌ Fehler: {str(error)}")

@bot.event
async def on_application_command_error(interaction, error):
    await interaction.response.send_message(f"❌ Fehler: {str(error)}", ephemeral=True)

# ------------- Cog/Extension Loader -------------
async def main():
    # Extensions/Cogs laden
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"[Extension] '{cog}' geladen.")
        except Exception as e:
            print(f"[Extension] Fehler beim Laden von '{cog}': {e}")

    # Bot starten
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
