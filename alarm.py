import discord
from discord import app_commands
from discord.ext import commands
from utils import load_json, save_json, is_admin

import os

ALARM_CONFIG_PATH = os.path.join("persistent_data", "alarm_config.json")
ALARM_LOG_PATH = os.path.join("persistent_data", "alarm_log.json")

class AlarmSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alarm_cfg = load_json(ALARM_CONFIG_PATH, {
            "alarm_leads": [],
            "alarm_users": [],
            "alarm_log_channel": None
        })
        self.alarm_log = load_json(ALARM_LOG_PATH, [])

    def save_config(self):
        save_json(ALARM_CONFIG_PATH, self.alarm_cfg)

    def save_log(self):
        save_json(ALARM_LOG_PATH, self.alarm_log)

    def get_claim_view(self, guild, streamer, zeit, info):
        class ClaimView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.claimed = False

            @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
            async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.claimed:
                    return await interaction.response.send_message("Diese Schicht wurde bereits übernommen!", ephemeral=True)
                self.claimed = True

                # Benachrichtigung an Claimer
                msg = (
                    f"✅ **Danke fürs Übernehmen der Schicht!**\n\n"
                    f"**Streamer:** {streamer}\n"
                    f"**Zeit:** {zeit}\n"
                    f"{'Zusatz: ' + info if info else ''}\n\n"
                    "Bitte sei **15 Minuten vor Schichtbeginn im General-Discordchannel**.\n"
                )
                try:
                    await interaction.user.send(msg)
                except Exception:
                    pass

                # Log anlegen
                alarm_log_entry = {
                    "streamer": streamer,
                    "zeit": zeit,
                    "info": info,
                    "claimer_id": interaction.user.id,
                    "claimer_name": interaction.user.display_name,
                    "claimed_at": discord.utils.utcnow().isoformat()
                }
                self.cog = self.cog if hasattr(self, 'cog') else None
                if self.cog:
                    self.cog.alarm_log.append(alarm_log_entry)
                    self.cog.save_log()
                    # Logchannel-Post
                    log_channel_id = self.cog.alarm_cfg.get("alarm_log_channel")
                    if log_channel_id:
                        log_ch = guild.get_channel(log_channel_id)
                        if log_ch:
                            await log_ch.send(
                                f"**Schicht von {streamer} ({zeit})** wurde von {interaction.user.mention} übernommen!"
                            )
                await interaction.message.delete()

        v = ClaimView()
        v.cog = self  # für Log-Speicherung
        return v

    # --- Slash Commands ---

    @app_commands.command(name="alarmmain", description="Poste das Alarm-Schichtsystem (nur Admin/AlarmLead)")
    async def alarmmain(self, interaction: discord.Interaction):
        # Nur AlarmLead/Admin
        if not is_admin(interaction.user) and interaction.user.id not in self.alarm_cfg["alarm_leads"]:
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

        embed = discord.Embed(
            title=":rotating_light: Alarm-Schichtsystem",
            description=(
                "Du bist AlarmLead oder Admin und kannst hier eine neue Alarm-Schichtanfrage posten.\n"
                "Drücke auf **Anfrage erstellen** um die Schicht einzutragen.\n\n"
                "Der Claim-Button ist für alle sichtbar!"
            ),
            color=discord.Color.red()
        )

        view = discord.ui.View(timeout=None)

        async def btn_cb(inter):
            # Nur AlarmLead/Admin
            if not is_admin(inter.user) and inter.user.id not in self.alarm_cfg["alarm_leads"]:
                return await inter.response.send_message("Keine Berechtigung!", ephemeral=True)
            alarm_cfg = self.alarm_cfg.copy()
            cog = self

            class AlarmModal(discord.ui.Modal, title="Alarm Schichtanfrage"):
                streamer = discord.ui.TextInput(label="Name Streamer", style=discord.TextStyle.short, required=True)
                zeit = discord.ui.TextInput(label="Welche Schicht (z.B. Montag 19.06 06:00 - 12:00)", style=discord.TextStyle.short, required=True)
                info = discord.ui.TextInput(label="Sonstiges (optional)", style=discord.TextStyle.paragraph, required=False)
                def __init__(self, alarm_cfg, cog):
                    super().__init__()
                    self.alarm_cfg = alarm_cfg
                    self.cog = cog
                async def on_submit(self, m_inter):
                    alarm_users_mentions = [
                        m_inter.guild.get_role(rid).mention
                        for rid in self.alarm_cfg.get("alarm_users", [])
                        if m_inter.guild.get_role(rid)
                    ]
                    alarm_users_ping = " ".join(alarm_users_mentions) if alarm_users_mentions else "@everyone"
                    try:
                        await m_inter.channel.send(
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
                            view=self.cog.get_claim_view(
                                m_inter.guild, self.streamer.value, self.zeit.value, self.info.value
                            )
                        )
                        await m_inter.response.send_message("Alarmanfrage gepostet.", ephemeral=True)
                    except Exception as e:
                        await m_inter.response.send_message(f"Fehler beim Erstellen: {e}", ephemeral=True)

            await inter.response.send_modal(AlarmModal(alarm_cfg, cog))

        view.add_item(discord.ui.Button(label="Anfrage erstellen", style=discord.ButtonStyle.danger, custom_id="btn_alarm_create"))
        view.children[0].callback = btn_cb

        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Alarm-Schichtsystem gepostet!", ephemeral=True)

    @app_commands.command(name="alarmlead", description="Setze einen AlarmLead (darf Alarmanfragen posten)")
    @app_commands.describe(user="Discord User")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id not in self.alarm_cfg["alarm_leads"]:
            self.alarm_cfg["alarm_leads"].append(user.id)
            self.save_config()
        await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead!", ephemeral=True)

    @app_commands.command(name="alarmleadremove", description="Entfernt einen AlarmLead")
    @app_commands.describe(user="Discord User")
    async def alarmleadremove(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id in self.alarm_cfg["alarm_leads"]:
            self.alarm_cfg["alarm_leads"].remove(user.id)
            self.save_config()
        await interaction.response.send_message(f"{user.mention} ist kein AlarmLead mehr!", ephemeral=True)

    @app_commands.command(name="alarmusers", description="Fügt eine Rolle zu den AlarmUsers hinzu (wird gepingt)")
    @app_commands.describe(role="Discord Rolle")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in self.alarm_cfg["alarm_users"]:
            self.alarm_cfg["alarm_users"].append(role.id)
            self.save_config()
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt AlarmUser!", ephemeral=True)

    @app_commands.command(name="alarmusersdelete", description="Entfernt eine Rolle aus AlarmUsers")
    @app_commands.describe(role="Discord Rolle")
    async def alarmusersdelete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.alarm_cfg["alarm_users"]:
            self.alarm_cfg["alarm_users"].remove(role.id)
            self.save_config()
        await interaction.response.send_message(f"Rolle {role.mention} ist kein AlarmUser mehr!", ephemeral=True)

    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Anfragen")
    @app_commands.describe(channel="Log-Channel")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.alarm_cfg["alarm_log_channel"] = channel.id
        self.save_config()
        await interaction.response.send_message(f"Alarm-Logchannel gesetzt: {channel.mention}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AlarmSystem(bot))
