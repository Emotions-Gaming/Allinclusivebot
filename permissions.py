# permissions.py

import os
import json
from discord.ext import commands
from discord import app_commands, Interaction, Role

PERMISSIONS_FILE = "persistent_data/commands_permissions.json"

def load_permissions():
    """Lädt die Command-Permissions aus JSON (oder gibt {} zurück)."""
    if not os.path.exists(PERMISSIONS_FILE):
        return {}
    try:
        with open(PERMISSIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_permissions(data):
    os.makedirs(os.path.dirname(PERMISSIONS_FILE), exist_ok=True)
    with open(PERMISSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def has_permission_for(command_name):
    """
    Universal-Permission-Check für Slash-Commands.
    Benutzen in jedem Command als:
    @has_permission_for("strikegive")
    async def strikegive(...): ...
    """
    async def predicate(interaction: Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        perms = load_permissions()
        allowed_roles = perms.get(command_name, [])
        if not allowed_roles:
            return False
        user_role_ids = [role.id for role in getattr(interaction.user, "roles", [])]
        return any(role_id in user_role_ids for role_id in allowed_roles)
    return app_commands.check(predicate)

class PermissionsCog(commands.Cog):
    """Cog mit Commands zum Setzen und Anzeigen der Berechtigungen."""

    def __init__(self, bot):
        self.bot = bot
        # Datei initial anlegen, falls nicht vorhanden
        if not os.path.exists(PERMISSIONS_FILE):
            save_permissions({})

    @app_commands.command(
        name="befehlpermission",
        description="Gibt einer Rolle Zugriff auf einen Slash-Command (nur Admins)"
    )
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die Zugriff erhalten soll")
    @has_permission_for("befehlpermission")
    async def befehlpermission(self, interaction: Interaction, command: str, role: Role):
        """Fügt einer Rolle Zugriff auf einen Command hinzu."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        perms = load_permissions()
        allowed = set(perms.get(command, []))
        allowed.add(role.id)
        perms[command] = list(allowed)
        save_permissions(perms)
        await interaction.response.send_message(
            f"✅ Rolle {role.mention} hat nun Zugriff auf /{command}.", ephemeral=True
        )

    @app_commands.command(
        name="befehlpermissionremove",
        description="Entzieht einer Rolle den Zugriff auf einen Slash-Command (nur Admins)"
    )
    @app_commands.describe(command="Name des Befehls (ohne Slash)", role="Rolle, die entfernt werden soll")
    @has_permission_for("befehlpermissionremove")
    async def befehlpermissionremove(self, interaction: Interaction, command: str, role: Role):
        """Entzieht einer Rolle den Zugriff auf einen Command."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        perms = load_permissions()
        allowed = set(perms.get(command, []))
        if role.id in allowed:
            allowed.remove(role.id)
            perms[command] = list(allowed)
            save_permissions(perms)
            await interaction.response.send_message(
                f"✅ Rolle {role.mention} wurde von /{command} entfernt.", ephemeral=True
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
    @has_permission_for("befehlpermissions")
    async def befehlpermissions(self, interaction: Interaction, command: str):
        """Zeigt alle Rollen, die Zugriff auf einen Command haben."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Du hast keine Adminrechte!", ephemeral=True)
            return

        perms = load_permissions()
        role_ids = perms.get(command, [])
        if not role_ids:
            await interaction.response.send_message(
                f"🔒 Kein Zugriff gesetzt für /{command} (außer Admins)", ephemeral=True
            )
            return

        guild = interaction.guild
        mentions = []
        for rid in role_ids:
            role = guild.get_role(rid)
            if role:
                mentions.append(role.mention)
        if mentions:
            await interaction.response.send_message(
                f"🔒 Zugriff auf /{command}: {' '.join(mentions)}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🔒 Zugriff auf /{command}: (Rollen nicht gefunden!)", ephemeral=True
            )

# === Setup-Funktion für Extension-Loader ===
async def setup(bot):
    await bot.add_cog(PermissionsCog(bot))
