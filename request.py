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

# ---- Tag-IDs wie von dir ----
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}
TAG_SCRIPT = {"name": "Script", "emoji": "📜", "id": 1387921808224682147}

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.blue(),
    "done": discord.Color.teal()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "📤 Hochgeladen",
    "done": "✅ Fertig"
}

def build_thread_title(status, streamer, ersteller, customerid, typ, nr, scriptname=None):
    if typ == "custom":
        return f"[{status.capitalize()}] - {streamer} - {ersteller} - {customerid} - {TAG_CUSTOM['name']} - #{nr}"
    elif typ == "script":
        return f"[{status.capitalize()}] - {streamer} - {ersteller} - {scriptname} - {TAG_SCRIPT['name']} - #{nr}"
    elif typ == "ai":
        return f"[{status.capitalize()}] - {streamer} - {ersteller} - {TAG_AI['name']} - #{nr}"
    elif typ == "wunsch":
        return f"[{status.capitalize()}] - {streamer} - {ersteller} - {TAG_WUNSCH['name']} - #{nr}"
    else:
        return f"[{status.capitalize()}] - {streamer} - {ersteller} - {typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": [], "script": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data['streamer']}" if data.get("streamer") else "Anfrage"
    tagline = f"**Fan-Tag:** {data['fan_tag']}" if data.get("fan_tag") else ""
    sprache = f"**Sprache:** {data.get('sprache','')}" if data.get("sprache") else ""
    desc = data.get("desc", "")

    if data["type"] == "custom":
        desc = (
            f"{tagline}\n"
            f"**Preis und bezahlt?** {data['preis_bezahlt']}\n"
            f"{sprache}\n"
            f"**Anfrage + Bis Wann?** {data['anfrage_bis']}"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Sprache:** {data['sprache']}\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Bis wann:** {data['zeitgrenze']}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Typ:** {data['media_typ']}\n"
            f"**Sprache:** {data['sprache']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Bis wann:** {data['zeitgrenze']}"
        )
    elif data["type"] == "script":
        desc = (
            f"**Scriptname:** {data['scriptname']}\n"
            f"**Sprache:** {data['sprache']}\n"
            f"**Script-Wünsche:** {data['wünsche']}\n"
            f"**Bis wann:** {data['anfrage_bis']}"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

# ========== MODALS ==========

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.fan_tag = discord.ui.TextInput(label="Fan-Tag", max_length=32)
        self.preis_bezahlt = discord.ui.TextInput(label="Preis und bezahlt?", max_length=40)
        self.sprache = discord.ui.TextInput(label="Sprache", max_length=20)
        self.anfrage_bis = discord.ui.TextInput(label="Anfrage + Bis Wann?", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
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

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.sprache = discord.ui.TextInput(label="Sprache", max_length=20)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
        self.zeitgrenze = discord.ui.TextInput(label="Bis wann?", max_length=40)
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

class WunschRequestModal(discord.ui.Modal, title="Content Wunsch Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.media_typ = discord.ui.TextInput(label="Typ", max_length=20)
        self.sprache = discord.ui.TextInput(label="Sprache", max_length=20)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
        self.zeitgrenze = discord.ui.TextInput(label="Bis wann?", max_length=40)
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

class ScriptRequestModal(discord.ui.Modal, title="Sequence Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.scriptname = discord.ui.TextInput(
            label="Scriptname",
            placeholder="Name des Scripts",
            max_length=40
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch, Deutsch oder Both",
            max_length=20
        )
        self.wünsche = discord.ui.TextInput(
            label="Script-Wünsche",
            placeholder="Tageszeiten, Videos, Richtung etc.",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.anfrage_bis = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.scriptname)
        self.add_item(self.sprache)
        self.add_item(self.wünsche)
        self.add_item(self.anfrage_bis)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "scriptname": self.scriptname.value,
            "sprache": self.sprache.value,
            "wünsche": self.wünsche.value,
            "anfrage_bis": self.anfrage_bis.value,
        }
        await self.cog.post_request(interaction, data, "script")

# ==== Anfrage-Menü mit Script-Option ====
class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(self.cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        options = [
            discord.SelectOption(
                label="Custom Anfrage", value="custom", emoji=TAG_CUSTOM["emoji"], description="Individuelle Anfrage erstellen"
            ),
            discord.SelectOption(
                label="AI Voice Anfrage", value="ai", emoji=TAG_AI["emoji"], description="AI Voice Over nur für Mila & Xenia!"
            ),
            discord.SelectOption(
                label="Content Wunsch", value="wunsch", emoji=TAG_WUNSCH["emoji"], description="Content (Bild/Video/Audio) Wunsch"
            ),
            discord.SelectOption(
                label="Sequence Anfrage", value="script", emoji=TAG_SCRIPT["emoji"], description="Sequence-Anfrage erstellen"
            )
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
        elif value == "script":
            await interaction.response.send_modal(ScriptRequestModal(self.cog))

# ----------- ENDE TEIL 1 -----------
# ==== Haupt-Cog und Commands ====

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

    # ==== Lead-Management (inkl. Script) ====
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

    @app_commands.command(name="requestscriptlead", description="Fügt einen Script-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestscriptlead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["script"]:
            leads["script"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist jetzt Script-Lead.")

    @app_commands.command(name="requestscriptremovelead", description="Entfernt einen Script-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestscriptremovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["script"]:
            leads["script"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als Script-Lead entfernt.")

    # ======= Haupt-Request-Posting (inkl. Script-Typ & Titelstruktur) =======
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # ---- Tag-Objekt holen und Titel bauen ----
        if reqtype == "custom":
            tag_obj = discord.utils.get(forum.available_tags, id=int(TAG_CUSTOM["id"]))
            applied_tags = [tag_obj] if tag_obj else []
            tag_text = TAG_CUSTOM["name"]
            title = build_thread_title("offen", data['streamer'], str(interaction.user), data['fan_tag'], reqtype, nr)
        elif reqtype == "ai":
            tag_obj = discord.utils.get(forum.available_tags, id=int(TAG_AI["id"]))
            applied_tags = [tag_obj] if tag_obj else []
            tag_text = TAG_AI["name"]
            title = build_thread_title("offen", data['streamer'], str(interaction.user), None, reqtype, nr)
        elif reqtype == "wunsch":
            tag_obj = discord.utils.get(forum.available_tags, id=int(TAG_WUNSCH["id"]))
            applied_tags = [tag_obj] if tag_obj else []
            tag_text = TAG_WUNSCH["name"]
            title = build_thread_title("offen", data['streamer'], str(interaction.user), None, reqtype, nr)
        elif reqtype == "script":
            tag_obj = discord.utils.get(forum.available_tags, id=int(TAG_SCRIPT["id"]))
            applied_tags = [tag_obj] if tag_obj else []
            tag_text = TAG_SCRIPT["name"]
            title = build_thread_title("offen", data['streamer'], str(interaction.user), None, reqtype, nr, scriptname=data['scriptname'])
        else:
            tag_obj = None
            applied_tags = []
            tag_text = reqtype.capitalize()
            title = build_thread_title("offen", data['streamer'], str(interaction.user), None, reqtype, nr)

        thread_with_message = await forum.create_thread(
            name=title,
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
        if interaction.message:
            try:
                view = RequestMenuView(self)
                await interaction.message.edit(view=view)
            except Exception:
                pass

    # ==== DM an Lead (wie gehabt, mit Script-Feld) ====
    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        if reqtype == "custom":
            ids = leads["custom"]
        elif reqtype == "ai":
            ids = leads["ai"]
        elif reqtype == "wunsch":
            ids = leads["wunsch"]
        elif reqtype == "script":
            ids = leads["script"]
        else:
            ids = []
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
                    elif reqtype == "script":
                        msg += (
                            f"**Scriptname:** {data['scriptname']}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Wünsche:** {data['wünsche']}\n"
                            f"**Bis wann:** {data['anfrage_bis']}\n"
                        )
                    else:
                        msg += (
                            f"**Typ:** {data.get('media_typ','')}\n"
                            f"**Sprache:** {data['sprache']}\n"
                            f"**Anfrage:** {data.get('anfrage','')}\n"
                            f"**Bis wann:** {data.get('zeitgrenze','')}\n"
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

# ----------- ENDE TEIL 2 -----------
# ==== Anfrage-Menü mit Script-Option ====

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(self.cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        options = [
            discord.SelectOption(
                label="Custom Anfrage",
                value="custom",
                emoji=TAG_CUSTOM["emoji"],
                description="Eigene Wunsch-Anfrage (Voice/Video/sonstiges)"
            ),
            discord.SelectOption(
                label="AI Voice Anfrage",
                value="ai",
                emoji=TAG_AI["emoji"],
                description="AI Voice Over nur für Mila & Xenia!"
            ),
            discord.SelectOption(
                label="Content Wunsch",
                value="wunsch",
                emoji=TAG_WUNSCH["emoji"],
                description="Content (Bild/Video/Audio) Wunsch"
            ),
            discord.SelectOption(
                label="Sequence Anfrage",
                value="script",
                emoji=TAG_SCRIPT["emoji"],
                description="Script-Anfrage für Voice/Video"
            )
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
        elif value == "script":
            await interaction.response.send_modal(ScriptRequestModal(self.cog))

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
            label="Fan-Tag (Kunden-ID)",
            placeholder="Fan-ID, Twitch/Discord-Name oder ähnliches",
            max_length=40
        )
        self.preis_bezahlt = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 20€ / bezahlt? (Ja/Nein)",
            max_length=30
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Deutsch/Englisch",
            max_length=20
        )
        self.anfrage_bis = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Was genau, Frist (z. B. bis 19.06.2025)",
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

# ==== AI Voice Modal ====
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
            placeholder="Deutsch, Englisch oder Both",
            max_length=20
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Was soll gesagt werden? (max. 10 Sekunden)",
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Frist (z. B. bis 19.06.2025)",
            max_length=40
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

# ==== Wunsch Modal ====
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch erstellen"):
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
            placeholder="Bild/Video/Audio",
            max_length=30
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Deutsch, Englisch oder Both",
            max_length=20
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Was soll gemacht werden?",
            max_length=MAX_BODY_LEN
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis wann?",
            placeholder="Frist (z. B. bis 19.06.2025)",
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
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")

# ==== Script Modal ====
class ScriptRequestModal(discord.ui.Modal, title="Sequence Anfrage erstellen"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN
        )
        self.scriptname = discord.ui.TextInput(
            label="Scriptname",
            placeholder="Name des Scripts",
            max_length=40
        )
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch, Deutsch oder Both",
            max_length=20
        )
        self.wünsche = discord.ui.TextInput(
            label="Script-Wünsche",
            placeholder="Tageszeiten, Videos, Richtung etc.",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN
        )
        self.anfrage_bis = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="Bis zum 19.06.2025",
            max_length=40
        )
        self.add_item(self.streamer)
        self.add_item(self.scriptname)
        self.add_item(self.sprache)
        self.add_item(self.wünsche)
        self.add_item(self.anfrage_bis)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "scriptname": self.scriptname.value,
            "sprache": self.sprache.value,
            "wünsche": self.wünsche.value,
            "anfrage_bis": self.anfrage_bis.value,
        }
        await self.cog.post_request(interaction, data, "script")

# ==== Thread-View mit Status- und Close-Button ====
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# ==== Status Bearbeiten Button (Admins & Leads!) ====
class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="✏️")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = []
        if reqtype in leads:
            allowed_leads = leads[reqtype]
        if interaction.user.id not in allowed_leads and not utils.is_admin(interaction.user):
            return await utils.send_error(interaction, "Nur der zuständige Lead oder Admin kann den Status ändern!")
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
        typ = self.data['type']
        if typ == "custom":
            new_title = build_thread_title(
                new_status, self.data['streamer'], self.data['erstellername'], self.data['fan_tag'], typ, nr
            )
        elif typ == "script":
            new_title = build_thread_title(
                new_status, self.data['streamer'], self.data['erstellername'], None, typ, nr, scriptname=self.data['scriptname']
            )
        else:
            new_title = build_thread_title(
                new_status, self.data['streamer'], self.data['erstellername'], None, typ, nr
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

# ==== Anfrage schließen Button (Admins & Lead & Ersteller!) ====
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads[reqtype] if reqtype in leads else []
        if interaction.user.id not in allowed_leads and not utils.is_admin(interaction.user) and interaction.user.id != self.data["erstellerid"]:
            return await utils.send_error(interaction, "Nur der zuständige Lead, Admin oder Anfragesteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)

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

        typ = self.data['type']
        if typ == "custom":
            new_title = build_thread_title(self.data.get('status', 'done'), self.data['streamer'], self.data['erstellername'], self.data['fan_tag'], typ, nr)
            tag_obj = discord.utils.get(done_forum.available_tags, id=int(TAG_CUSTOM["id"]))
        elif typ == "script":
            new_title = build_thread_title(self.data.get('status', 'done'), self.data['streamer'], self.data['erstellername'], None, typ, nr, scriptname=self.data['scriptname'])
            tag_obj = discord.utils.get(done_forum.available_tags, id=int(TAG_SCRIPT["id"]))
        elif typ == "ai":
            new_title = build_thread_title(self.data.get('status', 'done'), self.data['streamer'], self.data['erstellername'], None, typ, nr)
            tag_obj = discord.utils.get(done_forum.available_tags, id=int(TAG_AI["id"]))
        elif typ == "wunsch":
            new_title = build_thread_title(self.data.get('status', 'done'), self.data['streamer'], self.data['erstellername'], None, typ, nr)
            tag_obj = discord.utils.get(done_forum.available_tags, id=int(TAG_WUNSCH["id"]))
        else:
            new_title = build_thread_title(self.data.get('status', 'done'), self.data['streamer'], self.data['erstellername'], None, typ, nr)
            tag_obj = None

        applied_tags = [tag_obj] if tag_obj else []
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=applied_tags
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'done'))
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
            discord.SelectOption(label="Status: Fertig", value="done")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id and not utils.is_admin(interaction.user):
            return await interaction.response.send_message("Nur du als Lead oder Admin kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        if new_status in ("abgelehnt", "uploaded", "done"):
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status, "")

# ==== Cog Setup ====
async def setup(bot):
    await bot.add_cog(RequestCog(bot))

# ENDE SCRIPT


