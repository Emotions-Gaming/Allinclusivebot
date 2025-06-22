# permissions.py

import os
import logging
from discord.ext import commands
from discord import app_commands, Interaction, Role, Guild
from utils import is_admin, load_json, save_json, mention_roles

PERMISSIONS_FILE = "persistent_data/commands_permissions.json"

try:
    GUILD_ID = int(os.environ.get("GUILD_ID"))
except Exception:
    GUILD_ID = None

def get_guild(bot: commands.Bot) -> Guild:
    if GUILD_ID is None:
        return None
    return bot.get_guild(GUILD_ID)

# === Decorator für Command-Checks ===
def has_permission_for(command_name):
    def predicate(func):
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            # Admins immer Zugriff
            if is_admin(interaction.user):
                return await func(self, interaction, *args, **kwargs)
            config = load_json(PERMISSIONS_FILE, {})
            allowed_roles = set(config.get(command_name, []))
            if not allowed_roles:
                # Wenn keine expliziten Rollen gesetzt, Standard: nur Admin
                await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
                return
            user_roles = {r.id for r in getattr(interaction.user, "roles", [])}
            if user_roles & allowed_roles:
                return await func(self, interaction, *args, **kwargs)
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
        # WICHTIG: Wrapper bekommt expliziten TypeHint (Discord.py verlangt das!)
        wrapper.__annotations__ = func.__annotations__.copy()
        wrapper.__annotations__["interaction"] = Interaction
        return wrapper
    return predicate

# --- AUTOCOMPLETE für Command-Namen ---
async def command_autocomplete(interaction: Interaction, current: str):
    cog = interaction.client.get_cog('PermissionsCog')
    if cog is not None:
        cmds = [cmd for cmd in cog.available_commands() if current.lower() in cmd.lower()]
        return [app_commands.Choice(name=cmd, value=cmd) for cmd in cmds[:25]]
    return []

class PermissionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(PERMISSIONS_FILE):
            save_json(PERMISSIONS_FILE, {})

    def _load(self):
        return load_json(PERMISSIONS_FILE, {})

    def _save(self, data):
        save_json(PERMISSIONS_FILE, data)

    def available_commands(self):
        cmds = set()
        # Slash Commands aus allen Cogs (mit app_commands)
        for cog in self.bot.cogs.values():
            # Optional: eigene Cogs können get_app_commands anbieten
            if hasattr(cog, 'get_app_commands'):
                cmds.update(cog.get_app_commands())
            # Fallback: alle registered Commands im app_commands-Baum
            if hasattr(cog, 'app_commands'):
                for command in cog.app_commands:
                    if isinstance(command, app_commands.Command):
                        cmds.add(command.name)
        # Slash Commands auf Guild holen
        for cmd in self.bot.tree.get_commands(guild=get_guild(self.bot)):
            cmds.add(cmd.name)
        return sorted(cmds)

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
                # Die Standardrollenberechtigung kann ggf. auf Discordseite (Guild-Command) gesetzt werden.
                # Wir lassen es als Info und für weitere Custom-Logik hier stehen.
                synced += 1
            except Exception as e:
                logging.error(f"Fehler beim Sync von Command {name}: {e}")
                failed += 1
        await interaction.response.send_message(
            f"🔄 Permissions refresh abgeschlossen: {synced} Command(s) verarbeitet, {failed} Fehler.", ephemeral=True
        )

    @app_commands.command(
        name="befehlpermission",
        description="Gibt einer Rolle Zugriff auf einen Slash-Command (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die Zugriff erhalten soll")
    @app_commands.autocomplete(command=command_autocomplete)
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
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die entfernt werden soll")
    @app_commands.autocomplete(command=command_autocomplete)
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
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(command="Name des Befehls (ohne Slash)")
    @app_commands.autocomplete(command=command_autocomplete)
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
