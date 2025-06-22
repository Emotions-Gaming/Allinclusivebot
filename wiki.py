import discord
from discord.ext import commands
from discord import app_commands

from utils import load_json, save_json, is_admin

WIKI_DATA_FILE = "wiki_pages.json"
WIKI_BACKUP_FILE = "wiki_backup.json"
WIKI_MAIN_CHANNEL_FILE = "wiki_main_channel.json"

def get_wiki_pages():
    return load_json(WIKI_DATA_FILE, {})

def save_wiki_pages(data):
    save_json(WIKI_DATA_FILE, data)

def get_wiki_backup():
    return load_json(WIKI_BACKUP_FILE, {})

def save_wiki_backup(data):
    save_json(WIKI_BACKUP_FILE, data)

def get_main_channel():
    data = load_json(WIKI_MAIN_CHANNEL_FILE, {})
    return data.get("channel_id", None)

def set_main_channel(cid):
    save_json(WIKI_MAIN_CHANNEL_FILE, {"channel_id": cid})

class WikiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Setzt den Hauptkanal für das Wiki-Menü
    @app_commands.command(name="wikimain", description="Setzt den Hauptkanal für das Wiki-Menü")
    @app_commands.describe(channel="Textkanal für das Wiki-Menü")
    async def wikimain(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        set_main_channel(channel.id)
        await interaction.response.send_message(f"Wiki-Main-Channel gesetzt: {channel.mention}", ephemeral=True)
        await self.post_wiki_menu(channel)

    # Speichert den aktuellen Channel als Wiki-Seite und löscht ihn
    @app_commands.command(name="wiki_page", description="Speichert den aktuellen Channel als Wiki-Seite und löscht ihn")
    async def wiki_page(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        ch = interaction.channel
        title = ch.name.replace("-", " ").capitalize()
        # Den ersten echten User-Post als Seiteninhalt nehmen (max 30 Nachrichten scannen)
        async for msg in ch.history(limit=30, oldest_first=True):
            if msg.author.bot:
                continue
            content = msg.content.strip()
            if not content:
                continue
            pages = get_wiki_pages()
            backup = get_wiki_backup()
            pages[title] = content
            save_wiki_pages(pages)
            backup[title] = content
            save_wiki_backup(backup)
            # Backup per DM an Command-User
            try:
                await interaction.user.send(
                    f"**Wiki-Backup:**\nTitel: `{title}`\n\n{content[:1800]}" +
                    (f"\n\n[Text gekürzt]" if len(content) > 1800 else "")
                )
            except Exception:
                pass
            await ch.delete()
            await interaction.response.send_message(
                f"Wiki-Seite '{title}' gespeichert, Channel gelöscht. Backup wurde dir per DM geschickt!", ephemeral=True)
            await self.post_wiki_menu(interaction.guild.get_channel(get_main_channel()))
            return
        await interaction.response.send_message(
            "Keine passende Nachricht im Channel gefunden. Seite nicht gespeichert.", ephemeral=True)

    # Löscht eine Wiki-Seite
    @app_commands.command(name="wiki_delete", description="Löscht eine Wiki-Seite")
    async def wiki_delete(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        pages = get_wiki_pages()
        if not pages:
            return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(pages)[:25]]
        sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            pages = get_wiki_pages()
            pages.pop(title, None)
            save_wiki_pages(pages)
            await inter.response.send_message(f"Seite '{title}' gelöscht.", ephemeral=True)
            await self.post_wiki_menu(interaction.guild.get_channel(get_main_channel()))
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle eine Seite zum Löschen:", view=view, ephemeral=True)

    # Bearbeite eine gespeicherte Wiki-Seite
    @app_commands.command(name="wiki_edit", description="Bearbeite eine gespeicherte Wiki-Seite")
    async def wiki_edit(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        pages = get_wiki_pages()
        if not pages:
            return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(pages)[:25]]
        sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            modal = discord.ui.Modal(title=f"Wiki-Seite bearbeiten: {title}")
            content_box = discord.ui.TextInput(label="Inhalt", style=discord.TextStyle.long, default=get_wiki_pages()[title], required=True, max_length=1800)
            modal.add_item(content_box)
            async def on_submit(m_inter):
                pages = get_wiki_pages()
                backup = get_wiki_backup()
                pages[title] = content_box.value
                save_wiki_pages(pages)
                backup[title] = content_box.value
                save_wiki_backup(backup)
                await m_inter.response.send_message(f"Seite '{title}' aktualisiert!", ephemeral=True)
                await self.post_wiki_menu(interaction.guild.get_channel(get_main_channel()))
            modal.on_submit = on_submit
            await inter.response.send_modal(modal)
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle eine Seite zum Bearbeiten:", view=view, ephemeral=True)

    # Stellt einzelne Wiki-Seiten als Channel wieder her
    @app_commands.command(name="wiki_backup", description="Stellt einzelne Wiki-Seiten als Channel wieder her")
    async def wiki_backup_cmd(self, interaction: discord.Interaction):
        backup = get_wiki_backup()
        if not backup:
            return await interaction.response.send_message("Keine Backups vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(backup)[:25]]
        sel = discord.ui.Select(placeholder="Backup-Seite wiederherstellen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            cat = interaction.channel.category
            ch = await interaction.guild.create_text_channel(title.replace(" ", "-").lower(), category=cat)
            text = backup[title]
            chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
            for chunk in chunks:
                await ch.send(chunk)
            await inter.response.send_message(f"Channel `{title}` wiederhergestellt!", ephemeral=True)
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle ein Backup zum Wiederherstellen:", view=view, ephemeral=True)

    # ---- WIKI MENU/Dropdown posten (immer max. 25 Seiten pro View, Discord-Limit) ----
    async def post_wiki_menu(self, ch=None):
        ch_id = get_main_channel()
        if not ch_id:
            return
        ch = ch or self.bot.get_channel(ch_id)
        if not ch:
            return
        pages = get_wiki_pages()
        async for msg in ch.history(limit=50):
            if msg.author == self.bot.user:
                try:
                    await msg.delete()
                except Exception:
                    pass
        if not pages:
            await ch.send("Keine Wiki-Seiten verfügbar.")
            return
        view = discord.ui.View(timeout=None)
        options = [
            discord.SelectOption(label=title, value=title)
            for title in list(pages)[:25]
        ]
        sel = discord.ui.Select(placeholder="Wiki-Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            text = get_wiki_pages().get(title, "")
            chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
            for chunk in chunks:
                await inter.response.send_message(f"**{title}**\n{chunk}", ephemeral=True)
        sel.callback = sel_cb
        view.add_item(sel)
        await ch.send("📚 **Wiki-Auswahl:**", view=view)


    # ... dein WikiCog-Code ...

async def reload_menu(self, config=None):
    if config is None:
        from utils import load_json
        config = load_json("setup_config.json", {})
    channel_id = config.get("wiki_main_channel")
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
    await self.post_wiki_menu()  # Deine bestehende Funktion!

WikiCog.reload_menu = reload_menu

async def setup(bot):
    await bot.add_cog(WikiCog(bot))