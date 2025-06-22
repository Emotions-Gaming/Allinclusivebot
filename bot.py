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

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        print("🔄 Entferne alte Slash-Commands (guild-only)...")
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"🟢 Slash-Commands gelöscht & neu registriert für Guild-ID {GUILD_ID}")
    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren der Commands: {e}")

    # Nach dem Sync: Liste alle Commands
    print("📋 Registrierte Slash-Commands auf diesem Server:")
    try:
        cmds = await bot.tree.fetch_commands(guild=discord.Object(id=GUILD_ID))
        if not cmds:
            print("⚠️ Keine Commands wurden gefunden!")
        for cmd in cmds:
            print(f"  - /{cmd.name} | Beschreibung: {cmd.description} | Typ: {cmd.type}")
    except Exception as e:
        print(f"❌ Fehler beim Abfragen der registrierten Commands: {e}")

    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    print("Alle Extensions geladen und ready!\n")

async def main():
    extensions = [
        "persist",
        "permissions",
        "setupbot",
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

if __name__ == "__main__":
    asyncio.run(main())
