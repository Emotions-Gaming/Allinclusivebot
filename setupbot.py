import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel, Embed
from utils import is_admin, load_json, save_json
from permissions import has_permission_for

GUILD_ID = int(os.environ.get("GUILD_ID"))

# Konfigurations-JSON für Settings/Defaults
SETUP_CONFIG = "persistent_data/setup_config.json"

def _load_config():
    return load_json(SETUP_CONFIG, {})

def _save_config(cfg):
    save_json(SETUP_CONFIG, cfg)

class SetupBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==== Setup-Menü posten (z.B. für Welcome oder Onboarding-Panel) ====
    @app_commands.command(
        name="setupwelcome",
        description="Postet das Willkommens-/Setup-Menü in diesen Channel (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("setupwelcome")
    async def setupwelcome(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        embed = Embed(
            title="👋 Willkommen beim Space Guide Bot",
            description=(
                "Alle wichtigen Funktionen stehen im Slash-Menü `/` bereit.\n"
                "Nutze `/setupinfo` für eine Übersicht aller Setups & Systeme.\n\n"
                "➜ **Nur Admins** können System- und Rollenrechte verteilen und konfigurieren."
            ),
            color=0x6c5ce7
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Willkommens-Panel gepostet!", ephemeral=True)

    # ==== Setup-Info (live Übersicht aller Module & Status) ====
    @app_commands.command(
        name="setupinfo",
        description="Zeigt eine Übersicht aller Space Guide Systeme (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("setupinfo")
    async def setupinfo(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return

        # Lade alle Modul-Status dynamisch:
        config = _load_config()
        cogs = [
            ("Persist/Backup", config.get("persist", "✅ OK")),
            ("Permissions", config.get("permissions", "✅ OK")),
            ("Schicht/Strike/Alarm", config.get("schicht", "✅ OK")),
            ("Translation", config.get("translation", "✅ OK")),
            ("Wiki", config.get("wiki", "✅ OK"))
        ]
        desc = ""
        for name, status in cogs:
            desc += f"• **{name}:** {status}\n"

        embed = Embed(
            title="🛠️ Space Guide Setup-Übersicht",
            description=desc,
            color=0x00b894
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==== Channel Check (Diagnostics) ====
    @app_commands.command(
        name="setupchannelcheck",
        description="Prüft, ob die wichtigsten Channels existieren (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("setupchannelcheck")
    async def setupchannelcheck(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        # Hier kannst du beliebige Channel-Checks erweitern:
        guild = interaction.guild
        important_channels = [
            "general", "admin", "strike-log", "alarm", "wiki"
        ]
        missing = []
        for cname in important_channels:
            if not discord.utils.get(guild.text_channels, name=cname):
                missing.append(cname)
        if missing:
            await interaction.response.send_message(
                f"⚠️ Fehlende Channels: {', '.join(missing)}", ephemeral=True
            )
        else:
            await interaction.response.send_message("✅ Alle wichtigen Channels vorhanden!", ephemeral=True)

    # ==== Diagnose: Bot-Status, Intents, usw. ====
    @app_commands.command(
        name="setupdiagnose",
        description="Zeigt Diagnosedaten zum Bot & System (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("setupdiagnose")
    async def setupdiagnose(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        bot = self.bot
        guild = bot.get_guild(GUILD_ID)
        loaded_cogs = list(bot.cogs.keys())
        embed = Embed(
            title="🤖 Bot Diagnose",
            description="System-/Bot-Diagnose Infos",
            color=0x636e72
        )
        embed.add_field(name="Guild", value=f"{guild.name} (ID: {guild.id})" if guild else "Not found", inline=False)
        embed.add_field(name="Loaded Cogs", value=", ".join(loaded_cogs) or "Keine", inline=False)
        embed.add_field(name="Discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Intents", value=str(bot.intents), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==== Erweiterbar: Channel/Role Setzen, System-Einstellungen ====
    # (hier kannst du beliebige weitere Setup/Init-Befehle ergänzen – alles sauber guild-only!)

# === Setup-Funktion für Extension-Loader ===
async def setup(bot):
    await bot.add_cog(SetupBotCog(bot))
