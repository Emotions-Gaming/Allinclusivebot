import os
import logging
import discord
from discord.ext import commands

# --- Logging-Konfiguration ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('bot')

# --- Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

logger.info("Aktiviere Intents: message_content=%s, members=%s, guilds=%s",
            intents.message_content, intents.members, intents.guilds)

# --- Umgebungsvariablen ---
token = os.getenv('DISCORD_TOKEN')
if not token:
    logger.error("Umgebungsvariable DISCORD_TOKEN fehlt. Abbruch.")
    exit(1)

guild_id_str = os.getenv('GUILD_ID')
if not guild_id_str:
    logger.error("Umgebungsvariable GUILD_ID fehlt. Abbruch.")
    exit(1)

guild_id = int(guild_id_str)
logger.info("Verwende GUILD_ID=%s", guild_id)

# --- Bot-Instanz ---
bot = commands.Bot(command_prefix='!', intents=intents)
bot.config = {'GUILD_ID': guild_id}

# --- Extensions laden ---
extensions = [
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
logger.info("Extension-Liste: %s", extensions)

import asyncio

async def main():
    # Extensions laden (async)
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            logger.info("Extension geladen: %s", ext)
        except Exception as e:
            logger.exception("Fehler beim Laden von Extension %s: %s", ext, e)
    logger.info("Starte Bot...")
    try:
        await bot.start(token)
    except Exception as e:
        logger.exception("Bot konnte nicht gestartet werden: %s", e)

@bot.event
async def on_ready():
    logger.info("=== Bot ist bereit ===")
    logger.info("Bot-Benutzer: %s#%s (ID: %s)", bot.user.name, bot.user.discriminator, bot.user.id)
    # Sync Slash-Commands nur für die Guild
    try:
        await bot.tree.sync(guild=discord.Object(id=guild_id))
        commands = bot.tree.get_commands(guild=discord.Object(id=guild_id))
        logger.info("Slash-Commands synchronisiert für Guild %s. Anzahl: %d", guild_id, len(commands))
        for cmd in commands:
            perms = getattr(cmd, 'permissions', [])
            role_ids = [p.id for p in perms if p.type == discord.app_commands.PermissionType.role]
            logger.info("- /%s: %s (Roles: %s)", cmd.name, cmd.description, role_ids)
    except Exception as e:
        logger.exception("Fehler beim Sync der Slash-Commands: %s", e)

# --- Programmstart ---
if __name__ == '__main__':
    asyncio.run(main())
