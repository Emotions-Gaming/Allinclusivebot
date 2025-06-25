# request.py

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

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "geschlossen": discord.Color.dark_grey(),
    "uploaded": discord.Color.purple(),
    "done": discord.Color.dark_green(),
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "geschlossen": "🛑 Geschlossen",
    "uploaded": "📤 Hochgeladen",
    "done": "✅ Erledigt"
}

def build_thread_title(status, streamer, ersteller, typ, nr, fantag=None, sprache=None):
    parts = [f"[{status.capitalize()}]", streamer, ersteller]
    if fantag: parts.append(fantag)
    if sprache: parts.append(sprache)
    parts.append(typ.capitalize())
    parts.append(f"#{nr}")
    return " - ".join(str(x) for x in parts if x)

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
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"**Fan-Tag:** {data.get('fantag','-')}\n"
            f"**Preis & Bezahlt?:** {data.get('preisbezahlt','-')}\n"
            f"**Sprache:** {data.get('sprache','-')}\n"
            f"**Anfrage + Deadline:** {data.get('anfrage','-')}\n"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Sprache:** {data.get('sprache','-')}\n"
            f"**Audio Wunsch:** {data.get('audiowunsch','-')}\n"
            f"**Bis Wann:** {data.get('zeitgrenze','-')}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Format:** {data.get('format','-')}\n"
            f"**Sprache:** {data.get('sprache','-')}\n"
            f"**Anfrage + Deadline:** {data.get('anfrage','-')}\n"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status,status)}",
        color=color
    )
    embed.set_footer(text=f"Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}  # thread_id: [(username, content), ...]

    # -------- Channel Setups (wie gehabt) ----------
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

    # -------- Lead Management (wie gehabt, +wunsch) ----------
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
        await utils.send_success(interaction, f"{user.mention} ist nun Contentwunsch-Lead.")

    @app_commands.command(name="requestwunschremovelead", description="Entfernt einen Wunsch-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestwunschremovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["wunsch"]:
            leads["wunsch"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als Contentwunsch-Lead entfernt.")

    # -------- Haupt-Request-Posting + Backup (mit Fix für send_lead_dm) ----------
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)

        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        thread_title = build_thread_title(
            "offen",
            data['streamer'],
            str(interaction.user),
            reqtype,
            nr,
            fantag=data.get('fantag'),
            sprache=data.get('sprache')
        )
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=[],
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

    # -------- LEAD DM ----------------------------------------
    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        ids = leads.get(reqtype, [])
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{reqtype.capitalize()}**-Anfrage von {interaction.user.mention}:\n"
                        f"**Streamer:** {data.get('streamer')}\n"
                        f"**Sprache:** {data.get('sprache','-')}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Fan-Tag:** {data.get('fantag','-')}\n"
                            f"**Preis/B:** {data.get('preisbezahlt','-')}\n"
                            f"**Anfrage:** {data.get('anfrage','-')}\n"
                        )
                    elif reqtype == "ai":
                        msg += (
                            ":information_source: Nur Mila und Xenia für AI Voice!\n"
                            ":alarm_clock: Textlänge max 10 Sek!\n"
                            f"**Audio Wunsch:** {data.get('audiowunsch','-')}\n"
                            f"**Bis Wann:** {data.get('zeitgrenze','-')}\n"
                        )
                    elif reqtype == "wunsch":
                        msg += (
                            f"**Format:** {data.get('format','-')}\n"
                            f"**Anfrage:** {data.get('anfrage','-')}\n"
                        )
                    msg += f"\n[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    # ... Rest wie gehabt (z. B. on_thread_message, Views, Modals, Status, Backup, etc.)

# ---- Views, Modals, usw. folgen HIER ----
# ---- Views und Modals ----

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
            discord.SelectOption(label="Content Wunsch", value="wunsch", description="Sonstiger Video/Audio/Bild Wunsch"),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog, self))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog, self))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog, self))
        # Nach Abschluss resetten!
        self.values = []
        await interaction.message.edit(view=self.view)

# --- Custom Anfrage Modal ---
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown

        self.streamer = discord.ui.TextInput(
            label="Streamer (Name des Streamers)",
            placeholder="z.B. Knossi",
            max_length=MAX_TITLE_LEN,
            required=True)
        self.fantag = discord.ui.TextInput(
            label="Fan-Tag (@12hh238712)",
            placeholder="@12hh238712 – bitte exakt wie im Discord",
            max_length=40,
            required=True)
        self.preisbezahlt = discord.ui.TextInput(
            label="Preis & Bezahlt? (400€, Bezahlt)",
            placeholder="400€, Bezahlt",
            max_length=40,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache (Englisch/Deutsch)",
            placeholder="Englisch ODER Deutsch",
            max_length=20,
            required=True)
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann? (Beschreibung + Deadline)",
            style=discord.TextStyle.paragraph,
            placeholder="Ich wünsche mir ein Video über ... Bis zum 19.06.2025",
            max_length=MAX_BODY_LEN,
            required=True)

        for item in [self.streamer, self.fantag, self.preisbezahlt, self.sprache, self.anfrage]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fantag": self.fantag.value,
            "preisbezahlt": self.preisbezahlt.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
        }
        await self.cog.post_request(interaction, data, "custom")
        # Modal-Reset
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# --- AI Voice Anfrage Modal ---
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown

        self.streamer = discord.ui.TextInput(
            label="Streamer (Name des Streamers)",
            placeholder="z.B. Knossi",
            max_length=MAX_TITLE_LEN,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache (Englisch/Deutsch)",
            placeholder="Englisch ODER Deutsch",
            max_length=20,
            required=True)
        self.audiowunsch = discord.ui.TextInput(
            label="Audio Wunsch (max. 10 Sekunden!)",
            style=discord.TextStyle.paragraph,
            placeholder="Satz oder Wunsch eintragen",
            max_length=MAX_BODY_LEN,
            required=True)
        self.zeitgrenze = discord.ui.TextInput(
            label="Bis Wann? (Deadline)",
            placeholder="Bis zum ...",
            max_length=40,
            required=True)

        for item in [self.streamer, self.sprache, self.audiowunsch, self.zeitgrenze]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "sprache": self.sprache.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "ai")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# --- Wunsch Anfrage Modal ---
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown

        self.streamer = discord.ui.TextInput(
            label="Streamer (Name des Streamers)",
            placeholder="z.B. Knossi",
            max_length=MAX_TITLE_LEN,
            required=True)
        self.format = discord.ui.TextInput(
            label="Video/Bild/Audio?",
            placeholder="Video / Bild / Audio",
            max_length=20,
            required=True)
        self.sprache = discord.ui.TextInput(
            label="Sprache (Englisch/Deutsch)",
            placeholder="Englisch ODER Deutsch",
            max_length=20,
            required=True)
        self.anfrage = discord.ui.TextInput(
            label="Anfrage + Bis Wann?",
            style=discord.TextStyle.paragraph,
            placeholder="Beschreibe deinen Wunsch, + Deadline!",
            max_length=MAX_BODY_LEN,
            required=True)

        for item in [self.streamer, self.format, self.sprache, self.anfrage]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "format": self.format.value,
            "sprache": self.sprache.value,
            "anfrage": self.anfrage.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# Ab hier folgen die Thread-View, Status, Close-Button, Backup, usw.
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
            discord.SelectOption(label="Geschlossen", value="geschlossen"),
            discord.SelectOption(label="Uploaded", value="uploaded"),
            discord.SelectOption(label="Done", value="done")
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        # Grund abfragen, wenn nötig
        grund = None
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status, self.lead))
        else:
            await self.finish_status_change(interaction, new_status, grund)

    async def finish_status_change(self, interaction, new_status, grund=None):
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        if grund:
            embed.add_field(name="Grund", value=grund, inline=False)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Zum Thread]({self.thread_channel.jump_url})" +
                    (f"\nGrund: {grund}" if grund else "")
                )
            except Exception:
                pass
        await interaction.followup.send(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Grund für Status-Änderung"):
    def __init__(self, cog, data, thread_channel, status, lead):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.status = status
        self.lead = lead
        self.reason = discord.ui.TextInput(
            label="Bitte Grund für diese Aktion angeben:",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        # Direkt Status-Änderung + Grund posten
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
        # Nur Ersteller ODER Lead!
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads.get(reqtype, [])
        if interaction.user.id not in allowed_leads and interaction.user.id != self.data['erstellerid']:
            return await utils.send_error(interaction, "Nur der Lead oder der Ersteller darf schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        # Nachrichten-Backup: Nur User, keine Bot-Statusmeldungen!
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if not msg.author.bot and msg.content.strip():
                name = msg.author.display_name
                content = msg.content
                messages.append(f"**{name}:** {content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        closed_thread_with_msg = await done_forum.create_thread(
            name=new_title,
            content="Backup der Anfrage.",
            applied_tags=[],
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
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen"),
            discord.SelectOption(label="Status: Uploaded", value="uploaded"),
            discord.SelectOption(label="Status: Done", value="done")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        grund = None
        # PopUp bei abgelehnt/uploaded/done
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status, self.lead))
            return
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                    f"[Zum Thread]({self.thread_channel.jump_url})"
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
