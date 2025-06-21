from discord import app_commands
import discord
import json
from utils import load_json, save_json, is_admin, get_member_by_id

ALARM_CFG_FILE = "alarm_config.json"
ALARM_USERS_FILE = "alarm_users.json"
ALARM_LEAD_FILE = "alarm_lead.json"
ALARM_LOG_FILE = "alarm_log_channel.json"

def load_alarm_lead(guild_id):
    return load_json(ALARM_LEAD_FILE, {}).get(str(guild_id))

def save_alarm_lead(guild_id, user_id):
    leads = load_json(ALARM_LEAD_FILE, {})
    if user_id:
        leads[str(guild_id)] = user_id
    else:
        leads.pop(str(guild_id), None)
    save_json(ALARM_LEAD_FILE, leads)

def load_alarm_roles(guild_id):
    return load_json(ALARM_USERS_FILE, {}).get(str(guild_id), [])

def save_alarm_roles(guild_id, roles):
    users = load_json(ALARM_USERS_FILE, {})
    users[str(guild_id)] = roles
    save_json(ALARM_USERS_FILE, users)

def load_alarm_log_channel(guild_id):
    return load_json(ALARM_LOG_FILE, {}).get(str(guild_id))

def save_alarm_log_channel(guild_id, channel_id):
    logs = load_json(ALARM_LOG_FILE, {})
    logs[str(guild_id)] = channel_id
    save_json(ALARM_LOG_FILE, logs)

class AlarmClaimView(discord.ui.View):
    def __init__(self, alarm_info, lead_id, log_channel_id):
        super().__init__(timeout=None)
        self.alarm_info = alarm_info
        self.lead_id = lead_id
        self.log_channel_id = log_channel_id

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        await interaction.message.delete()
        # DM an Claimenden
        try:
            await user.send(
                f"**Danke fürs Übernehmen der Schicht!**\n\n"
                f"Streamer: {self.alarm_info['streamer']}\n"
                f"Schicht: {self.alarm_info['date']}, {self.alarm_info['time']}\n"
                f"Bitte sei 15 Minuten vor Schichtbeginn im General-Discord-Channel."
            )
        except Exception:
            pass
        # Log an Log-Channel
        guild = interaction.guild
        if self.log_channel_id:
            log_ch = guild.get_channel(self.log_channel_id)
            if log_ch:
                lead_mention = f"<@{self.lead_id}>" if self.lead_id else "(kein Lead gesetzt)"
                await log_ch.send(
                    f"✅ **Schicht übernommen!** {user.mention}\n"
                    f"Streamer: {self.alarm_info['streamer']}\n"
                    f"Zeit: {self.alarm_info['date']} {self.alarm_info['time']}\n"
                    f"Lead: {lead_mention}"
                )
        await interaction.response.send_message("Schicht erfolgreich übernommen und DM gesendet!", ephemeral=True)

class AlarmMainView(discord.ui.View):
    def __init__(self, lead_id):
        super().__init__(timeout=None)
        self.lead_id = lead_id

    @discord.ui.button(label="Anfrage erstellen", style=discord.ButtonStyle.danger, custom_id="alarm_create_request")
    async def create_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_admin(interaction.user) or interaction.user.id == self.lead_id):
            return await interaction.response.send_message(
                "Nur der AlarmLead oder ein Admin kann eine Anfrage erstellen.", ephemeral=True)
        modal = AlarmRequestModal(self.lead_id)
        await interaction.response.send_modal(modal)

class AlarmRequestModal(discord.ui.Modal, title="Neue Alarm-Schichtanfrage"):
    streamer = discord.ui.TextInput(label="Name des Streamers", required=True)
    date = discord.ui.TextInput(label="Datum", required=True, placeholder="z.B. Montag, 19.06.")
    time = discord.ui.TextInput(label="Schichtzeit", required=True, placeholder="z.B. 06:00 - 12:00")
    def __init__(self, lead_id):
        super().__init__()
        self.lead_id = lead_id

    async def on_submit(self, interaction: discord.Interaction):
        alarm_roles = load_alarm_roles(interaction.guild_id)
        mention = " ".join([f"<@&{rid}>" for rid in alarm_roles]) if alarm_roles else "@everyone"
        alarm_info = {
            "streamer": self.streamer.value,
            "date": self.date.value,
            "time": self.time.value
        }
        view = AlarmClaimView(alarm_info, self.lead_id, load_alarm_log_channel(interaction.guild_id))
        embed = discord.Embed(
            title="🚨 Alarm-Schichtanfrage",
            description=(
                f"{mention}\n**Dringend Chatter benötigt!**\n\n"
                f"Streamer: `{self.streamer.value}`\n"
                f"Zeit: `{self.date.value}`\n"
                f"Schicht: `{self.time.value}`\n\n"
                "Klicke auf **Claim**, um die Schicht zu übernehmen!"
            ),
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Anfrage erstellt!", ephemeral=True)

# ==== Befehle ====

@app_commands.command(name="alarmmain", description="Postet das Alarm-Schichtsystem (nur für Lead/Admin).")
async def alarmmain(interaction: discord.Interaction):
    lead_id = load_alarm_lead(interaction.guild_id)
    lead_mention = f"<@{lead_id}>" if lead_id else "*kein Lead gesetzt*"
    embed = discord.Embed(
        title="🚨 Alarm-Schichtsystem",
        description=(
            "Drücke auf **Anfrage erstellen**, um eine neue Alarm-Schichtanfrage zu posten.\n\n"
            "Du bist AlarmLead/Admin? Dann kannst du zusätzlich Schichten direkt zuteilen per Command.\n\n"
            "**Direkt-Schichtzuteilung:**\n"
            "```/alarmzuteilung```"
        ),
        color=discord.Color.red()
    )
    embed.add_field(name="Aktueller AlarmLead", value=lead_mention)
    await interaction.channel.send(embed=embed, view=AlarmMainView(lead_id))
    await interaction.response.send_message("Alarm-Schichtsystem gepostet.", ephemeral=True)

@app_commands.command(name="alarmlead", description="Setzt den AlarmLead (nur Admin)")
@app_commands.describe(user="User, der Lead werden soll")
async def alarmlead(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_alarm_lead(interaction.guild_id, user.id)
    await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead!", ephemeral=True)

@app_commands.command(name="alarmleadremove", description="Entfernt den AlarmLead")
async def alarmleadremove(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_alarm_lead(interaction.guild_id, None)
    await interaction.response.send_message("AlarmLead entfernt!", ephemeral=True)

@app_commands.command(name="alarmleadinfo", description="Zeigt den aktuellen AlarmLead an")
async def alarmleadinfo(interaction: discord.Interaction):
    lead_id = load_alarm_lead(interaction.guild_id)
    if lead_id:
        await interaction.response.send_message(f"Aktueller AlarmLead: <@{lead_id}>", ephemeral=True)
    else:
        await interaction.response.send_message("Kein AlarmLead gesetzt!", ephemeral=True)

@app_commands.command(name="alarmusers", description="Fügt eine Rolle zu den Alarm-Schicht-Usern hinzu")
@app_commands.describe(role="Rolle für Alarm-Schicht")
async def alarmusers(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    roles = set(load_alarm_roles(interaction.guild_id))
    roles.add(role.id)
    save_alarm_roles(interaction.guild_id, list(roles))
    await interaction.response.send_message(f"Rolle {role.mention} für Alarm-Schicht hinzugefügt.", ephemeral=True)

@app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle von den Alarm-Schicht-Usern")
@app_commands.describe(role="Rolle entfernen")
async def alarmusersdelete(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    roles = set(load_alarm_roles(interaction.guild_id))
    roles.discard(role.id)
    save_alarm_roles(interaction.guild_id, list(roles))
    await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)

@app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Schichtsystem")
@app_commands.describe(channel="Kanal für Log")
async def alarmlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_alarm_log_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(f"Log-Channel gesetzt: {channel.mention}", ephemeral=True)

@app_commands.command(name="alarmzuteilung", description="Weist einem User direkt eine Schicht zu (nur Lead/Admin)")
@app_commands.describe(user="User, dem die Schicht zugewiesen wird")
async def alarmzuteilung(interaction: discord.Interaction, user: discord.Member):
    lead_id = load_alarm_lead(interaction.guild_id)
    if not (is_admin(interaction.user) or interaction.user.id == lead_id):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    # Modal für Schichtdaten
    class AlarmZuteilungModal(discord.ui.Modal, title="Schicht direkt zuteilen"):
        streamer = discord.ui.TextInput(label="Name des Streamers", required=True)
        date = discord.ui.TextInput(label="Datum", required=True, placeholder="z.B. Montag, 19.06.")
        time = discord.ui.TextInput(label="Schichtzeit", required=True, placeholder="z.B. 06:00 - 12:00")
        async def on_submit(self, m_inter: discord.Interaction):
            try:
                await user.send(
                    f"{interaction.user.display_name} hat dich zur Schicht eingeteilt!\n\n"
                    f"Streamer: {self.streamer.value}\n"
                    f"Datum: {self.date.value}\n"
                    f"Zeit: {self.time.value}\n"
                    f"Bitte erscheine 15 Minuten vor Schichtbeginn im General-Channel."
                )
            except Exception:
                pass
            log_ch_id = load_alarm_log_channel(interaction.guild_id)
            if log_ch_id:
                log_ch = interaction.guild.get_channel(log_ch_id)
                if log_ch:
                    await log_ch.send(
                        f"🔔 {interaction.user.mention} hat {user.mention} zur Schicht eingeteilt.\n"
                        f"Streamer: {self.streamer.value}\n"
                        f"Datum: {self.date.value}\n"
                        f"Zeit: {self.time.value}"
                    )
            await m_inter.response.send_message("Schicht erfolgreich eingeteilt & User informiert!", ephemeral=True)
    await interaction.response.send_modal(AlarmZuteilungModal())

# -- Setup function for extension loader --
async def setup(bot):
    bot.tree.add_command(alarmmain)
    bot.tree.add_command(alarmlead)
    bot.tree.add_command(alarmleadremove)
    bot.tree.add_command(alarmleadinfo)
    bot.tree.add_command(alarmusers)
    bot.tree.add_command(alarmusersdelete)
    bot.tree.add_command(alarmlog)
    bot.tree.add_command(alarmzuteilung)
