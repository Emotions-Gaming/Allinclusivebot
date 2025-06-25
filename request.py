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
    "hochgeladen": discord.Color.blue(),
    "done": discord.Color.teal(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "hochgeladen": "🔵 Hochgeladen",
    "done": "✅ Erledigt",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, ersteller, fan_tag, typ, nr):
    fan = f"{fan_tag} - " if fan_tag else ""
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {fan}{typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    # Erweitert um wunsch:
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": [], "wunsch": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data.get('streamer', 'Anfrage')}"
    desc = data.get("desc", "")

    if data["type"] == "custom":
        desc = (
            f"**Sprache:** *{data.get('sprache', 'Nicht angegeben')}*\n"
            f"**Fan-Tag:** {data.get('fan_tag','-')}\n"
            f"**Preis:** {data['preis']}\n"
            f"**Bezahlt?** {data['bezahlt']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n"
            f"**Sprache:** *{data.get('sprache', 'Nicht angegeben')}*\n\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "wunsch":
        desc = (
            f"**Sprache:** *{data.get('sprache', 'Nicht angegeben')}*\n"
            f"**Content Art:** {data['contentart']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    if data.get("grund"):
        embed.add_field(name="Begründung", value=data["grund"], inline=False)
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}

    # ======= Channel Setups =======
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

    # ======= LEAD Management =======
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

    # Wunsch Lead (für Content Wünsche)
    @app_commands.command(name="requestwunschlead", description="Fügt einen Wunsch-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestwunschlead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id not in leads["wunsch"]:
            leads["wunsch"].append(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} ist nun Content Wunsch Lead.")

    @app_commands.command(name="requestwunschremovelead", description="Entfernt einen Wunsch-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestwunschremovelead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        leads = await get_leads()
        if user.id in leads["wunsch"]:
            leads["wunsch"].remove(user.id)
            await save_leads(leads)
        await utils.send_success(interaction, f"{user.mention} wurde als Wunsch Lead entfernt.")

    # ======= Haupt-Request-Posting (POST_REQUEST wird weiter unten nachgereicht, Platz sparen) =======

# ===================== VIEWS & MODALS =====================

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
            discord.SelectOption(
                label="Custom Anfrage",
                value="custom",
                description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(
                label="AI Voice Anfrage",
                value="ai",
                description="AI Voice Custom anfragen"),
            discord.SelectOption(
                label="Content Wunsch",
                value="wunsch",
                description="Wunsch für Bild, Video, Audio u.a.")
        ]
        super().__init__(
            placeholder="Wähle eine Anfrage-Art…",
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog, self))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog, self))
        elif self.values[0] == "wunsch":
            await interaction.response.send_modal(WunschRequestModal(self.cog, self))

# ========== CUSTOM MODAL ==========
class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.fan_tag = discord.ui.TextInput(label="Fan Tag hinzufügen (z.B. @12hh238712)", max_length=32, required=False)
        self.sprache = discord.ui.TextInput(label="Sprache (Deutsch/Englisch)", placeholder="Welche Sprache spricht der Kunde?", style=discord.TextStyle.short, max_length=16, required=False)
        self.preis = discord.ui.TextInput(label="Preis (z. B. 400€)", max_length=20, required=True)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt?", placeholder="Ja/Nein", max_length=10, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze (z. B. bis Sonntag)", max_length=40, required=True)
        self.add_item(self.streamer)
        self.add_item(self.fan_tag)
        self.add_item(self.sprache)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "fan_tag": self.fan_tag.value,
            "sprache": self.sprache.value or "Nicht angegeben",
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "custom")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# ========== AI VOICE MODAL ==========
class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.sprache = discord.ui.TextInput(label="Sprache (Deutsch/Englisch)", style=discord.TextStyle.short, max_length=16, required=False)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze", max_length=40, required=True)
        self.add_item(self.streamer)
        self.add_item(self.sprache)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "sprache": self.sprache.value or "Nicht angegeben",
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "ai")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# ========== WUNSCH MODAL ==========
class WunschRequestModal(discord.ui.Modal, title="Content Wunsch"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.contentart = discord.ui.TextInput(label="Video/Bild/Audio?", max_length=32, required=True)
        self.sprache = discord.ui.TextInput(label="Sprache (Deutsch/Englisch)", style=discord.TextStyle.short, max_length=16, required=False)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Bis wann?", max_length=40, required=True)
        self.add_item(self.streamer)
        self.add_item(self.contentart)
        self.add_item(self.sprache)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "contentart": self.contentart.value,
            "sprache": self.sprache.value or "Nicht angegeben",
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "wunsch")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# ========== REQUEST THREAD VIEW & BUTTONS ==========

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
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"] if reqtype == "ai" else leads["wunsch"]
        # Nur Lead darf Status editieren!
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_message(
            "Wähle den neuen Status:",
            view=StatusDropdownView(self.cog, self.data, self.thread_channel),
            ephemeral=True
        )

class StatusDropdownView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=60)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusDropdown(cog, data, thread_channel))

class StatusDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel):
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Hochgeladen", value="hochgeladen"),
            discord.SelectOption(label="Done/Erledigt", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        # Für "abgelehnt", "hochgeladen" und "done" Grund erfragen:
        if new_status in ["abgelehnt", "hochgeladen", "done"]:
            await interaction.response.send_modal(StatusGrundModal(self.cog, self.data, self.thread_channel, new_status, nr))
        else:
            self.data['status'] = new_status
            new_title = build_thread_title(new_status, self.data['streamer'], self.data.get('erstellername', '-'), self.data.get('fan_tag', ''), self.data['type'], nr)
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
                        f"**Deine Anfrage** [{self.data['streamer']}]({self.thread_channel.jump_url})\nStatus: **{STATUS_DISPLAY[new_status]}**"
                    )
                except Exception:
                    pass
            await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusGrundModal(discord.ui.Modal, title="Grund für Entscheidung"):
    def __init__(self, cog, data, thread_channel, status, nr):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.status = status
        self.nr = nr
        self.grund = discord.ui.TextInput(
            label="Gib einen kurzen Grund ein (wird im Post angezeigt):",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.grund)

    async def on_submit(self, interaction: Interaction):
        self.data['status'] = self.status
        self.data['grund'] = self.grund.value
        new_title = build_thread_title(self.status, self.data['streamer'], self.data.get('erstellername', '-'), self.data.get('fan_tag', ''), self.data['type'], self.nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=self.status)
        await self.thread_channel.send(content=f"Status geändert von {interaction.user.mention}:", embed=embed)
        # DM an Ersteller inkl. Grund + Link:
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"**Deine Anfrage** [{self.data['streamer']}]({self.thread_channel.jump_url})\n"
                    f"Status: **{STATUS_DISPLAY[self.status]}**\nGrund: {self.grund.value}"
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[self.status]}** gesetzt!", ephemeral=True)

# ========== CLOSE (nur Lead & Ersteller) ==========

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
        # Nur Lead ODER Ersteller darf schließen!
        if (interaction.user.id not in allowed_leads and interaction.user.id != self.data["erstellerid"]):
            return await utils.send_error(interaction, "Nur der Lead oder der Anfragensteller kann schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        # Backup Verlauf filtern (keine Bot-Msgs/Status geändert...)
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if not msg.author.bot and msg.content.strip() != "":
                messages.append(f"**{msg.author.display_name}:** {msg.content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data['streamer'], self.data.get('erstellername', '-'), self.data.get('fan_tag', ''), self.data['type'], nr)
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

# ===== LEAD-DM-DROPDOWN: Analog wie Status oben (inkl. Grund bei Bedarf) =====

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
            discord.SelectOption(label="Status: Hochgeladen", value="hochgeladen"),
            discord.SelectOption(label="Status: Done/Erledigt", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        if new_status in ["abgelehnt", "hochgeladen", "done"]:
            await interaction.response.send_modal(StatusGrundModal(self.cog, self.data, self.thread_channel, new_status, nr))
        else:
            self.data['status'] = new_status
            new_title = build_thread_title(new_status, self.data['streamer'], self.data.get('erstellername', '-'), self.data.get('fan_tag', ''), self.data['type'], nr)
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
                        f"**Deine Anfrage** [{self.data['streamer']}]({self.thread_channel.jump_url})\nStatus: **{STATUS_DISPLAY[new_status]}**"
                    )
                except Exception:
                    pass
            await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

# ========== Haupt-POST_REQUEST: Muss ans Ende ==========
async def post_request(self, interaction, data, reqtype):
    config = await get_request_config()
    forum_id = config.get("active_forum")
    if not forum_id:
        return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
    forum = interaction.guild.get_channel(forum_id)
    all_threads = forum.threads
    nr = len(all_threads) + 1
    data["nr"] = nr
    data["fan_tag"] = data.get("fan_tag", "")
    thread_title = build_thread_title("offen", data['streamer'], str(interaction.user), data.get("fan_tag", ""), reqtype, nr)
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

RequestCog.post_request = post_request

# ========== SETUP ==========

async def setup(bot):
    await bot.add_cog(RequestCog(bot))

