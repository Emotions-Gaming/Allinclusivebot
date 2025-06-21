import discord
from discord import app_commands
from discord.ext import commands

from utils import load_json, save_json, is_admin, has_role, has_any_role, mention_roles, get_member_by_id

WIKI_DATA_FILE   = "wiki_pages.json"
WIKI_BACKUP_FILE = "wiki_backup.json"
WIKI_CHANNEL_CFG = "wiki_channel.json"

class WikiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wiki_pages  = load_json(WIKI_DATA_FILE, {})
        self.wiki_backup = load_json(WIKI_BACKUP_FILE, {})
        self.wiki_main_channel_id = load_json(WIKI_CHANNEL_CFG, {}).get("main_channel_id", None)
        self.save_backup()

    def save(self):
        save_json(WIKI_DATA_FILE, self.wiki_pages)
        save_json(WIKI_BACKUP_FILE, self.wiki_backup)
        save_json(WIKI_CHANNEL_CFG, {"main_channel_id": self.wiki_main_channel_id})

    def save_backup(self):
        for title, content in self.wiki_pages.items():
            self.wiki_backup[title] = content
        self.save()

    async def post_wiki_menu(self):
        if not self.wiki_main_channel_id:
            return
        ch = self.bot.get_channel(self.wiki_main_channel_id)
        if not ch:
            return
        async for msg in ch.history(limit=50):
            if msg.author == self.bot.user:
                try:
                    await msg.delete()
                except Exception:
                    pass
        if not self.wiki_pages:
            await ch.send("Keine Wiki-Seiten verfügbar.")
            return
        view = discord.ui.View(timeout=None)
        options = [discord.SelectOption(label=title, value=title) for title in list(self.wiki_pages)[:25]]
        sel = discord.ui.Select(placeholder="Wiki-Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            text = self.wiki_pages.get(title, "")
            chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
            for chunk in chunks:
                await inter.response.send_message(f"**{title}**\n{chunk}", ephemeral=True)
        sel.callback = sel_cb
        view.add_item(sel)
        await ch.send("📚 **Wiki-Auswahl:**", view=view)

    # === Slash-Commands ===

    @app_commands.command(name="wikimain", description="Setzt den Hauptkanal für das Wiki-Menü")
    @app_commands.describe(channel="Textkanal für das Wiki-Menü")
    async def wikimain(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.wiki_main_channel_id = channel.id
        self.save()
        await interaction.response.send_message(f"Wiki-Main-Channel gesetzt: {channel.mention}", ephemeral=True)
        await self.post_wiki_menu()

    @app_commands.command(name="wiki_page", description="Speichert den aktuellen Channel als Wiki-Seite und löscht ihn")
    async def wiki_page(self, interaction: discord.Interaction):
        ch = interaction.channel
        title = ch.name.replace("-", " ").capitalize()
        async for msg in ch.history(limit=30, oldest_first=True):
            if msg.author.bot:
                continue
            content = msg.content.strip()
            if not content:
                continue
            self.wiki_pages[title] = content
            self.save_backup()
            try:
                await interaction.user.send(
                    f"**Wiki-Backup:**\nTitel: `{title}`\n\n{content[:1800]}"
                    + (f"\n\n[Text gekürzt]" if len(content) > 1800 else "")
                )
            except Exception:
                pass
            await ch.delete()
            await interaction.response.send_message(
                f"Wiki-Seite '{title}' gespeichert, Channel gelöscht. Backup wurde dir per DM geschickt!", ephemeral=True)
            await self.post_wiki_menu()
            return
        await interaction.response.send_message(
            "Keine passende Nachricht im Channel gefunden. Seite nicht gespeichert.", ephemeral=True)

    @app_commands.command(name="wiki_delete", description="Löscht eine Wiki-Seite")
    async def wiki_delete(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if not self.wiki_pages:
            return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(self.wiki_pages)[:25]]
        sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            self.wiki_pages.pop(title, None)
            self.save_backup()
            await inter.response.send_message(f"Seite '{title}' gelöscht.", ephemeral=True)
            await self.post_wiki_menu()
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle eine Seite zum Löschen:", view=view, ephemeral=True)

    @app_commands.command(name="wiki_edit", description="Bearbeite eine gespeicherte Wiki-Seite")
    async def wiki_edit(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if not self.wiki_pages:
            return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(self.wiki_pages)[:25]]
        sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            modal = discord.ui.Modal(title=f"Wiki-Seite bearbeiten: {title}")
            content_box = discord.ui.TextInput(
                label="Inhalt", style=discord.TextStyle.long,
                default=self.wiki_pages[title], required=True, max_length=1800
            )
            modal.add_item(content_box)
            async def on_submit(m_inter):
                self.wiki_pages[title] = content_box.value
                self.save_backup()
                await m_inter.response.send_message(f"Seite '{title}' aktualisiert!", ephemeral=True)
                await self.post_wiki_menu()
            modal.on_submit = on_submit
            await inter.response.send_modal(modal)
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle eine Seite zum Bearbeiten:", view=view, ephemeral=True)

    @app_commands.command(name="wiki_backup", description="Stellt einzelne Wiki-Seiten als Channel wieder her")
    async def wiki_backup_cmd(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if not self.wiki_backup:
            return await interaction.response.send_message("Keine Backups vorhanden.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        options = [discord.SelectOption(label=title, value=title) for title in list(self.wiki_backup)[:25]]
        sel = discord.ui.Select(placeholder="Backup-Seite wiederherstellen...", options=options)
        async def sel_cb(inter):
            title = inter.data["values"][0]
            cat = interaction.channel.category
            ch = await interaction.guild.create_text_channel(title.replace(" ", "-").lower(), category=cat)
            text = self.wiki_backup[title]
            chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
            for chunk in chunks:
                await ch.send(chunk)
            await inter.response.send_message(f"Channel `{title}` wiederhergestellt!", ephemeral=True)
        sel.callback = sel_cb
        view.add_item(sel)
        await interaction.response.send_message("Wähle ein Backup zum Wiederherstellen:", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(WikiCog(bot))
