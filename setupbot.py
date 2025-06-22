import os
import discord
from discord.ext import commands
from discord import app_commands
from utils import load_json, save_json, is_admin

SETUP_FILE = "setup_config.json"

# Helper: Hole aktuelle Config, falls nicht geladen
def get_config():
    return load_json(SETUP_FILE, {})

# Helper: Speichern
def set_config(data):
    save_json(SETUP_FILE, data)

class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = get_config()

    @app_commands.command(name="startsetup", description="Geführtes Setup für alle Bot-Systeme (Admin only)")
    async def startsetup(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        await interaction.response.send_message("Starte geführtes Setup. Bitte folge den Anweisungen.", ephemeral=True)

        steps = [
            ("translation_main_channel", "Bitte erwähne den Channel, in dem das Übersetzungsmenü gepostet werden soll (z.B. #translation)."),
            ("wiki_main_channel", "Bitte erwähne den Channel, in dem das Wiki-Menü gepostet werden soll (z.B. #wiki)."),
            ("schicht_main_channel", "Bitte erwähne den Channel, in dem das Schichtsystem-Menü gepostet werden soll (z.B. #schicht)."),
            ("alarm_main_channel", "Bitte erwähne den Channel, in dem das Alarm-Schichtsystem-Menü gepostet werden soll (z.B. #alarm).")
        ]
        config = get_config()

        # Channels
        for key, msg in steps:
            await interaction.followup.send(msg, ephemeral=True)
            try:
                def check(m): return m.author == interaction.user and m.channel == interaction.channel
                m = await self.bot.wait_for("message", check=check, timeout=90)
                if m.channel_mentions:
                    channel = m.channel_mentions[0]
                    config[key] = channel.id
                    await m.reply(f"Channel `{channel.name}` gespeichert.", mention_author=False)
                else:
                    await m.reply("Kein Channel erkannt. Bitte als #channel senden.")
                    return
            except Exception:
                await interaction.followup.send("Timeout! Bitte Setup erneut starten.", ephemeral=True)
                return

        set_config(config)

        # Jetzt die Menüs initial posten & IDs speichern
        await self._refresh_all_menus(config, interaction.guild)

        await interaction.followup.send("Setup abgeschlossen & Menüs neu gepostet! Nutze `/refreshposts`, falls du sie später neu posten willst.", ephemeral=True)

    async def _refresh_all_menus(self, config, guild):
        # Hier wird angenommen, dass jede Extension eine reload_menu Funktion im globalen Namespace hat.
        # Falls nicht, müssen wir sie via bot.get_cog(...) ansteuern.
        for system, key in [
            ("translation", "translation_main_channel"),
            ("wiki", "wiki_main_channel"),
            ("schicht", "schicht_main_channel"),
            ("alarm", "alarm_main_channel")
        ]:
            try:
                chan = guild.get_channel(config.get(key))
                if chan is None:
                    continue
                ext = self.bot.get_cog(system.capitalize() + "Cog")
                if ext and hasattr(ext, "reload_menu"):
                    await ext.reload_menu(chan)
            except Exception as e:
                print(f"[SetupBot] Fehler beim Reload von {system}: {e}")

    @app_commands.command(name="refreshposts", description="Postet alle Menüs erneut (nach Update/Fehler)")
    async def refreshposts(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        config = get_config()
        await self._refresh_all_menus(config, interaction.guild)
        await interaction.response.send_message("Alle Menüs wurden neu gepostet und IDs gespeichert.", ephemeral=True)

    @app_commands.command(name="setupstatus", description="Zeigt aktuellen Setup-Status")
    async def setupstatus(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        config = get_config()
        text = "\n".join([f"**{k}**: {v}" for k, v in config.items()])
        await interaction.response.send_message(f"Aktueller Setup-Status:\n{text}", ephemeral=True)

    @app_commands.command(name="startuse", description="Schaltet den Bot in Produktivmodus (nach Setup) (Admin only)")
    async def startuse(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        config = get_config()
        config["setup_complete"] = True
        set_config(config)
        await interaction.response.send_message("Bot ist jetzt im Produktivmodus! Alle Systeme sind aktiv.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
