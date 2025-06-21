from discord.ext import commands
import discord
from discord import app_commands

from utils import load_json, save_json, is_admin

ALARM_CONFIG = "persistent_data/alarm_config.json"

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    def is_lead(self, user):
        return is_admin(user) or user.id == self.get_lead_id()

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
        is_lead = self.is_lead(interaction.user)

        embed = discord.Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Drücke auf **Anfrage erstellen**, um eine neue Alarm-Schichtanfrage zu posten.\n\n"
                "Du bist AlarmLead/Admin? Dann kannst du zusätzlich Schichten direkt zuteilen per Command."
            ),
            color=discord.Color.red()
        )

        view = AlarmMainView(self.bot, alarm_lead_id, is_lead)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Alarm-Schichtsystem gepostet.", ephemeral=True)

    # --- /Alarmzuteilung [Nutzer] ---
    @app_commands.command(name="alarmzuteilung", description="Teilt eine Alarm-Schicht direkt einem Nutzer zu (nur Lead/Admin).")
    @app_commands.describe(nutzer="User, der eingeteilt werden soll")
    async def alarmzuteilung(self, interaction: discord.Interaction, nutzer: discord.Member):
        # Nur Lead/Admin dürfen das machen
        if not self.is_lead(interaction.user):
            await interaction.response.send_message("Nur AlarmLead/Admin dürfen diesen Befehl nutzen.", ephemeral=True)
            return

        # Modal für Streamer-Name & Schichtzeit
        class ZuteilungModal(discord.ui.Modal, title="Alarm-Schicht zuteilen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", max_length=100)
            schicht = discord.ui.TextInput(label="Schichtzeit (z.B. 19.06 06:00 - 12:00)", max_length=100)

            async def on_submit(self, modal_inter):
                log_id = load_json(ALARM_CONFIG, {}).get("log_channel_id")
                log_ch = modal_inter.guild.get_channel(log_id) if log_id else None

                msg = (
                    f"{interaction.user.mention} hat {nutzer.mention} zur Schicht **{self.streamer.value}** "
                    f"({self.schicht.value}) eingeteilt."
                )
                if log_ch:
                    await log_ch.send(msg)
                try:
                    await nutzer.send(
                        f"{interaction.user.mention} hat dich zur Schicht **{self.streamer.value}** "
                        f"({self.schicht.value}) eingeteilt. Bitte erscheine 15 Minuten vorher im Discord General Channel."
                    )
                except Exception:
                    pass
                await modal_inter.response.send_message(f"{nutzer.mention} erfolgreich zur Schicht eingeteilt.", ephemeral=True)

        await interaction.response.send_modal(ZuteilungModal())

# ---- Hauptmenu View mit Anfrage erstellen Button ----
class AlarmMainView(discord.ui.View):
    def __init__(self, bot, alarm_lead_id, is_lead):
        super().__init__(timeout=None)
        self.bot = bot
        self.alarm_lead_id = alarm_lead_id
        self.is_lead = is_lead

    @discord.ui.button(label="Anfrage erstellen", style=discord.ButtonStyle.danger, custom_id="alarm_create")
    async def create_alarm(self, interaction: discord.Interaction, button: discord.ui.Button):
        class AlarmModal(discord.ui.Modal, title="Alarm-Schicht erstellen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", max_length=100)
            schicht = discord.ui.TextInput(label="Schichtzeit (z.B. 19.06 06:00 - 12:00)", max_length=100)
            async def on_submit(self, modal_inter):
                role_id = load_json(ALARM_CONFIG, {}).get("users_role_id")
                log_id = load_json(ALARM_CONFIG, {}).get("log_channel_id")
                role_mention = f"<@&{role_id}>" if role_id else "@everyone"
                log_ch = modal_inter.guild.get_channel(log_id) if log_id else None
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

# --- Claim Button View ---
class ClaimView(discord.ui.View):
    def __init__(self, streamer, schicht, lead):
        super().__init__(timeout=None)
        self.streamer = streamer
        self.schicht = schicht
        self.lead = lead

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
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
