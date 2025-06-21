import discord
from discord import app_commands
from discord.ext import commands
from utils import load_json, save_json, is_admin

import asyncio

GUILD_ID = int(os.getenv("GUILD_ID") or "1249813174731931740")

ALARM_CONFIG_FILE = "alarm_config.json"
ALARM_LOG_FILE = "alarm_log.json"

# Load persistent data
alarm_config = load_json(ALARM_CONFIG_FILE, {
    "lead_id": None,
    "user_roles": [],
    "log_channel_id": None
})

alarm_log = load_json(ALARM_LOG_FILE, [])

class Alarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Utility: Save config
    def save(self):
        save_json(ALARM_CONFIG_FILE, alarm_config)
        save_json(ALARM_LOG_FILE, alarm_log)

    # Helper: Get Lead member
    def get_lead(self, guild):
        if not alarm_config["lead_id"]:
            return None
        return guild.get_member(alarm_config["lead_id"])

    # Only Lead or Admin
    def is_lead_or_admin(self, user):
        return (user.id == alarm_config["lead_id"]) or is_admin(user)

    # ===================
    #   Slash-Commands
    # ===================

    @app_commands.command(name="alarmmain", description="Postet das Alarm-Schichtsystem Menü")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmmain(self, interaction: discord.Interaction):
        lead = self.get_lead(interaction.guild)
        embed = discord.Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Drücke auf **Anfrage erstellen**, um eine neue Alarm-Schichtanfrage zu posten.\n\n"
                "Du bist AlarmLead/Admin? Dann kannst du zusätzlich Schichten direkt zuteilen per Command.\n\n"
                "**Direkt-Schichtzuteilung:**\n"
                "```/alarmzuteilung [nutzer]```"
            ),
            color=discord.Color.red()
        )
        if lead:
            embed.set_footer(text=f"AlarmLead: {lead.display_name}")

        view = discord.ui.View(timeout=None)
        # Nur Lead/Admin darf Anfrage erstellen!
        if self.is_lead_or_admin(interaction.user):
            btn = discord.ui.Button(label="Anfrage erstellen", style=discord.ButtonStyle.danger)
            async def create_callback(btn_inter):
                # PopUp Modal
                class AlarmModal(discord.ui.Modal, title="Alarm-Schicht anlegen"):
                    streamer = discord.ui.TextInput(label="Name Streamer", required=True)
                    schicht = discord.ui.TextInput(label="Schichtzeit (Datum/Uhrzeit)", required=True)
                    async def on_submit(modal_inter):
                        users_role = None
                        if alarm_config["user_roles"]:
                            for rid in alarm_config["user_roles"]:
                                role = interaction.guild.get_role(rid)
                                if role:
                                    users_role = role
                                    break
                        mention = users_role.mention if users_role else "@everyone"
                        msg = (
                            f"{mention}\n"
                            f"Dringend Chatter benötigt!\n"
                            f"Streamer: **{self.streamer.value}**\n"
                            f"Zeit: **{self.schicht.value}**\n"
                        )
                        claim_view = discord.ui.View(timeout=None)
                        claim_btn = discord.ui.Button(label="Claim", style=discord.ButtonStyle.success)
                        async def claim_cb(claim_inter):
                            await claim_inter.response.send_message(
                                f"Du hast die Schicht übernommen! Checke deine DMs für Details.",
                                ephemeral=True
                            )
                            await claim_msg.delete()
                            # DM an den User
                            try:
                                await claim_inter.user.send(
                                    f"Du hast eine Schicht übernommen für:\n"
                                    f"Streamer: **{self.streamer.value}**\n"
                                    f"Zeit: **{self.schicht.value}**\n\n"
                                    "Bitte erscheine 15 Minuten vor Schichtbeginn im General Discordchannel."
                                )
                            except Exception:
                                pass
                            # Log in Channel
                            log_id = alarm_config.get("log_channel_id")
                            if log_id:
                                log_ch = interaction.guild.get_channel(log_id)
                                if log_ch:
                                    await log_ch.send(
                                        f"✅ {claim_inter.user.mention} hat die Schicht übernommen: "
                                        f"{self.streamer.value}, {self.schicht.value}"
                                    )
                        claim_btn.callback = claim_cb
                        claim_view.add_item(claim_btn)
                        claim_msg = await interaction.channel.send(msg, view=claim_view)
                        await modal_inter.response.send_message("Anfrage gepostet!", ephemeral=True)
                await btn_inter.response.send_modal(AlarmModal())
            btn.callback = create_callback
            view.add_item(btn)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name="alarmlead", description="Setzt oder zeigt den aktuellen Alarm-Lead")
    @app_commands.describe(user="User zum Lead machen (leer lassen zum Anzeigen)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmlead(self, interaction: discord.Interaction, user: discord.Member = None):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        if user:
            alarm_config["lead_id"] = user.id
            self.save()
            await interaction.response.send_message(f"{user.mention} ist jetzt AlarmLead!", ephemeral=True)
        else:
            lead = self.get_lead(interaction.guild)
            if lead:
                await interaction.response.send_message(f"AlarmLead: {lead.mention}", ephemeral=True)
            else:
                await interaction.response.send_message("Kein AlarmLead gesetzt.", ephemeral=True)
        # Update Menü falls existiert
        await self._update_alarmmain(interaction.guild)

    @app_commands.command(name="alarmleadremove", description="Entfernt den AlarmLead")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmleadremove(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        alarm_config["lead_id"] = None
        self.save()
        await interaction.response.send_message("AlarmLead entfernt!", ephemeral=True)
        await self._update_alarmmain(interaction.guild)

    @app_commands.command(name="alarmusers", description="Fügt eine Rolle als Alarm-Schichtbenutzer hinzu")
    @app_commands.describe(role="Rolle die Alarmanfragen erhalten darf")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmusers(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        if role.id not in alarm_config["user_roles"]:
            alarm_config["user_roles"].append(role.id)
            self.save()
        await interaction.response.send_message(f"Rolle {role.mention} hinzugefügt.", ephemeral=True)

    @app_commands.command(name="alarmusersremove", description="Entfernt eine AlarmUser-Rolle")
    @app_commands.describe(role="Rolle entfernen")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmusersremove(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        if role.id in alarm_config["user_roles"]:
            alarm_config["user_roles"].remove(role.id)
            self.save()
        await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)

    @app_commands.command(name="alarmlog", description="Setzt den Logkanal für Alarm-Schichten")
    @app_commands.describe(channel="Log-Channel")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admins!", ephemeral=True)
        alarm_config["log_channel_id"] = channel.id
        self.save()
        await interaction.response.send_message(f"Alarm-Logkanal ist jetzt {channel.mention}.", ephemeral=True)

    @app_commands.command(name="alarmzuteilung", description="Lead/Admin teilt einem Nutzer direkt eine Schicht zu")
    @app_commands.describe(nutzer="User für Schicht")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def alarmzuteilung(self, interaction: discord.Interaction, nutzer: discord.Member):
        if not self.is_lead_or_admin(interaction.user):
            return await interaction.response.send_message("Nur Lead/Admin!", ephemeral=True)
        # PopUp Modal
        class ZuteilungModal(discord.ui.Modal, title="Schicht direkt zuteilen"):
            streamer = discord.ui.TextInput(label="Name Streamer", required=True)
            schicht = discord.ui.TextInput(label="Schichtzeit (Datum/Uhrzeit)", required=True)
            async def on_submit(self, modal_inter):
                # DM an Nutzer
                try:
                    await nutzer.send(
                        f"{interaction.user.mention} hat dich zur Schicht eingeteilt!\n\n"
                        f"Streamer: **{self.streamer.value}**\n"
                        f"Zeit: **{self.schicht.value}**\n\n"
                        "Bitte erscheine 15 Minuten vor Schichtbeginn im Discord General Channel."
                    )
                except Exception:
                    pass
                # Log in Channel
                log_id = alarm_config.get("log_channel_id")
                if log_id:
                    log_ch = interaction.guild.get_channel(log_id)
                    if log_ch:
                        await log_ch.send(
                            f"⚡️ {interaction.user.mention} hat {nutzer.mention} zur Schicht eingeteilt: "
                            f"{self.streamer.value}, {self.schicht.value}"
                        )
                await modal_inter.response.send_message(f"{nutzer.mention} wurde benachrichtigt & Log erstellt!", ephemeral=True)
        await interaction.response.send_modal(ZuteilungModal())

    # --- Hilfsfunktion für Alarmmain-Update ---
    async def _update_alarmmain(self, guild):
        # Find a "latest" AlarmMain message (by this bot)
        for ch in guild.text_channels:
            try:
                async for msg in ch.history(limit=10):
                    if msg.author == guild.me and msg.embeds:
                        if (msg.embeds[0].title or "").startswith("🚨 Alarm-Schichtsystem"):
                            lead = self.get_lead(guild)
                            em = msg.embeds[0]
                            if lead:
                                em.set_footer(text=f"AlarmLead: {lead.display_name}")
                            else:
                                em.set_footer(text="Kein AlarmLead gesetzt.")
                            await msg.edit(embed=em)
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(Alarm(bot))
