import discord
from discord import app_commands
from discord.ext import commands

from utils import load_json, save_json, is_admin

ALARM_CONFIG_FILE = "alarm_config.json"

# Initialisiere oder lade Config
alarm_config = load_json(ALARM_CONFIG_FILE, {
    "lead_user_id": None,
    "alarm_roles": [],
    "alarm_notify_roles": [],
    "log_channel_id": None
})

def save_alarm_config():
    save_json(ALARM_CONFIG_FILE, alarm_config)

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----- LEAD SETZEN, ANZEIGEN, ENTFERNEN -----
    @app_commands.command(name="alarmlead", description="Setzt den Alarm-Lead (Discord-User)")
    @app_commands.describe(user="User als Lead")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        alarm_config["lead_user_id"] = user.id
        save_alarm_config()
        await interaction.response.send_message(f"Alarm-Lead gesetzt: {user.mention}", ephemeral=True)

    @app_commands.command(name="alarmleadshow", description="Zeigt den aktuellen Alarm-Lead")
    async def alarmleadshow(self, interaction: discord.Interaction):
        lead_id = alarm_config.get("lead_user_id")
        if not lead_id:
            return await interaction.response.send_message("Kein Alarm-Lead gesetzt.", ephemeral=True)
        lead_user = interaction.guild.get_member(lead_id)
        if lead_user:
            await interaction.response.send_message(f"Aktueller Alarm-Lead: {lead_user.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Lead nicht gefunden (ID: {lead_id})", ephemeral=True)

    @app_commands.command(name="alarmleadremove", description="Entfernt den aktuellen Alarm-Lead")
    async def alarmleadremove(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if not alarm_config.get("lead_user_id"):
            return await interaction.response.send_message("Es ist kein Alarm-Lead gesetzt.", ephemeral=True)
        alarm_config["lead_user_id"] = None
        save_alarm_config()
        await interaction.response.send_message("Alarm-Lead entfernt.", ephemeral=True)

    # ----- ROLLE FÜR ALARM-HANDLER HINZUFÜGEN/ENTFERNEN -----
    @app_commands.command(name="alarmrole", description="Fügt eine Rolle hinzu, die den Alarm auslösen darf")
    @app_commands.describe(role="Rolle für Alarm-Auslösung")
    async def alarmrole(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in alarm_config["alarm_roles"]:
            alarm_config["alarm_roles"].append(role.id)
            save_alarm_config()
        await interaction.response.send_message(f"Rolle {role.mention} kann jetzt Alarme auslösen.", ephemeral=True)

    @app_commands.command(name="alarmroledelete", description="Entfernt eine Alarm-Rolle")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmroledelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in alarm_config["alarm_roles"]:
            alarm_config["alarm_roles"].remove(role.id)
            save_alarm_config()
            await interaction.response.send_message(f"Rolle {role.mention} kann keine Alarme mehr auslösen.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} ist keine Alarm-Rolle.", ephemeral=True)

    # ----- ROLLE FÜR NOTIFICATION HINZUFÜGEN/ENTFERNEN -----
    @app_commands.command(name="alarmusers", description="Fügt eine Rolle hinzu, die bei Alarmen gepingt wird")
    @app_commands.describe(role="Rolle zum Pingen")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in alarm_config["alarm_notify_roles"]:
            alarm_config["alarm_notify_roles"].append(role.id)
            save_alarm_config()
        await interaction.response.send_message(f"Rolle {role.mention} wird jetzt bei Alarmschichten gepingt.", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle aus den Alarm-Pings")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in alarm_config["alarm_notify_roles"]:
            alarm_config["alarm_notify_roles"].remove(role.id)
            save_alarm_config()
            await interaction.response.send_message(f"Rolle {role.mention} wird nicht mehr bei Alarmen gepingt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} ist kein Alarm-Ping.", ephemeral=True)

    # ----- LOG-KANAL FESTLEGEN -----
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarme")
    @app_commands.describe(channel="Log-Channel")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        alarm_config["log_channel_id"] = channel.id
        save_alarm_config()
        await interaction.response.send_message(f"Log-Channel für Alarme gesetzt: {channel.mention}", ephemeral=True)

    # ----- ALARM-Hauptsystem: Alarm-Request posten (Button, Claim etc.) -----
    @app_commands.command(name="alarmmain", description="Erstellt eine neue Alarm-Schicht-Anfrage (Button für Berechtigte)")
    async def alarmmain(self, interaction: discord.Interaction):
        # Berechtigung: Alarm-Role oder Admin
        allowed_roles = alarm_config.get("alarm_roles", [])
        if not (is_admin(interaction.user) or any(r.id in allowed_roles for r in interaction.user.roles)):
            return await interaction.response.send_message("Keine Berechtigung für Alarm.", ephemeral=True)

        class AlarmRequestModal(discord.ui.Modal, title="Neue Alarmschicht erstellen"):
            streamer = discord.ui.TextInput(label="Name des Streamers", required=True, max_length=80)
            schicht = discord.ui.TextInput(label="Welche Schicht (Datum, Uhrzeit)?", required=True, max_length=80)
            async def on_submit(self, modal_inter: discord.Interaction):
                # Nachricht und Button posten
                ping_roles = [f"<@&{rid}>" for rid in alarm_config.get("alarm_notify_roles", [])]
                ping_text = " ".join(ping_roles) if ping_roles else "@here"
                embed = discord.Embed(
                    title="🚨 **Dringend Chatter benötigt!**",
                    description=(
                        f"**Streamer:** {self.streamer.value}\n"
                        f"**Schicht:** {self.schicht.value}\n\n"
                        f"{ping_text}"
                    ),
                    color=discord.Color.red()
                )
                claim_view = discord.ui.View(timeout=None)
                async def claim_callback(btn_inter):
                    # DM + Log
                    await btn_inter.response.send_message(
                        f"Du hast die Schicht übernommen!\nStreamer: **{self.streamer.value}**\nSchicht: **{self.schicht.value}**"
                        f"\nBitte befinde dich 15 Minuten vor Beginn im General-Discord-Channel.\n"
                        f"Bitte melde dich bei {await get_alarm_lead_mention(btn_inter.guild) or 'dem zuständigen Lead'}!",
                        ephemeral=True
                    )
                    # Log-Channel
                    log_id = alarm_config.get("log_channel_id")
                    log_ch = btn_inter.guild.get_channel(log_id) if log_id else None
                    if log_ch:
                        await log_ch.send(
                            f"✅ **Schicht übernommen:**\n"
                            f"- Streamer: **{self.streamer.value}**\n"
                            f"- Schicht: **{self.schicht.value}**\n"
                            f"- Von: {btn_inter.user.mention}"
                        )
                    # Ursprungsanfrage löschen
                    try:
                        await btn_inter.message.delete()
                    except Exception:
                        pass
                claim_btn = discord.ui.Button(label="Claim", style=discord.ButtonStyle.success)
                claim_btn.callback = claim_callback
                claim_view.add_item(claim_btn)
                await modal_inter.channel.send(embed=embed, view=claim_view)
                await modal_inter.response.send_message("Alarmschicht erstellt.", ephemeral=True)

        await interaction.response.send_modal(AlarmRequestModal())

# ---- Helper für Lead-Mention ----
async def get_alarm_lead_mention(guild):
    lead_id = alarm_config.get("lead_user_id")
    if lead_id:
        lead_user = guild.get_member(lead_id)
        if lead_user:
            return lead_user.mention
    return None

# ----- Setup -----
async def setup(bot):
    await bot.add_cog(Alarm(bot))
