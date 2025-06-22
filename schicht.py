# schicht.py

import os
import logging
import asyncio
from discord.ext import commands
from discord import app_commands, Interaction, Member, Role, VoiceChannel, TextChannel, Embed
from utils import is_admin, has_any_role, load_json, save_json

SCHICHT_CONFIG = "persistent_data/schicht_config.json"

def _load():
    return load_json(SCHICHT_CONFIG, {
        "rollen": [],
        "voice_channel_id": None,
        "log_channel_id": None
    })

def _save(data):
    save_json(SCHICHT_CONFIG, data)

def is_schichtberechtigt(user: Member) -> bool:
    if is_admin(user):
        return True
    config = _load()
    return has_any_role(user, config.get("rollen", []))

def get_voice_channel(guild, config):
    if not config.get("voice_channel_id"):
        return None
    return guild.get_channel(config["voice_channel_id"])

def get_log_channel(guild, config):
    if not config.get("log_channel_id"):
        return None
    return guild.get_channel(config["log_channel_id"])

# GUILD_ID (aus ENV, wie überall)
GUILD_ID = int(os.environ.get("GUILD_ID"))

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Panel/Info-Embed für Anleitung
    async def reload_menu(self):
        config = _load()
        guild = self.bot.get_guild(GUILD_ID)
        channel_id = config.get("schicht_main_channel")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        # Lösche alte Bot-Messages im Channel
        async for msg in channel.history(limit=30):
            if msg.author == self.bot.user and "Schichtübergabe – Hinweise" in (msg.content or ""):
                try:
                    await msg.delete()
                except Exception:
                    pass
        # Post neues Info-Panel
        text = (
            "👮‍♂️ **Schichtübergabe – Hinweise**\n\n"
            "Mit `/schichtuebergabe` kannst du die Schicht gezielt übergeben.\n\n"
            "**Ablauf:**\n"
            "1. Nutze den Command, während du im Voice bist\n"
            "2. Der neue Nutzer muss im Discord & Voice-Channel online sein\n"
            "3. Du wirst zuerst in den VoiceMaster verschoben\n"
            "4. Nach 2 Sekunden wird der Empfänger auch verschoben\n"
            "5. Ab jetzt läuft die Übergabe – ggf. relevante Infos im Chat posten!\n"
            "```/schichtuebergabe [@Nutzer]``` (Kopiere diesen Command für die Übergabe)"
        )
        await channel.send(text)

    @app_commands.command(
        name="schichtmain",
        description="Postet das zentrale Info-Panel für die Schichtübergabe"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtmain(self, interaction: Interaction):
        if not is_schichtberechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung für diesen Befehl.", ephemeral=True)
            return
        await self.reload_menu()
        await interaction.response.send_message("✅ Schichtmain-Panel wurde gepostet.", ephemeral=True)

    @app_commands.command(
        name="schichtuebergabe",
        description="Führt eine Schichtübergabe im Voice-Channel an einen anderen Nutzer durch"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtuebergabe(self, interaction: Interaction, ziel: Member):
        if not is_schichtberechtigt(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung für eine Schichtübergabe.", ephemeral=True)
            return

        config = _load()
        guild = interaction.guild or self.bot.get_guild(GUILD_ID)
        voice_channel = get_voice_channel(guild, config)
        if not voice_channel:
            await interaction.response.send_message("❌ Ziel-Voice-Channel ist nicht gesetzt! Setze ihn zuerst mit /schichtsetvoice.", ephemeral=True)
            return

        # Prüfe, ob beide User im Voice sind
        aufrufer_vc = interaction.user.voice.channel if interaction.user.voice else None
        ziel_vc = ziel.voice.channel if ziel.voice else None
        if not aufrufer_vc:
            await interaction.response.send_message("❌ Du bist nicht im Voice-Channel!", ephemeral=True)
            return
        if not ziel_vc:
            await interaction.response.send_message(f"❌ {ziel.display_name} ist nicht im Voice-Channel!", ephemeral=True)
            return

        # Zuerst den Caller verschieben, dann Ziel mit Delay
        try:
            await interaction.user.move_to(voice_channel)
        except Exception as e:
            await interaction.response.send_message(f"❌ Konnte dich nicht verschieben: {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Du wurdest in **{voice_channel.name}** verschoben. {ziel.mention} folgt gleich für die Schichtübergabe.", ephemeral=True
        )

        await asyncio.sleep(2)  # Kurze Wartezeit, dann Ziel verschieben

        try:
            await ziel.move_to(voice_channel)
            await ziel.send(f"Du wurdest zur Schichtübergabe in **{voice_channel.name}** verschoben.")
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Konnte {ziel.display_name} nicht verschieben: {e}", ephemeral=True
            )
            return

        # Logging
        log_channel = get_log_channel(guild, config)
        if log_channel:
            embed = Embed(
                title="Schichtübergabe durchgeführt",
                description=f"{interaction.user.mention} ➔ {ziel.mention}\n"
                            f"Voice: {voice_channel.mention}",
                color=0x3498db
            )
            await log_channel.send(embed=embed)

    @app_commands.command(
        name="schichtsetrolle",
        description="Fügt eine Rolle zu den Schichtrollen hinzu (darf Übergaben machen)"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtsetrolle(self, interaction: Interaction, rolle: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins dürfen Rollen setzen.", ephemeral=True)
            return
        config = _load()
        rollen = set(config.get("rollen", []))
        rollen.add(rolle.id)
        config["rollen"] = list(rollen)
        _save(config)
        await interaction.response.send_message(f"✅ {rolle.mention} darf jetzt Schichtübergaben machen.", ephemeral=True)

    @app_commands.command(
        name="schichtremoverolle",
        description="Entfernt eine Rolle aus den Schichtrollen"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtremoverolle(self, interaction: Interaction, rolle: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins dürfen Rollen entfernen.", ephemeral=True)
            return
        config = _load()
        rollen = set(config.get("rollen", []))
        if rolle.id in rollen:
            rollen.remove(rolle.id)
            config["rollen"] = list(rollen)
            _save(config)
            await interaction.response.send_message(f"✅ {rolle.mention} ist keine Schichtrolle mehr.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Diese Rolle war keine Schichtrolle.", ephemeral=True)

    @app_commands.command(
        name="schichtsetvoice",
        description="Setzt den Ziel-Voice-Channel für Schichtübergaben"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtsetvoice(self, interaction: Interaction, voice_channel: VoiceChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins dürfen den Ziel-Voice-Channel setzen.", ephemeral=True)
            return
        config = _load()
        config["voice_channel_id"] = voice_channel.id
        _save(config)
        await interaction.response.send_message(f"✅ Voice-Channel für Schichtübergaben ist jetzt {voice_channel.mention}.", ephemeral=True)

    @app_commands.command(
        name="schichtsetlog",
        description="Setzt den Log-Channel für Schichtübergaben"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtsetlog(self, interaction: Interaction, log_channel: TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins dürfen den Log-Channel setzen.", ephemeral=True)
            return
        config = _load()
        config["log_channel_id"] = log_channel.id
        _save(config)
        await interaction.response.send_message(f"✅ Log-Channel für Schichtübergaben ist jetzt {log_channel.mention}.", ephemeral=True)

    @app_commands.command(
        name="schichtinfo",
        description="Zeigt die aktuelle Schicht-Konfiguration"
    )
    @app_commands.guilds(GUILD_ID)
    async def schichtinfo(self, interaction: Interaction):
        if not is_schichtberechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        config = _load()
        guild = interaction.guild or self.bot.get_guild(GUILD_ID)
        rollen = [guild.get_role(rid) for rid in config.get("rollen", []) if guild.get_role(rid)]
        voice = guild.get_channel(config.get("voice_channel_id")) if config.get("voice_channel_id") else None
        log = guild.get_channel(config.get("log_channel_id")) if config.get("log_channel_id") else None

        msg = "**Schichtsystem-Konfiguration:**\n"
        msg += "- Schichtrollen: " + (", ".join(r.mention for r in rollen) if rollen else "*Keine*") + "\n"
        msg += "- Ziel-Voice-Channel: " + (voice.mention if voice else "*Nicht gesetzt*") + "\n"
        msg += "- Log-Channel: " + (log.mention if log else "*Nicht gesetzt*")
        await interaction.response.send_message(msg, ephemeral=True)

# === Setup-Funktion für Extension-Loader ===

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
