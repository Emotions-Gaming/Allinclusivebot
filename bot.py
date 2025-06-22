import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# ENV-Variablen laden
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID"))

# Intents setzen (passe ggf. an deine Anforderungen an)
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

# Bot-Objekt
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)

        # Erst Guild-Commands löschen, dann neu syncen
        bot.tree.clear_commands(guild=guild)  # KEIN await!
        await bot.tree.sync(guild=guild)
        print(f"🟢 Slash-Commands gelöscht & neu registriert für Guild-ID {GUILD_ID}")

    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren der Commands: {e}")
    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    print("Alle Extensions geladen und ready!")

async def main():
    extensions = [
        "persist",      # Backup-System
        "permissions",  # Command-Permissions-System
        "setupbot",     # Guided Admin Setup
        "translation",  # Übersetzungssystem
        "strike",       # Strikesystem
        "wiki",         # Wiki-System
        "schicht",      # Schichtsystem
        "alarm"         # Alarm-System
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

if __name__ == "__main__":
    asyncio.run(main())
