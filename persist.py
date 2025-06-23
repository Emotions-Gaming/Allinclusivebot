import os
import shutil
import logging
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from utils import is_admin, load_json, save_json
from permissions import has_permission_for
from discord.interactions import Interaction



# -- Konfiguration
PERSIST_DIR = "persistent_data"
BACKUP_DIR = "railway_data_backup"

DATA_FILES = [
    "strike_data.json",
    "strike_roles.json",
    "strike_autorole.json",
    "schicht_config.json",
    "alarm_config.json",
    "profiles.json",
    "translator_menu.json",
    "translator_prompt.json",
    "trans_category.json",
    "translation_log.json",
    "wiki_pages.json",
    "wiki_backup.json",
    "wiki_main_channel.json",
    "commands_permissions.json",
    "setup_config.json",
    # Neue Dateien hier ergänzen!
]

DATA_FILES = [os.path.join(PERSIST_DIR, f) for f in DATA_FILES]
BACKUP_FILES = [os.path.join(BACKUP_DIR, os.path.basename(f)) for f in DATA_FILES]

def ensure_dirs():
    """Stellt sicher, dass beide Verzeichnisse existieren."""
    for d in (PERSIST_DIR, BACKUP_DIR):
        if not os.path.exists(d):
            os.makedirs(d)

def file_exists(path):
    return os.path.isfile(path)

def backup_now():
    """Kopiert alle Live-Daten ins Backup-Verzeichnis."""
    ensure_dirs()
    for src, dest in zip(DATA_FILES, BACKUP_FILES):
        if file_exists(src):
            shutil.copy2(src, dest)
    logging.info("Backup erfolgreich durchgeführt.")

def restore_now():
    """Kopiert alle Backup-Daten zurück ins Live-Verzeichnis."""
    ensure_dirs()
    for src, dest in zip(BACKUP_FILES, DATA_FILES):
        if file_exists(src):
            shutil.copy2(src, dest)
    logging.info("Restore erfolgreich durchgeführt.")

def restore_missing_files():
    """
    Beim Bot-Start: Falls Datei im Live-System fehlt,
    wird sie (falls vorhanden) aus dem Backup-Verzeichnis wiederhergestellt.
    """
    ensure_dirs()
    for src, dest in zip(BACKUP_FILES, DATA_FILES):
        if not file_exists(dest) and file_exists(src):
            shutil.copy2(src, dest)
            logging.warning(f"{os.path.basename(dest)} fehlte und wurde aus Backup wiederhergestellt.")

class PersistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        restore_missing_files()  # Startup-Check!

    @app_commands.command(
        name="backupnow",
        description="Erstellt sofort ein Backup aller kritischen Daten (nur Admins)"
    )
    @app_commands.guilds(int(os.environ.get("GUILD_ID")))
    @has_permission_for("backupnow")
    async def backupnow(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True)
            return
        try:
            backup_now()
            await interaction.response.send_message("✅ Backup aller Daten erfolgreich durchgeführt!", ephemeral=True)
        except Exception as e:
            logging.error(f"Backup-Fehler: {e}")
            await interaction.response.send_message(f"❌ Fehler beim Backup: {e}", ephemeral=True)

    @app_commands.command(
        name="restorenow",
        description="Überschreibt ALLE Live-Daten mit dem letzten Backup! (nur Admins)"
    )
    @app_commands.guilds(int(os.environ.get("GUILD_ID")))
    @has_permission_for("restorenow")
    async def restorenow(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True)
            return
        try:
            restore_now()
            await interaction.response.send_message(
                "✅ Restore abgeschlossen! (Bitte Bot neu starten!)", ephemeral=True
            )
        except Exception as e:
            logging.error(f"Restore-Fehler: {e}")
            await interaction.response.send_message(f"❌ Fehler beim Restore: {e}", ephemeral=True)

    @app_commands.command(
        name="persiststatus",
        description="Zeigt Status aller Daten-/Backupfiles (nur Admins)"
    )
    @app_commands.guilds(int(os.environ.get("GUILD_ID")))
    @has_permission_for("persiststatus")
    async def persiststatus(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
            return
        ensure_dirs()
        msg = "📦 **Persist/Backup-Status**\n\n"
        for src, bkp in zip(DATA_FILES, BACKUP_FILES):
            exists = "✅" if file_exists(src) else "❌"
            backup = "🟢" if file_exists(bkp) else "⚠️"
            msg += f"`{os.path.basename(src):<28}` {exists} | Backup: {backup}\n"
        await interaction.response.send_message(msg, ephemeral=True)

# === Extension Loader ===
async def setup(bot):
    await bot.add_cog(PersistCog(bot))
