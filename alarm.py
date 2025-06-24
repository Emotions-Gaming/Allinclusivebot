# alarm.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
ALARM_CONFIG_PATH = os.path.join("persistent_data", "alarm_config.json")

def format_time(ts=None):
    return datetime.now().strftime("%d.%m.%Y %H:%M") if ts is None else ts

def get_lead_mention(guild, lead_id):
    if not lead_id:
        return "Nicht gesetzt"
    member = guild.get_member(lead_id)
    return member.mention if member else f"<@{lead_id}>"

class AlarmMainPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Schichtanfrage erstellen", style=discord.ButtonStyle.green, emoji="🟢")
    async def create_alarm(self, interaction: Interaction, button: discord.ui.Button):
        cog = self.cog
        if not await cog.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        await interaction.response.send_modal(AlarmCreateModal(cog))

    @discord.ui.button(label="Befehl kopieren", style=discord.ButtonStyle.gray, emoji="📋")
    async def copy_cmd(self, interaction: Interaction, button: discord.ui.Button):
        await utils.send_ephemeral(
            interaction,
            text="Kopiere den Befehl unten:\n```/alarmzuteilung [user]```",
            emoji="📋",
            color=discord.Color.blurple()
        )

class AlarmCreateModal(discord.ui.Modal, title="Neue Schichtanfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamername(n)",
            placeholder="Wen betreust du? (Mehrere möglich)",
            required=True
        )
        self.zeit = discord.ui.TextInput(
            label="Datum/Uhrzeit der Schicht",
            placeholder="z.B. 23.07.2025 19:00-22:00 Uhr",
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.zeit)

    async def on_submit(self, interaction: Interaction):
        cog = self.cog
        cfg = await cog.get_config()
        channel = interaction.channel
        user_role_ids = cfg.get("user_role_ids", [])
        ping_roles = utils.mention_roles(interaction.guild, user_role_ids)
        embed = discord.Embed(
            title="📝 Schichtanfrage",
            description=(
                f"**Streamer:** {self.streamer.value}\n"
                f"**Zeit:** {self.zeit.value}\n\n"
                f"{ping_roles if ping_roles else '_(Keine Rollen zum Pingen gesetzt)_'}\n"
                "\nKlicke auf den Button, um diese Schicht zu übernehmen!"
            ),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        view = ClaimView(cog, self.streamer.value, self.zeit.value)
        msg = await channel.send(embed=embed, view=view)
        await interaction.response.send_message("Schichtanfrage gepostet!", ephemeral=True)

class ClaimView(discord.ui.View):
    def __init__(self, cog, streamer, zeit):
        super().__init__(timeout=None)
        self.cog = cog
        self.streamer = streamer
        self.zeit = zeit

    @discord.ui.button(label="Schicht übernehmen", style=discord.ButtonStyle.green, emoji="✅")
    async def claim_btn(self, interaction: Interaction, button: discord.ui.Button):
        cfg = await self.cog.get_config()
        claimer = interaction.user
        zeitinfo = self.zeit
        streamerinfo = self.streamer
        log_channel = interaction.guild.get_channel(cfg.get("log_channel_id", 0)) if cfg.get("log_channel_id") else None
        info_text = (
            f"**Danke fürs Übernehmen der Schicht am {zeitinfo}!**\n"
            f"Du hast folgende Streamer: **{streamerinfo}**"
        )
        try:
            await claimer.send(info_text)
            dm_ok = True
        except Exception:
            dm_ok = False
        log_msg = (
            f"✅ {claimer.mention} hat die Schicht am `{zeitinfo}` für **{streamerinfo}** angenommen und wurde somit eingeteilt."
        )
        if log_channel:
            await log_channel.send(log_msg)
            if not dm_ok:
                await log_channel.send(
                    f"⚠️ {claimer.mention} konnte nicht angeschrieben werden (DM blockiert oder nicht erlaubt). Bitte selbstständig melden!"
                )
        await interaction.response.send_message("Schicht übernommen!", ephemeral=True)
        try:
            await interaction.message.delete()
        except Exception:
            pass

class AlarmZuteilModal(discord.ui.Modal, title="User direkt zu Schicht zuweisen"):
    def __init__(self, cog, user):
        super().__init__()
        self.cog = cog
        self.target = user
        self.streamer = discord.ui.TextInput(
            label="Streamername(n)",
            placeholder="Wen soll der User betreuen? (Mehrere möglich)",
            required=True
        )
        self.zeit = discord.ui.TextInput(
            label="Datum/Uhrzeit der Schicht",
            placeholder="z.B. 23.07.2025 19:00-22:00 Uhr",
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.zeit)

    async def on_submit(self, interaction: Interaction):
        zeitinfo = self.zeit.value
        streamerinfo = self.streamer.value
        cfg = await self.cog.get_config()
        log_channel = interaction.guild.get_channel(cfg.get("log_channel_id", 0)) if cfg.get("log_channel_id") else None
        lead = interaction.user
        target = self.target
        dm_text = (
            f"**Du wurdest zu der Schicht am {zeitinfo} zugeteilt!**\n"
            f"Du betreust folgende Streamer: **{streamerinfo}**\n"
            "Bitte sei 15 Minuten vor Schichtbeginn im General anwesend!"
        )
        try:
            await target.send(dm_text)
            dm_ok = True
        except Exception:
            dm_ok = False
        log_msg = (
            f"📝 {lead.mention} hat {target.mention} zur Schicht am `{zeitinfo}` für **{streamerinfo}** eingeteilt."
        )
        if log_channel:
            await log_channel.send(log_msg)
            if not dm_ok:
                await log_channel.send(
                    f"⚠️ {target.mention} konnte nicht angeschrieben werden (DM blockiert oder nicht erlaubt). Bitte selbstständig melden!"
                )
        await utils.send_success(interaction, f"{target.mention} wurde zugeteilt.")

class AlarmCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== Helper ==========
    async def get_config(self):
        return await utils.load_json(ALARM_CONFIG_PATH, {})

    async def save_config(self, data):
        await utils.save_json(ALARM_CONFIG_PATH, data)

    async def update_panel(self, guild):
        cfg = await self.get_config()
        main_channel_id = cfg.get("main_channel_id")
        main_message_id = cfg.get("main_message_id")
        if not main_channel_id:
            return
        channel = guild.get_channel(main_channel_id)
        if not channel:
            return
        try:
            if main_message_id:
                msg = await channel.fetch_message(main_message_id)
                await msg.delete()
        except Exception:
            pass
        embed, view = await self.make_panel_embed(guild)
        msg = await channel.send(embed=embed, view=view)
        cfg["main_message_id"] = msg.id
        await self.save_config(cfg)

    async def make_panel_embed(self, guild):
        cfg = await self.get_config()
        lead = get_lead_mention(guild, cfg.get("lead_id"))
        streamercopy = "/alarmzuteilung [user]"
        embed = discord.Embed(
            title="🚨 Alarm-Schichtsystem – Hauptpanel",
            description=(
                f"**Aktueller AlarmLead:** {lead}\n\n"
                "➔ Klicke unten auf „Schichtanfrage erstellen“ um eine neue Schicht anzulegen.\n"
                "➔ Oder benutze `/alarmzuteilung [user]` für eine direkte Zuteilung (siehe Copy-Button).\n"
                "\n**Ablauf Claim:**\n"
                "1. Claim-Button klicken\n"
                "2. Claim wird geloggt, Schichtanfrage verschwindet\n"
                "3. Du bekommst alle Infos als DM\n"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Schnellbefehl kopieren:", value=f"`{streamercopy}`", inline=False)
        view = AlarmMainPanelView(self)
        return embed, view

    async def is_lead(self, user, guild):
        cfg = await self.get_config()
        lead_id = cfg.get("lead_id")
        return utils.is_admin(user) or (lead_id and int(lead_id) == user.id)

    # ========== SLASH COMMANDS ==========

    @app_commands.command(
        name="alarmmain",
        description="Postet oder aktualisiert das Alarm-Schichtsystem-Panel (nur Lead/Admin)."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmmain(self, interaction: Interaction):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        channel = interaction.channel
        cfg["main_channel_id"] = channel.id
        await self.save_config(cfg)
        await self.update_panel(interaction.guild)
        await utils.send_success(interaction, "Alarm-Panel aktualisiert!")

    @app_commands.command(
        name="alarmlead",
        description="Setzt den AlarmLead für Schichten (nur Admins/Lead)."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmlead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        cfg["lead_id"] = user.id
        await self.save_config(cfg)
        await utils.send_success(interaction, f"AlarmLead gesetzt: {user.mention}")
        await self.update_panel(interaction.guild)

    @app_commands.command(
        name="alarmlead_remove",
        description="Entfernt den aktuellen AlarmLead (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmlead_remove(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if cfg.get("lead_id") == user.id:
            cfg["lead_id"] = None
            await self.save_config(cfg)
            await utils.send_success(interaction, f"{user.mention} ist nicht mehr Lead.")
            await self.update_panel(interaction.guild)
        else:
            await utils.send_error(interaction, f"{user.mention} ist nicht der aktuelle Lead.")

    @app_commands.command(
        name="alarmlead_info",
        description="Zeigt den aktuellen AlarmLead (privat, nur Admins/Lead)."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmlead_info(self, interaction: Interaction):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        guild = interaction.guild
        lead = get_lead_mention(guild, cfg.get("lead_id"))
        await utils.send_ephemeral(
            interaction,
            text=f"Aktueller AlarmLead: {lead}",
            emoji="🚨",
            color=discord.Color.blurple()
        )

    @app_commands.command(
        name="alarmusers_add",
        description="Fügt eine Rolle zu den pingbaren Userrollen hinzu."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmusers_add(self, interaction: Interaction, role: discord.Role):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        user_role_ids = set(cfg.get("user_role_ids", []))
        user_role_ids.add(role.id)
        cfg["user_role_ids"] = list(user_role_ids)
        await self.save_config(cfg)
        await utils.send_success(interaction, f"Rolle {role.mention} hinzugefügt.")

    @app_commands.command(
        name="alarmusers_remove",
        description="Entfernt eine Rolle von den pingbaren Userrollen."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmusers_remove(self, interaction: Interaction, role: discord.Role):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        user_role_ids = set(cfg.get("user_role_ids", []))
        if role.id in user_role_ids:
            user_role_ids.remove(role.id)
            cfg["user_role_ids"] = list(user_role_ids)
            await self.save_config(cfg)
            await utils.send_success(interaction, f"Rolle {role.mention} entfernt.")
        else:
            await utils.send_error(interaction, "Diese Rolle ist nicht in der Pingliste.")

    @app_commands.command(
        name="alarmlog",
        description="Setzt den Logchannel für Claims/Zuteilungen."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmlog(self, interaction: Interaction, channel: discord.TextChannel):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        cfg["log_channel_id"] = channel.id
        await self.save_config(cfg)
        await utils.send_success(interaction, f"Logchannel gesetzt: {channel.mention}")

    @app_commands.command(
        name="alarmzuteilung",
        description="Teilt direkt einen User einer Schicht zu (Modal, Lead/Admin only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def alarmzuteilung(self, interaction: Interaction, user: discord.Member):
        if not await self.is_lead(interaction.user, interaction.guild):
            return await utils.send_permission_denied(interaction)
        await interaction.response.send_modal(AlarmZuteilModal(self, user))


# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(AlarmCog(bot))
