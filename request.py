import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

# ========== Forum-Tags ==========
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
REQUEST_LEADS_PATH = os.path.join("persistent_data", "request_leads.json")
MAX_TITLE_LEN = 80
MAX_BODY_LEN = 500
MAX_COMMENT_LEN = 200

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "geschlossen": discord.Color.dark_grey(),
    "uploaded": discord.Color.teal(),
    "done": discord.Color.brand_green(),
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "geschlossen": "🛑 Geschlossen",
    "uploaded": "📤 Hochgeladen",
    "done": "✅ Fertig"
}

def build_thread_title(status, streamer, ersteller, typ, nr, fan_tag=None):
    fan = f"{fan_tag} - " if fan_tag else ""
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {fan}{typ.capitalize()} - #{nr}"

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
    desc = data.get("desc", "")
    if data["type"] == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis und Bezahlt?:** {data.get('preis', '')}\n"
            f"**Sprache:** {data.get('sprache', '')}\n"
            f"**Anfrage + Bis Wann?:** {data.get('anfrage', '')}\n"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Content-Typ:** {data.get('content_typ', '')}\n"
            f"**Sprache:** {data.get('sprache', '')}\n"
            f"**Anfrage:** {data.get('anfrage', '')}\n"
            f"**Bis Wann?:** {data.get('zeitgrenze', '')}\n"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status, status.capitalize())}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}

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
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # Tag-Id zuweisen
        if reqtype == "custom":
            tag_id = TAG_CUSTOM["id"]
            fan_tag = data.get("fan_tag")
        elif reqtype == "ai":
            tag_id = TAG_AI["id"]
            fan_tag = None
        elif reqtype == "wunsch":
            tag_id = TAG_WUNSCH["id"]
            fan_tag = None
        else:
            tag_id = None
            fan_tag = None

        applied_tags = [tag_id] if tag_id else []
        thread_title = build_thread_title("offen", data['streamer'], str(interaction.user), reqtype, nr, fan_tag=fan_tag)
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

    # ... Restliche Methoden: send_lead_dm, on_thread_message etc. ...
    # (Setze hier mit allen Buttons, Modals, Dropdowns und Lead-Actions fort.)
    # ======= RequestMenuView & Dropdown =======
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
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen"),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Wunsch-Content (Bild, Video, etc.) anfragen"),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# ======= Custom Modal mit Hilfetexten =======
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True,
        )
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag, mit @",
            max_length=50,
            required=True,
        )
        self.preis = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=40,
            required=True,
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=20,
            required=True,
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über … Bis zum 19.06.2025",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True,
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
        }
        await self.cog.post_request(interaction, data, "custom")
        # Kein Dropdown reset mehr nötig, Modal schließt automatisch

# ======= AI Modal =======
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True,
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Wunschtext für das Voiceover (max. 10 Sekunden)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True,
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Zeitgrenze",
            placeholder="Bis wann (z. B. bis Sonntag)",
            max_length=40,
            required=True,
        )
        self.add_item(self.streamer)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "ai")

# ======= Wunsch Modal =======
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True,
        )
        self.content_typ = discord.ui.TextInput(
            label="Video/Bild/Audio?",
            placeholder="Bitte Content-Typ angeben.",
            max_length=20,
            required=True,
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=20,
            required=True,
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Was wünschst du dir?",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True,
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Deadline (z. B. bis 19.06.2025)",
            max_length=40,
            required=True,
        )
        self.add_item(self.streamer)
        self.add_item(self.content_typ)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "content_typ": self.content_typ.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")
        # ---- Tag-IDs für die Thread-Filter ----
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

# ---- Filter-Tag-Logik für Typen ----
def get_tag_for_type(typ):
    if typ == "custom":
        return TAG_CUSTOM["id"]
    elif typ == "ai":
        return TAG_AI["id"]
    elif typ == "wunsch":
        return TAG_WUNSCH["id"]
    return None

# ---- Bearbeitungsrechte: Nur Lead oder Ersteller darf schließen ----
def user_is_lead_or_owner(user, data, leads):
    if user.id == data["erstellerid"]:
        return True
    reqtype = data.get("type")
    allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads.get("wunsch", [])
    return user.id in allowed_leads

# ---- Haupt-Request-Posting (Tag-Vergabe, Filter) ----
async def post_request(self, interaction, data, reqtype):
    config = await get_request_config()
    forum_id = config.get("active_forum")
    if not forum_id:
        return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
    forum = interaction.guild.get_channel(forum_id)

    all_threads = forum.threads
    nr = len(all_threads) + 1
    data["nr"] = nr

    tag_id = get_tag_for_type(reqtype)
    thread_title = build_thread_title("offen", data.get('streamer', ""), str(interaction.user), reqtype, nr)
    applied_tags = [tag_id] if tag_id else []
    # Hier die Tag-Vergabe (als int!)
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

# ---- View mit Status-Button & Close-Button ----
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
        if not user_is_lead_or_owner(interaction.user, self.data, leads):
            return await utils.send_error(interaction, "Nur Lead oder Ersteller darf den Status bearbeiten!")
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
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
            discord.SelectOption(label="Uploaded", value="uploaded"),
            discord.SelectOption(label="Done", value="done"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, "")

    async def finish_status_change(self, interaction, new_status, reason):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data.get('streamer', ""), self.data.get('erstellername', ""), self.data.get('type', ""), nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        if reason:
            embed.add_field(name="Begründung", value=reason, inline=False)
        await self.thread_channel.send(
            embed=embed
        )
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                msg = (
                    f"Deine Anfrage **{self.data.get('streamer', '')}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Zur Anfrage]({self.thread_channel.jump_url})"
                )
                if reason:
                    msg += f"\n**Begründung:** {reason}"
                await ersteller.send(msg)
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Begründung angeben"):
    def __init__(self, cog, data, thread_channel, lead, status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.status = status
        self.reason = discord.ui.TextInput(
            label="Grund/Begründung",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.status, self.reason.value
        )

# ---- CLOSE Request Button, nur Lead/Ersteller ----
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        if not user_is_lead_or_owner(interaction.user, self.data, leads):
            return await utils.send_error(interaction, "Nur Lead oder Ersteller kann schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        tag_id = get_tag_for_type(self.data.get('type', ''))
        applied_tags = [tag_id] if tag_id else []
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if msg.author.bot and "Status geändert" in msg.content:
                continue
            name = msg.author.display_name
            content = msg.content
            if content.strip() == "":
                continue
            messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data.get('streamer', ""), self.data.get('erstellername', ""), self.data.get('type', ""), nr)
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

# ====== Fortsetzung: Lead DM Dropdown, Backup und Setup folgt im nächsten Post! ======
# ==== Lead-Dropdown für Status aus DM (inkl. Reason Modal für bestimmte Status) ====

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
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen"),
            discord.SelectOption(label="Status: Uploaded", value="uploaded"),
            discord.SelectOption(label="Status: Done", value="done"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status, "")

# ==== CustomRequestModal – jetzt exakt nach deinen Vorgaben ====

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=80,
            required=True
        )
        self.fantag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag",
            max_length=32,
            required=True
        )
        self.preis_bezahlt = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=30,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=16,
            required=True
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über … Bis zum 19.06.2025",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.fantag)
        self.add_item(self.preis_bezahlt)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fantag": self.fantag.value,
            "preis": self.preis_bezahlt.value,
            "bezahlt": "Ja" if "ja" in self.preis_bezahlt.value.lower() or "bezahlt" in self.preis_bezahlt.value.lower() else "Nein",
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.anfrage.value.split("Bis zum")[-1].strip() if "Bis zum" in self.anfrage.value else "",
        }
        await self.cog.post_request(interaction, data, "custom")

# ==== AIRequestModal & WunschRequestModal – jeweils mit passenden Feldern ====

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=80,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=16,
            required=True
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Gewünschter AI Voice Text (max 10 Sekunden!)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="z. B. 19.06.2025",
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

class WunschRequestModal(discord.ui.Modal, title="Content Wunsch"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=80,
            required=True
        )
        self.contenttype = discord.ui.TextInput(
            label="Video/Bild/Audio?",
            placeholder="Bitte angeben!",
            max_length=30,
            required=True
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=16,
            required=True
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Was wird gewünscht?",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="z. B. 19.06.2025",
            max_length=40,
            required=True
        )
        self.add_item(self.streamer)
        self.add_item(self.contenttype)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "contenttype": self.contenttype.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ==== RequestMenuView & Dropdown – mit Reset (Disable nach Auswahl) ====

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
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen"),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Wünsche zu Video/Bild/Audio"),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))
        # Dropdown resetten
        self.disabled = True
        await interaction.message.edit(view=RequestMenuView(self.cog))

# ==== Alle Lead-Management-Befehle für custom, ai, wunsch ====

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
    if "wunsch" not in leads:
        leads["wunsch"] = []
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
    if "wunsch" in leads and user.id in leads["wunsch"]:
        leads["wunsch"].remove(user.id)
        await save_leads(leads)
    await utils.send_success(interaction, f"{user.mention} wurde als Wunsch-Lead entfernt.")

# ==== Setup ====
async def setup(bot):
    await bot.add_cog(RequestCog(bot))

# ==== Ende ====

