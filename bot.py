import os
import logging
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("command_diag")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"== Command Diagnostic for Bot {bot.user} ==")

    # 1) Globale Commands
    global_cmds = await bot.tree.fetch_commands()  # lädt alle globalen Slash-Commands
    logger.info(f"Globale Slash-Commands (insgesamt {len(global_cmds)}):")
    for cmd in global_cmds:
        logger.info(f"  • /{cmd.name}: {cmd.description}")

    # 2) Guild-spezifische Commands
    guild = discord.Object(id=GUILD_ID)
    guild_cmds = await bot.tree.fetch_commands(guild=guild)
    logger.info(f"Guild-only Slash-Commands in Guild {GUILD_ID} (insgesamt {len(guild_cmds)}):")
    for cmd in guild_cmds:
        logger.info(f"  • /{cmd.name}: {cmd.description}")

    # Beende danach
    await bot.close()

if __name__ == "__main__":
    bot.run(TOKEN)
