import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

DATA_DIR = os.environ.get("DATA_DIR", "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

SCHICHT_CONFIG_FILE = os.path.join(DATA_DIR, "schicht_config.json")
SCHICHT_RIGHTS_FILE = os.path.join(DATA_DIR, "schicht_rights.json")

def load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schicht_cfg = load_json_file(SCHICHT_CONFIG_FILE, {
            "text_channel_id": None,
            "voice_channel_id": None,
            "log_channel_id": None,
            "rollen": []
        })
        self.schicht_rights = set(load_json_file(SCHICHT_RIGHTS_FILE, []))

    def is_admin(self, user):
        return getattr(user, "guild_permissions", None) and user.guild_permissions.administrator

    # ==== BERECHTIGUNGEN ====
    @app_commands.command(name="schichtrolerights", description="Fügt eine Rolle als berechtigt für Schichtübergabe hinzu")
    @app_commands.describe(role="Rolle, die den Befehl ausführen darf")
    async def schichtrolerights(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_rights.add(role.id)
        save_json_file(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt für Schichtübergabe berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtroledeleterights", description="Entfernt eine Rolle aus der Schichtübergabe-Berechtigung")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtroledeleterights(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.schicht_rights:
            self.schicht_rights.remove(role.id)
            save_json_file(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))
            await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    # ==== SETTINGS ====
    @app_commands.command(name="schichtsettext", description="Setzt den Text-Channel für Schichtübergaben")
    @app_commands.describe(channel="Textchannel")
    async def schichtsettext(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_cfg["text_channel_id"] = channel.id
        save_json_file(SCHICHT_CONFIG_FILE, self.schicht_cfg)
        await interaction.response.send_message(f"Schicht-Textkanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetvoice", description="Setzt den Voice-Channel für Schichtübergaben")
    @app_commands.describe(channel="Voicechannel")
    async def schichtsetvoice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_cfg["voice_channel_id"] = channel.id
        save_json_file(SCHICHT_CONFIG_FILE, self.schicht_cfg)
        await interaction.response.send_message(f"Schicht-Voicekanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetlog", description="Setzt den Log-Channel für Schichtübergaben")
    @app_commands.describe(channel="Textchannel")
    async def schichtsetlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_cfg["log_channel_id"] = channel.id
        save_json_file(SCHICHT_CONFIG_FILE, self.schicht_cfg)
        await interaction.response.send_message(f"Schicht-Logkanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetrolle", description="Setzt die Rollen für Schichtübergabe (Mehrfachauswahl möglich)")
    @app_commands.describe(rolle="Rolle für Schichtübergabe")
    async def schichtsetrolle(self, interaction: discord.Interaction, rolle: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if rolle.id not in self.schicht_cfg["rollen"]:
            self.schicht_cfg["rollen"].append(rolle.id)
            save_json_file(SCHICHT_CONFIG_FILE, self.schicht_cfg)
            await interaction.response.send_message(f"Rolle {rolle.mention} für Schichtübergabe hinzugefügt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {rolle.mention} ist schon berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtremoverolle", description="Entfernt eine Rolle von den Schichtübergabe-Rollen")
    @app_commands.describe(rolle="Rolle entfernen")
    async def schichtremoverolle(self, interaction: discord.Interaction, rolle: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if rolle.id in self.schicht_cfg["rollen"]:
            self.schicht_cfg["rollen"].remove(rolle.id)
            save_json_file(SCHICHT_CONFIG_FILE, self.schicht_cfg)
            await interaction.response.send_message(f"Rolle {rolle.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {rolle.mention} ist nicht gesetzt.", ephemeral=True)

    # ==== AUTOCOMPLETE ====
    async def schicht_user_autocomplete(self, interaction: discord.Interaction, current: str):
        rollen = set(self.schicht_cfg.get("rollen", []))
        allowed = []
        for m in interaction.guild.members:
            if m.bot:
                continue
            is_role = any(r.id in rollen for r in m.roles)
            name_match = current.lower() in m.display_name.lower() or current.lower() in m.name.lower()
            if is_role and name_match:
                allowed.append(app_commands.Choice(name=m.display_name, value=str(m.id)))
            if len(allowed) >= 20:
                break
        return allowed

    # ==== SCHICHTÜBERGABE ====
    @app_commands.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter")
    @app_commands.describe(nutzer="Nutzer für Übergabe")
    @app_commands.autocomplete(nutzer=schicht_user_autocomplete)
    async def schichtuebergabe(self, interaction: discord.Interaction, nutzer: str):
        # Jeder, der die erlaubte Rolle hat, darf – oder Admin
        user_roles = [r.id for r in interaction.user.roles]
        if self.schicht_rights and not any(rid in self.schicht_rights for rid in user_roles) and not self.is_admin(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung für diesen Command.", ephemeral=True)
        rollen = set(self.schicht_cfg.get("rollen", []))
        guild = interaction.guild
        user = guild.get_member(int(nutzer))
        if not user:
            return await interaction.response.send_message("Nutzer nicht gefunden.", ephemeral=True)
        if not any(r.id in rollen for r in user.roles):
            return await interaction.response.send_message(f"{user.display_name} hat nicht die berechtigte Rolle.", ephemeral=True)
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
        if not user.voice or not user.voice.channel:
            try:
                await user.send(f"**{interaction.user.display_name}** möchte dir die Schicht übergeben, aber du bist nicht im Sprachkanal! Bitte geh online und join einem Channel.")
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal! Ich habe ihm eine DM geschickt.", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal und konnte nicht per DM benachrichtigt werden.", ephemeral=True)
            return
        v_id = self.schicht_cfg.get("voice_channel_id")
        if not v_id:
            return await interaction.response.send_message("VoiceMaster-Eingangskanal ist nicht gesetzt!", ephemeral=True)
        voice_ch = guild.get_channel(v_id)
        try:
            await interaction.user.move_to(voice_ch)
            await interaction.response.send_message(f"Du wurdest in den VoiceMaster-Kanal verschoben. Warte kurz...", ephemeral=True)
            await asyncio.sleep(5)
            await user.move_to(interaction.user.voice.channel)
            await interaction.followup.send(f"{user.mention} wurde ebenfalls verschoben. Schichtübergabe kann starten!", ephemeral=True)
            log_id = self.schicht_cfg.get("log_channel_id")
            if log_id:
                log_ch = guild.get_channel(log_id)
                if log_ch:
                    await log_ch.send(f"✅ **Schichtübergabe:** {interaction.user.mention} -> {user.mention} | Kanal: {voice_ch.mention}")
        except Exception as e:
            return await interaction.followup.send(f"Fehler beim Verschieben: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
