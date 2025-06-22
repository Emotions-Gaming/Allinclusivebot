import os
import logging
import discord
from discord.ext import commands
import asyncio

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("command_diag")

# --- Config ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
EXTENSIONS = [
    'utils',
    'permissions',
    'persist',
    'strike',
    'schicht',
    'alarm',
    'wiki',
    'translation',
    'setupbot',
]

# --- Bot & Intents ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def main():
    # 1) Lade alle Extensions
    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            logger.info("Extension geladen: %s", ext)
        except Exception as e:
            logger.exception("Fehler beim Laden von Extension %s: %s", ext, e)

    # 2) Warte, bis der Bot verbunden ist
    await bot.wait_until_ready()

    # 3) Liste globale Commands
    global_cmds = await bot.tree.fetch_commands()
    logger.info("Globale Slash-Commands (insgesamt %d):", len(global_cmds))
    for cmd in global_cmds:
        logger.info("  • /%s – %s", cmd.name, cmd.description)

    # 4) Liste Guild-spezifische Commands
    guild_obj = discord.Object(id=GUILD_ID)
    guild_cmds = await bot.tree.fetch_commands(guild=guild_obj)
    logger.info("Guild-only Slash-Commands in Guild %s (insgesamt %d):", GUILD_ID, len(guild_cmds))
    for cmd in guild_cmds:
        logger.info("  • /%s – %s", cmd.name, cmd.description)

    # 5) Herunterfahren
    await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
