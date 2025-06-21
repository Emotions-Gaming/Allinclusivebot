import discord
from discord import app_commands
from discord.ext import commands
from utils import load_json, save_json, is_admin

ALARM_CONFIG_FILE = "alarm_config.json"

class AlarmCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Beispiel-Struktur: {"alarm_leads": [userid...], "alarm_roles": [roleid...], "log_channel_id": 123, "claim_posts": {}}
        self.config = load_json(ALARM_CONFIG_FILE, {
            "alarm_leads": [],
            "alarm_roles": [],
            "log_channel_id": None,
            "claim_posts": {}
        })

    def save(self):
        save_json(ALARM_CONFIG_FILE, self.config)

    # ===== AlarmLead Verwaltung =====
    @app_commands.command(name="alarmlead", description="Setzt einen Alarm-Leiter (kann Alarm auslösen)")
    @app_commands.describe(user="Discord-User, der Alarm auslösen darf")
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id not in self.config["alarm_leads"]:
            self.config["alarm_leads"].append(user.id)
            self.save()
        await interaction.response.send_message(f"{user.mention} ist jetzt Alarm-Leiter!", ephemeral=True)

    @app_commands.command(name="alarmlead_delete", description="Entfernt einen Alarm-Leiter")
    @app_commands.describe(user="Discord-User entfernen")
    async def alarmlead_delete(self, interaction: discord.Interaction, user: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if user.id in self.config["alarm_leads"]:
            self.config["alarm_leads"].remove(user.id)
            self.save()
            await interaction.response.send_message(f"{user.mention} ist kein Alarm-Leiter mehr.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} war kein Alarm-Leiter.", ephemeral=True)

    # ===== Alarm-Rollen Verwaltung =====
    @app_commands.command(name="alarmusers", description="Fügt eine Rolle als Alarm-Empfänger hinzu (wird gepingt)")
    @app_commands.describe(role="Rolle, die alarmiert werden soll")
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id not in self.config["alarm_roles"]:
            self.config["alarm_roles"].append(role.id)
            self.save()
        await interaction.response.send_message(f"{role.mention} wird bei Alarm gepingt.", ephemeral=True)

    @app_commands.command(name="alarmusers_delete", description="Entfernt eine Alarm-Empfänger-Rolle")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusers_delete(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.config["alarm_roles"]:
            self.config["alarm_roles"].remove(role.id)
            self.save()
            await interaction.response.send_message(f"{role.mention} wird nicht mehr alarmiert.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{role.mention} war nicht alarmiert.", ephemeral=True)

    # ===== Log-Channel setzen =====
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Claims")
    @app_commands.describe(channel="Kanal für Alarm-Logs")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.config["log_channel_id"] = channel.id
        self.save()
        await interaction.response.send_message(f"Alarm-Logchannel gesetzt: {channel.mention}", ephemeral=True)

    # ===== AlarmMain: Postet eine Alarm-Anfrage =====
    @app_commands.command(name="alarmmain", description="Erstellt einen Alarm-Post mit Claim-Button")
    async def alarmmain(self, interaction: discord.Interaction):
        # Nur Alarm-Leads oder Admins
        if not (is_admin(interaction.user) or interaction.user.id in self.config["alarm_leads"]):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        # PopUp für Anfrage
        class AlarmModal(discord.ui.Modal, title="Alarm-Anfrage erstellen"):
            streamer = discord.ui.TextInput(label="Name vom Streamer", style=discord.TextStyle.short, max_length=64)
            schicht = discord.ui.TextInput(label="Welche Schicht (Datum, Zeit, etc.)", style=discord.TextStyle.short, max_length=100)
            async def on_submit(self2, modal_inter: discord.Interaction):
                alarm_roles = [interaction.guild.get_role(rid) for rid in self.config["alarm_roles"] if interaction.guild.get_role(rid)]
                role_mentions = " ".join([r.mention for r in alarm_roles])
                lead_user_id = self.config["alarm_leads"][0] if self.config["alarm_leads"] else None
                lead_user = interaction.guild.get_member(lead_user_id) if lead_user_id else None

                embed = discord.Embed(
                    title="🚨 **Dringend Chatter benötigt!**",
                    color=discord.Color.red(),
                    description=f"**Streamer:** {self2.streamer.value}\n"
                                f"**Schicht:** {self2.schicht.value}\n"
                                f"\nBitte melde dich bei {lead_user.mention if lead_user else 'dem Team'}!"
                )
                view = discord.ui.View(timeout=None)

                # Claim-Button
                class ClaimButton(discord.ui.Button):
                    def __init__(self, cog, streamer, schicht, lead_user, claim_message_id):
                        super().__init__(label="Claim übernehmen", style=discord.ButtonStyle.success)
                        self.cog = cog
                        self.streamer = streamer
                        self.schicht = schicht
                        self.lead_user = lead_user
                        self.claim_message_id = claim_message_id

                    async def callback(self, claim_inter):
                        # Log + DM
                        await claim_inter.response.send_message(
                            f"✅ Danke fürs Übernehmen!\n**Streamer:** {self.streamer}\n**Schicht:** {self.schicht}\n\n"
                            f"Bitte sei 15 Minuten vorher im General-Discord-Channel und melde dich bei {self.lead_user.mention if self.lead_user else 'dem Team'}.",
                            ephemeral=True
                        )
                        # Log ins Log-Channel
                        log_id = self.cog.config.get("log_channel_id")
                        if log_id:
                            log_ch = claim_inter.guild.get_channel(log_id)
                            if log_ch:
                                await log_ch.send(
                                    f"🔔 **Alarm-Claim:** {claim_inter.user.mention} übernimmt `{self.streamer}` | Schicht: {self.schicht}")
                        # DM
                        try:
                            await claim_inter.user.send(
                                f"Du hast die Alarm-Schicht übernommen!\n"
                                f"**Streamer:** {self.streamer}\n"
                                f"**Schicht:** {self.schicht}\n"
                                f"Bitte sei 15 Minuten vor Schichtbeginn online und melde dich bei {self.lead_user.mention if self.lead_user else 'dem Team'}.")
                        except Exception:
                            pass
                        # Lösche Post
                        msg_id = self.claim_message_id
                        if msg_id:
                            ch = claim_inter.channel
                            try:
                                msg = await ch.fetch_message(msg_id)
                                await msg.delete()
                            except Exception:
                                pass

                # Sende Alarm-Post
                msg = await interaction.channel.send(
                    content=role_mentions,
                    embed=embed
                )
                claim_button = ClaimButton(self.bot.get_cog("AlarmCog"), self2.streamer.value, self2.schicht.value, lead_user, msg.id)
                view.add_item(claim_button)
                await msg.edit(view=view)
                await modal_inter.response.send_message("Alarm wurde gepostet!", ephemeral=True)

        await interaction.response.send_modal(AlarmModal())

async def setup(bot):
    await bot.add_cog(AlarmCog(bot))
