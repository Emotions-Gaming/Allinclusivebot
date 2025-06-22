# permissions.py

import os
import logging
from discord.ext import commands
from discord import app_commands, Interaction, Role, Guild
from utils import is_admin, load_json, save_json, mention_roles

PERMISSIONS_FILE = "persistent_data/commands_permissions.json"

# GUILD_ID laden (aus ENV oder Setup-Datei)
try:
    GUILD_ID = int(os.environ.get("GUILD_ID"))
except Exception:
    GUILD_ID = None  # muss beim Laden geprüft werden!

def get_guild(bot: commands.Bot) -> Guild:
    """Hilfsfunktion, gibt das Guild-Objekt zurück."""
    if GUILD_ID is None:
        return None
    return bot.get_guild(GUILD_ID)

class PermissionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(PERMISSIONS_FILE):
            save_json(PERMISSIONS_FILE, {})  # Initialisieren

    def _load(self):
        return load_json(PERMISSIONS_FILE, {})

    def _save(self, data):
        save_json(PERMISSIONS_FILE, data)

    @app_commands.command(
        name="refreshpermissions",
        description="Synchronisiert alle Slash-Command-Berechtigungen laut Config (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    async def refreshpermissions(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        guild = get_guild(self.bot)
        if not guild:
            await interaction.response.send_message("❌ Guild nicht gefunden (GUILD_ID prüfen)!", ephemeral=True)
            return

        config = self._load()
        synced, failed = 0, 0

        for command in self.bot.tree.get_commands(guild=guild):
            name = command.name
            allowed_roles = config.get(name, [])
            try:
                # Rolle-Objekte holen (können ungültig sein)
                role_objs = [guild.get_role(rid) for rid in allowed_roles]
                role_ids = [r.id for r in role_objs if r]
                if role_ids:
                    perms = app_commands.default_permissions()
                    await command.edit(guild=guild, default_member_permissions=perms, roles=role_ids)
                else:
                    # Keine Rollen → nur Admins sehen den Command
                    perms = app_commands.default_permissions()
                    await command.edit(guild=guild, default_member_permissions=perms, roles=[])
                synced += 1
            except Exception as e:
                logging.error(f"Fehler beim Sync von Command {name}: {e}")
                failed += 1

        await interaction.response.send_message(
            f"🔄 Permissions refresh abgeschlossen: {synced} Command(s) aktualisiert, {failed} Fehler.", ephemeral=True
        )

    @app_commands.command(
        name="befehlpermission",
        description="Gibt einer Rolle Zugriff auf einen Slash-Command (nur Admins)"
    )
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die Zugriff erhalten soll")
    @app_commands.guilds(GUILD_ID)
    async def befehlpermission(self, interaction: Interaction, command: str, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        config = self._load()
        allowed = set(config.get(command, []))
        allowed.add(role.id)
        config[command] = list(allowed)
        self._save(config)
        await interaction.response.send_message(
            f"✅ Rolle {role.mention} hat nun Zugriff auf /{command}. (Bitte /refreshpermissions ausführen!)", ephemeral=True
        )

    @app_commands.command(
        name="befehlpermissionremove",
        description="Entzieht einer Rolle den Zugriff auf einen Slash-Command (nur Admins)"
    )
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die entfernt werden soll")
    @app_commands.guilds(GUILD_ID)
    async def befehlpermissionremove(self, interaction: Interaction, command: str, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        config = self._load()
        allowed = set(config.get(command, []))
        if role.id in allowed:
            allowed.remove(role.id)
            config[command] = list(allowed)
            self._save(config)
            await interaction.response.send_message(
                f"✅ Rolle {role.mention} wurde von /{command} entfernt. (Bitte /refreshpermissions ausführen!)", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ Diese Rolle hatte keinen Zugriff auf /{command}.", ephemeral=True
            )

    @app_commands.command(
        name="befehlpermissions",
        description="Zeigt alle erlaubten Rollen für einen Command"
    )
    @app_commands.describe(command="Name des Befehls (ohne Slash)")
    @app_commands.guilds(GUILD_ID)
    async def befehlpermissions(self, interaction: Interaction, command: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        guild = get_guild(self.bot)
        config = self._load()
        role_ids = config.get(command, [])
        if role_ids:
            mentions = mention_roles(guild, role_ids)
            await interaction.response.send_message(
                f"🔒 Zugriff auf /{command}: {mentions}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🔒 Kein Zugriff gesetzt für /{command} (außer Admins)", ephemeral=True
            )

# === Setup-Funktion für Extension-Loader ===

async def setup(bot):
    await bot.add_cog(PermissionsCog(bot))
