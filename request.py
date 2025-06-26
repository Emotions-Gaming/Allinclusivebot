import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

# ==== Deine TAGS für Forum-Filter ====
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
    "hochgeladen": discord.Color.teal(),
    "fertig": discord.Color.dark_green(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "hochgeladen": "📤 Hochgeladen",
    "fertig": "✅ Fertig",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, ersteller, tag, typ, nr):
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {tag} - {typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    # alle leads für custom, ai, wunsch
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    typ = data.get("type", "")
    title = f"📩 {data['streamer']} • {data.get('fan_tag','')}" if data.get("streamer") else "Anfrage"
    desc = ""
    if typ == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fan_tag','')}\n"
            f"**Preis/Bezahlt?** {data.get('preis','')} ({data.get('bezahlt','')})\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','')}"
        )
    elif typ == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','')}"
        )
    elif typ == "wunsch":
        desc = (
            f"**Streamer:** {data.get('streamer','')}\n"
            f"**Content-Typ:** {data.get('content_typ','')}\n"
            f"**Sprache:** {data.get('sprache','')}\n"
            f"**Anfrage:** {data.get('anfrage','')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','')}"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {typ.capitalize()} • Erstellt von: {data.get('erstellername','')}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== LEAD MANAGEMENT (für alle Typen) ====================
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

    # Die restlichen Setup/Channel-Befehle kommen in Part 2!
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

    # ========== REQUEST MENU, MODALS UND DROPDOWNS ==========

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Individuelle Anfrage", emoji=TAG_CUSTOM["emoji"]),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Over anfragen", emoji=TAG_AI["emoji"]),
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Video/Bild/Audio Content Wunsch", emoji=TAG_WUNSCH["emoji"]),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        v = self.values[0]
        if v == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif v == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        elif v == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog))

# ==== Custom Anfrage Modal ====
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        # 1. Streamer (Name des Streamers)
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="z. B. EliasN97", max_length=60)
        # 2. Fan-Tag (@12hh238712 – Discord Tag)
        self.fan_tag = discord.ui.TextInput(label="Fan-Tag", placeholder="@12hh238712 (Discord-Tag)", max_length=40)
        # 3. Preis und bezahlt? (400$, Bezahlt)
        self.preis = discord.ui.TextInput(label="Preis & bezahlt?", placeholder="400$, Bezahlt", max_length=40)
        # 4. Sprache (Englisch/Deutsch)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=20)
        # 5. Anfrage + Bis Wann? (Möchte ein Video über... Bis zum 19.06.2025)
        self.anfrage = discord.ui.TextInput(label="Anfrage + Bis Wann?", style=discord.TextStyle.paragraph, placeholder="Möchte ein Video über ... Bis zum 19.06.2025", max_length=MAX_BODY_LEN)

        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.preis)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)

    async def on_submit(self, interaction: Interaction):
        # Anfrage + Bis Wann aufteilen
        anfrage_raw = self.anfrage.value
        if "Bis zum" in anfrage_raw:
            parts = anfrage_raw.split("Bis zum", 1)
            anfrage = parts[0].strip()
            zeitgrenze = "Bis zum" + parts[1].strip()
        else:
            anfrage = anfrage_raw
            zeitgrenze = ""
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "preis": self.preis.value,
            "bezahlt": "Bezahlt" if "bezahlt" in self.preis.value.lower() else "",
            "sprache": self.sprache.value,
            "anfrage": anfrage,
            "zeitgrenze": zeitgrenze,
        }
        await self.cog.post_request(interaction, data, "custom")

# ==== AI Voice Modal ====
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="z. B. Papaplatte", max_length=60)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, placeholder="Text oder Beschreibung", max_length=MAX_BODY_LEN)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=20)
        self.zeitgrenze = discord.ui.TextInput(label="Bis Wann?", placeholder="z. B. Bis Sonntag", max_length=40)
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

# ==== Wunsch Modal ====
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", placeholder="z. B. Knossi", max_length=60)
        self.content_typ = discord.ui.TextInput(label="Typ (Video/Bild/Audio)", placeholder="Video/Bild/Audio", max_length=25)
        self.sprache = discord.ui.TextInput(label="Sprache", placeholder="Englisch/Deutsch", max_length=20)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
        self.zeitgrenze = discord.ui.TextInput(label="Bis Wann?", placeholder="z. B. Bis Mittwoch", max_length=40)
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

# ========== POSTING & FILTER/THREAD LOGIK ==========

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1

        # Tag handling (Filter)
        if reqtype == "custom":
            applied_tags = [TAG_CUSTOM["id"]]
        elif reqtype == "ai":
            applied_tags = [TAG_AI["id"]]
        elif reqtype == "wunsch":
            applied_tags = [TAG_WUNSCH["id"]]
        else:
            applied_tags = []

        thread_title = build_thread_title(
            "offen", 
            data.get('streamer',''), 
            str(interaction.user), 
            data.get("fan_tag", data.get("content_typ","")), 
            reqtype, 
            nr
        )

        # Fix: Forum erwartet eine Liste von Tag-IDs als String, nicht als Objekt!
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=[str(tag_id) for tag_id in applied_tags],
        )
        channel = thread_with_message.thread

        # weitere Meta-Infos
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        data["nr"] = nr

        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

# ... StatusEditButton, CloseRequestButton, RequestThreadView etc. kommen im nächsten Part!
# ========== REQUEST THREAD VIEW ==========

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
        # Nur Lead darf!
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data.get("erstellerid"):
            return await utils.send_error(interaction, "Nur Lead oder Ersteller darf den Status ändern!")
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
            discord.SelectOption(label="Uploaded", value="uploaded", emoji="📤"),
            discord.SelectOption(label="Done", value="done", emoji="✅"),
            discord.SelectOption(label="Geschlossen", value="geschlossen", emoji="🛑"),
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        # Wenn Grund notwendig ist (abgelehnt, uploaded, done)
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await self.finish_status_change(interaction, new_status, "")

    async def finish_status_change(self, interaction, new_status, reason):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(
            new_status,
            self.data.get('streamer',''),
            self.data.get('fan_tag', self.data.get('content_typ', '')),
            self.data['type'],
            nr
        )
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        reason_line = f"\n**Grund:** {reason}" if reason else ""
        await self.thread_channel.send(
            content=f"{STATUS_DISPLAY.get(new_status,'')} von {interaction.user.mention}:{reason_line}",
            embed=embed
        )
        # DM an Ersteller (inkl. Link & Grund)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data.get('streamer','')}** wurde auf **{STATUS_DISPLAY.get(new_status,'')}** gesetzt!\n"
                    f"{'**Grund:** '+reason if reason else ''}\n"
                    f"**Link:** {self.thread_channel.jump_url}"
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY.get(new_status,'')}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für den Status"):
    def __init__(self, cog, data, thread_channel, lead, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead = lead
        self.new_status = new_status
        self.grund = discord.ui.TextInput(label="Grund", placeholder="Kurze Begründung...", style=discord.TextStyle.paragraph, max_length=250)
        self.add_item(self.grund)

    async def on_submit(self, interaction: Interaction):
        # Grund übernehmen
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
        # Nur Lead oder Ersteller darf schließen!
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads.get(reqtype, [])
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data.get("erstellerid"):
            return await utils.send_error(interaction, "Nur Lead oder Ersteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            # Botmeldungen und Statuswechsel rausfiltern
            if msg.author.bot:
                continue
            content = msg.content
            if content.startswith("Status geändert") or content.startswith("🟦") or content.startswith("🟩") or content.startswith("🟨") or content.startswith("🟥") or content.startswith("🛑"):
                continue
            name = msg.author.display_name
            if content.strip() == "":
                continue
            messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(
            self.data.get('status', 'geschlossen'),
            self.data.get('streamer',''),
            self.data.get('fan_tag', self.data.get('content_typ', '')),
            self.data['type'],
            nr
        )
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[str(TAG_CUSTOM["id"])] if self.data['type']=="custom" else (
                [str(TAG_AI["id"])] if self.data['type']=="ai" else [str(TAG_WUNSCH["id"])]
            ),
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status=self.data.get('status', 'geschlossen'))
        await closed_channel.send(embed=embed)
        await closed_channel.send(backup_body)
        await self.thread_channel.edit(archived=True, locked=True)
        await interaction.response.send_message("Anfrage als erledigt verschoben und gesperrt!", ephemeral=True)

# ========== LEAD STATUS DROPDOWN FÜR DM ==========

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
            discord.SelectOption(label="Status: Uploaded", value="uploaded", emoji="📤"),
            discord.SelectOption(label="Status: Done", value="done", emoji="✅"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen", emoji="🛑"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        # Wenn Grund notwendig ist
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, self.lead, new_status))
        else:
            await StatusDropdown(self.cog, self.data, self.thread_channel, self.lead).finish_status_change(interaction, new_status, "")

# ========== COG SETUP ==========

async def setup(bot):
    await bot.add_cog(RequestCog(bot))
