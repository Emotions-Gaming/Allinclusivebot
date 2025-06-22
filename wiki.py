import os
import discord
from discord import app_commands, Interaction, TextChannel
from discord.ui import View, Select, Modal, TextInput
from discord.ext import commands
from .utils import load_json, save_json, is_admin
import logging

# Guild-Konstante
GUILD_ID = int(os.getenv("GUILD_ID"))

logger = logging.getLogger(__name__)

# JSON-Dateien
PAGES_FILE = "wiki_pages.json"
BACKUP_FILE = "wiki_backup.json"
MAIN_CHANNEL_FILE = "wiki_main_channel.json"

class WikiCog(commands.Cog):
    """Cog für Wiki-System"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Lade Hauptkanal
        data = load_json(MAIN_CHANNEL_FILE, {}) or {}
        self.main_channel_id = data.get("channel_id")

    def save_main_channel(self, channel_id: int):
        save_json(MAIN_CHANNEL_FILE, {"channel_id": channel_id})
        self.main_channel_id = channel_id

    def get_pages(self) -> dict[str, str]:
        return load_json(PAGES_FILE, {}) or {}

    def save_page(self, title: str, content: str):
        pages = self.get_pages()
        pages[title] = content
        save_json(PAGES_FILE, pages)
        # Backup
        backups = load_json(BACKUP_FILE, {}) or {}
        backups[title] = content
        save_json(BACKUP_FILE, backups)

    def delete_page(self, title: str):
        pages = self.get_pages()
        if title in pages:
            del pages[title]
            save_json(PAGES_FILE, pages)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wikimain", description="Setzt den Hauptkanal für das Wiki-Menü")
    @app_commands.checks.has_permissions(administrator=True)
    async def wikimain(self, interaction: Interaction, channel: TextChannel):
        self.save_main_channel(channel.id)
        await interaction.response.send_message(f"Wiki-Hauptkanal gesetzt auf {channel.mention}.", ephemeral=True)
        await self.post_menu()

    async def post_menu(self):
        if not self.main_channel_id:
            return
        channel = self.bot.get_channel(self.main_channel_id)
        if not channel:
            return
        # Entferne alte Bot-Nachrichten
        async for msg in channel.history(limit=50):
            if msg.author == self.bot.user:
                await msg.delete()
        pages = self.get_pages()
        if not pages:
            await channel.send("Keine Wiki-Seiten gespeichert.")
            return
        options = [discord.SelectOption(label=title, description=content[:50]) for title, content in pages.items()]
        select = Select(placeholder="Wähle eine Wiki-Seite", options=options, custom_id="wiki_select")
        view = View()
        view.add_item(select)
        select.callback = self.on_select
        await channel.send("**Wiki-Menü**", view=view)

    async def on_select(self, interaction: Interaction):
        title = interaction.data['values'][0]
        pages = self.get_pages()
        content = pages.get(title, "")
        # Ephemeral Antwort
        await interaction.response.send_message(f"**{title}**\n{content}", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wiki_page", description="Speichert den aktuellen Channel als Wiki-Seite")
    @app_commands.checks.has_permissions(administrator=True)
    async def wiki_page(self, interaction: Interaction):
        channel = interaction.channel
        # Hol ersten nicht-Bot-Post
        messages = await channel.history(limit=30).flatten()
        for msg in messages:
            if not msg.author.bot:
                content = msg.content
                title = channel.name
                self.save_page(title, content)
                await interaction.response.send_message(f"Seite '{title}' gespeichert.", ephemeral=True)
                await self.post_menu()
                return
        await interaction.response.send_message("Kein Inhalt gefunden.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wiki_delete", description="Löscht eine gespeicherte Wiki-Seite")
    @app_commands.checks.has_permissions(administrator=True)
    async def wiki_delete(self, interaction: Interaction, page: str):
        pages = self.get_pages()
        if page not in pages:
            await interaction.response.send_message("Seite nicht gefunden.", ephemeral=True)
            return
        self.delete_page(page)
        await interaction.response.send_message(f"Seite '{page}' gelöscht.", ephemeral=True)
        await self.post_menu()

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wiki_backup", description="Stellt eine Seite aus dem Backup wieder her")
    @app_commands.checks.has_permissions(administrator=True)
    async def wiki_backup(self, interaction: Interaction, page: str):
        backups = load_json(BACKUP_FILE, {}) or {}
        content = backups.get(page)
        if not content:
            await interaction.response.send_message("Backup nicht gefunden.", ephemeral=True)
            return
        # Erstelle Channel mit Titel
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Wiki")
        new_chan = await guild.create_text_channel(name=page, category=category)
        # Splitting content
        chunks = [content[i:i+1800] for i in range(0, len(content), 1800)]
        for chunk in chunks:
            await new_chan.send(chunk)
        await interaction.response.send_message(f"Seite '{page}' wiederhergestellt in {new_chan.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = WikiCog(bot)
    bot.add_cog(cog)
    # Sync-Menü bei Startup
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    await cog.post_menu()
