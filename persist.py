# persist.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands, tasks
import os
import aiofiles
import asyncio
from datetime import datetime, timezone
import utils

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
PERSIST_PATH = "persistent_data"
BACKUP_ROOT = "railway_data_backup"
LOG_CHANNEL_PATH = os.path.join(PERSIST_PATH, "persist_log_channel.json")  # Speichert optional den Log-Channel

# Hier alle kritischen Dateien eintragen (nur Filenamen, keine Pfade)
DATA_FILES = [
    "strike_data.json",
    "strike_roles.json",
    "strike_autorole.json",
    "schicht_config.json",
    "alarm_config.json",
    "profiles.json",
    "translation_log.json",
    "translator_prompt.json",
    "translator_menu.json",
    "trans_category.json",
    "translator_log.json",
    "wiki_pages.json",
    "wiki_backup.json",
    "wiki_main_channel.json",
    "setup_config.json",
    "commands_permissions.json"
]

# ===== Helper =====
def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

async def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"[persist.py] Fehler beim Anlegen von {path}: {e}")

async def get_log_channel(bot):
    cfg = await utils.load_json(LOG_CHANNEL_PATH, {})
    if "log_channel_id" in cfg:
        chan = bot.get_channel(cfg["log_channel_id"])
        return chan
    return None

# ===== Persist Cog =====

class PersistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.automatic_backup_interval = 4  # in Stunden (anpassbar)
        self.automatic_backup.start()

    async def cog_load(self):
        await self.restore_missing_files()  # Automatisches Restore beim Start

    async def restore_missing_files(self):
        await ensure_dir(PERSIST_PATH)
        await ensure_dir(BACKUP_ROOT)
        restored = 0
        for fname in DATA_FILES:
            live = os.path.join(PERSIST_PATH, fname)
            backup = os.path.join(BACKUP_ROOT, fname)
            if not os.path.exists(live) and os.path.exists(backup):
                await utils.atomic_copy(backup, live)
                restored += 1
        print(f"[persist.py] Automatisch {restored} Dateien beim Start restauriert.")

    # -------------- Commands --------------

    @app_commands.command(
        name="backupnow",
        description="Erstellt sofort ein vollständiges Backup aller Bot-Daten (Admin-Only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def backup_now(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)

        timestamp = get_timestamp()
        backup_dir = os.path.join(BACKUP_ROOT, timestamp)
        await ensure_dir(backup_dir)

        copied = 0
        missing = []
        for fname in DATA_FILES:
            src = os.path.join(PERSIST_PATH, fname)
            dst = os.path.join(backup_dir, fname)
            if os.path.exists(src):
                await utils.atomic_copy(src, dst)
                copied += 1
            else:
                missing.append(fname)

        # Optional: aktuelles Set als "latest" zusätzlich kopieren (direkt im root)
        for fname in DATA_FILES:
            src = os.path.join(PERSIST_PATH, fname)
            dst = os.path.join(BACKUP_ROOT, fname)
            if os.path.exists(src):
                await utils.atomic_copy(src, dst)

        await utils.send_success(
            interaction,
            text=f"Backup abgeschlossen: **{copied}** Dateien gesichert (`{timestamp}`)\n{'⚠️ Folgende Dateien fehlten: ' + ', '.join(missing) if missing else ''}"
        )
        await self.log_action(f"Backup durchgeführt ({copied} Dateien, {timestamp}).")

    @app_commands.command(
        name="restorenow",
        description="Stellt alle Daten aus dem letzten Backup wieder her (Admin-Only, überschreibt alles!)."
    )
    @app_commands.guilds(MY_GUILD)
    async def restore_now(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)

        copied = 0
        missing = []
        for fname in DATA_FILES:
            src = os.path.join(BACKUP_ROOT, fname)
            dst = os.path.join(PERSIST_PATH, fname)
            if os.path.exists(src):
                await utils.atomic_copy(src, dst)
                copied += 1
            else:
                missing.append(fname)
        await utils.send_ephemeral(
            interaction,
            text=f"Restore abgeschlossen: **{copied}** Dateien wiederhergestellt.\n{'⚠️ Folgende Dateien fehlen im Backup: ' + ', '.join(missing) if missing else ''}\n\n**Bot-Neustart empfohlen!**",
            emoji="♻️",
            color=discord.Color.blurple()
        )
        await self.log_action(f"Restore durchgeführt ({copied} Dateien). Neustart empfohlen.")

    @app_commands.command(
        name="persistlogchannel",
        description="Setzt den Log-Channel für Persistenz-Events."
    )
    @app_commands.guilds(MY_GUILD)
    async def set_log_channel(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await utils.save_json(LOG_CHANNEL_PATH, {"log_channel_id": channel.id})
        await utils.send_success(interaction, f"Persistenz-Log-Channel gesetzt: {channel.mention}")

    # -------------- Automatisches Backup --------------

    @tasks.loop(hours=4)
    async def automatic_backup(self):
        await self.backup_task()

    @automatic_backup.before_loop
    async def before_automatic_backup(self):
        await self.bot.wait_until_ready()

    async def backup_task(self):
        timestamp = get_timestamp()
        backup_dir = os.path.join(BACKUP_ROOT, timestamp)
        await ensure_dir(backup_dir)
        copied = 0
        for fname in DATA_FILES:
            src = os.path.join(PERSIST_PATH, fname)
            dst = os.path.join(backup_dir, fname)
            if os.path.exists(src):
                await utils.atomic_copy(src, dst)
                copied += 1
        # Aktuelles Set als "latest" kopieren
        for fname in DATA_FILES:
            src = os.path.join(PERSIST_PATH, fname)
            dst = os.path.join(BACKUP_ROOT, fname)
            if os.path.exists(src):
                await utils.atomic_copy(src, dst)
        # Optional Log-Channel-Info
        await self.log_action(f"Automatisches Backup ({copied} Dateien, {timestamp}).")

    # -------------- Logging-Helper --------------

    async def log_action(self, text):
        logchan = await get_log_channel(self.bot)
        if logchan:
            embed = discord.Embed(
                description=f"🗂️ **Persistenz-Event**\n{text}\n`{get_timestamp()}`",
                color=discord.Color.teal()
            )
            try:
                await logchan.send(embed=embed)
            except Exception as e:
                print(f"[persist.py] Fehler beim Schreiben in Logchannel: {e}")

    # -------------- Setup --------------
    # Nochmal: setup.py-style Registrierung
async def setup(bot):
    await bot.add_cog(PersistCog(bot))
