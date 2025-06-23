# bot.py

import discord
from discord.ext import commands
import os
import logging
import sys
import asyncio

# ENV laden
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

if not TOKEN or not GUILD_ID:
    print("❌ ENV DISCORD_TOKEN und GUILD_ID müssen gesetzt sein!")
    sys.exit(1)

# Logging sehr detailiert
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Liste aller Cogs/Extensions – hier NUR Dateinamen ohne .py!
COGS = [
    "persist",
    "permissions",
    "setupbot",
    "translation",
    "strike",
    "wiki",
    "schicht",
    "alarm",
]

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    logging.info(f"🟣 discord.py Version: {discord.__version__}")
    logging.info(f"🔄 Bot connected as {bot.user} in guild: {guild.name} ({guild.id})")

    # Lade Extensions
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logging.info(f"🧩 Extension geladen: {cog}")
        except Exception as e:
            logging.error(f"❌ Fehler beim Laden von Extension {cog}: {e}", exc_info=True)

    # Nur guild-commands, nie global!
    # Lösche und synchronisiere NUR auf GUILD_ID!
    try:
        bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        cmds = await bot.tree.fetch_commands(guild=discord.Object(id=GUILD_ID))
        logging.info(f"🟢 Slash-Commands neu registriert: {[c.name for c in cmds]}")
    except Exception as e:
        logging.error(f"❌ Fehler beim SlashCommand-Sync: {e}", exc_info=True)

    logging.info(f"✅ BOT ONLINE: {bot.user} ({bot.user.id}) – Alle Systeme bereit!")

# Bei Fehlern im Command
@bot.tree.error
async def on_app_command_error(interaction, error):
    try:
        await interaction.response.send_message(
            f"❌ Fehler: {error}", ephemeral=True
        )
    except Exception:
        pass
    logging.error(f"❌ SlashCommand-Error: {error}", exc_info=True)

# Optional: Shutdown-Handler für persistente Daten sichern
async def shutdown():
    logging.info("🔄 Shutdown-Handler: Speichere persistente Daten...")
    # Hier könnten Persist- oder andere Systeme gezielt angesprochen werden
    await asyncio.sleep(0.5)
    logging.info("🔴 BOT STOPPED")

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        asyncio.run(shutdown())
        sys.exit(0)
    except Exception as e:
        logging.error(f"❌ BOT CRASHED: {e}", exc_info=True)
        sys.exit(1)
