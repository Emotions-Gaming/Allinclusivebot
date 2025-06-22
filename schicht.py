import discord
from discord.ext import commands
from discord import app_commands
from utils import load_json, save_json, is_admin, has_role, has_any_role
import os

GUILD_ID = int(os.getenv("GUILD_ID"))  # Für das Guild-Decorator!

SCHICHT_CONFIG_FILE = "schicht_config.json"
SCHICHT_RIGHTS_FILE = "schicht_rights.json"

def get_schicht_cfg():
    return load_json(SCHICHT_CONFIG_FILE, {
        "text_channel_id": None,
        "voice_channel_id": None,
        "log_channel_id": None,
        "rollen": []
    })

def save_schicht_cfg(data):
    save_json(SCHICHT_CONFIG_FILE, data)

def get_rights():
    return set(load_json(SCHICHT_RIGHTS_FILE, []))

def save_rights(s):
    save_json(SCHICHT_RIGHTS_FILE, list(s))

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="schichtsetvoice", description="Setzt den Voice-Kanal für Schichtübergaben")
    @app_commands.describe(channel="Voice-Kanal")
    async def schichtsetvoice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        cfg["voice_channel_id"] = channel.id
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Voice-Kanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="schichtsetlog", description="Setzt den Log-Channel für Schichtübergaben")
    @app_commands.describe(channel="Log-Channel")
    async def schichtsetlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        cfg["log_channel_id"] = channel.id
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="schichtsetrolle", description="Fügt eine berechtigte Rolle für Schichtübergaben hinzu")
    @app_commands.describe(role="Rolle, die Schichtübergabe machen darf")
    async def schichtsetrolle(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        rollen = set(cfg.get("rollen", []))
        rollen.add(role.id)
        cfg["rollen"] = list(rollen)
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Rolle {role.mention} darf jetzt Schichtübergaben machen.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="schichtremoverolle", description="Entfernt eine berechtigte Rolle für Schichtübergaben")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtremoverolle(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        rollen = set(cfg.get("rollen", []))
        if role.id in rollen:
            rollen.remove(role.id)
            cfg["rollen"] = list(rollen)
            save_schicht_cfg(cfg)
            await interaction.response.send_message(f"Rolle {role.mention} kann jetzt **nicht mehr** Schichtübergaben machen.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="schichtinfo", description="Infos & Anleitung zum Schichtsystem")
    @app_commands.guilds(GUILD_ID)
    async def schichtinfo(self, interaction: discord.Interaction):
        cfg = get_schicht_cfg()
        rollen = cfg.get("rollen", [])
        guild = interaction.guild
        rollen_txt = " / ".join([guild.get_role(rid).mention for rid in rollen if guild.get_role(rid)]) if rollen else "_Keine Rollen festgelegt_"
        log_channel = guild.get_channel(cfg.get("log_channel_id")) if cfg.get("log_channel_id") else None
        voice_channel = guild.get_channel(cfg.get("voice_channel_id")) if cfg.get("voice_channel_id") else None
        emb = discord.Embed(
            title="👥 Schichtübergabe-System",
            description="Hier können berechtigte Nutzer Schichtübergaben direkt im Voice durchführen.",
            color=discord.Color.blurple()
        )
        emb.add_field(name="Wer darf Übergaben machen?", value=rollen_txt, inline=False)
        emb.add_field(name="Voice-Kanal", value=voice_channel.mention if voice_channel else "_Nicht gesetzt_", inline=True)
        emb.add_field(name="Log-Channel", value=log_channel.mention if log_channel else "_Nicht gesetzt_", inline=True)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    # Restliche Logik wie gehabt...

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
