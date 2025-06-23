import os
import discord
from discord.ext import commands
from discord import app_commands, Member, TextChannel, CategoryChannel, Role, Embed
from utils import is_admin, load_json, save_json
from permissions import has_permission_for
# Wichtig: KEIN from discord import Interaction !

GUILD_ID = int(os.environ.get("GUILD_ID"))
ALARM_JSON = "persistent_data/alarm_config.json"

def _load_alarm():
    return load_json(ALARM_JSON, {
        "lead_id": None,
        "user_role_ids": [],
        "log_channel_id": None,
        "main_channel_id": None,
        "main_message_id": None
    })

def _save_alarm(cfg):
    save_json(ALARM_JSON, cfg)

def is_lead_or_admin(user):
    cfg = _load_alarm()
    return is_admin(user) or (cfg["lead_id"] and user.id == cfg["lead_id"])

def mention_roles(guild, role_ids):
    return " ".join(r.mention for r in (guild.get_role(rid) for rid in role_ids) if r)

class AlarmCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== Hauptpanel / reload_menu ==========
    async def reload_menu(self):
        cfg = _load_alarm()
        main_channel_id = cfg.get("main_channel_id")
        if not main_channel_id:
            return
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(main_channel_id)
        if not channel:
            return
        try:
            if cfg.get("main_message_id"):
                msg = await channel.fetch_message(cfg["main_message_id"])
                await msg.delete()
        except Exception:
            pass

        embed = Embed(
            title="🚨 Alarm-Schicht Panel",
            description=(
                f"**AlarmLead:** {guild.get_member(cfg['lead_id']).mention if cfg['lead_id'] else 'Nicht gesetzt'}\n"
                f"{mention_roles(guild, cfg['user_role_ids'])}\n\n"
                "Mit dem Button unten kannst du eine Alarm-Schichtanfrage starten (nur für AlarmLead/Admin).\n\n"
                "**Direkte Zuteilung:**\n"
                "```/alarmzuteilung```\n"
                "_Kopieren, Nutzer auswählen, abschicken!_\n\n"
                "➜ AlarmClaim schaltet nach erfolgreicher Übernahme automatisch die Anfrage ab und loggt alles."
            ),
            color=0xf39c12
        )
        view = AlarmPanelView(self)
        msg = await channel.send(embed=embed, view=view)
        cfg["main_message_id"] = msg.id
        _save_alarm(cfg)

    @app_commands.command(
        name="alarmmain",
        description="Postet/zurücksetzt das Alarm-Hauptpanel"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmmain")
    async def alarmmain(self, interaction: discord.Interaction):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_alarm()
        cfg["main_channel_id"] = interaction.channel.id
        _save_alarm(cfg)
        await self.reload_menu()
        await interaction.response.send_message("✅ Hauptpanel gepostet!", ephemeral=True)

    # ========== Lead-Management ==========
    @app_commands.command(
        name="alarmlead",
        description="Setzt den AlarmLead"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmlead")
    async def alarmlead(self, interaction: discord.Interaction, user: Member):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins.", ephemeral=True)
            return
        cfg = _load_alarm()
        cfg["lead_id"] = user.id
        _save_alarm(cfg)
        await interaction.response.send_message(f"✅ {user.mention} ist jetzt AlarmLead!", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="alarmlead_remove",
        description="Entfernt den AlarmLead"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmlead_remove")
    async def alarmlead_remove(self, interaction: discord.Interaction, user: Member):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins.", ephemeral=True)
            return
        cfg = _load_alarm()
        if cfg.get("lead_id") == user.id:
            cfg["lead_id"] = None
            _save_alarm(cfg)
            await interaction.response.send_message(f"✅ {user.mention} ist kein AlarmLead mehr.", ephemeral=True)
            await self.reload_menu()
        else:
            await interaction.response.send_message("ℹ️ User ist aktuell kein Lead.", ephemeral=True)

    @app_commands.command(
        name="alarmlead_info",
        description="Zeigt aktuellen AlarmLead"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmlead_info")
    async def alarmlead_info(self, interaction: discord.Interaction):
        cfg = _load_alarm()
        guild = self.bot.get_guild(GUILD_ID)
        lead = guild.get_member(cfg["lead_id"]) if cfg["lead_id"] else None
        await interaction.response.send_message(
            f"Aktueller AlarmLead: {lead.mention if lead else 'Nicht gesetzt'}",
            ephemeral=True
        )

    # ========== User-Rollen-Ping/Verwaltung ==========
    @app_commands.command(
        name="alarmusers_add",
        description="Fügt eine Rolle zum User-Ping hinzu"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmusers_add")
    async def alarmusers_add(self, interaction: discord.Interaction, role: Role):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_alarm()
        roles = set(cfg["user_role_ids"])
        roles.add(role.id)
        cfg["user_role_ids"] = list(roles)
        _save_alarm(cfg)
        await interaction.response.send_message(f"✅ {role.mention} wird bei Alarm gepingt.", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="alarmusers_remove",
        description="Entfernt eine Rolle aus dem User-Ping"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmusers_remove")
    async def alarmusers_remove(self, interaction: discord.Interaction, role: Role):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_alarm()
        if role.id in cfg["user_role_ids"]:
            cfg["user_role_ids"].remove(role.id)
            _save_alarm(cfg)
            await interaction.response.send_message(f"✅ {role.mention} wird nicht mehr gepingt.", ephemeral=True)
            await self.reload_menu()
        else:
            await interaction.response.send_message("ℹ️ Diese Rolle war nicht hinterlegt.", ephemeral=True)

    # ========== Log-Channel ==========
    @app_commands.command(
        name="alarmlog",
        description="Setzt Log-Channel für Alarmübernahmen"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmlog")
    async def alarmlog(self, interaction: discord.Interaction, channel: TextChannel):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_alarm()
        cfg["log_channel_id"] = channel.id
        _save_alarm(cfg)
        await interaction.response.send_message(f"✅ Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    # ========== Direkte Zuteilung ==========
    @app_commands.command(
        name="alarmzuteilung",
        description="Weist einem Nutzer direkt eine Schicht zu"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("alarmzuteilung")
    async def alarmzuteilung(self, interaction: discord.Interaction, user: Member):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        class ZuteilModal(discord.ui.Modal, title="Alarm-Schicht zuweisen"):
            streamer = discord.ui.TextInput(label="Name Streamer/Schicht", required=True, max_length=80)
            zeit = discord.ui.TextInput(label="Schicht (Datum/Uhrzeit)", required=True, max_length=80)

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    await user.send(
                        f"🚨 **Alarm-Schicht zugeteilt:**\n"
                        f"Streamer: {self.streamer.value}\n"
                        f"Zeit: {self.zeit.value}\n"
                        f"(Bitte bestätige deine Teilnahme im Chat/Voice!)"
                    )
                except Exception:
                    pass
                cfg = _load_alarm()
                guild = interaction.guild or self.bot.get_guild(GUILD_ID)
                log_channel = guild.get_channel(cfg.get("log_channel_id"))
                if log_channel:
                    await log_channel.send(
                        f"✅ {user.mention} wurde direkt für Alarm-Schicht zugeteilt!\n"
                        f"Streamer: **{self.streamer.value}**\n"
                        f"Zeit: **{self.zeit.value}**"
                    )
                await modal_interaction.response.send_message("✅ Zuteilung abgeschlossen!", ephemeral=True)

        await interaction.response.send_modal(ZuteilModal())

# ========== Views / Button-Logik für Panel ==========

class AlarmPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Schichtanfrage erstellen", style=discord.ButtonStyle.green, custom_id="alarm_request")
    async def create_alarm_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Nur AlarmLead/Admin.", ephemeral=True)
            return
        class AlarmRequestModal(discord.ui.Modal, title="Alarm-Schichtanfrage erstellen"):
            streamer = discord.ui.TextInput(label="Name Streamer/Schicht", required=True, max_length=80)
            zeit = discord.ui.TextInput(label="Schicht (Datum/Uhrzeit)", required=True, max_length=80)

            async def on_submit(self, modal_interaction: discord.Interaction):
                cfg = _load_alarm()
                guild = interaction.guild or self.cog.bot.get_guild(GUILD_ID)
                channel = guild.get_channel(cfg["main_channel_id"])
                role_pings = mention_roles(guild, cfg["user_role_ids"])
                embed = Embed(
                    title="🚨 Neue Alarm-Schichtanfrage",
                    description=(
                        f"{role_pings}\n"
                        f"Streamer: **{self.streamer.value}**\n"
                        f"Zeit: **{self.zeit.value}**\n\n"
                        f"Übernehme die Schicht mit dem Button unten!"
                    ),
                    color=0xe67e22
                )
                view = ClaimView(self.cog, self.streamer.value, self.zeit.value, interaction.user)
                await channel.send(embed=embed, view=view)
                await modal_interaction.response.send_message("✅ Alarmanfrage erstellt!", ephemeral=True)

        await interaction.response.send_modal(AlarmRequestModal())

class ClaimView(discord.ui.View):
    def __init__(self, cog, streamer, zeit, lead):
        super().__init__(timeout=None)
        self.cog = cog
        self.streamer = streamer
        self.zeit = zeit
        self.lead = lead

    @discord.ui.button(label="Schicht übernehmen", style=discord.ButtonStyle.blurple)
    async def claim_alarm(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = _load_alarm()
        guild = interaction.guild or self.cog.bot.get_guild(GUILD_ID)
        log_channel = guild.get_channel(cfg.get("log_channel_id"))
        try:
            await interaction.user.send(
                f"✅ Du hast die Alarm-Schicht übernommen!\n"
                f"Streamer: {self.streamer}\n"
                f"Zeit: {self.zeit}\n"
                f"Bitte melde dich im Voice/Chat für die Schicht."
            )
        except Exception:
            pass
        if log_channel:
            await log_channel.send(
                f"✅ {interaction.user.mention} hat die Alarm-Schicht übernommen!\n"
                f"Streamer: **{self.streamer}**\n"
                f"Zeit: **{self.zeit}**"
            )
        try:
            await interaction.message.delete()
        except Exception:
            pass
        await interaction.response.send_message("✅ Schicht übernommen! Check deine DMs.", ephemeral=True)

# === Extension-Loader ===

async def setup(bot):
    await bot.add_cog(AlarmCog(bot))
