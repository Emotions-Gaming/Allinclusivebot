import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
REQUEST_LEADS_PATH = os.path.join("persistent_data", "request_leads.json")
MAX_TITLE_LEN = 80
MAX_BODY_LEN = 500
MAX_COMMENT_LEN = 200

TAG_CUSTOM = {"name": "Custom", "emoji": "🛠️"}
TAG_AI = {"name": "AI Voice", "emoji": "🤖"}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "✨"}

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "geschlossen": discord.Color.dark_grey(),
    "uploaded": discord.Color.teal(),
    "done": discord.Color.dark_green(),
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "geschlossen": "🛑 Geschlossen",
    "uploaded": "⬆️ Hochgeladen",
    "done": "✅ Erledigt"
}

def build_thread_title(status, streamer, ersteller, typ, nr):
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data.get('streamer', 'Anfrage')}"
    lang = f"**Sprache:** {data.get('sprache', 'Nicht angegeben')}\n" if data.get("sprache") else ""
    tag = f"**Fan-Tag:** {data.get('fan_tag','')}\n" if data.get("fan_tag") else ""
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"{tag}{lang}"
            f"**Preis & Bezahlt:** {data['preis']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"{lang}"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"{lang}"
            f"**Medium:** {data['medium']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Bis Wann:** {data['zeitgrenze']}"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}
        self.forum_tags = {}

    async def cog_load(self):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return
        guild = self.bot.get_guild(GUILD_ID)
        forum = guild.get_channel(forum_id)
        if forum and hasattr(forum, "available_tags"):
            self.forum_tags = {tag.name: tag for tag in forum.available_tags}

    @app_commands.command(name="requestsetactive", description="Setzt das Forum für aktive Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetactive(self, interaction: Interaction, channel: discord.ForumChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await get_request_config()
        config["active_forum"] = channel.id
        await save_request_config(config)
        await utils.send_success(interaction, f"Aktive Requests-Forum gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetdone", description="Setzt das Forum für erledigte Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetdone(self, interaction: Interaction, channel: discord.ForumChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await get_request_config()
        config["done_forum"] = channel.id
        await save_request_config(config)
        await utils.send_success(interaction, f"Done-Forum gesetzt: {channel.mention}")

    @app_commands.command(name="requestmain", description="Postet das Anfrage-Menü (nur Textkanäle erlaubt!)")
    @app_commands.guilds(MY_GUILD)
    async def requestmain(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        embed = discord.Embed(
            title="📩 Anfrage-System",
            description=(
                f"{TAG_CUSTOM['emoji']} **Custom Anfrage:** Individuelle Wünsche, Video-Produktionen, etc.\n"
                f"{TAG_AI['emoji']} **AI Voice Anfrage:** Text zu KI-Sprache\n"
                f"{TAG_WUNSCH['emoji']} **Content Wunsch:** Allgemeiner Medienwunsch\n\n"
                "Wähle eine Option, um eine neue Anfrage zu stellen."
            ),
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

    # LEAD MANAGEMENT, weitere Admin-Commands wie gehabt (aus Platzgründen hier nicht dupliziert!)

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr
        tag_map = {"custom": TAG_CUSTOM["name"], "ai": TAG_AI["name"], "wunsch": TAG_WUNSCH["name"]}
        selected_tag_name = tag_map.get(reqtype, "Custom")
        tag_obj = None
        if hasattr(forum, "available_tags"):
            tag_obj = next((t for t in forum.available_tags if t.name == selected_tag_name), None)
        applied_tags = [tag_obj.id] if tag_obj else []

        thread_title = build_thread_title("offen", data.get('streamer', ""), str(interaction.user), reqtype, nr)
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=applied_tags,
        )
        channel = thread_with_message.thread
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
        self.chat_backups[channel.id] = []
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        ids = leads.get(reqtype, [])
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = f"Neue **{reqtype.capitalize()} Anfrage** von {interaction.user.mention}:\n"
                    if reqtype == "custom":
                        msg += (
                            f"**Streamer:** {data['streamer']}\n"
                            f"**Fan-Tag:** {data['fan_tag']}\n"
                            f"**Preis & Bezahlt:** {data['preis']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Anfrage:** {data['anfrage']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Streamer:** {data['streamer']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Audio Wunsch:** {data['audiowunsch']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    elif reqtype == "wunsch":
                        msg += (
                            f"**Streamer:** {data['streamer']}\n"
                            f"**Medium:** {data['medium']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Anfrage:** {data['anfrage']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    async def on_thread_message(self, message):
        if message.channel.id in self.chat_backups:
            if not message.author.bot:
                self.chat_backups[message.channel.id].append(
                    (message.author.display_name, message.content)
                )

# ALLE Views, Dropdowns, Modals, Buttons, etc. gehören hier weiter rein!
# ========== RequestMenuView & Typen-Auswahl ==========

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.dropdown = RequestTypeDropdown(cog)
        self.add_item(self.dropdown)

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage", emoji=TAG_CUSTOM['emoji']),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="KI-Sprache: Text zu Voice", emoji=TAG_AI['emoji']),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Allgemeiner Content-Wunsch", emoji=TAG_WUNSCH['emoji']),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        # Modal reset handling
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))
        # Reset dropdown after selection (for next usage)
        self.view.clear_items()
        self.view.add_item(RequestTypeDropdown(self.cog))
        await interaction.message.edit(view=self.view)

# ========== CustomRequestModal (mit allen Feldern & Beschreibung) ==========

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True
        )
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="z.B. @12hh238712 (siehe Discord-Profil!)",
            max_length=32,
            required=True
        )
        self.preis = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z.B. 400€, Bezahlt",
            max_length=30,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=20,
            required=True
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Was möchtest du? Bis wann? (z.B. Möchte ein Video über ... bis 19.06.2025)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis": self.preis.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.anfrage.value.split("bis")[-1].strip() if "bis" in self.anfrage.value else "",
        }
        await self.cog.post_request(interaction, data, "custom")

# ========== AIRequestModal ==========

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=20,
            required=True
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Was soll gesagt werden? (max 10 Sekunden!)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="z.B. bis 20.07.2025",
            max_length=40,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.sprache)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "sprache": self.sprache.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "ai")

# ========== WunschRequestModal ==========

class WunschRequestModal(discord.ui.Modal, title="Content Wunsch"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True
        )
        self.medium = discord.ui.TextInput(
            label="Medium",
            placeholder="Video/Bild/Audio?",
            max_length=15,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=20,
            required=True
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Beschreibe deinen Content-Wunsch",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="z.B. bis 20.07.2025",
            max_length=40,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.medium)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "medium": self.medium.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ========== Thread View mit Status/Schließen-Buttons ==========

class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="✏️")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads.get(reqtype, [])
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel, interaction.user),
            ephemeral=True
        )

class StatusDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead):
        super().__init__(timeout=60)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.add_item(StatusDropdown(cog, data, thread_channel, lead))

class StatusDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel, lead):
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Uploaded", value="uploaded"),
            discord.SelectOption(label="Done", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        # Popup für Grund falls nötig
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status, self.lead))
        else:
            await self.finish_status_change(interaction, new_status)

    async def finish_status_change(self, interaction, new_status, reason=None):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        if reason:
            self.data['status_reason'] = reason
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        if reason:
            embed.add_field(name="Begründung", value=reason, inline=False)
        await self.thread_channel.send(
            embed=embed
        )
        # DM mit Link an Ersteller
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                link = self.thread_channel.jump_url
                msg = (
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"{'Begründung: ' + reason if reason else ''}\n"
                    f"[Hier zum Post]({link})"
                )
                await ersteller.send(msg)
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für Statusänderung"):
    def __init__(self, cog, data, thread_channel, status, lead):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.status = status
        self.lead = lead
        self.reason = discord.ui.TextInput(
            label="Grund/Kommentar",
            placeholder="Bitte gib einen kurzen Grund an.",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.status, self.reason.value
        )

class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        # NUR Lead oder Ersteller darf schließen!
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads.get(reqtype, [])
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur Lead oder Anfragesteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                if not msg.content.startswith("Status geändert"):
                    name = msg.author.display_name
                    content = msg.content
                    if content.strip() == "":
                        continue
                    messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        tag_map = {"custom": TAG_CUSTOM["name"], "ai": TAG_AI["name"], "wunsch": TAG_WUNSCH["name"]}
        tag_obj = None
        if hasattr(done_forum, "available_tags"):
            tag_obj = next((t for t in done_forum.available_tags if t.name == tag_map.get(self.data["type"], "Custom")), None)
        applied_tags = [tag_obj.id] if tag_obj else []
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=applied_tags,
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# ===== Lead-DM (Dropdown in DM für schnelle Status-Änderung) =====
class LeadActionsDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.add_item(LeadActionsDropdown(cog, data, thread_channel, lead))

class LeadActionsDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel, lead):
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        options = [
            discord.SelectOption(label="Status: Offen", value="offen"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Status: Uploaded", value="uploaded"),
            discord.SelectOption(label="Status: Done", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        # Grund-Modal für einige Status
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status, self.lead))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status)

# ========== Setup ==========

async def setup(bot):
    await bot.add_cog(RequestCog(bot))

