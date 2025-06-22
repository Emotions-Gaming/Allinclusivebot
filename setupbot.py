# setupbot.py

import logging
import os
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel
from utils import is_admin, load_json, save_json

SETUP_FILE = "persistent_data/setup_config.json"

# Liste der zu konfigurierenden Systeme und ihre JSON-Keys
SYSTEMS = {
    "translation": "translation_main_channel",
    "wiki": "wiki_main_channel",
    "schicht": "schicht_main_channel",
    "alarm": "alarm_main_channel"
}

class SetupBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialisiere Setup-Config falls nicht vorhanden
        if not os.path.exists(SETUP_FILE):
            save_json(SETUP_FILE, {k: None for k in SYSTEMS.values()})

    def _load(self):
        return load_json(SETUP_FILE, {})

    def _save(self, data):
        save_json(SETUP_FILE, data)

    @app_commands.command(
        name="startsetup",
        description="Geführtes Setup: Konfiguriere alle Menü-Channels (nur Admins)"
    )
    async def startsetup(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Adminrechte!", ephemeral=True)
            return

        config = self._load()
        await interaction.response.send_message(
            "🔧 Starte Setup – bitte folge den Anweisungen. Alle Antworten werden nur dir angezeigt.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel

        # Fragt für jedes System den Channel ab
        for system, key in SYSTEMS.items():
            await interaction.followup.send(f"Bitte erwähne den Textkanal für das **{system}-Menü** (z.B. #channel):", ephemeral=True)
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=120)
            except Exception:
                await interaction.followup.send(f"⏰ Timeout! Kein Channel für **{system}** erhalten.", ephemeral=True)
                return
            # Versuche Channel-ID aus Mention zu holen
            channel_id = None
            if msg.channel_mentions:
                channel_id = msg.channel_mentions[0].id
            else:
                await interaction.followup.send(f"❌ Keine gültige Channel-Erwähnung erkannt. Bitte mit #channel antworten.", ephemeral=True)
                return
            config[key] = channel_id
            self._save(config)
            await interaction.followup.send(f"✅ {system}-Menü-Channel gesetzt: <#{channel_id}>", ephemeral=True)

        config["setup_complete"] = True
        self._save(config)
        await interaction.followup.send("🎉 Setup abgeschlossen! Menüs werden jetzt gepostet...", ephemeral=True)

        # Postet die Menüs neu (ruft reload_menu in jedem Cog auf)
        for cog_name in SYSTEMS:
            cog = self.bot.get_cog(cog_name.capitalize() + "Cog")
            if cog and hasattr(cog, "reload_menu"):
                try:
                    await cog.reload_menu()
                except Exception as e:
                    logging.error(f"Fehler beim reload_menu von {cog_name}: {e}")

    @app_commands.command(
        name="refreshposts",
        description="Postet alle Menüpanels/Embeds neu in die hinterlegten Channels (nur Admins)"
    )
    async def refreshposts(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Adminrechte!", ephemeral=True)
            return
        for cog_name in SYSTEMS:
            cog = self.bot.get_cog(cog_name.capitalize() + "Cog")
            if cog and hasattr(cog, "reload_menu"):
                try:
                    await cog.reload_menu()
                except Exception as e:
                    logging.error(f"Fehler beim reload_menu von {cog_name}: {e}")
        await interaction.response.send_message("🔄 Menüs wurden neu gepostet (sofern Cogs geladen und Funktion vorhanden).", ephemeral=True)

    @app_commands.command(
        name="setupstatus",
        description="Zeigt die aktuelle Setup-Konfiguration"
    )
    async def setupstatus(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Adminrechte!", ephemeral=True)
            return
        config = self._load()
        msg = "📋 **Aktueller Setup-Status:**\n"
        for k in SYSTEMS.values():
            v = config.get(k)
            if v:
                msg += f"- {k}: <#{v}>\n"
            else:
                msg += f"- {k}: *(Nicht gesetzt)*\n"
        msg += f"- setup_complete: {config.get('setup_complete', False)}"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="startuse",
        description="Setzt das Setup auf abgeschlossen (nur Admins)"
    )
    async def startuse(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Adminrechte!", ephemeral=True)
            return
        config = self._load()
        config["setup_complete"] = True
        self._save(config)
        await interaction.response.send_message("🚀 Setup als abgeschlossen markiert! Bot ist nun produktiv.", ephemeral=True)

# === Setup-Funktion für Extension-Loader ===

async def setup(bot):
    await bot.add_cog(SetupBotCog(bot))
