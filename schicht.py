# schicht.py

import os
import json
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands

GUILD_ID = int(os.getenv("GUILD_ID") or "0")
DATA_DIR = "persistent_data"

SCHICHT_CONFIG = os.path.join(DATA_DIR, "schicht_config.json")
SCHICHT_RIGHTS_FILE = os.path.join(DATA_DIR, "schicht_rights.json")
ALARM_USERS_FILE = os.path.join(DATA_DIR, "alarm_users.json")
ALARM_ROLE_FILE = os.path.join(DATA_DIR, "alarm_role.json")
ALARM_LOG_FILE = os.path.join(DATA_DIR, "alarm_log.json")

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schicht_cfg = load_json(SCHICHT_CONFIG, {
            "text_channel_id": None,
            "voice_channel_id": None,
            "log_channel_id": None,
            "rollen": []
        })
        self.schicht_rights = set(load_json(SCHICHT_RIGHTS_FILE, []))
        self.alarm_users = set(load_json(ALARM_USERS_FILE, []))
        self.alarm_roles = set(load_json(ALARM_ROLE_FILE, []))
        self.alarm_log_channel = load_json(ALARM_LOG_FILE, None)

    def save_all(self):
        save_json(SCHICHT_CONFIG, self.schicht_cfg)
        save_json(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))
        save_json(ALARM_USERS_FILE, list(self.alarm_users))
        save_json(ALARM_ROLE_FILE, list(self.alarm_roles))
        save_json(ALARM_LOG_FILE, self.alarm_log_channel)

    def is_admin(self, user):
        return user.guild_permissions.administrator or getattr(user, "id", None) == getattr(getattr(user, "guild", None), "owner_id", None)

    # =================== SCHICHT-ÜBERGABE ===================

    @app_commands.command(name="schichtrolerights", description="Fügt eine Rolle als berechtigt für Schichtübergabe hinzu")
    @app_commands.describe(role="Rolle, die den Befehl ausführen darf")
    async def schichtrolerights(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_rights.add(role.id)
        self.save_all()
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt für Schichtübergabe berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtroledeleterights", description="Entfernt eine Rolle aus der Schichtübergabe-Berechtigung")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtroledeleterights(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.schicht_rights:
            self.schicht_rights.remove(role.id)
            self.save_all()
            await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    # Zeigt User mit korrekter Rolle im Autocomplete
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
            if len(allowed) >= 20: break
        return allowed

    @app_commands.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter")
    @app_commands.describe(nutzer="Nutzer für Übergabe")
    @app_commands.autocomplete(nutzer=schicht_user_autocomplete)
    async def schichtuebergabe(self, interaction: discord.Interaction, nutzer: str):
        # Rollenrechte-Check
        user_roles = [r.id for r in interaction.user.roles]
        if self.schicht_rights and not any(rid in self.schicht_rights for rid in user_roles) and not self.is_admin(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung für diesen Command.", ephemeral=True)

        rollen = set(self.schicht_cfg.get("rollen", []))
        guild = interaction.guild
        user = guild.get_member(int(nutzer))
        if not user:
            return await interaction.response.send_message("Nutzer nicht gefunden.", ephemeral=True)
        # Check: Hat user die richtige Rolle?
        if not any(r.id in rollen for r in user.roles):
            return await interaction.response.send_message(f"{user.display_name} hat nicht die berechtigte Rolle.", ephemeral=True)
        # Check: Fragender im Voice?
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
        # Check: Zielnutzer im Voice?
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
                    await log_ch.send(
                        f"✅ **Schichtübergabe:** {interaction.user.mention} -> {user.mention} | Kanal: {voice_ch.mention}")
        except Exception as e:
            return await interaction.followup.send(f"Fehler beim Verschieben: {e}", ephemeral=True)

    # =================== ALARM-SCHICHT SYSTEM ===================

    @app_commands.command(name="alarmrole", description="Fügt einen Benutzer als Alarm-Operator hinzu")
    @app_commands.describe(benutzer="Discord-User")
    async def alarmrole(self, interaction: discord.Interaction, benutzer: discord.Member):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.alarm_users.add(benutzer.id)
        self.save_all()
        await interaction.response.send_message(f"{benutzer.mention} ist jetzt Alarm-Schicht-Operator.", ephemeral=True)

    @app_commands.command(name="alarmroledelete", description="Entfernt einen Benutzer aus den Alarm-Operatoren")
    @app_commands.describe(benutzer="Discord-User")
    async def alarmroledelete(self, interaction: discord.Interaction, benutzer: discord.Member):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if benutzer.id in self.alarm_users:
            self.alarm_users.remove(benutzer.id)
            self.save_all()
            await interaction.response.send_message(f"{benutzer.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{benutzer.mention} war kein Alarm-Operator.", ephemeral=True)

    @app_commands.command(name="alarmusers", description="Setzt die zu alarmierende Rolle")
    @app_commands.describe(role="Discord-Rolle, die bei Alarm gepingt wird")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.alarm_roles.add(role.id)
        self.save_all()
        await interaction.response.send_message(f"{role.mention} wird bei Alarm gepingt.", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt die Alarm-Rolle")
    @app_commands.describe(role="Discord-Rolle")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.alarm_roles:
            self.alarm_roles.remove(role.id)
            self.save_all()
            await interaction.response.send_message(f"{role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{role.mention} war keine Alarm-Rolle.", ephemeral=True)

    @app_commands.command(name="alarmlog", description="Setzt den Alarm-Logchannel")
    @app_commands.describe(channel="Channel für Log")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.alarm_log_channel = channel.id
        self.save_all()
        await interaction.response.send_message(f"Alarm-Logchannel ist jetzt {channel.mention}.", ephemeral=True)

    @app_commands.command(name="alarmmain", description="Erstellt ein Alarm-Schicht-Panel im aktuellen Channel")
    async def alarmmain(self, interaction: discord.Interaction):
        # Rechte prüfen: Nur Admins oder Alarm-Operatoren!
        if not self.is_admin(interaction.user) and interaction.user.id not in self.alarm_users:
            return await interaction.response.send_message("Keine Berechtigung für das Alarm-Panel!", ephemeral=True)
        # Button posten
        btn = discord.ui.Button(label="Neue Alarm-Schicht anlegen", style=discord.ButtonStyle.danger)

        async def alarm_button_cb(inter):
            if not self.is_admin(inter.user) and inter.user.id not in self.alarm_users:
                return await inter.response.send_message("Keine Berechtigung!", ephemeral=True)
            # Modal für Anfrage
            class AlarmModal(discord.ui.Modal, title="Alarm-Schicht Anfrage"):
                streamer = discord.ui.TextInput(label="Name von Streamer", required=True)
                schicht = discord.ui.TextInput(label="Welche Schicht (Datum/Uhrzeit)", required=True, placeholder="Bsp. Montag 19.06. 06:00 - 12:00")
                async def on_submit(self, modal_inter):
                    alarm_roles = [f"<@&{rid}>" for rid in self.alarm_roles]
                    role_ping = " ".join(alarm_roles) if alarm_roles else "@here"
                    claim_btn = discord.ui.Button(label="Claim", style=discord.ButtonStyle.success)
                    # Claim-Callback
                    async def claim_cb(claim_inter):
                        # Nur ein User kann claimen!
                        try:
                            await claim_inter.message.delete()
                        except: pass
                        # DM an Claimer
                        try:
                            await claim_inter.user.send(
                                f"**Danke fürs Übernehmen der Schicht!**\n"
                                f"Streamer: {self.streamer.value}\n"
                                f"Schicht: {self.schicht.value}\n"
                                f"Bitte befinde dich 15 Minuten vor Schichtbeginn im General-Discord-Channel ein."
                            )
                        except: pass
                        # Log an Admin/Log-Channel
                        log_id = self.alarm_log_channel
                        if log_id:
                            log_ch = claim_inter.guild.get_channel(log_id)
                            if log_ch:
                                await log_ch.send(
                                    f"Alarm-Schicht übernommen von {claim_inter.user.mention}\n"
                                    f"Streamer: {self.streamer.value}\nSchicht: {self.schicht.value}\n"
                                )
                        await claim_inter.response.send_message("Du hast die Schicht übernommen. Infos wurden dir per DM geschickt.", ephemeral=True)
                    claim_btn.callback = claim_cb
                    view = discord.ui.View(timeout=None)
                    view.add_item(claim_btn)
                    msg = (
                        f"{role_ping}\n"
                        f"**Dringend Chatter benötigt!**\n"
                        f"Streamer: {self.streamer.value}\n"
                        f"Zeit: {self.schicht.value}\n"
                    )
                    await modal_inter.channel.send(msg, view=view)
                    await modal_inter.response.send_message("Alarm-Anfrage gepostet!", ephemeral=True)
            await inter.response.send_modal(AlarmModal())
        btn.callback = alarm_button_cb
        view = discord.ui.View(timeout=None)
        view.add_item(btn)
        await interaction.channel.send("### Alarm-Schicht Panel\nKlicke auf den Button um eine Alarm-Anfrage zu stellen.", view=view)
        await interaction.response.send_message("Alarm-Panel gepostet.", ephemeral=True)

# --- Cog Setup ---
async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
