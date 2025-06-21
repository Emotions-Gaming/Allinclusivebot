import os
import shutil
import discord
from discord import app_commands
from discord.ext import commands
from utils import is_admin  # falls du das zentral nutzen willst

DATA_FILES = [
    "profiles.json", "translation_log.json", "translator_menu.json",
    "strike_data.json", "strike_list.json", "strike_roles.json", "strike_autorole.json",
    "wiki_pages.json", "wiki_backup.json",
    "schicht_config.json", "schicht_rights.json",
    "alarm_config.json"
]

DATA_BACKUP_DIR = "railway_data_backup"

def ensure_persistence():
    """Backup vorhandener Daten in DATA_BACKUP_DIR"""
    if not os.path.isdir(DATA_BACKUP_DIR):
        os.makedirs(DATA_BACKUP_DIR, exist_ok=True)
    for f in DATA_FILES:
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(DATA_BACKUP_DIR, f))
    # Restore falls Dateien fehlen (beim Neustart/Update)
    for f in DATA_FILES:
        src = os.path.join(DATA_BACKUP_DIR, f)
        if not os.path.exists(f) and os.path.exists(src):
            shutil.copy2(src, f)

def restore_persistence():
    """Kopiere alle Daten aus DATA_BACKUP_DIR zurück ins Hauptverzeichnis."""
    if not os.path.isdir(DATA_BACKUP_DIR):
        return
    for f in DATA_FILES:
        src = os.path.join(DATA_BACKUP_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, f)

class PersistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        ensure_persistence()  # Sofort Backup/Restore prüfen

    @app_commands.command(name="backupnow", description="Backup aller wichtigen Bot-Daten jetzt durchführen (Railway/Host)")
    async def backupnow(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        ensure_persistence()
        await interaction.response.send_message("Backup aller Daten durchgeführt!", ephemeral=True)

    @app_commands.command(name="restorenow", description="Restore aller Bot-Daten aus Backup (Railway/Host)")
    async def restorenow(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        restore_persistence()
        await interaction.response.send_message("Restore aus Backup durchgeführt!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PersistCog(bot))
