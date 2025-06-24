# wiki.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
WIKI_PAGES_PATH = os.path.join("persistent_data", "wiki_pages.json")
WIKI_BACKUP_PATH = os.path.join("persistent_data", "wiki_backup.json")
WIKI_MAIN_CHANNEL_PATH = os.path.join("persistent_data", "wiki_main_channel.json")

MAX_DROPDOWN = 25
DISCORD_MAX_LEN = 2000

# ========== Helper ==========

async def get_pages():
    return await utils.load_json(WIKI_PAGES_PATH, {})

async def save_pages(data):
    await utils.save_json(WIKI_PAGES_PATH, data)

async def get_backup():
    return await utils.load_json(WIKI_BACKUP_PATH, {})

async def save_backup(data):
    await utils.save_json(WIKI_BACKUP_PATH, data)

async def get_main_channel_id():
    return await utils.load_json(WIKI_MAIN_CHANNEL_PATH, 0)

async def set_main_channel_id(cid):
    await utils.save_json(WIKI_MAIN_CHANNEL_PATH, cid)

def chunk_text(text, size=1800):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ========== Dropdowns/Views ==========

class WikiMenuView(discord.ui.View):
    def __init__(self, pages: dict):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label=title[:100], value=title)
            for title in list(pages.keys())[:MAX_DROPDOWN]
        ]
        self.add_item(WikiDropdown(options, pages))

class WikiDropdown(discord.ui.Select):
    def __init__(self, options, pages):
        super().__init__(
            placeholder="Wähle eine Wiki-Seite…",
            options=options,
            min_values=1, max_values=1
        )
        self.pages = pages

    async def callback(self, interaction: Interaction):
        page_title = self.values[0]
        page = self.pages.get(page_title)
        page_chunks = chunk_text(page if page else "_Kein Inhalt gefunden._", size=1800)
        for idx, chunk in enumerate(page_chunks):
            embed = discord.Embed(
                title=f"📖 {page_title}" if idx == 0 else f"📖 {page_title} (Teil {idx+1})",
                description=chunk,
                color=discord.Color.blurple()
            )
            if idx == 0:
                await utils.send_ephemeral(interaction, text=" ", embed=embed)
            else:
                # Folge-Nachrichten, nicht interaction.response sondern followup!
                await interaction.followup.send(embed=embed, ephemeral=True)

# ========== Slash Commands ==========

class WikiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper to (re)post the Wiki Menu
    async def reload_menu(self, channel_id=None):
        cid = channel_id or await get_main_channel_id()
        if not cid:
            return
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(cid)
        pages = await get_pages()
        if not channel or not pages:
            return
        # Lösche alte Bot-Nachrichten (nur von Bot, um Dopplungen zu vermeiden)
        async for msg in channel.history(limit=20):
            if msg.author == guild.me and msg.components:
                try:
                    await msg.delete()
                except Exception:
                    pass
        embed = discord.Embed(
            title="📚 Wiki-System",
            description="Wähle unten eine Seite aus, um deren Inhalt zu sehen. (Antwort ist nur für dich sichtbar!)",
            color=discord.Color.blurple()
        )
        view = WikiMenuView(pages)
        await channel.send(embed=embed, view=view)

    @app_commands.command(
        name="wikimain",
        description="Setzt den Hauptkanal für das Wiki-Menü (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def wikimain(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await set_main_channel_id(channel.id)
        await self.reload_menu(channel.id)
        await utils.send_success(interaction, f"Wiki-Menü wurde in {channel.mention} gepostet!")

    @app_commands.command(
        name="wiki_page",
        description="Speichert den aktuellen Channel als neue Wiki-Seite (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def wiki_page(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        channel = interaction.channel
        msgs = [m async for m in channel.history(limit=30)]
        text_msg = next((m for m in msgs if not m.author.bot and m.content.strip()), None)
        if not text_msg:
            return await utils.send_error(interaction, "Kein Inhalt gefunden! (Letzte 30 Nachrichten prüfen.)")
        content = text_msg.content.strip()
        title = channel.name
        pages = await get_pages()
        backup = await get_backup()
        pages[title] = content
        backup[title] = content
        await save_pages(pages)
        await save_backup(backup)
        try:
            await interaction.user.send(
                f"Backup deiner Wiki-Seite '{title}':\n```{content[:1800]}```"
            )
        except Exception:
            pass
        await self.reload_menu()
        await utils.send_success(interaction, f"Wikiseite **{title}** gesichert!")

    @app_commands.command(
        name="wiki_delete",
        description="Löscht eine Wiki-Seite (nur Admins, Dropdown-Auswahl)."
    )
    @app_commands.guilds(MY_GUILD)
    async def wiki_delete(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        pages = await get_pages()
        if not pages:
            return await utils.send_error(interaction, "Keine Wiki-Seiten vorhanden.")
        view = WikiDeleteView(self)
        await interaction.response.send_message(
            "Wähle die zu löschende Seite aus:", view=view, ephemeral=True
        )

    @app_commands.command(
        name="wiki_edit",
        description="Bearbeitet eine Wiki-Seite (nur Admins, Dropdown/Modal)."
    )
    @app_commands.guilds(MY_GUILD)
    async def wiki_edit(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        pages = await get_pages()
        if not pages:
            return await utils.send_error(interaction, "Keine Wiki-Seiten vorhanden.")
        view = WikiEditView(self)
        await interaction.response.send_message(
            "Wähle die zu bearbeitende Seite aus:", view=view, ephemeral=True
        )

    @app_commands.command(
        name="wiki_backup",
        description="Stellt eine Wiki-Seite aus dem Backup als neuen Channel wieder her (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def wiki_backup(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        backup = await get_backup()
        if not backup:
            return await utils.send_error(interaction, "Keine Backups vorhanden.")
        view = WikiBackupView(self)
        await interaction.response.send_message(
            "Wähle eine Backup-Seite aus:", view=view, ephemeral=True
        )

# ========== Delete/Edit/Backup Views ==========

class WikiDeleteView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
        self.add_item(WikiDeleteDropdown(self))

class WikiDeleteDropdown(discord.ui.Select):
    def __init__(self, parent):
        self.parent = parent
        pages = utils.load_json_sync(WIKI_PAGES_PATH, {})
        options = [
            discord.SelectOption(label=title[:100], value=title)
            for title in list(pages.keys())[:MAX_DROPDOWN]
        ]
        super().__init__(
            placeholder="Seite auswählen…", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: Interaction):
        title = self.values[0]
        pages = await get_pages()
        if title not in pages:
            await utils.send_error(interaction, "Seite nicht gefunden.")
            return
        del pages[title]
        await save_pages(pages)
        await self.parent.cog.reload_menu()
        await utils.send_success(interaction, f"Seite **{title}** gelöscht.")

class WikiEditView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
        self.add_item(WikiEditDropdown(self))

class WikiEditDropdown(discord.ui.Select):
    def __init__(self, parent):
        self.parent = parent
        pages = utils.load_json_sync(WIKI_PAGES_PATH, {})
        options = [
            discord.SelectOption(label=title[:100], value=title)
            for title in list(pages.keys())[:MAX_DROPDOWN]
        ]
        super().__init__(
            placeholder="Seite auswählen…", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: Interaction):
        title = self.values[0]
        pages = await get_pages()
        content = pages.get(title, "")
        await interaction.response.send_modal(WikiEditModal(self.parent.cog, title, content))

class WikiEditModal(discord.ui.Modal, title="Wiki-Seite bearbeiten"):
    def __init__(self, cog, title, content):
        super().__init__()
        self.cog = cog
        self.title_ = title
        self.content_input = discord.ui.TextInput(
            label=f"Inhalt von '{title}' bearbeiten",
            style=discord.TextStyle.paragraph,
            default=content,
            required=True
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: Interaction):
        pages = await get_pages()
        pages[self.title_] = self.content_input.value
        await save_pages(pages)
        await self.cog.reload_menu()
        await utils.send_success(interaction, f"Inhalt von **{self.title_}** aktualisiert.")

class WikiBackupView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
        self.add_item(WikiBackupDropdown(self))

class WikiBackupDropdown(discord.ui.Select):
    def __init__(self, parent):
        self.parent = parent
        backup = utils.load_json_sync(WIKI_BACKUP_PATH, {})
        options = [
            discord.SelectOption(label=title[:100], value=title)
            for title in list(backup.keys())[:MAX_DROPDOWN]
        ]
        super().__init__(
            placeholder="Backup auswählen…", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: Interaction):
        title = self.values[0]
        backup = await get_backup()
        text = backup.get(title, "")
        if not text:
            await utils.send_error(interaction, "Kein Text im Backup gefunden.")
            return
        category = interaction.channel.category
        guild = interaction.guild
        if not category:
            await utils.send_error(interaction, "Bitte Command in einer Kategorie verwenden!")
            return
        try:
            new_channel = await guild.create_text_channel(name=title[:90], category=category)
            for chunk in chunk_text(text):
                await new_channel.send(chunk)
            await utils.send_success(interaction, f"Backup **{title}** als Channel wiederhergestellt: {new_channel.mention}")
        except Exception:
            await utils.send_error(interaction, "Konnte Channel nicht erstellen.")

# ========== Setup ==========

async def setup(bot):
    await bot.add_cog(WikiCog(bot))
