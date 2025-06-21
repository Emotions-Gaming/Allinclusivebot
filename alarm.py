from discord.ext import commands
from discord import app_commands, Interaction, Embed, ui
import discord
from utils import load_json, save_json, is_admin, has_role, has_any_role, mention_roles, get_member_by_id

ALARM_CONFIG_FILE = "persistent_data/alarm_config.json"
ALARM_LOG_FILE = "persistent_data/alarm_log.json"

def get_alarm_cfg():
    return load_json(ALARM_CONFIG_FILE, {
        "lead_ids": [],
        "user_roles": [],
        "log_channel_id": None
    })

def save_alarm_cfg(cfg):
    save_json(ALARM_CONFIG_FILE, cfg)

def add_alarm_lead(user_id):
    cfg = get_alarm_cfg()
    if user_id not in cfg["lead_ids"]:
        cfg["lead_ids"].append(user_id)
        save_alarm_cfg(cfg)

def remove_alarm_lead(user_id):
    cfg = get_alarm_cfg()
    if user_id in cfg["lead_ids"]:
        cfg["lead_ids"].remove(user_id)
        save_alarm_cfg(cfg)

def get_alarm_leads(guild):
    cfg = get_alarm_cfg()
    return [guild.get_member(uid) for uid in cfg["lead_ids"]]

def add_alarm_role(role_id):
    cfg = get_alarm_cfg()
    if role_id not in cfg["user_roles"]:
        cfg["user_roles"].append(role_id)
        save_alarm_cfg(cfg)

def remove_alarm_role(role_id):
    cfg = get_alarm_cfg()
    if role_id in cfg["user_roles"]:
        cfg["user_roles"].remove(role_id)
        save_alarm_cfg(cfg)

def set_alarm_log_channel(channel_id):
    cfg = get_alarm_cfg()
    cfg["log_channel_id"] = channel_id
    save_alarm_cfg(cfg)

def get_alarm_log_channel(guild):
    cfg = get_alarm_cfg()
    return guild.get_channel(cfg.get("log_channel_id"))

class AlarmClaimView(ui.View):
    def __init__(self, info, claimable=True):
        super().__init__(timeout=None)
        self.info = info
        self.claimed = False
        if claimable:
            self.add_item(AlarmClaimButton(info))

class AlarmClaimButton(ui.Button):
    def __init__(self, info):
        super().__init__(label="Claim", style=discord.ButtonStyle.success)
        self.info = info

    async def callback(self, interaction: Interaction):
        # Jeder kann claimen!
        if hasattr(self, 'claimed_by') and self.claimed_by:
            await interaction.response.send_message("Diese Schicht wurde bereits übernommen!", ephemeral=True)
            return
        self.claimed_by = interaction.user
        # Nachricht löschen
        try:
            await interaction.message.delete()
        except Exception:
            pass
        # DM an Claimer
        try:
            msg = (
                f"✅ **Du hast eine Alarm-Schicht übernommen!**\n"
                f"**Streamer:** {self.info['streamer']}\n"
                f"**Zeitraum:** {self.info['date']} ({self.info['time']})\n"
                f"Bitte sei 15 Minuten vorher im General-Discord-Channel!\n"
            )
            await interaction.user.send(msg)
        except Exception:
            pass
        # Log an Logchannel
        log_ch = get_alarm_log_channel(interaction.guild)
        if log_ch:
            log_msg = (
                f"⏰ **Alarm-Schicht wurde übernommen!**\n"
                f"Streamer: {self.info['streamer']}\n"
                f"Zeitraum: {self.info['date']} ({self.info['time']})\n"
                f"Claimed von: {interaction.user.mention}"
            )
            await log_ch.send(log_msg)
        await interaction.response.send_message("Danke fürs Übernehmen der Schicht!", ephemeral=True)

class AlarmRequestModal(ui.Modal, title="Alarm-Schicht erstellen"):
    streamer = ui.TextInput(label="Name Streamer", required=True, max_length=100)
    date = ui.TextInput(label="Datum (z.B. 23.06.2025)", required=True, max_length=100)
    time = ui.TextInput(label="Zeitraum (z.B. 16:00-22:00)", required=True, max_length=100)
    def __init__(self, post_channel, ping_role_ids):
        super().__init__()
        self.post_channel = post_channel
        self.ping_role_ids = ping_role_ids

    async def on_submit(self, interaction: Interaction):
        claim_info = {
            "streamer": self.streamer.value,
            "date": self.date.value,
            "time": self.time.value
        }
        ping_str = mention_roles(interaction.guild, self.ping_role_ids)
        emb = Embed(
            title="🚨 Alarm-Schichtanfrage",
            description=(
                f"{ping_str}\n\n"
                f"Dringend Chatter benötigt!\n\n"
                f"**Streamer:** {self.streamer.value}\n"
                f"**Datum:** {self.date.value}\n"
                f"**Zeitraum:** {self.time.value}\n"
            ),
            color=discord.Color.red()
        )
        view = AlarmClaimView(claim_info, claimable=True)
        await self.post_channel.send(embed=emb, view=view)
        await interaction.response.send_message("Alarm-Schichtanfrage gepostet!", ephemeral=True)

class AlarmMainView(ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.add_item(AlarmCreateButton(interaction))

class AlarmCreateButton(ui.Button):
    def __init__(self, interaction):
        super().__init__(label="Anfrage erstellen", style=discord.ButtonStyle.danger)
        self.interaction = interaction

    async def callback(self, interaction: Interaction):
        # Nur Lead/Admin
        leads = get_alarm_cfg().get("lead_ids", [])
        if not (is_admin(interaction.user) or interaction.user.id in leads):
            await interaction.response.send_message("Nur ein AlarmLead oder Admin kann Anfragen erstellen!", ephemeral=True)
            return
        # Modal öffnen
        ping_roles = get_alarm_cfg().get("user_roles", [])
        await interaction.response.send_modal(AlarmRequestModal(interaction.channel, ping_roles))

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="alarmmain", description="Postet das Alarm-Schichtsystem-Menü")
    async def alarmmain(self, interaction: Interaction):
        # Nur Lead/Admin
        leads = get_alarm_cfg().get("lead_ids", [])
        if not (is_admin(interaction.user) or interaction.user.id in leads):
            return await interaction.response.send_message("Nur ein AlarmLead oder Admin kann das Hauptmenü posten!", ephemeral=True)
        emb = Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Du bist AlarmLead oder Admin und kannst hier eine neue Alarm-Schichtanfrage posten.\n"
                "Drücke auf **Anfrage erstellen** um die Schicht einzutragen.\n\n"
                "Der Claim-Button ist für alle sichtbar!"
            ),
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=emb, view=AlarmMainView(interaction))
        await interaction.response.send_message("Alarm-Schichtsystem-Menü gepostet!", ephemeral=True)

    @app_commands.command(name="alarmlead", description="Setzt einen AlarmLead (Schichtverantwortlichen)")
    @app_commands.describe(user="User, der AlarmLead werden soll")
    async def alarmlead(self, interaction: Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins können einen AlarmLead setzen.", ephemeral=True)
        add_alarm_lead(user.id)
        await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead.", ephemeral=True)

    @app_commands.command(name="alarmleadremove", description="Entfernt einen AlarmLead")
    @app_commands.describe(user="User, der kein Lead mehr sein soll")
    async def alarmleadremove(self, interaction: Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins können Leads entfernen.", ephemeral=True)
        remove_alarm_lead(user.id)
        await interaction.response.send_message(f"{user.mention} ist kein AlarmLead mehr.", ephemeral=True)

    @app_commands.command(name="alarmusers", description="Fügt eine Rolle zu Alarm-Usern hinzu (wird gepingt)")
    @app_commands.describe(role="Rolle die bei Alarmanfrage gepingt werden soll")
    async def alarmusers(self, interaction: Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        add_alarm_role(role.id)
        await interaction.response.send_message(f"{role.mention} ist jetzt Alarm-User.", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle von Alarm-Usern")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusersdelete(self, interaction: Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        remove_alarm_role(role.id)
        await interaction.response.send_message(f"{role.mention} ist kein Alarm-User mehr.", ephemeral=True)

    @app_commands.command(name="alarmlog", description="Setzt den Logchannel für Alarm-Anfragen")
    @app_commands.describe(channel="Channel für Log")
    async def alarmlog(self, interaction: Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        set_alarm_log_channel(channel.id)
        await interaction.response.send_message(f"Logchannel gesetzt: {channel.mention}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Alarm(bot))
