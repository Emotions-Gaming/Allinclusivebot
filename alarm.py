from discord.ext import commands
import discord
from discord import app_commands
import datetime

from utils import load_json, save_json, is_admin, has_role, has_any_role, mention_roles, get_member_by_id

ALARM_CONFIG = "persistent_data/alarm_config.json"
ALARM_LOG = "persistent_data/alarm_log.json"

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper zum AlarmLead laden/speichern
    def get_lead_id(self):
        return load_json(ALARM_CONFIG, {}).get("lead_id", None)

    def set_lead_id(self, uid):
        cfg = load_json(ALARM_CONFIG, {})
        cfg["lead_id"] = uid
        save_json(ALARM_CONFIG, cfg)

    def get_alarmusers_role(self):
        return load_json(ALARM_CONFIG, {}).get("users_role_id", None)

    def set_alarmusers_role(self, role_id):
        cfg = load_json(ALARM_CONFIG, {})
        cfg["users_role_id"] = role_id
        save_json(ALARM_CONFIG, cfg)

    def remove_alarmusers_role(self):
        cfg = load_json(ALARM_CONFIG, {})
        cfg.pop("users_role_id", None)
        save_json(ALARM_CONFIG, cfg)

    def get_log_channel_id(self):
        return load_json(ALARM_CONFIG, {}).get("log_channel_id", None)

    def set_log_channel_id(self, cid):
        cfg = load_json(ALARM_CONFIG, {})
        cfg["log_channel_id"] = cid
        save_json(ALARM_CONFIG, cfg)

    # --- /AlarmLead [User] ---
    @app_commands.command(name="alarmlead", description="Setze den AlarmLead (verantwortlicher Schichtmanager)")
    @app_commands.describe(user="Nutzer, der AlarmLead werden soll")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return
        self.set_lead_id(user.id)
        await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead.", ephemeral=True)

    # --- /AlarmLeadDelete ---
    @app_commands.command(name="alarmleaddelete", description="Entfernt den AlarmLead")
    async def alarmleaddelete(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return
        self.set_lead_id(None)
        await interaction.response.send_message("AlarmLead entfernt.", ephemeral=True)

    # --- /AlarmUsers [Role] ---
    @app_commands.command(name="alarmusers", description="Setzt die Rolle für AlarmUser (kann Alarm-Schichten übernehmen)")
    @app_commands.describe(role="Rolle für Alarm-Schichtübernahmen")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return
        self.set_alarmusers_role(role.id)
        await interaction.response.send_message(f"AlarmUsers-Rolle gesetzt: {role.mention}", ephemeral=True)

    # --- /AlarmUsersDelete [Role] ---
    @app_commands.command(name="alarmusersdelete", description="Entfernt die Rolle für AlarmUser")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return
        if self.get_alarmusers_role() == role.id:
            self.remove_alarmusers_role()
            await interaction.response.send_message(f"{role.mention} ist nicht mehr AlarmUser-Rolle.", ephemeral=True)
        else:
            await interaction.response.send_message("Diese Rolle war nicht gesetzt.", ephemeral=True)

    # --- /AlarmLog [Channel] ---
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Schichtanfragen")
    @app_commands.describe(channel="Kanal für Alarm-Logs")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return
        self.set_log_channel_id(channel.id)
        await interaction.response.send_message(f"Alarm-Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    # --- /AlarmMain ---
    @app_commands.command(name="alarmmain", description="Zeigt das Hauptmenü für Alarm-Schichtsystem")
    async def alarmmain(self, interaction: discord.Interaction):
        alarm_lead_id = self.get_lead_id()
        is_lead = is_admin(interaction.user) or (alarm_lead_id and interaction.user.id == alarm_lead_id)

        embed = discord.Embed(
            title=":asterisk_symbol: Alarm-Schichtsystem",
            description=(
                "**Du bist AlarmLead oder Admin und kannst hier eine neue Alarm-Schichtanfrage posten.**\n"
                "Drücke auf **Anfrage erstellen** um die Schicht einzutragen.\n\n"
                "**Der Claim-Button ist für alle sichtbar!**"
            ),
            color=discord.Color.red()
        )

        view = AlarmMainView(self.bot, alarm_lead_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Alarm-Schichtsystem gepostet.", ephemeral=True)

    # --------- Button-Logik für Anfrage und Schichtzuteilung (AlarmMainView) ---------
class AlarmMainView(discord.ui.View):
    def __init__(self, bot, alarm_lead_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.alarm_lead_id = alarm_lead_id

    @discord.ui.button(label="Anfrage erstellen", style=discord.ButtonStyle.danger, custom_id="alarm_create")
    async def create_alarm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # AlarmLead/Admin only
        if not (is_admin(interaction.user) or interaction.user.id == self.alarm_lead_id):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return

        # Modal für Anfrage
        class AlarmModal(discord.ui.Modal, title="Alarm-Schicht erstellen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", max_length=100)
            schicht = discord.ui.TextInput(label="Schichtzeit (z.B. 19.06 06:00 - 12:00)", max_length=100)
            async def on_submit(self, modal_inter):
                # Alarm-User-Rolle & Log laden
                role_id = load_json(ALARM_CONFIG, {}).get("users_role_id")
                log_id = load_json(ALARM_CONFIG, {}).get("log_channel_id")
                role_mention = f"<@&{role_id}>" if role_id else "@everyone"
                log_ch = modal_inter.guild.get_channel(log_id) if log_id else None
                # Anfrage-Post (mit Claim-Button)
                embed = discord.Embed(
                    title="🚨 Alarm-Schichtanfrage",
                    description=(
                        f"{role_mention}\n\n"
                        f"**Dringend Chatter benötigt!**\n"
                        f"**Streamer:** {self.streamer.value}\n"
                        f"**Zeit:** {self.schicht.value}\n"
                        "Klicke auf **Claim** um die Schicht zu übernehmen."
                    ),
                    color=discord.Color.red()
                )
                view = ClaimView(self.streamer.value, self.schicht.value, interaction.user)
                post = await modal_inter.channel.send(embed=embed, view=view)
                await modal_inter.response.send_message("Alarm-Schichtanfrage erstellt!", ephemeral=True)
                if log_ch:
                    await log_ch.send(f"Neue Alarm-Schichtanfrage: {post.jump_url}")

        await interaction.response.send_modal(AlarmModal())

    @discord.ui.button(label="Schicht zuteilen", style=discord.ButtonStyle.primary, custom_id="alarm_assign")
    async def assign_alarm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Nur AlarmLead/Admin
        if not (is_admin(interaction.user) or interaction.user.id == self.alarm_lead_id):
            await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
            return

        # Members-Dropdown vorbereiten (alle mit AlarmUser-Rolle)
        role_id = load_json(ALARM_CONFIG, {}).get("users_role_id")
        guild = interaction.guild
        if not role_id:
            await interaction.response.send_message("AlarmUsers-Rolle nicht gesetzt.", ephemeral=True)
            return
        role = guild.get_role(role_id)
        member_options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in role.members if not m.bot
        ]
        if not member_options:
            await interaction.response.send_message("Keine verfügbaren Nutzer.", ephemeral=True)
            return

        class AssignModal(discord.ui.Modal, title="Schicht zuteilen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", max_length=100)
            schicht = discord.ui.TextInput(label="Schichtzeit (z.B. 19.06 06:00 - 12:00)", max_length=100)
            member = discord.ui.Select(placeholder="Nutzer auswählen", options=member_options, min_values=1, max_values=1)

            async def on_submit(self, modal_inter):
                target_id = int(self.member.values[0])
                user = guild.get_member(target_id)
                if not user:
                    await modal_inter.response.send_message("User nicht gefunden.", ephemeral=True)
                    return
                lead = interaction.user
                # Log-Channel
                log_id = load_json(ALARM_CONFIG, {}).get("log_channel_id")
                log_ch = guild.get_channel(log_id) if log_id else None
                msg = (
                    f"{lead.mention} hat {user.mention} zur Schicht **{self.streamer.value}** "
                    f"({self.schicht.value}) eingeteilt."
                )
                if log_ch:
                    await log_ch.send(msg)
                try:
                    await user.send(
                        f"{lead.mention} hat dich zur Schicht **{self.streamer.value}** "
                        f"({self.schicht.value}) eingeteilt. Bitte erscheine 15 Minuten vorher im Discord General Channel."
                    )
                except Exception:
                    pass
                await modal_inter.response.send_message("Schicht erfolgreich zugewiesen!", ephemeral=True)

        await interaction.response.send_modal(AssignModal())

# --- Claim Button View ---
class ClaimView(discord.ui.View):
    def __init__(self, streamer, schicht, lead):
        super().__init__(timeout=None)
        self.streamer = streamer
        self.schicht = schicht
        self.lead = lead

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Log & DM an Claimer
        log_id = load_json(ALARM_CONFIG, {}).get("log_channel_id")
        log_ch = interaction.guild.get_channel(log_id) if log_id else None
        if log_ch:
            await log_ch.send(
                f"{interaction.user.mention} hat die Alarm-Schicht **{self.streamer}** ({self.schicht}) übernommen!"
            )
        try:
            await interaction.user.send(
                f"Du hast die Alarm-Schicht **{self.streamer}** ({self.schicht}) übernommen.\n"
                "Bitte erscheine 15 Minuten vor Schichtbeginn im General Channel."
            )
        except Exception:
            pass
        try:
            if self.lead:
                await self.lead.send(
                    f"{interaction.user.mention} hat die Alarm-Schicht **{self.streamer}** ({self.schicht}) geclaimt!"
                )
        except Exception:
            pass
        await interaction.message.delete()
        await interaction.response.send_message("Schicht übernommen! Check deine DMs.", ephemeral=True)

# --- Cog Setup ---
async def setup(bot):
    await bot.add_cog(Alarm(bot))
