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

TAG_CUSTOM = {"name": "Custom", "emoji": "📝"}
TAG_AI = {"name": "AI Voice", "emoji": "🤖"}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "✨"}

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

def build_thread_title(status, streamer, ersteller, typ, nr, fan_tag=""):
    tag = f"- {fan_tag}" if fan_tag else ""
    return f"[{status.capitalize()}] - {streamer} - {ersteller} {tag} - {typ.capitalize()} - #{nr}"

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
    title = f"📩 {data.get('streamer','')}"
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis / Bezahlt?:** {data.get('preis','')} / {data.get('bezahlt','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
            f"**Bis Wann?:** {data.get('zeitgrenze','')}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Medium:** {data.get('medium','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann?:** {data.get('zeitgrenze','')}"
        )
    if data.get("status_reason"):
        desc += f"\n\n**Begründung:** {data['status_reason']}"
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status,'Unbekannt')}",
        color=color
    )
    embed.set_footer(text=f"Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}

    # Channel Setups
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

    # LEAD Management
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

    # ======= Haupt-Request-Posting + Helper Views, siehe unten! =======

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr
        # Thread Tag setzen
        applied_tags = []
        if reqtype == "custom":
            tag = discord.utils.get(forum.available_tags, name=TAG_CUSTOM["name"])
            if tag: applied_tags.append(tag.id)
        elif reqtype == "ai":
            tag = discord.utils.get(forum.available_tags, name=TAG_AI["name"])
            if tag: applied_tags.append(tag.id)
        elif reqtype == "wunsch":
            tag = discord.utils.get(forum.available_tags, name=TAG_WUNSCH["name"])
            if tag: applied_tags.append(tag.id)
        fan_tag = data.get('fan_tag', '')
        thread_title = build_thread_title("offen", data.get('streamer',''), str(interaction.user), reqtype, nr, fan_tag)
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
        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
        self.chat_backups[channel.id] = []
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        key = reqtype
        ids = leads.get(key, [])
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{reqtype.capitalize()}** Anfrage von {interaction.user.mention}:\n"
                        f"**Streamer:** {data.get('streamer')}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
                            f"**Preis / Bezahlt?:** {data.get('preis','')} / {data.get('bezahlt','')}\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Anfrage:** {data.get('anfrage','')}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
                            f"**Bis Wann?:** {data.get('zeitgrenze','')}\n"
                        )
                    elif reqtype == "wunsch":
                        msg += (
                            f"**Medium:** {data.get('medium','')}\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Anfrage:** {data.get('anfrage','')}\n"
                            f"**Bis Wann?:** {data.get('zeitgrenze','')}\n"
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

# ==== RequestMenuView, Dropdown, Modals, ThreadView, LeadActions, StatusReasonModal, etc. ====

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
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage", emoji="📝"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Over Wunsch", emoji="🤖"),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Bilder, Videos, Audio-Wünsche", emoji="✨"),
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
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="Name des Streamers", max_length=MAX_TITLE_LEN, required=True)
        self.fan_tag = discord.ui.TextInput(label="Fan-Tag", placeholder="@12hh238712 (Discord-Tag, mit @)", max_length=40, required=True)
        self.preis = discord.ui.TextInput(label="Preis", placeholder="400€", max_length=20, required=True)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt?", placeholder="Ja/Nein", max_length=10, required=True)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=15, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage + Bis Wann?", style=discord.TextStyle.paragraph, placeholder="Möchte ein Video über ... Bis zum 19.06.2025", max_length=MAX_BODY_LEN, required=True)
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
        }
        await self.cog.post_request(interaction, data, "custom")

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="Name des Streamers", max_length=MAX_TITLE_LEN, required=True)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=15, required=True)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, placeholder="Kurze Beschreibung", max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Bis Wann?", placeholder="19.06.2025", max_length=40, required=True)
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
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="Name des Streamers", max_length=MAX_TITLE_LEN, required=True)
        self.medium = discord.ui.TextInput(label="Medium", placeholder="Video/Bild/Audio?", max_length=20, required=True)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=15, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Bis Wann?", placeholder="19.06.2025", max_length=40, required=True)
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

# -- RequestThreadView, Status-Logik, LeadActions, Reason-Modal etc. folgen --
# === Thread-View, Status-Logik, Status-Wechsel (mit Reason), Backup, Close, LeadActions ===

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
        # Nur Lead oder Anfragesteller
        leads = await get_leads()
        allowed = []
        if self.data["type"] == "custom":
            allowed = leads["custom"]
        elif self.data["type"] == "ai":
            allowed = leads["ai"]
        elif self.data["type"] == "wunsch":
            allowed = leads["wunsch"]
        if interaction.user.id != self.data["erstellerid"] and interaction.user.id not in allowed:
            return await utils.send_error(interaction, "Nur der Lead oder der Ersteller kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel, interaction.user),
            ephemeral=True
        )

class StatusDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead):
        super().__init__(timeout=120)
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
            discord.SelectOption(label="Hochgeladen", value="uploaded", emoji="📤"),
            discord.SelectOption(label="Fertig", value="done", emoji="✅"),
            discord.SelectOption(label="Geschlossen", value="geschlossen", emoji="🛑")
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        # Bei abgelehnt/uploaded/done: Reason Modal!
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
            return
        await self.finish_status_change(interaction, new_status)

    async def finish_status_change(self, interaction, new_status, reason=None):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        if reason:
            self.data["status_reason"] = reason
        else:
            self.data.pop("status_reason", None)
        fan_tag = self.data.get('fan_tag', '')
        new_title = build_thread_title(new_status, self.data.get('streamer',''), self.data['erstellername'], self.data['type'], nr, fan_tag)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        await self.thread_channel.send(embed=embed)
        # DM an User inkl. Thread-Link & Grund
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                msg = f"Deine Anfrage **{self.data.get('streamer','')}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!"
                if reason:
                    msg += f"\nGrund: {reason}"
                msg += f"\n[Zum Post]({self.thread_channel.jump_url})"
                await ersteller.send(msg)
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund angeben"):
    def __init__(self, cog, data, thread_channel, lead, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.new_status = new_status
        self.reason = discord.ui.TextInput(
            label="Begründung",
            placeholder="Warum wurde abgelehnt, hochgeladen oder fertig markiert?",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.new_status, self.reason.value
        )

class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        # Nur Ersteller oder Lead darf schließen!
        leads = await get_leads()
        allowed = []
        if self.data["type"] == "custom":
            allowed = leads["custom"]
        elif self.data["type"] == "ai":
            allowed = leads["ai"]
        elif self.data["type"] == "wunsch":
            allowed = leads["wunsch"]
        if interaction.user.id != self.data["erstellerid"] and interaction.user.id not in allowed:
            return await utils.send_error(interaction, "Nur der Lead oder der Ersteller kann diesen Post schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        fan_tag = self.data.get('fan_tag', '')
        # Backup (filtere „Status geändert“/Botnachrichten raus)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if msg.author.bot and ("Status geändert" in msg.content or "Status wurde auf" in msg.content):
                continue
            name = msg.author.display_name
            content = msg.content
            if content.strip() == "":
                continue
            messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data.get('streamer',''), self.data['erstellername'], self.data['type'], nr, fan_tag)
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[]
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# ==== Lead DM-Status-Change (Dropdown) ====

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
            discord.SelectOption(label="Offen", value="offen", emoji="🟦"),
            discord.SelectOption(label="Angenommen", value="angenommen", emoji="🟩"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung", emoji="🟨"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt", emoji="🟥"),
            discord.SelectOption(label="Hochgeladen", value="uploaded", emoji="📤"),
            discord.SelectOption(label="Fertig", value="done", emoji="✅"),
            discord.SelectOption(label="Geschlossen", value="geschlossen", emoji="🛑")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        # Bei abgelehnt/uploaded/done: Reason Modal!
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
            return
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status)

# ==== Setup ====

async def setup(bot):
    await bot.add_cog(RequestCog(bot))

