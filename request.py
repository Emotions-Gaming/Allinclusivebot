import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
REQUEST_LEADS_PATH = os.path.join("persistent_data", "request_leads.json")
MAX_TITLE_LEN = 80
MAX_BODY_LEN = 500
MAX_COMMENT_LEN = 200

# ---- Tag-IDs (deine echten Foren-Tags eintragen) ----
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

# ---- Status
STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.blue(),
    "done": discord.Color.teal(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "📤 Hochgeladen",
    "done": "✅ Fertig",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, ersteller, tag, typ, nr):
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {tag} - {typ.capitalize()} - #{nr}"

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
    title = f"📩 {data['streamer']}" if data.get("streamer") else "Anfrage"
    tagline = f"**Fan-Tag:** {data['fan_tag']}" if data.get("fan_tag") else ""
    sprache = f"**Sprache:** {data['sprache']}" if data.get("sprache") else ""
    desc = data.get("desc", "")

    # CUSTOM
    if data["type"] == "custom":
        desc = (
            f"{tagline}\n"
            f"**Preis und bezahlt?** {data['preis_bezahlt']}\n"
            f"{sprache}\n"
            f"**Anfrage + Bis Wann?** {data['anfrage_bis']}"
        )
    # AI
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Sprache:** {data['sprache']}\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Bis wann:** {data['zeitgrenze']}"
        )
    # WUNSCH
    elif data["type"] == "wunsch":
        desc = (
            f"**Typ:** {data['media_typ']}\n"
            f"**Sprache:** {data['sprache']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Bis wann:** {data['zeitgrenze']}"
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

    # ==== Setup-Kommandos ====
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

    # ==== Menü posten ====
    @app_commands.command(name="requestmain", description="Postet das Anfrage-Menü")
    @app_commands.guilds(MY_GUILD)
    async def requestmain(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        embed = discord.Embed(
            title="📩 Anfrage-System",
            description="Wähle unten eine Kategorie aus, um eine Anfrage zu erstellen.",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

    # ==== Lead-Management ====
    @app_commands.command(name="requestcustomlead", description="Fügt einen Custom-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestcustomlead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["custom"]:
            leads["custom"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist jetzt Custom-Lead.")

    @app_commands.command(name="requestcustomremovelead", description="Entfernt einen Custom-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestcustomremovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["custom"]:
            leads["custom"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als Custom-Lead entfernt.")

    @app_commands.command(name="requestailead", description="Fügt einen AI-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestailead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["ai"]:
            leads["ai"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist jetzt AI-Lead.")

    @app_commands.command(name="requestairemovelead", description="Entfernt einen AI-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestairemovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["ai"]:
            leads["ai"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als AI-Lead entfernt.")

    @app_commands.command(name="requestwunschlead", description="Fügt einen Wunsch-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestwunschlead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["wunsch"]:
            leads["wunsch"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist jetzt Wunsch-Lead.")

    @app_commands.command(name="requestwunschremovelead", description="Entfernt einen Wunsch-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestwunschremovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["wunsch"]:
            leads["wunsch"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als Wunsch-Lead entfernt.")

    # ======= Haupt-Request-Posting (mit Tags) =======
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")

        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # KATEGORIE-TAG wählt nach Typ
        if reqtype == "custom":
            applied_tags = [TAG_CUSTOM["id"]]
            tag_text = TAG_CUSTOM["name"]
        elif reqtype == "ai":
            applied_tags = [TAG_AI["id"]]
            tag_text = TAG_AI["name"]
        else:
            applied_tags = [TAG_WUNSCH["id"]]
            tag_text = TAG_WUNSCH["name"]

        thread_title = build_thread_title("offen", data['streamer'], str(interaction.user), tag_text, reqtype, nr)
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=applied_tags
        )
        channel = thread_with_message.thread

        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        data["tag"] = tag_text
        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
        self.chat_backups[channel.id] = []
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    # ==== DM an Lead (wie gehabt) ====
    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        if reqtype == "custom":
            ids = leads["custom"]
        elif reqtype == "ai":
            ids = leads["ai"]
        else:
            ids = leads["wunsch"]
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{data['tag']} Anfrage** von {interaction.user.mention}:\n"
                        f"**Streamer:** {data['streamer']}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Fan-Tag:** {data['fan_tag']}\n"
                            f"**Preis und bezahlt?** {data['preis_bezahlt']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Anfrage + Bis Wann?** {data['anfrage_bis']}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Audio Wunsch:** {data['audiowunsch']}\n"
                            f"**Bis wann:** {data['zeitgrenze']}\n"
                        )
                    else:
                        msg += (
                            f"**Typ:** {data['media_typ']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Anfrage:** {data['anfrage']}\n"
                            f"**Bis wann:** {data['zeitgrenze']}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    # ====== Nachrichten Backup für später (done-thread) ======
    async def on_thread_message(self, message):
        if message.channel.id in self.chat_backups:
            if not message.author.bot:
                self.chat_backups[message.channel.id].append(
                    (message.author.display_name, message.content)
                )

# ==== VIEWS & MODALS folgen (Custom, AI, Wunsch, Statuswechsel usw.) ====
# ==== Anfrage-Menü View ====
class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(self.cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", emoji=TAG_CUSTOM["emoji"], description="Individuelle Anfrage erstellen"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", emoji=TAG_AI["emoji"], description="AI Voice Over Anfrage"),
            discord.SelectOption(label="Content Wunsch", value="wunsch", emoji=TAG_WUNSCH["emoji"], description="Content (Bild/Video/Audio) Wunsch")
        ]
        super().__init__(
            placeholder="Wähle eine Anfrage-Art…",
            min_values=1, max_values=1, options=options
        )
        self.cog = cog

    async def callback(self, interaction: Interaction):
        value = self.values[0]
        if value == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif value == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif value == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# ==== Custom Anfrage Modal ====
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag eingeben",
            max_length=32
        )
        self.preis_bezahlt = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=40
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.anfrage_bis = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über … Bis zum 19.06.2025",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis_bezahlt)
        self.add_item(self.sprache)
        self.add_item(self.anfrage_bis)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis_bezahlt": self.preis_bezahlt.value,
            "sprache": self.sprache.value,
            "anfrage_bis": self.anfrage_bis.value,
        }
        await self.cog.post_request(interaction, data, "custom")

# ==== AI Voice Anfrage Modal ====
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Gewünschter Text für Voice Over",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.sprache)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
            "sprache": self.sprache.value
        }
        await self.cog.post_request(interaction, data, "ai")

# ==== Content Wunsch Modal ====
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.media_typ = discord.ui.TextInput(
            label="Typ",
            placeholder="Video, Bild oder Audio?",
            max_length=20
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Wunsch beschreiben",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.media_typ)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "media_typ": self.media_typ.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ==== Thread-View mit Status- und Close-Button ====
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# ==== Status Bearbeiten Button ====
class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="✏️")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel, interaction.user),
            ephemeral=True
        )

# ==== Status-Dropdown ====
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
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Fertig", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, "")

    async def finish_status_change(self, interaction, new_status, grund):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(
            new_status, self.data['streamer'], self.data['erstellername'], self.data['tag'], self.data['type'], nr
        )
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        content = f"Status geändert von {interaction.user.mention}:"
        if grund:
            content += f"\n**Begründung:** {grund}"
        await self.thread_channel.send(content=content, embed=embed)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Hier zum Post]({self.thread_channel.jump_url})\n"
                    + (f"**Begründung:** {grund}" if grund else "")
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für den Status"):
    def __init__(self, cog, data, thread_channel, lead, status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.status = status
        self.reason = discord.ui.TextInput(
            label="Grund",
            placeholder="Bitte gib einen Grund für diese Statusänderung an.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.status, self.reason.value
        )

# ==== Anfrage schließen Button ====
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        # Nur Lead oder Ersteller darf schließen!
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur der zuständige Lead oder der Anfragesteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)

        # Filter Bot-Systemnachrichten aus dem Verlauf raus
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if msg.author.bot:
                if not any(
                    k in msg.content for k in [
                        "Status geändert von", "Anfrage erstellt", "Backup der Anfrage"
                    ]
                ):
                    messages.append(f"**{msg.author.display_name}:** {msg.content}")
            else:
                if msg.content.strip() != "":
                    messages.append(f"**{msg.author.display_name}:** {msg.content}")

        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(
            self.data.get('status', 'geschlossen'), self.data['streamer'], self.data['erstellername'],
            self.data['tag'], self.data['type'], nr
        )
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[TAG_CUSTOM["id"] if self.data['type'] == "custom"
                         else TAG_AI["id"] if self.data['type'] == "ai"
                         else TAG_WUNSCH["id"]]
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# ==== Lead-Actions-Dropdown (DM) ====
class LeadActionsDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead):
        super().__init__(timeout=None)
        self.add_item(LeadActionsDropdown(cog, data, thread_channel, lead))

class LeadActionsDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel, lead):
        options = [
            discord.SelectOption(label="Status: Offen", value="offen"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Status: Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Status: Fertig", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status, "")

# ==== Setup zum Schluss ====
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
# ==== Anfrage-Menü View ====
class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(self.cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", emoji=TAG_CUSTOM["emoji"], description="Individuelle Anfrage erstellen"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", emoji=TAG_AI["emoji"], description="AI Voice Over Anfrage"),
            discord.SelectOption(label="Content Wunsch", value="wunsch", emoji=TAG_WUNSCH["emoji"], description="Content (Bild/Video/Audio) Wunsch")
        ]
        super().__init__(
            placeholder="Wähle eine Anfrage-Art…",
            min_values=1, max_values=1, options=options
        )
        self.cog = cog

    async def callback(self, interaction: Interaction):
        value = self.values[0]
        if value == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif value == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif value == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# ==== Custom Anfrage Modal ====
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag eingeben",
            max_length=32
        )
        self.preis_bezahlt = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=40
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.anfrage_bis = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über … Bis zum 19.06.2025",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis_bezahlt)
        self.add_item(self.sprache)
        self.add_item(self.anfrage_bis)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis_bezahlt": self.preis_bezahlt.value,
            "sprache": self.sprache.value,
            "anfrage_bis": self.anfrage_bis.value,
        }
        await self.cog.post_request(interaction, data, "custom")

# ==== AI Voice Anfrage Modal ====
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Gewünschter Text für Voice Over",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.sprache)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
            "sprache": self.sprache.value
        }
        await self.cog.post_request(interaction, data, "ai")

# ==== Content Wunsch Modal ====
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.media_typ = discord.ui.TextInput(
            label="Typ",
            placeholder="Video, Bild oder Audio?",
            max_length=20
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch oder Deutsch",
            max_length=20
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Wunsch beschreiben",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.media_typ)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "media_typ": self.media_typ.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ==== Thread-View mit Status- und Close-Button ====
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# ==== Status Bearbeiten Button ====
class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="✏️")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel, interaction.user),
            ephemeral=True
        )

# ==== Status-Dropdown ====
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
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Fertig", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, "")

    async def finish_status_change(self, interaction, new_status, grund):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(
            new_status, self.data['streamer'], self.data['erstellername'], self.data['tag'], self.data['type'], nr
        )
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        content = f"Status geändert von {interaction.user.mention}:"
        if grund:
            content += f"\n**Begründung:** {grund}"
        await self.thread_channel.send(content=content, embed=embed)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Hier zum Post]({self.thread_channel.jump_url})\n"
                    + (f"**Begründung:** {grund}" if grund else "")
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für den Status"):
    def __init__(self, cog, data, thread_channel, lead, status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.status = status
        self.reason = discord.ui.TextInput(
            label="Grund",
            placeholder="Bitte gib einen Grund für diese Statusänderung an.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.status, self.reason.value
        )
# ==== Thread-View mit Status- und Close-Button ====
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# ==== Status Bearbeiten Button ====
class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="✏️")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel, interaction.user),
            ephemeral=True
        )

# ==== Status-Dropdown ====
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
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Fertig", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, "")

    async def finish_status_change(self, interaction, new_status, grund):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(
            new_status, self.data['streamer'], self.data['erstellername'], self.data['tag'], self.data['type'], nr
        )
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        content = f"Status geändert von {interaction.user.mention}:"
        if grund:
            content += f"\n**Begründung:** {grund}"
        await self.thread_channel.send(content=content, embed=embed)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Hier zum Post]({self.thread_channel.jump_url})\n"
                    + (f"**Begründung:** {grund}" if grund else "")
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für den Status"):
    def __init__(self, cog, data, thread_channel, lead, status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.status = status
        self.reason = discord.ui.TextInput(
            label="Grund",
            placeholder="Bitte gib einen Grund für diese Statusänderung an.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.status, self.reason.value
        )

# ==== Anfrage schließen Button ====
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        # Nur Lead oder Ersteller darf schließen!
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur der zuständige Lead oder der Anfragesteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)

        # Filter Bot-Systemnachrichten aus dem Verlauf raus
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if msg.author.bot:
                # Filtere Bot-System-Nachrichten raus:
                if not any(
                    k in msg.content for k in [
                        "Status geändert von", "Anfrage erstellt", "Backup der Anfrage"
                    ]
                ):
                    messages.append(f"**{msg.author.display_name}:** {msg.content}")
            else:
                if msg.content.strip() != "":
                    messages.append(f"**{msg.author.display_name}:** {msg.content}")

        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(
            self.data.get('status', 'geschlossen'), self.data['streamer'], self.data['erstellername'],
            self.data['tag'], self.data['type'], nr
        )
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[TAG_CUSTOM["id"] if self.data['type'] == "custom"
                         else TAG_AI["id"] if self.data['type'] == "ai"
                         else TAG_WUNSCH["id"]]
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# ==== Lead-Actions-Dropdown (DM) ====
class LeadActionsDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead):
        super().__init__(timeout=None)
        self.add_item(LeadActionsDropdown(cog, data, thread_channel, lead))

class LeadActionsDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel, lead):
        options = [
            discord.SelectOption(label="Status: Offen", value="offen"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Status: Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Status: Fertig", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status, "")

# ==== Cog-Setup ====
async def setup(bot):
    await bot.add_cog(RequestCog(bot))

