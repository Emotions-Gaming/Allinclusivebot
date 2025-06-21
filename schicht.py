import discord
from discord import app_commands
from discord.ext import commands
from utils import load_json, save_json, is_admin

SCHICHT_CONFIG_FILE   = "schicht_config.json"
SCHICHT_RIGHTS_FILE   = "schicht_rights.json"

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_json(SCHICHT_CONFIG_FILE, {
            "text_channel_id": None,
            "voice_channel_id": None,
            "log_channel_id": None,
            "rollen": []
        })
        self.schicht_rights = set(load_json(SCHICHT_RIGHTS_FILE, []))

    def save(self):
        save_json(SCHICHT_CONFIG_FILE, self.config)
        save_json(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))

    # ===== Rollenverwaltung =====
    @app_commands.command(name="schichtrolerights", description="Fügt eine Rolle als berechtigt für Schichtübergabe hinzu")
    @app_commands.describe(role="Rolle, die den Befehl ausführen darf")
    async def schichtrolerights(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_rights.add(role.id)
        self.save()
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt für Schichtübergabe berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtroledeleterights", description="Entfernt eine Rolle aus der Schichtübergabe-Berechtigung")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtroledeleterights(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.schicht_rights:
            self.schicht_rights.remove(role.id)
            self.save()
            await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    # ===== Settings =====
    @app_commands.command(name="schichtsetvoice", description="Setzt den Voice-Masterkanal für Schichtübergaben")
    @app_commands.describe(channel="Voicekanal")
    async def schichtsetvoice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.config["voice_channel_id"] = channel.id
        self.save()
        await interaction.response.send_message(f"Voice-Master-Kanal ist jetzt {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetlog", description="Setzt den Log-Channel für Schichtübergaben")
    @app_commands.describe(channel="Textkanal für Logs")
    async def schichtsetlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.config["log_channel_id"] = channel.id
        self.save()
        await interaction.response.send_message(f"Logkanal ist jetzt {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetrole", description="Fügt eine Rolle als 'Schichtrolle' hinzu (kann Schicht empfangen)")
    @app_commands.describe(role="Rolle, die Schichten erhalten kann")
    async def schichtsetrole(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in self.config["rollen"]:
            self.config["rollen"].append(role.id)
            self.save()
            await interaction.response.send_message(f"Rolle {role.mention} kann jetzt Schichten empfangen.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war bereits Schichtrolle.", ephemeral=True)

    @app_commands.command(name="schichtremoverole", description="Entfernt eine Schichtrolle")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtremoverole(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.config["rollen"]:
            self.config["rollen"].remove(role.id)
            self.save()
            await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht als Schichtrolle gespeichert.", ephemeral=True)

    # ===== User-Autocomplete =====
    async def schicht_user_autocomplete(self, interaction: discord.Interaction, current: str):
        rollen = set(self.config.get("rollen", []))
        allowed = []
        for m in interaction.guild.members:
            if m.bot:
                continue
            is_role = any(r.id in rollen for r in m.roles)
            name_match = current.lower() in m.display_name.lower() or current.lower() in m.name.lower()
            if is_role and name_match:
                allowed.append(app_commands.Choice(name=m.display_name, value=str(m.id)))
            if len(allowed) >= 20: break
        return allowed

    # ===== Schichtübergabe =====
    @app_commands.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter")
    @app_commands.describe(nutzer="Nutzer für Übergabe")
    @app_commands.autocomplete(nutzer=schicht_user_autocomplete)
    async def schichtuebergabe(self, interaction: discord.Interaction, nutzer: str):
        user_roles = [r.id for r in interaction.user.roles]
        # Nur Rollen aus schicht_rights oder Admins dürfen Befehl nutzen
        if self.schicht_rights and not any(rid in self.schicht_rights for rid in user_roles) and not is_admin(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung für diesen Command.", ephemeral=True)

        rollen = set(self.config.get("rollen", []))
        guild = interaction.guild
        user = guild.get_member(int(nutzer))
        if not user:
            return await interaction.response.send_message("Nutzer nicht gefunden.", ephemeral=True)
        # Empfänger muss richtige Rolle haben
        if not any(r.id in rollen for r in user.roles):
            return await interaction.response.send_message(f"{user.display_name} hat nicht die berechtigte Rolle.", ephemeral=True)
        # Fragender im Voice?
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
        # Zielnutzer im Voice?
        if not user.voice or not user.voice.channel:
            try:
                await user.send(
                    f"**{interaction.user.display_name}** möchte dir die Schicht übergeben, aber du bist nicht im Sprachkanal! Bitte geh online und join einem Channel.")
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal! Ich habe ihm eine DM geschickt.", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal und konnte nicht per DM benachrichtigt werden.", ephemeral=True)
            return
        v_id = self.config.get("voice_channel_id")
        if not v_id:
            return await interaction.response.send_message("VoiceMaster-Eingangskanal ist nicht gesetzt!", ephemeral=True)
        voice_ch = guild.get_channel(v_id)
        try:
            await interaction.user.move_to(voice_ch)
            await interaction.response.send_message(f"Du wurdest in den VoiceMaster-Kanal verschoben. Warte kurz...", ephemeral=True)
            await asyncio.sleep(5)
            await user.move_to(interaction.user.voice.channel)
            await interaction.followup.send(f"{user.mention} wurde ebenfalls verschoben. Schichtübergabe kann starten!", ephemeral=True)
            log_id = self.config.get("log_channel_id")
            if log_id:
                log_ch = guild.get_channel(log_id)
                if log_ch:
                    await log_ch.send(
                        f"✅ **Schichtübergabe:** {interaction.user.mention} -> {user.mention} | Kanal: {voice_ch.mention}")
        except Exception as e:
            return await interaction.followup.send(f"Fehler beim Verschieben: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
