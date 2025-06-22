import discord
from discord import app_commands, Interaction, Role, Guild
from .utils import load_json, save_json, is_admin

# Pfad zur Permissions-JSON
PERM_FILE = "commands_permissions.json"

class PermissionCog(app_commands.Group):
    """Cog zur Verwaltung von Slash-Command-Rechten."""
    def __init__(self, bot: discord.Client, guild_id: int):
        super().__init__(name="permissions", description="Rechteverwaltung für Slash-Commands")
        self.bot = bot
        self.guild_id = guild_id
        # Lade bestehende Rechte
        self.perm_data: dict[str, list[int]] = load_json(PERM_FILE, {}) or {}

    def save(self):
        save_json(PERM_FILE, self.perm_data)

    async def sync_permissions(self):
        guild: Guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            return
        for command in self.bot.tree.get_commands(guild=guild):
            # Erlaubte Rollen für den Command
            allowed = self.perm_data.get(command.name, [])
            perms = [app_commands.CommandPermission(id=rid, type=app_commands.PermissionType.role, permission=True)
                     for rid in allowed]
            await command.edit(guild=guild, default_permission=False, permissions=perms)

    @app_commands.command(name="befehlpermission", description="Erlaube einer Rolle einen Befehl zu benutzen")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_permission(self, interaction: Interaction, command_name: str, role: Role):
        """
        Fügt eine Rolle in die Liste erlaubter Rollen für `command_name`.
        """
        # Validierung
        cmd = discord.utils.get(self.bot.tree.get_commands(guild=interaction.guild), name=command_name)
        if cmd is None:
            await interaction.response.send_message(f"Befehl `{command_name}` nicht gefunden.", ephemeral=True)
            return
        lst = self.perm_data.setdefault(command_name, [])
        if role.id in lst:
            await interaction.response.send_message("Rolle hat bereits Zugriff.", ephemeral=True)
            return
        lst.append(role.id)
        self.save()
        await interaction.response.send_message(f"Zugriff für `{command_name}` an Rolle {role.mention} hinzugefügt.", ephemeral=True)

    @app_commands.command(name="befehlpermissionremove", description="Entziehe einer Rolle das Recht auf einen Befehl")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_permission(self, interaction: Interaction, command_name: str, role: Role):
        cmd = discord.utils.get(self.bot.tree.get_commands(guild=interaction.guild), name=command_name)
        if cmd is None:
            await interaction.response.send_message(f"Befehl `{command_name}` nicht gefunden.", ephemeral=True)
            return
        lst = self.perm_data.get(command_name, [])
        if role.id not in lst:
            await interaction.response.send_message("Rolle hat keinen Zugriff.", ephemeral=True)
            return
        lst.remove(role.id)
        self.save()
        await interaction.response.send_message(f"Zugriff für `{command_name}` von Rolle {role.mention} entfernt.", ephemeral=True)

    @app_commands.command(name="befehlpermissions", description="Zeigt, welche Rollen Zugriff auf einen Befehl haben")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_permissions(self, interaction: Interaction, command_name: str):
        cmd = discord.utils.get(self.bot.tree.get_commands(guild=interaction.guild), name=command_name)
        if cmd is None:
            await interaction.response.send_message(f"Befehl `{command_name}` nicht gefunden.", ephemeral=True)
            return
        lst = self.perm_data.get(command_name, [])
        if not lst:
            await interaction.response.send_message("Keine Rollen haben Zugriff auf diesen Befehl.", ephemeral=True)
            return
        mentions = [interaction.guild.get_role(rid).mention for rid in lst if interaction.guild.get_role(rid)]
        await interaction.response.send_message(f"Zugriff für `{command_name}` haben: {' '.join(mentions)}", ephemeral=True)

    @app_commands.command(name="refreshpermissions", description="Synchronisiert alle Berechtigungen auf dem Server")
    @app_commands.checks.has_permissions(administrator=True)
    async def refresh(self, interaction: Interaction):
        await self.sync_permissions()
        await interaction.response.send_message("Permissions wurden aktualisiert.", ephemeral=True)

async def setup(bot: discord.Client):
    guild_id = int(bot.config.get('GUILD_ID'))
    cog = PermissionCog(bot, guild_id)
    bot.tree.add_command(cog, guild=discord.Object(id=guild_id))
    await bot.tree.sync(guild=discord.Object(id=guild_id))
    # initial sync
    await cog.sync_permissions()
