import os
import shutil
import discord
from discord import app_commands, Interaction
from discord.ext import tasks
from .utils import load_json, save_json, is_admin
import logging

logger = logging.getLogger(__name__)

# Konfiguration
DATA_FILES = [
    "strike_data.json",
    "schicht_config.json",
    "translator_menu.json",
    "translation_log.json",
    "profiles.json",
    "wiki_pages.json",
    "wiki_backup.json",
    "alarm_config.json",
    "commands_permissions.json",
    "setup_config.json",
]
LIVE_DIR = os.getenv("PERSISTENT_PATH", "persistent_data")
BACKUP_DIR = os.getenv("BACKUP_PATH", "railway_data_backup")

class PersistCog(discord.Cog):
    """Cog für Datenpersistenz und Backup/Restore."""
    def __init__(self, bot: discord.Client):
        self.bot = bot
        os.makedirs(LIVE_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self.auto_backup.start()

    def cog_unload(self):
        self.auto_backup.cancel()

    @tasks.loop(hours=6)
    async def auto_backup(self):
        logger.info("Automatisches Backup gestartet...")
        try:
            for fname in DATA_FILES:
                src = os.path.join(LIVE_DIR, fname)
                dst = os.path.join(BACKUP_DIR, fname)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            logger.info("Automatisches Backup abgeschlossen.")
        except Exception as e:
            logger.error(f"Fehler im automatischen Backup: {e}")

    @auto_backup.before_loop
    async def before_auto(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="backupnow", description="Erstelle sofort ein Backup aller Daten")
    @app_commands.checks.has_permissions(administrator=True)
    async def backupnow(self, interaction: Interaction):
        """Manuelles Backup aller persistenten Daten."""
        try:
            for fname in DATA_FILES:
                src = os.path.join(LIVE_DIR, fname)
                dst = os.path.join(BACKUP_DIR, fname)
                if os.path.isfile(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            await interaction.response.send_message("Backup aller Daten durchgeführt!", ephemeral=True)
        except Exception as e:
            logger.error(f"Fehler beim manuellen Backup: {e}")
            await interaction.response.send_message(f"Fehler beim Backup: {e}", ephemeral=True)

    @app_commands.command(name="restorenow", description="Stelle alle Daten aus dem letzten Backup wieder her")
    @app_commands.checks.has_permissions(administrator=True)
    async def restorenow(self, interaction: Interaction):
        """Restore aller Daten aus dem Backup-Ordner."""
        try:
            for fname in DATA_FILES:
                backup_file = os.path.join(BACKUP_DIR, fname)
                live_file = os.path.join(LIVE_DIR, fname)
                if os.path.isfile(backup_file):
                    os.makedirs(os.path.dirname(live_file), exist_ok=True)
                    shutil.copy2(backup_file, live_file)
                else:
                    logger.warning(f"Keine Backup-Datei für {fname} gefunden.")
            await interaction.response.send_message("Restore abgeschlossen! Bitte Bot neu starten.", ephemeral=True)
        except Exception as e:
            logger.error(f"Fehler beim Restore: {e}")
            await interaction.response.send_message(f"Fehler beim Restore: {e}", ephemeral=True)

@persist = PersistCog

async def setup(bot: discord.Client):
    cog = PersistCog(bot)
    bot.add_cog(cog)
    # Synchronisiere Slash-Commands
    await bot.tree.sync(guild=discord.Object(id=int(bot.config.get('GUILD_ID'))))
