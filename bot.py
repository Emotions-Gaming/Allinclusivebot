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

async def wipe_commands():
    # 1. Globale Commands löschen
    print("🔄 Entferne ALLE (globale + guild) Slash-Commands...")
    print("  → Lösche globale Commands...")
    global_before = await bot.tree.fetch_commands()
    print(f"  Vorher global: {len(global_before)}")
    bot.tree.clear_commands()
    await bot.tree.sync()
    global_after = await bot.tree.fetch_commands()
    print(f"  Nachher global: {len(global_after)}")

    # 2. Guild-Commands löschen
    guild = discord.Object(id=GUILD_ID)
    print("  → Lösche Guild-Commands...")
    guild_before = await bot.tree.fetch_commands(guild=guild)
    print(f"  Vorher guild: {len(guild_before)}")
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)
    guild_after = await bot.tree.fetch_commands(guild=guild)
    print(f"  Nachher guild: {len(guild_after)}")

    print("✅ Wipe abgeschlossen (Discord-Caching kann 1-60 Minuten dauern!)")
    print("Beende Prozess in 5 Sekunden…")
    await asyncio.sleep(5)
    exit(0)

@bot.event
async def on_ready():
    await wipe_commands()
    print(f"✅ Bot online: {bot.user} ({bot.user.id})")

if __name__ == "__main__":
    asyncio.run(bot.start(DISCORD_TOKEN))
