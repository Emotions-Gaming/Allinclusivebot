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

# Deine Tags
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

# Im post_request oder wo du Thread erstellst:
if reqtype == "custom":
    tag_id = TAG_CUSTOM["id"]
elif reqtype == "ai":
    tag_id = TAG_AI["id"]
elif reqtype == "wunsch":
    tag_id = TAG_WUNSCH["id"]
else:
    tag_id = None

applied_tags = [tag_id] if tag_id else []

# Und dann so:
thread_with_message = await forum.create_thread(
    name=thread_title,
    content="Neue Anfrage erstellt.",
    applied_tags=applied_tags,
)



STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.purple(),
    "done": discord.Color.dark_green(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "🟪 Hochgeladen",
    "done": "✅ Fertig",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, ersteller, fan_tag, typ, nr):
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {fan_tag} - {typ.capitalize()} - #{nr}"

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
            f"**Fan-Tag:** {data.get('fan_tag', '-')}\n"
            f"**Preis & bezahlt?:** {data.get('preis_bezahlt', '-')}\n"
            f"**Sprache:** {data.get('sprache', '-')}\n"
            f"**Anfrage + Bis Wann?:** {data.get('anfrage', '-')}\n"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Sprache:** {data.get('sprache', '-')}\n"
            f"**Audio Wunsch:** {data.get('audiowunsch', '-')}\n"
            f"**Bis Wann?:** {data.get('zeitgrenze', '-')}\n"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Video/Bild/Audio?:** {data.get('wunsch_typ', '-')}\n"
            f"**Sprache:** {data.get('sprache', '-')}\n"
            f"**Anfrage + Bis Wann?:** {data.get('anfrage', '-')}\n"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

# -- Weiter mit RequestCog, den Views und den Modals --
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

    # ========== Haupt-Request-Posting (mit Tag) ==========
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # Tag-Logik
        if reqtype == "custom":
            tag_id = str(TAG_CUSTOM["id"])
        elif reqtype == "ai":
            tag_id = str(TAG_AI["id"])
        elif reqtype == "wunsch":
            tag_id = str(TAG_WUNSCH["id"])
        else:
            tag_id = None

        thread_title = build_thread_title("offen", data['streamer'], str(interaction.user),
                                         data.get('fan_tag', "-"), reqtype, nr)
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
        self.chat_backups[channel.id] = []
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        if reqtype == "custom":
            ids = leads["custom"]
        elif reqtype == "ai":
            ids = leads["ai"]
        elif reqtype == "wunsch":
            ids = leads["wunsch"]
        else:
            ids = []
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{reqtype.capitalize()} Anfrage** von {interaction.user.mention}:\n"
                        f"**Streamer:** {data['streamer']}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Fan-Tag:** {data.get('fan_tag','-')}\n"
                            f"**Preis & bezahlt?:** {data.get('preis_bezahlt','-')}\n"
                            f"**Sprache:** {data.get('sprache','-')}\n"
                            f"**Anfrage + Bis Wann?:** {data.get('anfrage','-')}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Sprache:** {data.get('sprache','-')}\n"
                            f"**Audio Wunsch:** {data.get('audiowunsch','-')}\n"
                            f"**Bis Wann?:** {data.get('zeitgrenze','-')}\n"
                        )
                    elif reqtype == "wunsch":
                        msg += (
                            f"**Typ:** {data.get('wunsch_typ','-')}\n"
                            f"**Sprache:** {data.get('sprache','-')}\n"
                            f"**Anfrage + Bis Wann?:** {data.get('anfrage','-')}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

# ==== Views, Dropdowns, Modal-Classes etc. folgen in Part 3/3! ====
# ==== FILTER-TAGS als globale Konstanten ====
# Deine Tags
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

# Im post_request oder wo du Thread erstellst:
if reqtype == "custom":
    tag_id = TAG_CUSTOM["id"]
elif reqtype == "ai":
    tag_id = TAG_AI["id"]
elif reqtype == "wunsch":
    tag_id = TAG_WUNSCH["id"]
else:
    tag_id = None

applied_tags = [tag_id] if tag_id else []

# Und dann so:
thread_with_message = await forum.create_thread(
    name=thread_title,
    content="Neue Anfrage erstellt.",
    applied_tags=applied_tags,
)


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
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage", emoji=TAG_CUSTOM["emoji"]),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen", emoji=TAG_AI["emoji"]),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Wünsche (Video/Bild/Audio)", emoji=TAG_WUNSCH["emoji"])
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

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
            placeholder="@12hh238712 (Discord Tag, so wie angezeigt!)",
            max_length=40,
            required=True,
        )
        self.preis_bezahlt = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=40,
            required=True,
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=25,
            required=True,
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            style=discord.TextStyle.paragraph,
            placeholder="Möchte ein Video über ... Bis zum 19.06.2025",
            max_length=MAX_BODY_LEN,
            required=True,
        )
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis_bezahlt)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis_bezahlt": self.preis_bezahlt.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
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
            required=True,
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=25,
            required=True,
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            style=discord.TextStyle.paragraph,
            placeholder="Text (max. 10 Sekunden) für AI Voice Over",
            max_length=MAX_BODY_LEN,
            required=True,
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="z. B. bis Sonntag",
            max_length=40,
            required=True,
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
            max_length=MAX_TITLE_LEN,
            required=True,
        )
        self.wunsch_typ = discord.ui.TextInput(
            label="Typ (Video/Bild/Audio?)",
            placeholder="Was wünschst du dir?",
            max_length=20,
            required=True,
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=25,
            required=True,
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            style=discord.TextStyle.paragraph,
            placeholder="Beschreibung deines Wunschs und Deadline",
            max_length=MAX_BODY_LEN,
            required=True,
        )
        self.add_item(self.streamer)
        self.add_item(self.wunsch_typ)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "wunsch_typ": self.wunsch_typ.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ---- RequestThreadView, StatusEditButton, StatusDropdownView, StatusDropdown, CloseRequestButton ----
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
        # Nur Lead oder Anfragesteller
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur der zuständige Lead oder der Ersteller kann den Status ändern!")
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
            discord.SelectOption(label="Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        reason_needed = new_status in ["abgelehnt", "uploaded", "done"]
        if reason_needed:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status)

    async def finish_status_change(self, interaction, new_status, reason_text=None):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data['streamer'], self.data.get("fan_tag", "-"), self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        if reason_text:
            embed.add_field(name="Grund", value=reason_text, inline=False)
        await self.thread_channel.send(
            embed=embed
        )
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            msg = f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY.get(new_status, new_status)}**!\n"
            msg += f"Hier geht's direkt zum Post: {self.thread_channel.jump_url}"
            if reason_text:
                msg += f"\n**Grund:** {reason_text}"
            try:
                await ersteller.send(msg)
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY.get(new_status, new_status)}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für die Statusänderung"):
    def __init__(self, cog, data, thread_channel, lead, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.new_status = new_status
        self.grund = discord.ui.TextInput(
            label="Grund",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.grund)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.new_status, self.grund.value
        )

class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data["type"]
        allowed_leads = leads.get(reqtype, [])
        # Nur Lead oder Anfragesteller darf schließen
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur der zuständige Lead oder der Ersteller kann schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if not msg.author.bot and msg.content.strip():
                name = msg.author.display_name
                content = msg.content
                messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(
            self.data.get('status', 'geschlossen'),
            self.data['streamer'],
            self.data.get("fan_tag", "-"),
            self.data['type'],
            nr
        )
        tag = (
            TAG_CUSTOM["id"] if self.data['type'] == "custom"
            else TAG_AI["id"] if self.data['type'] == "ai"
            else TAG_WUNSCH["id"] if self.data['type'] == "wunsch"
            else None
        )
        applied_tags = [tag] if tag is not None else []

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
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        reason_needed = new_status in ["abgelehnt", "uploaded", "done"]
        if reason_needed:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status)

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
