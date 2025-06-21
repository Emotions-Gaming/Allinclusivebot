# alarm.py – Alarm/Chatter-Claim-System
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from utils import load_json, save_json, is_admin

ALARM_FILE = "alarm_config.json"

def load_alarm():
    return load_json(ALARM_FILE, {
        "lead_id": None,
        "user_role_ids": [],
        "log_channel_id": None,
        "main_channel_id": None
    })

def save_alarm(data):
    save_json(ALARM_FILE, data)

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alarm = load_alarm()

    def cog_unload(self):
        save_alarm(self.alarm)

    # --- Rechte Checks ---
    def is_lead(self, user):
        return self.alarm["lead_id"] == user.id or is_admin(user)

    # --- Slash: Lead setzen ---
    @app_commands.command(name="alarmlead", description="Setzt den AlarmLead, der bei Claims benachrichtigt wird")
    @app_commands.describe(user="Verantwortlicher Lead (User)")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        self.alarm["lead_id"] = user.id
        save_alarm(self.alarm)
        await interaction.response.send_message(f"AlarmLead gesetzt: {user.mention}", ephemeral=True)

    # --- Slash: Alarm-Nutzer-Rolle(n) hinzufügen/entfernen ---
    @app_commands.command(name="alarmusers", description="Fügt eine Rolle zur Alarmrolle hinzu (wird bei Alarm gepingt)")
    @app_commands.describe(role="Alarm-Rolle")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        if role.id not in self.alarm["user_role_ids"]:
            self.alarm["user_role_ids"].append(role.id)
            save_alarm(self.alarm)
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt Alarmrolle.", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle aus den Alarmrollen")
    @app_commands.describe(role="Alarm-Rolle entfernen")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        if role.id in self.alarm["user_role_ids"]:
            self.alarm["user_role_ids"].remove(role.id)
            save_alarm(self.alarm)
        await interaction.response.send_message(f"Rolle {role.mention} ist keine Alarmrolle mehr.", ephemeral=True)

    # --- Slash: LogChannel für Claims setzen ---
    @app_commands.command(name="alarmlog", description="Setzt den Channel für Alarm-Logs")
    @app_commands.describe(channel="Channel für Log")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        self.alarm["log_channel_id"] = channel.id
        save_alarm(self.alarm)
        await interaction.response.send_message(f"Alarm-Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    # --- Slash: Haupt-Alarmmenü posten (mit Button) ---
    @app_commands.command(name="alarmmain", description="Postet das Alarm-Schicht-Menü im aktuellen Channel")
    async def alarmmain(self, interaction: discord.Interaction):
        if not self.is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin kann diesen Befehl nutzen.", ephemeral=True)
        embed = discord.Embed(
            title="🚨 Alarm-Schicht Anfrage",
            description="Drücke auf **Anfrage erstellen**, um einen Chatter/Schicht-Anfrage zu posten.",
            color=discord.Color.red()
        )
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="Anfrage erstellen", style=discord.ButtonStyle.primary)
        async def btn_cb(inter):
            if not self.is_lead(inter.user):
                return await inter.response.send_message("Keine Berechtigung.", ephemeral=True)
            modal = discord.ui.Modal(title="Alarm-Anfrage erstellen")
            streamer = discord.ui.TextInput(label="Name des Streamers", max_length=50)
            zeitraum = discord.ui.TextInput(label="Schicht-Zeitraum (z.B. 21.06. 06:00-12:00)", max_length=50)
            modal.add_item(streamer)
            modal.add_item(zeitraum)
            async def on_submit(modal_inter):
                role_mentions = " ".join(f"<@&{rid}>" for rid in self.alarm["user_role_ids"])
                lead = interaction.guild.get_member(self.alarm["lead_id"]) if self.alarm["lead_id"] else None
                msg = (
                    f"{role_mentions}\n"
                    f"**Dringend Chatter benötigt!**\n"
                    f"**Streamer:** {streamer.value}\n"
                    f"**Zeit:** {zeitraum.value}\n\n"
                    f"→ Klicke auf 'Claim', um die Schicht zu übernehmen."
                )
                claim_view = discord.ui.View(timeout=None)
                claim_btn = discord.ui.Button(label="Claim", style=discord.ButtonStyle.success)
                async def claim_cb(claim_inter):
                    try:
                        await claim_inter.message.delete()
                    except Exception:
                        pass
                    await claim_inter.response.send_message(
                        f"{claim_inter.user.mention} hat die Schicht übernommen!\n"
                        f"Bitte melde dich vor Schichtbeginn im General-Channel.\n"
                        f"Streamer: {streamer.value}\n"
                        f"Zeit: {zeitraum.value}\n", ephemeral=True)
                    # DM an Claimer
                    try:
                        await claim_inter.user.send(
                            f"Du hast erfolgreich die Alarm-Schicht übernommen!\n"
                            f"**Streamer:** {streamer.value}\n"
                            f"**Zeit:** {zeitraum.value}\n"
                            f"Bitte sei 15 Minuten vorher im General-Voice.\n"
                            f"Bei Fragen: Wende dich an "
                            f"{lead.mention if lead else 'einen Admin'}."
                        )
                    except Exception:
                        pass
                    # Log
                    log_id = self.alarm["log_channel_id"]
                    log_ch = claim_inter.guild.get_channel(log_id) if log_id else None
                    if log_ch:
                        await log_ch.send(
                            f"🚨 **Alarm-Schicht übernommen:**\n"
                            f"Streamer: {streamer.value}\n"
                            f"Zeit: {zeitraum.value}\n"
                            f"Von: {claim_inter.user.mention}\n"
                            f"Lead: {lead.mention if lead else 'Unbekannt'}"
                        )
                    # Lead benachrichtigen
                    if lead:
                        try:
                            await lead.send(
                                f"{claim_inter.user.display_name} hat die Alarm-Schicht übernommen!\n"
                                f"Streamer: {streamer.value}\n"
                                f"Zeit: {zeitraum.value}\n"
                                f"Bitte im Blick behalten."
                            )
                        except Exception:
                            pass
                claim_btn.callback = claim_cb
                claim_view.add_item(claim_btn)
                await modal_inter.channel.send(msg, view=claim_view)
                await modal_inter.response.send_message("Anfrage gepostet!", ephemeral=True)
            modal.on_submit = on_submit
            await inter.response.send_modal(modal)
        btn.callback = btn_cb
        view.add_item(btn)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Alarm-Menü gepostet.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Alarm(bot))
