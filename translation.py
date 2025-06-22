import os
import discord
from discord import app_commands, Interaction, Member, TextChannel, CategoryChannel
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
from .utils import load_json, save_json, is_admin
from .utils import get_member_by_id
import logging

# Guild-Konstante
GUILD_ID = int(os.getenv("GUILD_ID"))

logger = logging.getLogger(__name__)

# JSON-Dateien
PROFILES_FILE = "profiles.json"
PROMPT_FILE = "translator_prompt.json"
MENU_FILE = "translator_menu.json"
LOG_FILE = "translation_log.json"
CATEGORY_FILE = "trans_category.json"

class TranslationModal(Modal):
    def __init__(self, profile: str):
        super().__init__(title=f"Übersetzung - {profile}")
        self.profile = profile
        self.input = TextInput(label="Text zum Übersetzen", style=discord.TextStyle.paragraph)
        self.add_item(self.input)

    async def on_submit(self, interaction: Interaction):
        text = self.input.value
        # TODO: Call translation API with profile and additional prompt
        translated = f"[Übersetzt im Stil {self.profile}]: {text}"
        # Log
        logs = load_json(LOG_FILE, []) or []
        logs.append({"user": interaction.user.id, "profile": self.profile, "src": text, "dst": translated})
        save_json(LOG_FILE, logs)
        await interaction.response.send_message(translated, ephemeral=False)

class TranslationCog(commands.Cog):
    """Cog für Übersetzungssystem"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Lade Profile
        self.profiles = load_json(PROFILES_FILE, {}) or {}
        # Lade Zusatz-Prompt
        self.prompt_rules = load_json(PROMPT_FILE, []) or []
        # Menu-Channel & Log-Channel
        cfg = load_json(MENU_FILE, {}) or {}
        self.menu_channel_id = cfg.get("menu_channel_id")
        self.log_channel_id = cfg.get("log_channel_id")
        # Category für Sessions
        self.category_id = load_json(CATEGORY_FILE, {}).get("category_id")

    def save_menu_cfg(self):
        save_json(MENU_FILE, {"menu_channel_id": self.menu_channel_id, "log_channel_id": self.log_channel_id})

    def save_category(self):
        save_json(CATEGORY_FILE, {"category_id": self.category_id})

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatorpost", description="Poste das Übersetzungs-Menü")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatorpost(self, interaction: Interaction):
        channel = interaction.channel
        self.menu_channel_id = channel.id
        self.save_menu_cfg()
        # Build dropdown
        options = [discord.SelectOption(label=name, description=desc) for name, desc in self.profiles.items()]
        select = Select(placeholder="Wähle ein Übersetzer-Profil", options=options, custom_id="translator_select")
        view = View()
        view.add_item(select)
        select.callback = self.on_select
        await interaction.response.send_message("**Übersetzungs-Menü**", view=view)

    async def on_select(self, interaction: Interaction):
        profile = interaction.data['values'][0]
        modal = TranslationModal(profile)
        await interaction.response.send_modal(modal)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatoraddprofile", description="Fügt ein Übersetzer-Profil hinzu")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatoraddprofile(self, interaction: Interaction, name: str, description: str):
        self.profiles[name] = description
        save_json(PROFILES_FILE, self.profiles)
        await interaction.response.send_message(f"Profil '{name}' hinzugefügt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatordeleteprofile", description="Löscht ein Übersetzer-Profil")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatordeleteprofile(self, interaction: Interaction, name: str):
        if name not in self.profiles:
            await interaction.response.send_message("Profil nicht gefunden.", ephemeral=True)
            return
        del self.profiles[name]
        save_json(PROFILES_FILE, self.profiles)
        await interaction.response.send_message(f"Profil '{name}' gelöscht.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatorprompt", description="Fügt eine Zusatz-Prompt-Regel hinzu")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatorprompt(self, interaction: Interaction, rule: str):
        self.prompt_rules.append(rule)
        save_json(PROMPT_FILE, self.prompt_rules)
        await interaction.response.send_message("Prompt-Regel hinzugefügt.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatorpromptdelete", description="Entfernt eine Prompt-Regel")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatorpromptdelete(self, interaction: Interaction, index: int):
        if index < 0 or index >= len(self.prompt_rules):
            await interaction.response.send_message("Ungültiger Index.", ephemeral=True)
            return
        removed = self.prompt_rules.pop(index)
        save_json(PROMPT_FILE, self.prompt_rules)
        await interaction.response.send_message(f"Prompt-Regel entfernt: {removed}", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatorsetcategorie", description="Setzt die Kategorie für Session-Channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatorsetcategorie(self, interaction: Interaction, category: CategoryChannel):
        self.category_id = category.id
        self.save_category()
        await interaction.response.send_message(f"Session-Kategorie gesetzt auf {category.name}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="translatorlog", description="Setzt den Log-Channel für Übersetzungen")
    @app_commands.checks.has_permissions(administrator=True)
    async def translatorlog(self, interaction: Interaction, channel: TextChannel):
        self.log_channel_id = channel.id
        self.save_menu_cfg()
        await interaction.response.send_message(f"Log-Channel gesetzt auf {channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = TranslationCog(bot)
    bot.add_cog(cog)
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))