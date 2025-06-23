# permissions.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
PERMISSIONS_PATH = os.path.join("persistent_data", "commands_permissions.json")

class PermissionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===== Interne Helper =====

    async def get_allowed_roles(self, command_name: str) -> list[int]:
        """Liefert erlaubte Rollen-IDs für einen Command."""
        perms = await utils.load_json(PERMISSIONS_PATH, {})
        return perms.get(command_name, [])

    async def set_allowed_roles(self, command_name: str, role_ids: list[int]):
        perms = await utils.load_json(PERMISSIONS_PATH, {})
        perms[command_name] = role_ids
        await utils.save_json(PERMISSIONS_PATH, perms)

    async def has_command_permission(self, member: discord.Member, command_name: str) -> bool:
        # Admins haben IMMER alle Rechte
        if utils.is_admin(member):
            return True
        allowed = await self.get_allowed_roles(command_name)
        return utils.has_any_role(member, allowed)

    # ===== Slash Commands =====

    @app_commands.command(
        name="befehlpermission",
        description="Gibt einer Rolle das Recht, einen Command zu nutzen (Admin only)."
    )
    @app_commands.guilds(GUILD_ID)
    async def add_permission(self, interaction: Interaction, command: str, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        command = command.lower()
        # Existiert der Command?
        if not any(cmd.name == command for cmd in self.bot.tree.get_commands(guild=discord.Object(GUILD_ID))):
            return await utils.send_error(interaction, f"Command `{command}` existiert nicht!")
        # Hole aktuelle Rollen
        allowed = await self.get_allowed_roles(command)
        if role.id in allowed:
            return await utils.send_error(interaction, f"{role.mention} darf `{command}` bereits nutzen.")
        allowed.append(role.id)
        await self.set_allowed_roles(command, allowed)
        await utils.send_success(interaction, f"{role.mention} darf jetzt `{command}` ausführen.\nVergiss nicht `/refreshpermissions` auszuführen!")

    @app_commands.command(
        name="befehlpermissionremove",
        description="Entzieht einer Rolle das Recht für einen Command (Admin only)."
    )
    @app_commands.guilds(GUILD_ID)
    async def remove_permission(self, interaction: Interaction, command: str, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        command = command.lower()
        allowed = await self.get_allowed_roles(command)
        if role.id not in allowed:
            return await utils.send_error(interaction, f"{role.mention} hatte kein Recht für `{command}`.")
        allowed.remove(role.id)
        await self.set_allowed_roles(command, allowed)
        await utils.send_success(interaction, f"{role.mention} darf `{command}` nun nicht mehr nutzen.\nBitte `/refreshpermissions` ausführen!")

    @app_commands.command(
        name="befehlpermissions",
        description="Zeigt die erlaubten Rollen für einen Command (Admin only)."
    )
    @app_commands.guilds(GUILD_ID)
    async def list_permissions(self, interaction: Interaction, command: str):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        command = command.lower()
        allowed = await self.get_allowed_roles(command)
        rolestr = utils.pretty_role_list(interaction.guild, allowed)
        await utils.send_ephemeral(
            interaction,
            text=f"**Zugriff für `{command}`:**\n{rolestr}",
            emoji="🛡️",
            color=discord.Color.blurple()
        )

    @app_commands.command(
        name="refreshpermissions",
        description="Synchronisiert alle Slash-Command-Rechte auf dem Server (Admin only)."
    )
    @app_commands.guilds(GUILD_ID)
    async def refresh_permissions(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        perms = await utils.load_json(PERMISSIONS_PATH, {})
        cmds = self.bot.tree.get_commands(guild=discord.Object(GUILD_ID))
        count = 0
        for cmd in cmds:
            roles = perms.get(cmd.name, [])
            # Baue CommandPermissions
            # Admins haben IMMER Zugriff
            admin_ids = [r.id for r in interaction.guild.roles if r.permissions.administrator]
            allow_roles = list(set(roles + admin_ids))
            try:
                await cmd.edit(
                    guild=interaction.guild,
                    default_member_permissions=None,
                    dm_permission=False,
                    # roles dürfen explizit den Command nutzen
                    # Discord.py v2.4+: roles param als Liste von discord.Role (NICHT role IDs!)
                    roles=[interaction.guild.get_role(rid) for rid in allow_roles if interaction.guild.get_role(rid)]
                )
                count += 1
            except Exception as e:
                print(f"[permissions.py] Fehler beim Sync für {cmd.name}: {e}")
        await utils.send_success(interaction, f"**{count} Slash-Commands** wurden für diese Guild synchronisiert.\nAlle Berechtigungen sind jetzt aktiv.")

    # ===== Helper für andere Cogs (exportiert) =====

    async def user_has_permission(self, member: discord.Member, command_name: str) -> bool:
        """Kann von anderen Cogs importiert werden."""
        return await self.has_command_permission(member, command_name)

# ==== Cog Setup ====

async def setup(bot):
    await bot.add_cog(PermissionsCog(bot))

# ===== HowTo (für andere Cogs): =====
# import permissions
# await permissions.user_has_permission(member, "strikegive")
# if nicht erlaubt: await utils.send_permission_denied(interaction)
