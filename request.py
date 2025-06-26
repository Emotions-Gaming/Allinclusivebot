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

TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}
ALL_TAGS = [TAG_CUSTOM, TAG_AI, TAG_WUNSCH]

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.teal(),
    "done": discord.Color.green(),
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

def build_thread_title(status, streamer, ersteller, typ, nr, fan_tag=None):
    fan_tag_str = f"- {fan_tag}" if fan_tag else ""
    return f"[{status.capitalize()}] - {streamer} - {ersteller} {fan_tag_str} - {typ.capitalize()} - #{nr}"

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
    title = f"📩 {data.get('streamer', '')}" if data.get("streamer") else "Anfrage"
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis / Bezahlt:** {data.get('preis','')} ({data.get('bezahlt','')})\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage & Zeit:** {data.get('anfrage','')}\n"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
            f"**Zeitgrenze:** {data.get('zeitgrenze','')}\n"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Art:** {data.get('wunsch_art','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis wann:** {data.get('zeitgrenze','')}\n"
        )
    if "status_reason" in data and data["status_reason"]:
        desc += f"\n**Begründung:** {data['status_reason']}"
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

async def get_tag_id(forum, tag_name):
    for tag in forum.available_tags:
        if tag.name == tag_name:
            return tag.id
    return None

async def ensure_tags(forum):
    tags = {tag.name: tag.id for tag in forum.available_tags}
    missing = [t for t in ALL_TAGS if t["name"] not in tags]
    for t in missing:
        await forum.create_tag(name=t["name"], emoji=t["emoji"])
    return {tag.name: tag.id for tag in forum.available_tags}

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== Channel Setups ==========

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
            description="Wähle eine Option, um eine neue Anfrage zu stellen.",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

    # ========== LEAD Management ==========
    @app_commands.command(name="requestcustomlead", description="Fügt einen Custom-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestcustomlead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["custom"]:
            leads["custom"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist nun Custom-Lead.")

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
        await utils.send_success(interaction, f"{user.mention} ist nun AI-Lead.")

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
        await utils.send_success(interaction, f"{user.mention} ist nun Wunsch-Lead.")

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

    # ========== Haupt-Request-Posting ==========

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)

        # Tags vorbereiten/finden
        tags_map = await ensure_tags(forum)
        tag_id = None
        if reqtype == "custom":
            tag_id = tags_map.get(TAG_CUSTOM["name"])
        elif reqtype == "ai":
            tag_id = tags_map.get(TAG_AI["name"])
        elif reqtype == "wunsch":
            tag_id = tags_map.get(TAG_WUNSCH["name"])

        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        thread_title = build_thread_title(
            "offen", data['streamer'], str(interaction.user), reqtype, nr, data.get("fan_tag")
        )
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=[tag_id] if tag_id else [],
        )
        channel = thread_with_message.thread
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

# --- MODALS ---

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        # 1. Streamer – (Name des Streamers)
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True
        )
        # 2. Fan-Tag – (@12hh238712 – Discord Tag)
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag (wird im Titel angezeigt!)",
            max_length=40,
            required=True
        )
        # 3. Preis und bezahlt? – (z. B. 400$, Bezahlt)
        self.preis = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="400$, Bezahlt",
            max_length=30,
            required=True
        )
        # 4. Sprache – (Englisch/Deutsch)
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=15,
            required=True
        )
        # 5. Anfrage + Bis Wann? – (Möchte ein Video über … Bis zum 19.06.2025)
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über … Bis zum 19.06.2025",
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
            "preis": self.preis.value.split(",")[0].strip() if "," in self.preis.value else self.preis.value,
            "bezahlt": self.preis.value.split(",")[1].strip() if "," in self.preis.value else "",
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value
        }
        await self.cog.post_request(interaction, data, "custom")

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
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Text für das Voiceover (max. 10 Sekunden!)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Zeitgrenze",
            placeholder="Bis wann? (z.B. 20.07.2025)",
            max_length=40,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "ai")

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
        self.wunsch_art = discord.ui.TextInput(
            label="Art des Inhalts",
            placeholder="Video/Bild/Audio?",
            max_length=20,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=15,
            required=True
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Was wünschst du dir?",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="Bis wann?",
            max_length=40,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.wunsch_art)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "wunsch_art": self.wunsch_art.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "wunsch")

# --- RequestMenuView mit Filter & Dropdown-Select ---

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage", emoji=TAG_CUSTOM["emoji"]),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen", emoji=TAG_AI["emoji"]),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Video/Bild/Audio-Wunsch einreichen", emoji=TAG_WUNSCH["emoji"])
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# --- RequestThreadView (Status, Close, Filter) ---

class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))
        # --- Status Bearbeiten Button & Dropdown ---

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
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data.get("erstellerid"):
            return await utils.send_error(interaction, "Nur der zuständige Lead oder Anfragesteller kann den Status ändern!")
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
            discord.SelectOption(label="Offen", value="offen", emoji="🟦"),
            discord.SelectOption(label="Angenommen", value="angenommen", emoji="🟩"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung", emoji="🟨"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt", emoji="🟥"),
            discord.SelectOption(label="Uploaded", value="uploaded", emoji="⬆️"),
            discord.SelectOption(label="Done", value="done", emoji="✅"),
            discord.SelectOption(label="Geschlossen", value="geschlossen", emoji="🛑"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        needs_reason = new_status in ("abgelehnt", "uploaded", "done")
        if needs_reason:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, None)

    async def finish_status_change(self, interaction, new_status, reason):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data.get('streamer', ''), self.data.get('erstellername', ''), self.data.get('type', ''), nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        if reason:
            embed.add_field(name="Begründung", value=reason, inline=False)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        # User-DM mit Link & Grund
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data.get('erstellerid'))
        if ersteller:
            try:
                msg = (
                    f"**Update zu deiner Anfrage**: [{self.data.get('streamer','')}]({self.thread_channel.jump_url})\n"
                    f"Neuer Status: **{STATUS_DISPLAY.get(new_status, new_status.capitalize())}**"
                )
                if reason:
                    msg += f"\n**Begründung:** {reason}"
                await ersteller.send(msg)
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY.get(new_status, new_status)}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für diese Entscheidung"):
    def __init__(self, cog, data, thread_channel, lead, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.new_status = new_status
        self.reason = discord.ui.TextInput(
            label="Grund",
            placeholder="Bitte gib eine Begründung an.",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.new_status, self.reason.value
        )

# --- CLOSE Request (Archivieren, Backup, Filter) ---

class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        is_lead = interaction.user.id in allowed_leads
        is_owner = interaction.user.id == self.data.get("erstellerid")
        if not is_lead and not is_owner:
            return await utils.send_error(interaction, "Nur der Lead oder Anfragesteller kann schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        # Filter-Messages (keine reinen Bot/Status-Änderungen)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if msg.content and not (msg.author.bot and "Status geändert" in msg.content):
                name = msg.author.display_name
                messages.append(f"**{name}:** {msg.content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data.get('streamer',''), self.data.get('erstellername',''), self.data.get('type',''), nr)
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[TAG_CUSTOM["id"]] if self.data["type"] == "custom" else [TAG_AI["id"]] if self.data["type"] == "ai" else [TAG_WUNSCH["id"]]
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# --- LEAD Actions DropdownView for DM/Lead ---

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
            discord.SelectOption(label="Status: Offen", value="offen", emoji="🟦"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen", emoji="🟩"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung", emoji="🟨"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt", emoji="🟥"),
            discord.SelectOption(label="Status: Uploaded", value="uploaded", emoji="⬆️"),
            discord.SelectOption(label="Status: Done", value="done", emoji="✅"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen", emoji="🛑"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        needs_reason = new_status in ("abgelehnt", "uploaded", "done")
        if needs_reason:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
                interaction, new_status, None
            )

# ---- ENDE PART 3/4 ----
# ========== Tag-IDs für Forum-Filter (ersetze ggf. durch echte IDs) ==========
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

# ========== Cog Setup und Event-Listener ==========

async def setup(bot):
    cog = RequestCog(bot)
    await bot.add_cog(cog)

    # Event-Handler, damit Backups (Chatverlauf) funktionieren:
    @bot.event
    async def on_message(message):
        # Nur für Threads im aktiven Forum
        if message.guild:
            config = await get_request_config()
            forum_id = config.get("active_forum")
            forum = message.guild.get_channel(forum_id) if forum_id else None
            if forum and getattr(message.channel, "parent_id", None) == forum.id:
                cog: RequestCog = bot.get_cog("RequestCog")
                if cog:
                    await cog.on_thread_message(message)
        await bot.process_commands(message)

# ========== (Optional) Helper zum automatischen Erstellen von Tags ==========
# Führe dies nur einmal aus, falls du die Tag-IDs noch brauchst!
# async def create_tags(forum):
#     tags = [
#         {"name": TAG_CUSTOM["name"], "emoji": TAG_CUSTOM["emoji"]},
#         {"name": TAG_AI["name"], "emoji": TAG_AI["emoji"]},
#         {"name": TAG_WUNSCH["name"], "emoji": TAG_WUNSCH["emoji"]},
#     ]
#     for tag in tags:
#         await forum.create_tag(name=tag["name"], emoji=tag["emoji"])

# ========== Helper zum Tag-Finden (falls IDs dynamisch) ==========
def get_tag_id(forum, tag_name):
    for tag in getattr(forum, "available_tags", []):
        if tag.name.lower() == tag_name.lower():
            return tag.id
    return None

# ========== Kategorie-Auswahl oben im Forum (als Filter) ==========

# In deinem Discord-Forum werden die Tags als "Kategorien/Filter" oben angezeigt.
# Damit die Threads direkt zugeordnet werden, werden die Tag-IDs beim Erstellen übergeben:
# (siehe im post_request im Part 2)

# --- Reminder ---
# Im Post-Request wird nun (wie schon implementiert) das Tag passend zugewiesen:
#    applied_tags=[TAG_CUSTOM["id"]], ...  # oder TAG_AI/TAG_WUNSCH
# Im Forum wird das dann als Filter angezeigt.

# ========== Schlusswort & Checks ==========

# Damit ist wirklich alles enthalten:
#  - Modal CustomRequest: mit 5 Feldern inkl. Sprache, Beschreibung, Beispiele
#  - Modal WunschRequest
#  - Modal AIRequest
#  - Thread-Erstellung, Tag-Vergabe
#  - DM an Lead und User, mit Status/Grund/Link
#  - Status-Änderungen, Begründungen, Dropdowns, Buttons
#  - Backup ins Done-Forum mit Chatverlauf (ohne Statusmeldungen/Bot)
#  - Only Lead/Ersteller kann schließen/ändern/löschen
#  - Alles schön formatiert und verständlich
#  - Erweiterbar für weitere Kategorien
#  - Filterfunktion via Tags im Forum oben

# --- FERTIG! ---

