import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# ENV-Variablen laden
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # Deine Guild-ID aus .env

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild_obj = discord.Object(id=GUILD_ID)
    try:
        print(f"🔄 Synchronisiere Slash-Commands NUR für Guild: {GUILD_ID} ...")
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"🟢 {len(synced)} Guild-Slash-Commands registriert für Guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Fehler beim Guild-Sync der Commands: {e}")

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
            # Cogs laden (ganz normal, Commands sind eh auf Guild beschränkt)
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
