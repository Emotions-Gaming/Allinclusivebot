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

TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.blue(),
    "done": discord.Color.green(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "📤 Uploaded",
    "done": "✅ Done",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, tag_or_content, typ, nr):
    return f"[{status.capitalize()}] - {streamer} - {tag_or_content} - {typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    # lead-dict: {"custom": [...], "ai": [...], "wunsch": [...]}
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data.get('streamer', '')}"
    if data["type"] == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis & bezahlt:** {data.get('preis','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann?** {data.get('zeitgrenze','')}"
        )
    elif data["type"] == "ai":
        desc = (
            ":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            ":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Bis Wann?** {data.get('zeitgrenze','')}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Typ:** {data.get('content_typ','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann?** {data.get('zeitgrenze','')}"
        )
    else:
        desc = ""
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status,'')}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data.get('erstellername','')}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== LEAD MANAGEMENT ==========

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

    # ========== CHANNEL SETUP, REQUESTMAIN, MODALS, POST HANDLING ETC ==========
    # ========== CHANNEL SETUPS ==========

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
            description="Wähle eine Kategorie, um eine neue Anfrage zu stellen.",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

# --- RequestMenu/Dropdown, alle 3 Anfragearten ---
class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Individuelle Anfrage stellen", emoji=TAG_CUSTOM["emoji"]),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Anfrage", emoji=TAG_AI["emoji"]),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Sonstiger Wunsch (Video, Bild, Audio)", emoji=TAG_WUNSCH["emoji"]),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        value = self.values[0]
        if value == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif value == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif value == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# --- MODALS für alle Anfragearten ---
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            placeholder="Name des Streamers",
            max_length=MAX_TITLE_LEN,
            required=True)
        self.fan_tag = discord.ui.TextInput(
            label="Fan-Tag",
            placeholder="@12hh238712 – Discord Tag des Kunden",
            max_length=40,
            required=True)
        self.preis = discord.ui.TextInput(
            label="Preis und bezahlt?",
            placeholder="z. B. 400$, Bezahlt",
            max_length=40,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=30,
            required=True)
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            placeholder="Möchte ein Video über ... Bis zum 19.06.2025",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True)
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
            "zeitgrenze": self.anfrage.value.split("Bis zum")[-1].strip() if "Bis zum" in self.anfrage.value else "",
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
            required=True)
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch",
            placeholder="Wunschtext oder Beschreibung",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=30,
            required=True)
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="z. B. bis Sonntag, 19.06.",
            max_length=40,
            required=True)
        self.add_item(self.streamer)
        self.add_item(self.audiowunsch)
        self.add_item(self.sprache)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "sprache": self.sprache.value,
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
            required=True)
        self.content_typ = discord.ui.TextInput(
            label="Video/Bild/Audio?",
            placeholder="Was wird gewünscht?",
            max_length=30,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache",
            placeholder="Englisch/Deutsch",
            max_length=30,
            required=True)
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            placeholder="Beschreibe den Wunsch",
            style=discord.TextStyle.paragraph,
            max_length=MAX_BODY_LEN,
            required=True)
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis Wann?",
            placeholder="z. B. bis Sonntag, 19.06.",
            max_length=40,
            required=True)
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

    # -------- Hier bitte mit „fortsetzen“ antworten für den Thread-Post, Tag-Filter, Status-Logik, etc. --------
    # ---- TAG IDs/Mapping ----
    TAGS = {
        "custom": TAG_CUSTOM["id"],
        "ai": TAG_AI["id"],
        "wunsch": TAG_WUNSCH["id"],
    }

    # ========== Haupt-Request-Posting (mit Tag/Filter, Status, Lead-DM) ==========
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)

        # Hole alle Threads für laufende Nummer
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # Filter-Tag zuweisen
        tag_id = TAGS[reqtype]
        applied_tags = [tag_id]

        thread_title = build_thread_title(
            "offen",
            data.get('streamer', ''),
            str(interaction.user),
            reqtype,
            nr
        )

        # Forum-Thread anlegen mit Filter-Tag
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

    # ----- Lead-DM -----
    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        ids = leads.get(reqtype, [])
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{reqtype.capitalize()} Anfrage** von {interaction.user.mention}:\n"
                        f"**Streamer:** {data.get('streamer','')}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
                            f"**Preis/Bezahlt?** {data.get('preis','')}\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Anfrage:** {data.get('anfrage','')}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Bis Wann:** {data.get('zeitgrenze','')}\n"
                        )
                    elif reqtype == "wunsch":
                        msg += (
                            f"**Typ:** {data.get('content_typ','')}\n"
                            f"**Sprache:** {data.get('sprache','')}\n"
                            f"**Anfrage:** {data.get('anfrage','')}\n"
                            f"**Bis Wann:** {data.get('zeitgrenze','')}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    # ========== Request Thread-View ==========
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# -------- STATUS-BEARBEITEN-BUTTON (nur für Lead oder Ersteller) --------
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
        is_lead = interaction.user.id in allowed_leads
        is_ersteller = interaction.user.id == self.data['erstellerid']
        if not (is_lead or is_ersteller):
            return await utils.send_error(interaction, "Nur der Lead oder der Ersteller kann den Status ändern!")
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
            discord.SelectOption(label="Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Erledigt", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen")
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
        new_title = build_thread_title(new_status, self.data.get('streamer',''), self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        content = f"Status geändert von {interaction.user.mention}:"
        if reason:
            content += f"\n**Grund:** {reason}"
        await self.thread_channel.send(content=content, embed=embed)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data.get('streamer','')}** hat nun den Status: **{STATUS_DISPLAY.get(new_status,new_status.capitalize())}**!\n"
                    f"{'**Grund:** ' + reason if reason else ''}\n"
                    f"[Zum Post]({self.thread_channel.jump_url})"
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY.get(new_status,new_status.capitalize())}** geändert!", ephemeral=True)

# --- Status Reason Modal ---
class StatusReasonModal(discord.ui.Modal, title="Gib bitte einen Grund an!"):
    def __init__(self, cog, data, thread_channel, lead, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.new_status = new_status
        self.reason = discord.ui.TextInput(
            label="Grund",
            placeholder="Kurze Begründung (Pflichtfeld)",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
            interaction, self.new_status, self.reason.value
        )

# -------- CLOSE REQUEST BUTTON (nur Ersteller/Lead!) --------
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads.get(reqtype, [])
        is_lead = interaction.user.id in allowed_leads
        is_ersteller = interaction.user.id == self.data['erstellerid']
        if not (is_lead or is_ersteller):
            return await utils.send_error(interaction, "Nur der Lead oder der Ersteller kann den Post schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            # NUR USER-Nachrichten sichern, keine Bot-Status-Änderungen etc!
            if not msg.author.bot or ("Status geändert" not in msg.content):
                name = msg.author.display_name
                content = msg.content
                if content.strip() == "":
                    continue
                messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data.get('streamer',''), self.data['erstellername'], self.data['type'], nr)
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[TAGS.get(self.data['type'])],
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
            discord.SelectOption(label="Status: Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Status: Erledigt", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(
                interaction, new_status, ""
            )

# ========== SETUP ==========

# ========== HILFSFUNKTIONEN, EMBEDS, TITLE BUILDER ==========

def build_thread_title(status, streamer, ersteller, typ, nr):
    # typ kann 'custom', 'ai' oder 'wunsch' sein
    status_disp = status.capitalize() if not status.lower() in STATUS_DISPLAY else STATUS_DISPLAY[status.lower()]
    return f"[{status_disp}] - {streamer} - {ersteller} - {typ.capitalize()} - #{nr}"

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    typ = data.get("type", "custom")
    title = f"📩 {data.get('streamer','')}" if data.get("streamer") else "Anfrage"
    # Custom, AI oder Wunsch
    if typ == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis/Bezahlt?** {data.get('preis','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
        )
    elif typ == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','')}\n"
        )
    elif typ == "wunsch":
        desc = (
            f"**Typ:** {data.get('content_typ','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','')}\n"
        )
    else:
        desc = data.get("desc", "")
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status, status.capitalize())}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {typ.capitalize()} • Erstellt von: {data.get('erstellername','')}")
    return embed

# ========== STATUS-FARBEN, -LABELS ==========
STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "uploaded": discord.Color.teal(),
    "done": discord.Color.dark_green(),
    "geschlossen": discord.Color.dark_grey(),
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "⬆️ Hochgeladen",
    "done": "✅ Erledigt",
    "geschlossen": "🛑 Geschlossen"
}

# ========== TAGS/Filter (ID etc.) ==========
TAG_CUSTOM = {"name": "Custom", "emoji": "🎨", "id": 1387599528831615087}
TAG_AI     = {"name": "AI Voice", "emoji": "🗣️", "id": 1387599571441680505}
TAG_WUNSCH = {"name": "Wunsch", "emoji": "💡", "id": 1387599595667722330}
TAGS = {
    "custom": TAG_CUSTOM["id"],
    "ai": TAG_AI["id"],
    "wunsch": TAG_WUNSCH["id"],
}

# ========== JSON-Hilfsfunktionen ==========

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

# ========== (Falls nötig, weitere Utils, z. B. Permission-Checks etc.) ==========

# Deine utils.is_admin(), utils.send_success(), utils.send_error(), utils.load_json(), utils.save_json()
# und andere Hilfsfunktionen sollten so wie in deinem alten Script vorhanden sein.

# ========== SETUP (NOCHMAL FÜR SICHERHEIT) ==========

async def setup(bot):
    await bot.add_cog(RequestCog(bot))

