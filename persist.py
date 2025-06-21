import os
import shutil
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILES = [
    "profiles.json", "translation_log.json", "translator_menu.json",
    "strike_data.json", "strike_list.json", "strike_roles.json", "strike_autorole.json",
    "wiki_pages.json", "wiki_backup.json",
    "schicht_config.json", "schicht_rights.json",
    "alarm_config.json"
]

DATA_BACKUP_DIR = "railway_data_backup"

def ensure_persistence():
    # Backup vorhandener Daten (beim Herunterfahren/Speichern)
    if not os.path.isdir(DATA_BACKUP_DIR):
        os.mkdir(DATA_BACKUP_DIR)
    for f in DATA_FILES:
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(DATA_BACKUP_DIR, f))
    # Restore falls Dateien fehlen (beim Neustart/Update)
    for f in DATA_FILES:
        src = os.path.join(DATA_BACKUP_DIR, f)
        if not os.path.exists(f) and os.path.exists(src):
            shutil.copy2(src, f)

class PersistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="backupnow", description="Backup aller wichtigen Bot-Daten jetzt durchführen (Railway/Host)")
    async def backupnow(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        ensure_persistence()
        await interaction.response.send_message("Backup aller Daten durchgeführt!", ephemeral=True)

async def setup(bot):
    ensure_persistence()   # Sofort sicherstellen!
    await bot.add_cog(PersistCog(bot))
