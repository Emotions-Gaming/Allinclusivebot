from utils import load_json, save_json, is_admin, get_member_by_id
import discord
from discord import app_commands

ALARM_CFG_FILE = "alarm_config.json"
ALARM_LEAD_FILE = "alarm_lead.json"

# ------- Helper -------

def get_alarm_lead(guild_id):
    return load_json(ALARM_LEAD_FILE, {}).get(str(guild_id))

def set_alarm_lead(guild_id, user_id):
    data = load_json(ALARM_LEAD_FILE, {})
    if user_id:
        data[str(guild_id)] = user_id
    else:
        data.pop(str(guild_id), None)
    save_json(ALARM_LEAD_FILE, data)

def get_alarm_log_channel(guild):
    cfg = load_json(ALARM_CFG_FILE, {})
    ch_id = cfg.get(str(guild.id), {}).get("log_channel_id")
    return guild.get_channel(ch_id) if ch_id else None

def set_alarm_log_channel(guild_id, ch_id):
    cfg = load_json(ALARM_CFG_FILE, {})
    if str(guild_id) not in cfg:
        cfg[str(guild_id)] = {}
    cfg[str(guild_id)]["log_channel_id"] = ch_id
    save_json(ALARM_CFG_FILE, cfg)

def set_alarm_main_channel(guild_id, ch_id):
    cfg = load_json(ALARM_CFG_FILE, {})
    if str(guild_id) not in cfg:
        cfg[str(guild_id)] = {}
    cfg[str(guild_id)]["main_channel_id"] = ch_id
    save_json(ALARM_CFG_FILE, cfg)

def get_alarm_main_channel(guild):
    cfg = load_json(ALARM_CFG_FILE, {})
    ch_id = cfg.get(str(guild.id), {}).get("main_channel_id")
    return guild.get_channel(ch_id) if ch_id else None

async def refresh_alarmmain_embed(guild):
    lead_id = get_alarm_lead(guild.id)
    lead_mention = f"<@{lead_id}>" if lead_id else "*kein Lead gesetzt*"
    ch = get_alarm_main_channel(guild)
    if not ch:
        return
    # Lösche alte Bot-Messages (max 10)
    async for msg in ch.history(limit=10):
        if msg.author.bot and msg.embeds and "Alarm-Schichtsystem" in msg.embeds[0].title:
            try: await msg.delete()
            except: pass
    # Embed & View neu posten
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
    await ch.send(embed=embed, view=AlarmMainView(lead_id))

# ------- Views & Modals -------

class AlarmMainView(discord.ui.View):
    def __init__(self, lead_id):
        super().__init__(timeout=None)
        self.lead_id = lead_id

    @discord.ui.button(label="Anfrage erstellen", style=discord.ButtonStyle.danger)
    async def create_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_admin(interaction.user) or interaction.user.id == self.lead_id):
            return await interaction.response.send_message("Nur AlarmLead/Admin kann das!", ephemeral=True)
        await interaction.response.send_modal(AlarmRequestModal())

class AlarmRequestModal(discord.ui.Modal, title="Alarm-Schichtanfrage erstellen"):
    streamer = discord.ui.TextInput(label="Name des Streamers", required=True, max_length=100)
    schicht = discord.ui.TextInput(label="Welche Schicht? (z.B. Montag 19.06 06:00 - 12:00)", required=True, max_length=100)
    info = discord.ui.TextInput(label="Weitere Hinweise (optional)", required=False, max_length=180)

    async def on_submit(self, interaction: discord.Interaction):
        log_ch = get_alarm_log_channel(interaction.guild)
        if not log_ch:
            return await interaction.response.send_message("Kein Alarm-LogChannel gesetzt! Bitte zuerst /alarmlog ausführen.", ephemeral=True)
        embed = discord.Embed(
            title="🆘 Dringend Chatter benötigt!",
            description=(
                f"**Streamer:** {self.streamer.value}\n"
                f"**Schicht:** {self.schicht.value}\n"
                f"{'**Hinweise:** ' + self.info.value if self.info.value else ''}\n\n"
                f"> Klicke auf **Claim**, wenn du die Schicht übernehmen möchtest!"
            ),
            color=discord.Color.red()
        )
        view = ClaimView(self.streamer.value, self.schicht.value, self.info.value)
        await log_ch.send(embed=embed, view=view)
        await interaction.response.send_message("Anfrage erfolgreich gepostet!", ephemeral=True)

class ClaimView(discord.ui.View):
    def __init__(self, streamer, schicht, info):
        super().__init__(timeout=None)
        self.streamer = streamer
        self.schicht = schicht
        self.info = info

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send(
                f"✅ **Danke fürs Übernehmen!**\n\n"
                f"Streamer: {self.streamer}\n"
                f"Schicht: {self.schicht}\n"
                f"{'Hinweise: ' + self.info if self.info else ''}\n\n"
                f"Bitte befinde dich 15 Minuten vor Schichtbeginn im General-Discord-Channel!"
            )
        except Exception:
            pass
        await interaction.channel.send(
            f"**Schicht übernommen!**\n"
            f"Chatter: {interaction.user.mention}\n"
            f"Streamer: {self.streamer}\n"
            f"Schicht: {self.schicht}\n"
        )
        await interaction.message.delete()

# -------- Commands --------

@app_commands.command(name="alarmmain", description="Postet das Alarm-Schichtsystem")
async def alarmmain(interaction: discord.Interaction):
    if not (is_admin(interaction.user) or interaction.user.id == get_alarm_lead(interaction.guild_id)):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    set_alarm_main_channel(interaction.guild_id, interaction.channel.id)
    await refresh_alarmmain_embed(interaction.guild)
    await interaction.response.send_message("Alarm-Schichtsystem gepostet.", ephemeral=True)

@app_commands.command(name="alarmlead", description="Setzt den AlarmLead (nur Admin)")
@app_commands.describe(user="User, der Lead werden soll")
async def alarmlead(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    set_alarm_lead(interaction.guild_id, user.id)
    await refresh_alarmmain_embed(interaction.guild)
    await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead!", ephemeral=True)

@app_commands.command(name="alarmleadremove", description="Entfernt den AlarmLead")
async def alarmleadremove(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    set_alarm_lead(interaction.guild_id, None)
    await refresh_alarmmain_embed(interaction.guild)
    await interaction.response.send_message("AlarmLead entfernt!", ephemeral=True)

@app_commands.command(name="alarmleadinfo", description="Zeigt den aktuellen AlarmLead")
async def alarmleadinfo(interaction: discord.Interaction):
    lead_id = get_alarm_lead(interaction.guild_id)
    if not lead_id:
        return await interaction.response.send_message("Kein AlarmLead gesetzt.", ephemeral=True)
    await interaction.response.send_message(f"Aktueller AlarmLead: <@{lead_id}>", ephemeral=True)

@app_commands.command(name="alarmlog", description="Setzt den LogChannel für Alarmanfragen")
@app_commands.describe(channel="Textkanal als Alarm-Log")
async def alarmlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    set_alarm_log_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(f"Alarm-LogChannel gesetzt: {channel.mention}", ephemeral=True)

@app_commands.command(name="alarmzuteilung", description="Lead/Admin teilt direkt eine Schicht zu")
@app_commands.describe(nutzer="Nutzer, der die Schicht bekommt")
async def alarmzuteilung(interaction: discord.Interaction, nutzer: discord.Member):
    if not (is_admin(interaction.user) or interaction.user.id == get_alarm_lead(interaction.guild_id)):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

    class ZuteilungModal(discord.ui.Modal, title="Direkt-Schichtzuteilung"):
        streamer = discord.ui.TextInput(label="Name des Streamers", required=True, max_length=100)
        schicht = discord.ui.TextInput(label="Welche Schicht? (z.B. Montag 19.06 06:00 - 12:00)", required=True, max_length=100)
        info = discord.ui.TextInput(label="Weitere Hinweise (optional)", required=False, max_length=180)

        async def on_submit(self, modal_inter: discord.Interaction):
            log_ch = get_alarm_log_channel(modal_inter.guild)
            if not log_ch:
                return await modal_inter.response.send_message("Kein Alarm-LogChannel gesetzt! Bitte zuerst /alarmlog ausführen.", ephemeral=True)
            embed = discord.Embed(
                title="👮‍♂️ Schicht direkt zugeteilt!",
                description=(
                    f"{interaction.user.mention} hat {nutzer.mention} zur Schicht eingeteilt.\n\n"
                    f"**Streamer:** {self.streamer.value}\n"
                    f"**Schicht:** {self.schicht.value}\n"
                    f"{'**Hinweise:** ' + self.info.value if self.info.value else ''}"
                ),
                color=discord.Color.blue()
            )
            await log_ch.send(embed=embed)
            try:
                await nutzer.send(
                    f"{interaction.user.mention} hat dich zur Schicht eingeteilt!\n"
                    f"Streamer: {self.streamer.value}\n"
                    f"Schicht: {self.schicht.value}\n"
                    f"{'Hinweise: ' + self.info.value if self.info.value else ''}\n"
                    f"Bitte erscheine 15 Minuten vor Schichtbeginn im General Channel!"
                )
            except Exception:
                pass
            await modal_inter.response.send_message("Schicht zugeteilt, Nutzer wurde informiert!", ephemeral=True)
    await interaction.response.send_modal(ZuteilungModal())

# ------------- ENDE ------------------
