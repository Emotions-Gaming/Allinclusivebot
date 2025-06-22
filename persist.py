import os
import shutil
import discord
from discord.ext import commands
from discord import app_commands
from utils import is_admin

# Liste aller wichtigen persistenten Dateien (immer erweitern, falls neue Systeme dazukommen)
DATA_FILES = [
    "profiles.json", "translation_log.json", "translator_menu.json",
    "strike_data.json", "strike_roles.json", "strike_autorole.json",
    "wiki_pages.json", "wiki_backup.json",
    "schicht_config.json", "schicht_rights.json",
    "alarm_config.json", "alarm_log.json",
    "commands_permissions.json",
]
DATA_BACKUP_DIR = "railway_data_backup"
PERSIST_PATH = "persistent_data"

def ensure_persistence():
    # Backup vorhandener Daten (beim Herunterfahren/Speichern)
    if not os.path.isdir(DATA_BACKUP_DIR):
        os.mkdir(DATA_BACKUP_DIR)
    for f in DATA_FILES:
        src = os.path.join(PERSIST_PATH, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DATA_BACKUP_DIR, f))
    # Restore falls Dateien fehlen (beim Neustart/Update)
    for f in DATA_FILES:
        src = os.path.join(DATA_BACKUP_DIR, f)
        dst = os.path.join(PERSIST_PATH, f)
        if not os.path.exists(dst) and os.path.exists(src):
            shutil.copy2(src, dst)

class PersistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        for f in DATA_FILES:
            src = os.path.join(DATA_BACKUP_DIR, f)
            dst = os.path.join(PERSIST_PATH, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
        await interaction.response.send_message("Restore abgeschlossen! (Restart nötig!)", ephemeral=True)

async def setup(bot):
    ensure_persistence()
    await bot.add_cog(PersistCog(bot))
