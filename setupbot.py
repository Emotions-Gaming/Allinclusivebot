# setupbot.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
SETUP_CONFIG_PATH = os.path.join("persistent_data", "setup_config.json")

SYSTEMS = [
    ("Übersetzungs-Menü", "translation_main_channel", "translation"),
    ("Wiki-Menü", "wiki_main_channel", "wiki"),
    ("Schichtsystem-Menü", "schicht_main_channel", "schicht"),
    ("Alarm-Schichtsystem-Menü", "alarm_main_channel", "alarm"),
]

class SetupBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===== Helper =====

    async def get_setup_config(self):
        return await utils.load_json(SETUP_CONFIG_PATH, {})

    async def save_setup_config(self, config):
        await utils.save_json(SETUP_CONFIG_PATH, config)

    async def call_reload_menu(self, system_key: str, channel_id: int):
        """Ruft die reload_menu-Funktion des jeweiligen Systems auf (falls vorhanden)."""
        try:
            cog = self.bot.get_cog(system_key.capitalize() + "Cog")
            if cog and hasattr(cog, "reload_menu"):
                await cog.reload_menu(channel_id)
        except Exception as e:
            print(f"[setupbot] Fehler beim reload_menu für {system_key}: {e}")

    # ===== Slash-Commands =====

    @app_commands.command(
        name="startsetup",
        description="Startet das geführte Setup für alle Hauptsysteme (Admin only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def start_setup(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await utils.send_ephemeral(interaction, "Geführtes Setup wird gestartet! Bitte beantworte alle Fragen zügig. Tippe 'abbrechen', um das Setup zu beenden.", emoji="⚙️")
        config = {}
        for sysname, key, syskey in SYSTEMS:
            try:
                await interaction.followup.send(f"Bitte wähle den Channel für **{sysname}** per #Mention oder tippe `skip` zum Überspringen:", ephemeral=True)
                def check(m):
                    return m.author.id == interaction.user.id and m.channel == interaction.channel
                msg = await self.bot.wait_for("message", timeout=90, check=check)
                if msg.content.lower().strip() == "abbrechen":
                    await utils.send_error(interaction, "Setup abgebrochen.")
                    return
                if msg.content.lower().strip() == "skip":
                    continue
                if not msg.channel_mentions:
                    await utils.send_error(interaction, "Kein Channel gefunden – bitte nochmal `/startsetup` ausführen.")
                    return
                channel_id = msg.channel_mentions[0].id
                config[key] = channel_id
            except asyncio.TimeoutError:
                await utils.send_error(interaction, "Timeout – Setup bitte erneut starten!")
                return
        config["setup_complete"] = True
        await self.save_setup_config(config)
        # Menüs posten
        for _, key, syskey in SYSTEMS:
            if key in config:
                await self.call_reload_menu(syskey, config[key])
        await utils.send_success(interaction, "Setup abgeschlossen! Alle Systeme wurden konfiguriert und die Menüs gepostet.")

    @app_commands.command(
        name="refreshposts",
        description="Postet alle Hauptmenüs in die gespeicherten Channels neu (Admin only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def refresh_posts(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await self.get_setup_config()
        posted = 0
        for _, key, syskey in SYSTEMS:
            if key in config:
                await self.call_reload_menu(syskey, config[key])
                posted += 1
        await utils.send_success(interaction, f"{posted} Menüs neu gepostet!")

    @app_commands.command(
        name="setupstatus",
        description="Zeigt den aktuellen Setup-Status und alle Menüs/Channels (Admin only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def setup_status(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await self.get_setup_config()
        lines = []
        for sysname, key, _ in SYSTEMS:
            val = config.get(key)
            if val:
                chan = interaction.guild.get_channel(val)
                lines.append(f"**{sysname}:** {chan.mention if chan else f'`{val}` (Channel fehlt!)'}")
            else:
                lines.append(f"**{sysname}:** *(nicht gesetzt)*")
        done = config.get("setup_complete", False)
        color = discord.Color.green() if done else discord.Color.gold()
        await utils.send_ephemeral(
            interaction,
            text="\n".join(lines) + f"\n\n**Setup abgeschlossen:** {'✅' if done else '❌'}",
            emoji="📝",
            color=color
        )

    @app_commands.command(
        name="startuse",
        description="Schaltet den Bot auf produktiv (setzt setup_complete auf true) (Admin only)."
    )
    @app_commands.guilds(MY_GUILD)
    async def start_use(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await self.get_setup_config()
        config["setup_complete"] = True
        await self.save_setup_config(config)
        await utils.send_success(interaction, "Bot ist jetzt im Produktivmodus! (setup_complete: true)")

# ===== Cog-Setup =====
async def setup(bot):
    await bot.add_cog(SetupBotCog(bot))
