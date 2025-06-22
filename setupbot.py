import os
import discord
from discord import app_commands, Interaction
from discord.ext import commands
from .utils import load_json, save_json, is_admin
import logging

# Guild-Konstante
guild_id = int(os.getenv("GUILD_ID"))

logger = logging.getLogger(__name__)
CONFIG_FILE = "setup_config.json"

class SetupCog(commands.Cog):
    """Geführtes Setup und Neustart-Menüs aller Subsysteme"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        data = load_json(CONFIG_FILE, {}) or {}
        self.config = {
            "translation_main_channel": data.get("translation_main_channel"),
            "wiki_main_channel": data.get("wiki_main_channel"),
            "schicht_main_channel": data.get("schicht_main_channel"),
            "alarm_main_channel": data.get("alarm_main_channel"),
            "setup_complete": data.get("setup_complete", False)
        }

    def save(self):
        save_json(CONFIG_FILE, self.config)

    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="startsetup", description="Starte das geführte Admin-Setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def startsetup(self, interaction: Interaction):
        await interaction.response.send_message("Starte Setup. Bitte antworte im Chat auf die Fragen.", ephemeral=True)
        # Channel-Abfrage-Reihe
        def check(m): return m.author == interaction.user and m.channel == interaction.channel

        await interaction.followup.send("Bitte mentionne den Channel für das Übersetzungs-Menü.")
        msg = await self.bot.wait_for('message', check=check, timeout=60)
        self.config['translation_main_channel'] = msg.channel_mentions[0].id

        await interaction.followup.send("Bitte mentionne den Channel für das Wiki-Menü.")
        msg = await self.bot.wait_for('message', check=check, timeout=60)
        self.config['wiki_main_channel'] = msg.channel_mentions[0].id

        await interaction.followup.send("Bitte mentionne den Channel für das Schicht-Menü.")
        msg = await self.bot.wait_for('message', check=check, timeout=60)
        self.config['schicht_main_channel'] = msg.channel_mentions[0].id

        await interaction.followup.send("Bitte mentionne den Channel für das Alarm-Panel.")
        msg = await self.bot.wait_for('message', check=check, timeout=60)
        self.config['alarm_main_channel'] = msg.channel_mentions[0].id

        self.config['setup_complete'] = True
        self.save()
        await interaction.followup.send("Setup abgeschlossen! Menüs werden in den Channels gepostet.")

        # Poste alle Menüs neu
        # Translation
        trans_cog = self.bot.get_cog('TranslationCog')
        if trans_cog:
            channel = self.bot.get_channel(self.config['translation_main_channel'])
            await trans_cog.translatorpost.callback(trans_cog, await channel.send)
        # Wiki
        wiki_cog = self.bot.get_cog('WikiCog')
        if wiki_cog:
            wiki_cog.main_channel_id = self.config['wiki_main_channel']
            await wiki_cog.post_menu()
        # Schicht
        schicht_cog = self.bot.get_cog('SchichtCog')
        if schicht_cog:
            channel = self.bot.get_channel(self.config['schicht_main_channel'])
            await channel.send("Schicht-Info neu laden mit /schichtinfo")
        # Alarm
        alarm_cog = self.bot.get_cog('AlarmCog')
        if alarm_cog:
            channel = self.bot.get_channel(self.config['alarm_main_channel'])
            await channel.send("Alarm-Panel neu laden mit /alarmmain")

    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="refreshposts", description="Postet alle Haupt-Menüs neu")
    @app_commands.checks.has_permissions(administrator=True)
    async def refreshposts(self, interaction: Interaction):
        await interaction.response.send_message("Menüs werden neu gepostet.", ephemeral=True)
        # Wiederhole Posting oben
        await self.startsetup.callback(self, interaction)

    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="setupstatus", description="Zeigt Setup-Status an")
    @app_commands.checks.has_permissions(administrator=True)
    async def setupstatus(self, interaction: Interaction):
        embed = discord.Embed(title="Setup-Status")
        for key, val in self.config.items():
            embed.add_field(name=key, value=str(val), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guilds(discord.Object(id=guild_id))
    @app_commands.command(name="startuse", description="Schalte Bot auf produktiv")
    @app_commands.checks.has_permissions(administrator=True)
    async def startuse(self, interaction: Interaction):
        self.config['setup_complete'] = True
        self.save()
        await interaction.response.send_message("Bot läuft jetzt produktiv.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = SetupCog(bot)
    bot.add_cog(cog)
    await bot.tree.sync(guild=discord.Object(id=guild_id))
