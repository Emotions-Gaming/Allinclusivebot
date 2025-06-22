import discord
from discord.ext import commands
from discord import app_commands

from utils import load_json, save_json, is_admin, get_member_by_id, mention_roles

ALARM_CONFIG_FILE = "alarm_config.json"

def get_alarm_cfg():
    return load_json(ALARM_CONFIG_FILE, {
        "lead_id": None,
        "user_role_ids": [],
        "log_channel_id": None,
        "main_channel_id": None,
        "main_message_id": None,
    })

def save_alarm_cfg(cfg):
    save_json(ALARM_CONFIG_FILE, cfg)

def is_lead(user):
    cfg = get_alarm_cfg()
    return (user.id == cfg.get("lead_id")) or is_admin(user)

class AlarmCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_panel(self, guild):
        cfg = get_alarm_cfg()
        channel = guild.get_channel(cfg.get("main_channel_id"))
        if not channel or not cfg.get("main_message_id"):
            return
        try:
            msg = await channel.fetch_message(cfg["main_message_id"])
        except Exception:
            return
        # Embed aktualisieren mit aktuellem Lead
        lead = get_member_by_id(guild, cfg.get("lead_id")) if cfg.get("lead_id") else None
        lead_text = lead.mention if lead else "_Nicht gesetzt_"
        emb = discord.Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Drücke auf **Anfrage erstellen**, um eine neue Alarm-Schichtanfrage zu posten.\n\n"
                "Du bist AlarmLead/Admin? Dann kannst du direkt Schichten zuteilen:\n"
                "```/alarmzuteilung```"
            ),
            color=discord.Color.red()
        )
        emb.add_field(name="Aktueller AlarmLead", value=lead_text, inline=False)
        view = self.get_panel_view(cfg, lead)
        await msg.edit(embed=emb, view=view)

    def get_panel_view(self, cfg, lead):
        # Anfrage erstellen (nur Lead/Admin)
        class AlarmRequestBtn(discord.ui.Button):
            def __init__(self, cog):
                super().__init__(label="Anfrage erstellen", style=discord.ButtonStyle.primary)
                self.cog = cog
            async def callback(self, interaction: discord.Interaction):
                if not is_lead(interaction.user):
                    return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
                await self.cog.open_alarm_modal(interaction)
        view = discord.ui.View(timeout=None)
        view.add_item(AlarmRequestBtn(self))
        return view

    async def open_alarm_modal(self, interaction):
        class AlarmModal(discord.ui.Modal, title="Alarm-Schichtanfrage erstellen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", required=True, max_length=50)
            schicht = discord.ui.TextInput(label="Welche Schicht (Datum/Uhrzeit)?", required=True, max_length=100)
            async def on_submit(self, modal_inter: discord.Interaction):
                cfg = get_alarm_cfg()
                roles_ping = mention_roles(interaction.guild, cfg.get("user_role_ids", []))
                log_ch = interaction.guild.get_channel(cfg.get("log_channel_id")) if cfg.get("log_channel_id") else None
                # Alarm-Request posten
                emb = discord.Embed(
                    title="🚨 Alarm-Schichtanfrage",
                    description=(
                        f"{roles_ping}\n\n"
                        f"**Dringend Chatter benötigt!**\n"
                        f"**Streamer:** {self.streamer.value}\n"
                        f"**Schicht:** {self.schicht.value}\n"
                        "\nKlicke auf **Claim** um zu übernehmen."
                    ),
                    color=discord.Color.red()
                )
                v = discord.ui.View(timeout=None)
                class ClaimBtn(discord.ui.Button):
                    def __init__(self):
                        super().__init__(label="Claim", style=discord.ButtonStyle.success)
                    async def callback(claim_self, claim_inter):
                        # DM + Log + Löschen
                        try:
                            await claim_inter.user.send(
                                f"✅ Du hast die Alarm-Schicht übernommen!\n"
                                f"Streamer: {self.streamer.value}\n"
                                f"Schicht: {self.schicht.value}\n"
                                "Bitte erscheine 15 Minuten vor Beginn im General-Channel!"
                            )
                        except Exception:
                            pass
                        if log_ch:
                            await log_ch.send(
                                f"**Alarm-Schicht wurde übernommen!**\n"
                                f"Schicht: {self.schicht.value}\n"
                                f"Streamer: {self.streamer.value}\n"
                                f"Von: {claim_inter.user.mention}"
                            )
                        await claim_inter.response.send_message("Schicht übernommen! Du hast eine DM erhalten.", ephemeral=True)
                        try: await claim_self.message.delete()
                        except: pass
                claim_btn = ClaimBtn()
                v.add_item(claim_btn)
                msg = await interaction.channel.send(embed=emb, view=v)
                claim_btn.message = msg
                await modal_inter.response.send_message("Anfrage erstellt!", ephemeral=True)
        await interaction.response.send_modal(AlarmModal())

    # -- Slash-Befehle --

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmmain", description="Postet das Alarm-Schichtsystem-Panel")
    async def alarmmain(self, interaction: discord.Interaction):
        if not is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        channel = interaction.channel
        lead = get_member_by_id(interaction.guild, cfg.get("lead_id")) if cfg.get("lead_id") else None
        lead_text = lead.mention if lead else "_Nicht gesetzt_"
        emb = discord.Embed(
            title="🚨 Alarm-Schichtsystem",
            description=(
                "Drücke auf **Anfrage erstellen**, um eine neue Alarm-Schichtanfrage zu posten.\n\n"
                "Du bist AlarmLead/Admin? Dann kannst du direkt Schichten zuteilen:\n"
                "```/alarmzuteilung```"
            ),
            color=discord.Color.red()
        )
        emb.add_field(name="Aktueller AlarmLead", value=lead_text, inline=False)
        view = self.get_panel_view(cfg, lead)
        msg = await channel.send(embed=emb, view=view)
        cfg["main_channel_id"] = channel.id
        cfg["main_message_id"] = msg.id
        save_alarm_cfg(cfg)
        await interaction.response.send_message("Alarm-Schichtsystem-Panel gepostet!", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmlead", description="Setzt einen Nutzer als AlarmLead")
    @app_commands.describe(nutzer="User der AlarmLead werden soll")
    async def alarmlead(self, interaction: discord.Interaction, nutzer: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        cfg["lead_id"] = nutzer.id
        save_alarm_cfg(cfg)
        await self.update_panel(interaction.guild)
        await interaction.response.send_message(f"{nutzer.mention} ist jetzt AlarmLead.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmlead_remove", description="Entfernt den AlarmLead")
    @app_commands.describe(nutzer="Lead der entfernt werden soll")
    async def alarmlead_remove(self, interaction: discord.Interaction, nutzer: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Nur Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        if cfg.get("lead_id") == nutzer.id:
            cfg["lead_id"] = None
            save_alarm_cfg(cfg)
            await self.update_panel(interaction.guild)
            await interaction.response.send_message(f"{nutzer.display_name} ist kein AlarmLead mehr.", ephemeral=True)
        else:
            await interaction.response.send_message("Diese Person ist nicht Lead.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmlead_info", description="Zeigt den aktuellen AlarmLead")
    async def alarmlead_info(self, interaction: discord.Interaction):
        cfg = get_alarm_cfg()
        lead = get_member_by_id(interaction.guild, cfg.get("lead_id")) if cfg.get("lead_id") else None
        if lead:
            await interaction.response.send_message(f"Aktueller AlarmLead: {lead.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("Es ist kein AlarmLead gesetzt.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmusers_add", description="Fügt eine Rolle zur Alarm-Rolle hinzu (Ping bei Anfrage)")
    @app_commands.describe(role="Rolle hinzufügen")
    async def alarmusers_add(self, interaction: discord.Interaction, role: discord.Role):
        if not is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        uroles = set(cfg.get("user_role_ids", []))
        uroles.add(role.id)
        cfg["user_role_ids"] = list(uroles)
        save_alarm_cfg(cfg)
        await interaction.response.send_message(f"{role.mention} ist jetzt Alarm-User.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmusers_remove", description="Entfernt eine Rolle aus der Alarm-Rolle")
    @app_commands.describe(role="Rolle entfernen")
    async def alarmusers_remove(self, interaction: discord.Interaction, role: discord.Role):
        if not is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        uroles = set(cfg.get("user_role_ids", []))
        if role.id in uroles:
            uroles.remove(role.id)
            cfg["user_role_ids"] = list(uroles)
            save_alarm_cfg(cfg)
            await interaction.response.send_message(f"{role.mention} ist kein Alarm-User mehr.", ephemeral=True)
        else:
            await interaction.response.send_message("Rolle war nicht Alarm-User.", ephemeral=True)

    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Schichtanfragen")
    @app_commands.describe(channel="Log-Channel")
    async def alarmlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin!", ephemeral=True)
        cfg = get_alarm_cfg()
        cfg["log_channel_id"] = channel.id
        save_alarm_cfg(cfg)
        await interaction.response.send_message(f"Log-Channel gesetzt: {channel.mention}", ephemeral=True)


    @app_commands.guilds(GUILD_ID)
    @app_commands.command(name="alarmzuteilung", description="(Lead) Teilt einem Nutzer direkt eine Schicht zu")
    @app_commands.describe(nutzer="Nutzer für Schicht")
    async def alarmzuteilung(self, interaction: discord.Interaction, nutzer: discord.Member):
        if not is_lead(interaction.user):
            return await interaction.response.send_message("Nur AlarmLead/Admin!", ephemeral=True)
        class AlarmZuteilModal(discord.ui.Modal, title="Schicht zuteilen"):
            streamer = discord.ui.TextInput(label="Name von Streamer", required=True, max_length=50)
            schicht = discord.ui.TextInput(label="Welche Schicht (Datum/Uhrzeit)?", required=True, max_length=100)
            async def on_submit(self, modal_inter: discord.Interaction):
                cfg = get_alarm_cfg()
                lead = get_member_by_id(interaction.guild, cfg.get("lead_id")) if cfg.get("lead_id") else interaction.user
                log_ch = interaction.guild.get_channel(cfg.get("log_channel_id")) if cfg.get("log_channel_id") else None
                try:
                    await nutzer.send(
                        f"🚨 **Du wurdest zur Schicht eingeteilt!**\n"
                        f"Von: {lead.mention}\n"
                        f"Streamer: {self.streamer.value}\n"
                        f"Schicht: {self.schicht.value}\n"
                        "Bitte erscheine 15 Minuten vor Beginn im General-Channel!"
                    )
                except Exception:
                    pass
                if log_ch:
                    await log_ch.send(
                        f"**Schicht zugeteilt:**\n"
                        f"{lead.mention} hat {nutzer.mention} zur Schicht eingeteilt!\n"
                        f"Streamer: {self.streamer.value}\n"
                        f"Schicht: {self.schicht.value}"
                    )
                await modal_inter.response.send_message("Schicht wurde zugeteilt!", ephemeral=True)
        await interaction.response.send_modal(AlarmZuteilModal())

# ... dein AlarmCog-Code ...

async def reload_menu(self, config=None):
    if config is None:
        from utils import load_json
        config = load_json("setup_config.json", {})
    channel_id = config.get("alarm_main_channel")
    if not channel_id:
        return
    channel = self.bot.get_channel(channel_id)
    if not channel:
        return
    async for msg in channel.history(limit=50):
        if msg.author == self.bot.user:
            try:
                await msg.delete()
            except:
                pass
    await self.post_alarmmain(channel)  # Deine Funktion zum Menü posten!

AlarmCog.reload_menu = reload_menu

async def setup(bot):
    await bot.add_cog(AlarmCog(bot))