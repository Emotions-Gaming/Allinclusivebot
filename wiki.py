# wiki.py

import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel, Embed
from utils import is_admin, load_json, save_json

GUILD_ID = int(os.environ.get("GUILD_ID"))
PAGES_JSON = "persistent_data/wiki_pages.json"
BACKUP_JSON = "persistent_data/wiki_backup.json"
MAIN_CHANNEL_JSON = "persistent_data/wiki_main_channel.json"

def _load_pages():
    return load_json(PAGES_JSON, {})

def _save_pages(pages):
    save_json(PAGES_JSON, pages)

def _load_backup():
    return load_json(BACKUP_JSON, {})

def _save_backup(bkp):
    save_json(BACKUP_JSON, bkp)

def _load_main():
    return load_json(MAIN_CHANNEL_JSON, {})

def _save_main(data):
    save_json(MAIN_CHANNEL_JSON, data)

class WikiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==== reload_menu für setupbot ====
    async def reload_menu(self):
        main = _load_main()
        main_channel_id = main.get("main_channel_id")
        if not main_channel_id:
            return
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(main_channel_id)
        if not channel:
            return
        # Lösche alte Menüs vom Bot
        async for msg in channel.history(limit=30):
            if msg.author == self.bot.user and msg.embeds and "Wiki-Menü" in (msg.embeds[0].title or ""):
                try:
                    await msg.delete()
                except Exception:
                    pass
        pages = _load_pages()
        options = [discord.SelectOption(label=title, description=text[:70].replace("\n", " "))
                   for title, text in list(pages.items())[:25]]
        embed = Embed(
            title="📚 Wiki-Menü",
            description="Wähle eine Seite aus dem Dropdown-Menü, um den Inhalt zu sehen.",
            color=0x1abc9c
        )
        view = WikiSelectView(pages)
        await channel.send(embed=embed, view=view)

    @app_commands.command(
        name="wikimain",
        description="Setzt den Hauptkanal & postet das Wiki-Menü (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    async def wikimain(self, interaction: Interaction, channel: TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_main({"main_channel_id": channel.id})
        await self.reload_menu()
        await interaction.response.send_message("✅ Wiki-Menü im Channel gepostet!", ephemeral=True)

    @app_commands.command(
        name="wiki_page",
        description="Speichert diesen Channel als Wiki-Seite (nur Admin!)"
    )
    @app_commands.guilds(GUILD_ID)
    async def wiki_page(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        channel = interaction.channel
        title = channel.name
        messages = [msg async for msg in channel.history(limit=30, oldest_first=True)
                    if not msg.author.bot and msg.content.strip()]
        if not messages:
            await interaction.response.send_message("❌ Kein Inhalt gefunden.", ephemeral=True)
            return
        text = messages[0].content.strip()
        # Speichern
        pages = _load_pages()
        backup = _load_backup()
        pages[title] = text
        backup[title] = text
        _save_pages(pages)
        _save_backup(backup)
        # Admin per DM schicken
        try:
            dm_embed = Embed(
                title=f"📄 Wiki-Backup: {title}",
                description=f"{text}",
                color=0x1abc9c
            )
            await interaction.user.send(embed=dm_embed)
        except Exception:
            pass
        # Channel löschen
        try:
            await channel.delete()
        except Exception:
            await interaction.response.send_message("⚠️ Seite gespeichert, aber Channel konnte nicht gelöscht werden.", ephemeral=True)
            await self.reload_menu()
            return
        await interaction.response.send_message("✅ Seite gespeichert, Backup per DM gesendet und Channel gelöscht!", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="wiki_delete",
        description="Löscht eine Wiki-Seite (Dropdown, nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    async def wiki_delete(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        pages = _load_pages()
        if not pages:
            await interaction.response.send_message("ℹ️ Keine Seiten vorhanden.", ephemeral=True)
            return

        class DeleteView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=60)
                self.cog = cog
                self.add_item(DeleteSelect(self.cog, list(pages.keys())[:25]))

        class DeleteSelect(discord.ui.Select):
            def __init__(self, cog, options):
                super().__init__(
                    placeholder="Seite wählen…",
                    options=[discord.SelectOption(label=title) for title in options]
                )
                self.cog = cog

            async def callback(self, interaction: Interaction):
                pages = _load_pages()
                backup = _load_backup()
                if self.values[0] in pages:
                    del pages[self.values[0]]
                    _save_pages(pages)
                if self.values[0] in backup:
                    del backup[self.values[0]]
                    _save_backup(backup)
                await interaction.response.send_message(f"✅ Seite **{self.values[0]}** gelöscht!", ephemeral=True)
                await self.cog.reload_menu()

        await interaction.response.send_message(
            "Wähle eine Seite zum Löschen:",
            view=DeleteView(self),
            ephemeral=True
        )

    @app_commands.command(
        name="wiki_edit",
        description="Bearbeite eine Wiki-Seite (Dropdown, Modal, nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    async def wiki_edit(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        pages = _load_pages()
        if not pages:
            await interaction.response.send_message("ℹ️ Keine Seiten vorhanden.", ephemeral=True)
            return

        class EditView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=60)
                self.cog = cog
                self.add_item(EditSelect(self.cog, list(pages.keys())[:25]))

        class EditSelect(discord.ui.Select):
            def __init__(self, cog, options):
                super().__init__(
                    placeholder="Seite wählen…",
                    options=[discord.SelectOption(label=title) for title in options]
                )
                self.cog = cog

            async def callback(self, interaction: Interaction):
                title = self.values[0]
                old = _load_pages().get(title, "")

                class EditModal(discord.ui.Modal, title=f"Wiki editieren: {title}"):
                    content = discord.ui.TextInput(label="Seiteninhalt", style=discord.TextStyle.paragraph, default=old, max_length=1800)

                    async def on_submit(self, modal_interaction: Interaction):
                        pages = _load_pages()
                        backup = _load_backup()
                        pages[title] = self.content.value
                        backup[title] = self.content.value
                        _save_pages(pages)
                        _save_backup(backup)
                        await modal_interaction.response.send_message(f"✅ Seite **{title}** aktualisiert!", ephemeral=True)
                        await self.cog.reload_menu()

                await interaction.response.send_modal(EditModal())

        await interaction.response.send_message(
            "Wähle eine Seite zum Bearbeiten:",
            view=EditView(self),
            ephemeral=True
        )

    @app_commands.command(
        name="wiki_backup",
        description="Stellt eine Seite aus Backup wieder her (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    async def wiki_backup(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        backup = _load_backup()
        if not backup:
            await interaction.response.send_message("ℹ️ Keine Backups vorhanden.", ephemeral=True)
            return

        class RestoreView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=60)
                self.cog = cog
                self.add_item(RestoreSelect(self.cog, list(backup.keys())[:25]))

        class RestoreSelect(discord.ui.Select):
            def __init__(self, cog, options):
                super().__init__(
                    placeholder="Backup-Seite wählen…",
                    options=[discord.SelectOption(label=title) for title in options]
                )
                self.cog = cog

            async def callback(self, interaction: Interaction):
                title = self.values[0]
                text = _load_backup().get(title, "")
                # Stelle als neuen Channel in aktuelle Kategorie her
                category = interaction.channel.category
                if not category:
                    await interaction.response.send_message("❌ Muss in einer Kategorie ausgeführt werden.", ephemeral=True)
                    return
                guild = interaction.guild or self.cog.bot.get_guild(GUILD_ID)
                # Channelnamen ggf. kürzen und prüfen
                cname = f"wiki-{title}".replace(" ", "-").lower()[:90]
                try:
                    new_ch = await guild.create_text_channel(cname, category=category)
                except Exception:
                    await interaction.response.send_message("❌ Channel konnte nicht erstellt werden.", ephemeral=True)
                    return
                # Text ggf. splitten
                chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
                for chunk in chunks:
                    await new_ch.send(chunk)
                await interaction.response.send_message(f"✅ Wiki-Seite **{title}** wiederhergestellt: {new_ch.mention}", ephemeral=True)
                await self.cog.reload_menu()

        await interaction.response.send_message(
            "Wähle eine Seite aus dem Backup zum Wiederherstellen:",
            view=RestoreView(self),
            ephemeral=True
        )

# ==== User-Menü: Dropdown zum Nachschlagen der Seiten ====

class WikiSelectView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label=title, description=text[:70].replace("\n", " "))
            for title, text in list(pages.items())[:25]
        ]
        self.add_item(WikiSelect(options, pages))

class WikiSelect(discord.ui.Select):
    def __init__(self, options, pages):
        super().__init__(
            placeholder="Wiki-Seite auswählen...",
            options=options
        )
        self.pages = pages

    async def callback(self, interaction: Interaction):
        title = self.values[0]
        text = self.pages.get(title, "")
        embed = Embed(
            title=f"📄 Wiki: {title}",
            description=text if text else "*Kein Inhalt gefunden*",
            color=0x1abc9c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ==== Extension Loader ====
async def setup(bot):
    await bot.add_cog(WikiCog(bot))
