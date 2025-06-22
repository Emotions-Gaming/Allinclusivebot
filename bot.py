import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# ENV-Variablen laden (Railway: Variablen im Dashboard)
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID"))  # GUILD_ID MUSS gesetzt sein!

# --- Discord Intents ---
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True  # Nur setzen, wenn Bot auch auf Messages reagieren muss

# --- Bot-Objekt ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Ready Event ---
@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        # 1. Alle bisherigen Guild-Commands löschen
        await bot.tree.sync(guild=guild)  # Initiales Sync, falls leer
        await bot.tree.clear_commands(guild=guild)  # Wirklich alle raus!
        await bot.tree.sync(guild=guild)  # Jetzt neu aufbauen!
        print(f"🟢 Slash-Commands gelöscht & neu registriert für Guild-ID {GUILD_ID}")
    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren der Commands: {e}")
    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    print("Alle Extensions geladen und ready!")

# --- Main Funktion zum Laden der Extensions ---
async def main():
    extensions = [
        "persist",
        "permissions",
        "setupbot",      # <- Optional: nur aktiv, wenn du das Setup-System nutzt!
        "translation",
        "strike",
        "wiki",
        "schicht",
        "alarm"
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"🧩 Extension geladen: {ext}")
        except Exception as e:
            print(f"❌ Fehler beim Laden von {ext}: {e}")
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Bot konnte nicht gestartet werden: {e}")

# --- Bot-Start ---
if __name__ == "__main__":
    asyncio.run(main())
