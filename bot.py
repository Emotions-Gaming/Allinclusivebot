import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    try:
        print("🔄 Entferne alle Slash-Commands auf Guild:", GUILD_ID)
        await bot.tree.sync(guild=guild)
        old = await bot.tree.fetch_commands(guild=guild)
        print(f"  Vorher: {len(old)} Slash-Commands vorhanden.")
        # Fix: clear_commands ist kein awaitable!
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        after = await bot.tree.fetch_commands(guild=guild)
        print(f"  Nachher: {len(after)} Slash-Commands vorhanden.")
        if not after:
            print("✅ Alle Slash-Commands erfolgreich gelöscht.")
        else:
            print("⚠️ Einige Commands konnten nicht gelöscht werden:", [c.name for c in after])
    except Exception as e:
        print("❌ Fehler beim Command-Wipe:", e)

    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    print("Beende Prozess in 5 Sekunden…")
    await asyncio.sleep(5)
    exit(0)

if __name__ == "__main__":
    asyncio.run(bot.start(DISCORD_TOKEN))
