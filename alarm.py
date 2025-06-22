```python
import os
import discord
from discord import app_commands, Interaction, Member, Role, TextChannel
from discord.ui import View, Button, Modal, TextInput
from discord.ext import commands, tasks
from .utils import load_json, save_json, is_admin, mention_roles
import logging

logger = logging.getLogger(__name__)

# Guild-Konstante
GUILD_ID = int(os.getenv("GUILD_ID"))
CONFIG_FILE = "alarm_config.json"

class AlarmConfig:
    def __init__(self):
        data = load_json(CONFIG_FILE, {}) or {}
        self.lead_id = data.get("lead_id")
        self.user_role_ids = data.get("user_role_ids", [])
        self.log_channel_id = data.get("log_channel_id")
        self.main_channel_id = data.get("main_channel_id")
        self.main_message_id = data.get("main_message_id")

    def save(self):
        data = {
            "lead_id": self.lead_id,
            "user_role_ids": self.user_role_ids,
            "log_channel_id": self.log_channel_id,
            "main_channel_id": self.main_channel_id,
            "main_message_id": self.main_message_id
        }
        save_json(CONFIG_FILE, data)

class AlarmModal(Modal):
    def __init__(self):
        super().__init__(title="Alarm-Anfrage erstellen")
        self.streamer = TextInput(label="Name des Streamers", placeholder="z.B. CoolStreamer", required=True)
        self.time = TextInput(label="Schicht (Datum/Uhrzeit)", placeholder="YYYY-MM-DD HH:MM", required=True)
        self.add_item(self.streamer)
        self.add_item(self.time)

    async def on_submit(self, interaction: Interaction):
        cfg = interaction.client.get_cog("AlarmCog").config
        # Anfrage posten
        chan = interaction.channel
        mention_str = mention_roles(interaction.guild, cfg.user_role_ids)
        embed = discord.Embed(title="Neue Alarm-Schicht-Anfrage")
        embed.add_field(name="Streamer", value=self.streamer.value)
        embed.add_field(name="Schichtzeit", value=self.time.value)
        msg = await chan.send(content=mention_str, embed=embed, view=ClaimView())
        await interaction.response.send_message("Anfrage erstellt!", ephemeral=True)

class ClaimView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Claim", style=discord.ButtonStyle.primary, custom_id="alarm_claim"))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="alarm_claim")
    async def claim(self, button: Button, interaction: Interaction):
        cfg = interaction.client.get_cog("AlarmCog").config
        user = interaction.user
        # DM senden
        try:
            await user.send("Du hast die Alarm-Schicht übernommen.")
        except Exception:
            pass
        # Log
        if cfg.log_channel_id:
            logchan = interaction.guild.get_channel(cfg.log_channel_id)
            await logchan.send(f"{user.mention} hat die Alarm-Schicht übernommen.")
        await interaction.message.delete()

class AlarmCog(commands.Cog, name="AlarmCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = AlarmConfig()

    @tasks.loop(minutes=1)
    async def alarm_loop(self):
        # Placeholder für zeitgesteuerte Alarme
        pass

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmmain", description="Poste das zentrale Alarm-Panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmmain(self, interaction: Interaction):
        cfg = self.config
        embed = discord.Embed(title="🔔 Alarm-Panel")
        lead = interaction.guild.get_member(cfg.lead_id)
        embed.add_field(name="Aktueller Lead", value=lead.mention if lead else "Nicht gesetzt", inline=False)
        view = View()
        view.add_item(Button(label="Anfrage erstellen", style=discord.ButtonStyle.success, custom_id="alarm_request"))
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        cfg.main_channel_id = msg.channel.id
        cfg.main_message_id = msg.id
        cfg.save()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if interaction.data.get("custom_id") == "alarm_request":
            if not (is_admin(interaction.user) or interaction.user.id == self.config.lead_id):
                await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
                return
            await interaction.response.send_modal(AlarmModal())

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmlead", description="Setzt den Alarm-Lead")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmlead(self, interaction: Interaction, user: Member):
        self.config.lead_id = user.id
        self.config.save()
        await interaction.response.send_message(f"Alarm-Lead gesetzt auf {user.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmlead_remove", description="Entfernt den Alarm-Lead")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmlead_remove(self, interaction: Interaction):
        self.config.lead_id = None
        self.config.save()
        await interaction.response.send_message("Alarm-Lead entfernt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmlead_info", description="Zeigt aktuellen Alarm-Lead")
    async def alarmlead_info(self, interaction: Interaction):
        lead = interaction.guild.get_member(self.config.lead_id)
        await interaction.response.send_message(f"Current Alarm-Lead: {lead.mention if lead else 'Nicht gesetzt'}", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmusers_add", description="Fügt eine Rolle hinzu, die bei Alarmanfrage gepingt wird")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmusers_add(self, interaction: Interaction, role: Role):
        if role.id in self.config.user_role_ids:
            await interaction.response.send_message("Rolle ist bereits vorhanden.", ephemeral=True)
            return
        self.config.user_role_ids.append(role.id)
        self.config.save()
        await interaction.response.send_message(f"Rolle {role.mention} hinzugefügt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmusers_remove", description="Entfernt eine Ping-Rolle für Alarmanfragen")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmusers_remove(self, interaction: Interaction, role: Role):
        if role.id not in self.config.user_role_ids:
            await interaction.response.send_message("Rolle nicht in der Liste.", ephemeral=True)
            return
        self.config.user_role_ids.remove(role.id)
        self.config.save()
        await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmlog", description="Setzt den Log-Channel für Alarm-Übernahmen")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarm_log(self, interaction: Interaction, channel: TextChannel):
        self.config.log_channel_id = channel.id
        self.config.save()
        await interaction.response.send_message(f"Log-Channel gesetzt auf {channel.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="alarmzuteilung", description="Direkte Zuteilung einer Alarm-Schicht an einen User")
    @app_commands.checks.has_permissions(administrator=True)
    async def alarmzuteilung(self, interaction: Interaction, user: Member):
        modal = AlarmModal()
        await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot):
    cog = AlarmCog(bot)
    bot.add_cog(cog)
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
```
