import os
import discord
from discord.ext import commands
from discord import app_commands
from utils import load_json, save_json, is_admin

COMMAND_PERMS_FILE = "commands_permissions.json"
PERM_DATA_PATH = "persistent_data"

# --- Hilfsfunktionen für Permission-Handling ---
def get_perms():
    path = os.path.join(PERM_DATA_PATH, COMMAND_PERMS_FILE)
    return load_json(path, {})

def save_perms(perms):
    path = os.path.join(PERM_DATA_PATH, COMMAND_PERMS_FILE)
    save_json(path, perms)

class PermissionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="refreshpermissions", description="Alle Slash-Command-Rechte neu vergeben/aktualisieren (Admin)")
    async def refreshpermissions(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        perms = get_perms()
        guild = interaction.guild

        # Gehe alle registrierten Commands durch
        cmds = [cmd for cmd in self.bot.tree.get_commands(guild=guild) or self.bot.tree.get_commands()]
        for command in cmds:
            c_name = command.name
            allowed_role_ids = perms.get(c_name, [])
            # Setze Permissions (Discord 2.3+ macht das per CommandSync und Permissions-API)
            try:
                # Per Default: nur für Admins verfügbar
                await command.edit(guild=guild, default_permission=False)
                # Wenn Rollen gesetzt, gib nur diesen Zugriff
                if allowed_role_ids:
                    perms_obj = [
                        discord.app_commands.CommandPermission(role_id, True, command) for role_id in allowed_role_ids
                    ]
                    await command.edit(guild=guild, permissions=perms_obj)
            except Exception as e:
                print(f"Fehler beim Setzen der Permissions für {c_name}: {e}")

        await interaction.response.send_message("Permissions für alle Commands wurden aktualisiert.", ephemeral=True)

    @app_commands.command(name="befehlpermission", description="Rolle zu einem Befehl hinzufügen (Admin)")
    @app_commands.describe(command="Name des Befehls", role="Rolle die erlaubt werden soll")
    async def befehlpermission(self, interaction: discord.Interaction, command: str, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        perms = get_perms()
        if command not in perms:
            perms[command] = []
        if role.id not in perms[command]:
            perms[command].append(role.id)
            save_perms(perms)
        await interaction.response.send_message(
            f"Rolle {role.mention} kann jetzt `{command}` verwenden. Bitte `/refreshpermissions` ausführen!", ephemeral=True
        )

    @app_commands.command(name="befehlpermissionremove", description="Rolle von einem Befehl entfernen (Admin)")
    @app_commands.describe(command="Name des Befehls", role="Rolle die entfernt werden soll")
    async def befehlpermissionremove(self, interaction: discord.Interaction, command: str, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        perms = get_perms()
        if command in perms and role.id in perms[command]:
            perms[command].remove(role.id)
            save_perms(perms)
        await interaction.response.send_message(
            f"Rolle {role.mention} kann `{command}` nicht mehr verwenden. Bitte `/refreshpermissions` ausführen!", ephemeral=True
        )

    @app_commands.command(name="befehlpermissions", description="Zeigt die erlaubten Rollen für einen Befehl (Admin)")
    @app_commands.describe(command="Name des Befehls")
    async def befehlpermissions(self, interaction: discord.Interaction, command: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        perms = get_perms()
        guild = interaction.guild
        roles = [guild.get_role(rid) for rid in perms.get(command, [])]
        role_mentions = [role.mention for role in roles if role]
        if not role_mentions:
            return await interaction.response.send_message(f"Keine Rollen für `{command}` gesetzt.", ephemeral=True)
        await interaction.response.send_message(
            f"Folgende Rollen dürfen `{command}` verwenden: {' '.join(role_mentions)}", ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(PermissionCog(bot))
