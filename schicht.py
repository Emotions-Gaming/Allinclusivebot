```python
import os
import discord
from discord import app_commands, Interaction, Member, Role, VoiceChannel, TextChannel
from discord.ext import commands
from .utils import load_json, save_json, is_admin
import logging

# Guild-Konstante
GUILD_ID = int(os.getenv("GUILD_ID"))

logger = logging.getLogger(__name__)

# Konfig-Datei
default = {}
CONFIG_FILE = "schicht_config.json"

class SchichtConfig:
    def __init__(self):
        data = load_json(CONFIG_FILE, {}) or {}
        self.roles = data.get("roles", [])
        self.voice_channel = data.get("voice_channel")
        self.log_channel = data.get("log_channel")

    def save(self):
        save_json(CONFIG_FILE, {
            "roles": self.roles,
            "voice_channel": self.voice_channel,
            "log_channel": self.log_channel
        })

class SchichtCog(commands.Cog):
    """Cog für Schichtverwaltung"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = SchichtConfig()

    def user_is_authorized(self, member: Member) -> bool:
        return is_admin(member) or any(role.id in self.config.roles for role in member.roles)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtaddrole", description="Fügt eine Rolle als schichtberechtigt hinzu")
    async def schichtaddrole(self, interaction: Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können Rollen hinzufügen.", ephemeral=True)
            return
        if role.id in self.config.roles:
            await interaction.response.send_message("Rolle ist bereits berechtigt.", ephemeral=True)
            return
        self.config.roles.append(role.id)
        self.config.save()
        await interaction.response.send_message(f"Rolle {role.mention} ist nun schichtberechtigt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtremoverole", description="Entfernt eine schichtberechtigte Rolle")
    async def schichtremoverole(self, interaction: Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können Rollen entfernen.", ephemeral=True)
            return
        if role.id not in self.config.roles:
            await interaction.response.send_message("Rolle war nicht in der Liste.", ephemeral=True)
            return
        self.config.roles.remove(role.id)
        self.config.save()
        await interaction.response.send_message(f"Rolle {role.mention} ist nicht mehr schichtberechtigt.", ephemeral=True)

    # Aliases
    schichtrolerights = schichtaddrole
    schichtroledeleterights = schichtremoverole

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtsetvoice", description="Setzt den Voice-Kanal für schichtübergaben")
    async def schichtsetvoice(self, interaction: Interaction, channel: VoiceChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können den Voice-Kanal setzen.", ephemeral=True)
            return
        self.config.voice_channel = channel.id
        self.config.save()
        await interaction.response.send_message(f"VoiceMaster-Channel gesetzt auf {channel.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtlog", description="Setzt den Log-Kanal für schichtübergaben")
    async def schichtlog(self, interaction: Interaction, channel: TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können den Log-Kanal setzen.", ephemeral=True)
            return
        self.config.log_channel = channel.id
        self.config.save()
        await interaction.response.send_message(f"Log-Channel gesetzt auf {channel.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtinfo", description="Zeigt die aktuelle Schicht-Konfiguration")
    async def schichtinfo(self, interaction: Interaction):
        roles = [interaction.guild.get_role(rid).mention for rid in self.config.roles if interaction.guild.get_role(rid)] or ["Keine"]
        voice = interaction.guild.get_channel(self.config.voice_channel).mention if self.config.voice_channel else "Nicht gesetzt"
        log = interaction.guild.get_channel(self.config.log_channel).mention if self.config.log_channel else "Nicht gesetzt"
        embed = discord.Embed(title="Schicht-Konfiguration")
        embed.add_field(name="Berechtigte Rollen", value=" ".join(roles), inline=False)
        embed.add_field(name="VoiceMaster-Channel", value=voice, inline=True)
        embed.add_field(name="Log-Channel", value=log, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="schichtuebergabe", description="Übergibt die Schicht an einen anderen Nutzer")
    async def schichtuebergabe(self, interaction: Interaction, user: Member):
        if not self.user_is_authorized(interaction.user):
            await interaction.response.send_message("Du bist nicht berechtigt, eine Schicht zu übergeben.", ephemeral=True)
            return
        if not interaction.user.voice or not user.voice:
            await interaction.response.send_message("Beide müssen sich in einem Voice-Channel befinden.", ephemeral=True)
            return
        if not self.config.voice_channel:
            await interaction.response.send_message("VoiceMaster-Channel ist nicht gesetzt.", ephemeral=True)
            return
        dest = interaction.guild.get_channel(self.config.voice_channel)
        try:
            await interaction.user.move_to(dest)
            await user.move_to(dest)
        except Exception as e:
            logger.error(f"Fehler beim Voice-Move: {e}")
        if self.config.log_channel:
            logchan = interaction.guild.get_channel(self.config.log_channel)
            await logchan.send(f"Schicht von {interaction.user.mention} an {user.mention} übergeben in {dest.mention}.")
        await interaction.response.send_message(f"Schicht an {user.mention} übergeben.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = SchichtCog(bot)
    bot.add_cog(cog)
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
```
