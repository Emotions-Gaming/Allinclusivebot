import discord
from discord.ext import commands
from discord import app_commands
from utils import load_json, save_json, is_admin
import asyncio

ALARM_CONFIG_FILE = "persistent_data/alarm_config.json"
ALARM_LOG_FILE = "persistent_data/alarm_log.json"

class AlarmSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alarm_cfg = load_json(ALARM_CONFIG_FILE, {
            "alarm_roles": [],
            "alarm_leads": [],
            "alarm_users": [],
            "alarm_log_channel": None
        })

    # ========== Alarm Lead setzen/entfernen ==========
    @app_commands.command(name="alarmlead", description="Fügt einen Alarm Lead hinzu")
    @app_commands.describe(user="Nutzer als Lead festlegen")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id not in self.alarm_cfg["alarm_leads"]:
            self.alarm_cfg["alarm_leads"].append(user.id)
            save_json(ALARM_CONFIG_FILE, self.alarm_cfg)
            await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} ist bereits AlarmLead.", ephemeral=True)

    @app_commands.command(name="alarmleadremove", description="Entfernt einen Alarm Lead")
    @app_commands.describe(user="Nutzer als Lead entfernen")
    async def alarmleadremove(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id in self.alarm_cfg["alarm_leads"]:
            self.alarm_cfg["alarm_leads"].remove(user.id)
            save_json(ALARM_CONFIG_FILE, self.alarm_cfg)
            await interaction.response.send_message(f"{user.mention} ist kein AlarmLead mehr.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} war kein AlarmLead.", ephemeral=True)

    # ========== Alarm Users Rollen festlegen ==========
    @app_commands.command(name="alarmusers", description="Fügt eine Rolle zu den AlarmUsers hinzu")
    @app_commands.describe(role="Rolle für Alarm-Anfragen")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in self.alarm_cfg["alarm_users"]:
            self.alarm_cfg["alarm_users"].append(role.id)
            save_json(ALARM_CONFIG_FILE, self.alarm_cfg)
            await interaction.response.send_message(f"{role.mention} ist jetzt AlarmUser-Rolle.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{role.mention} ist bereits AlarmUser-Rolle.", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle von den AlarmUsers")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.alarm_cfg["alarm_users"]:
            self.alarm_cfg["alarm_users"].remove(role.id)
            save_json(ALARM_CONFIG_FILE, self.alarm_cfg)
            await interaction.response.send_message(f"{role.mention} ist keine AlarmUser-Rolle mehr.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{role.mention} war keine AlarmUser-Rolle.", ephemeral=True)

    # ========== Log Channel festlegen ==========
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Anfragen")
    @app_commands.describe(channel="Logkanal")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.alarm_cfg["alarm_log_channel"] = channel.id
        save_json(ALARM_CONFIG_FILE, self.alarm_cfg)
        await interaction.response.send_message(f"Alarm LogChannel gesetzt: {channel.mention}", ephemeral=True)

    # ========== ALARM MAIN (fester Info-Post mit Button) ==========
    @app_commands.command(name="alarmmain", description="Postet Alarm-Schichtanfrage Menü mit Button")
    async def alarmmain(self, interaction: discord.Interaction):
        # Nur AlarmLead oder Admin
        if not is_admin(interaction.user) and interaction.user.id not in self.alarm_cfg["alarm_leads"]:
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

        embed = discord.Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Du bist AlarmLead oder Admin und kannst hier eine neue Alarm-Schichtanfrage posten.\n"
                "Drücke auf **Anfrage erstellen** um die Schicht einzutragen.\n\n"
                "Der Claim-Button ist für alle sichtbar!"
            ),
            color=discord.Color.red()
        )
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="Anfrage erstellen", style=discord.ButtonStyle.danger)

        async def btn_cb(inter):
            # Nur AlarmLead oder Admin
            if not is_admin(inter.user) and inter.user.id not in self.alarm_cfg["alarm_leads"]:
                return await inter.response.send_message("Keine Berechtigung!", ephemeral=True)
            # Modal/Popup für Daten:
            class AlarmModal(discord.ui.Modal, title="Alarm Schichtanfrage"):
                streamer = discord.ui.TextInput(label="Name Streamer", style=discord.TextStyle.short, required=True)
                zeit = discord.ui.TextInput(label="Welche Schicht (z.B. Montag 19.06 06:00 - 12:00)", style=discord.TextStyle.short, required=True)
                info = discord.ui.TextInput(label="Sonstiges (optional)", style=discord.TextStyle.paragraph, required=False)

                async def on_submit(self, m_inter):
                    alarm_users_mentions = [
                        inter.guild.get_role(rid).mention
                        for rid in self.alarm_cfg["alarm_users"]
                        if inter.guild.get_role(rid)
                    ]
                    alarm_users_ping = " ".join(alarm_users_mentions) if alarm_users_mentions else "@everyone"
                    post = await inter.channel.send(
                        content=f"{alarm_users_ping}\n**Dringend Chatter benötigt!**",
                        embed=discord.Embed(
                            title=f"Alarm: {self.streamer.value}",
                            description=(
                                f"**Zeit:** {self.zeit.value}\n"
                                f"{self.info.value.strip() if self.info.value else ''}\n\n"
                                f"**Claim diesen Alarm, wenn du übernehmen willst!**"
                            ),
                            color=discord.Color.orange()
                        ),
                        view=self.get_claim_view(inter.guild, self.streamer.value, self.zeit.value, self.info.value)
                    )
                    await m_inter.response.send_message("Alarmanfrage gepostet.", ephemeral=True)

            await inter.response.send_modal(AlarmModal())

        btn.callback = btn_cb
        view.add_item(btn)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Alarm-Schichtsystem Menü gepostet.", ephemeral=True)

    # ========== CLAIM VIEW ==========
    def get_claim_view(self, guild, streamer, zeit, info):
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="Claim", style=discord.ButtonStyle.success)

        async def claim_cb(inter):
            await inter.message.delete()
            # DM an Claimer
            msg = (
                f"**Danke fürs Übernehmen der Schicht!**\n"
                f"Streamer: **{streamer}**\nZeit: **{zeit}**\n"
                f"{info.strip() if info else ''}\n"
                "\nBitte befinde dich 15 Minuten vor Schichtbeginn im General Discordchannel."
            )
            try:
                await inter.user.send(msg)
            except Exception:
                pass
            # Log
            alarm_log_id = self.alarm_cfg.get("alarm_log_channel")
            if alarm_log_id:
                log_channel = guild.get_channel(alarm_log_id)
                if log_channel:
                    await log_channel.send(
                        f"📝 Schicht von {streamer} am {zeit} wurde übernommen von {inter.user.mention} ({inter.user.name})"
                    )
            # Lead benachrichtigen
            lead_mentions = [guild.get_member(lead_id).mention for lead_id in self.alarm_cfg.get("alarm_leads", []) if guild.get_member(lead_id)]
            if lead_mentions:
                await inter.channel.send(f"Bitte melde dich bei {', '.join(lead_mentions)} für weitere Details!", delete_after=30)

        btn.callback = claim_cb
        view.add_item(btn)
        return view

async def setup(bot):
    await bot.add_cog(AlarmSystem(bot))
