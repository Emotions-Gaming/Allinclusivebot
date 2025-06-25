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
REQUEST_COUNT_PATH = os.path.join("persistent_data", "request_counter.json")
MAX_TITLE_LEN = 80
MAX_BODY_LEN = 500
MAX_COMMENT_LEN = 200

AI_VOICE_INFO = (
    "‼️ **Hinweis:** Aktuell sind nur **Mila** und **Xenia** für AI Voice verfügbar!\n"
    "Die gewünschten Texte dürfen maximal **10 Sekunden** lang sein."
)

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, username, typ, nr):
    return f"[{STATUS_DISPLAY[status]}] - {streamer} - {username} - {typ.capitalize()} - #{nr}"

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = build_thread_title(status, data['streamer'], data['erstellername'], data['type'], data['nr'])
    if data["type"] == "custom":
        desc = (
            f"**Preis:** {data['preis']}\n"
            f"**Bezahlt?** {data['bezahlt']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "ai":
        desc = (
            f"{AI_VOICE_INFO}\n\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    else:
        desc = ""
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY[status]}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

async def get_request_counter():
    d = await utils.load_json(REQUEST_COUNT_PATH, {"count": 1})
    return d.get("count", 1)

async def increment_request_counter():
    d = await utils.load_json(REQUEST_COUNT_PATH, {"count": 1})
    d["count"] = d.get("count", 1) + 1
    await utils.save_json(REQUEST_COUNT_PATH, d)
    return d["count"] - 1

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_threads = {} # thread_id: data
        self.chat_backups = {}   # thread_id: list of (author, content)

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

    # ========== Haupt-Request-Posting ==========
    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        nr = await increment_request_counter()
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        data["nr"] = nr
        thread_title = build_thread_title("offen", data['streamer'], data['erstellername'], data['type'], data['nr'])
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=[],
        )
        channel = thread_with_message.thread
        embed = build_embed(data, status="offen")
        view = PostActionsView(self, data, channel)
        await channel.send(embed=embed, view=view)
        self.active_threads[channel.id] = data.copy()
        self.chat_backups[channel.id] = []
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        ids = leads["custom"] if reqtype == "custom" else leads["ai"]
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = RequestActionView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{'Custom' if reqtype == 'custom' else 'AI Voice'} Anfrage** von {interaction.user.mention}:\n"
                        f"**Streamer:** {data['streamer']}\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"**Preis:** {data['preis']}\n"
                            f"**Bezahlt?** {data['bezahlt']}\n"
                            f"**Anfrage:** {data['anfrage']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    else:
                        msg += (
                            f"{AI_VOICE_INFO}\n"
                            f"**Audio Wunsch:** {data['audiowunsch']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    # ========== Chat-Backup ==========
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        if message.channel.id in self.active_threads:
            backup = self.chat_backups.get(message.channel.id, [])
            backup.append((str(message.author), message.content))
            self.chat_backups[message.channel.id] = backup

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen"),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog, self))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog, self))

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.preis = discord.ui.TextInput(label="Preis (z. B. 400€)", max_length=20, required=True)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt?", placeholder="Ja/Nein", max_length=10, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze (z. B. bis Sonntag)", max_length=40, required=True)
        self.add_item(self.streamer)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "custom")
        # Set dropdown back to default so Menü kann wieder genutzt werden
        self.dropdown.values = []

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze", max_length=40, required=True)
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
        self.dropdown.values = []

# ========== Actions im Post ==========
class PostActionsView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

# Status bearbeiten Button für Leads
class StatusEditButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Status bearbeiten", style=discord.ButtonStyle.primary, emoji="🛠")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"]
        if interaction.user.id not in allowed_leads:
            return await utils.send_error(interaction, "Nur der zuständige Lead kann den Status ändern!")
        await interaction.response.send_modal(StatusEditModal(self.cog, self.data, self.thread_channel))

# Modal für Statusauswahl
class StatusEditModal(discord.ui.Modal, title="Status ändern"):
    status_options = [
        ("offen", "🟦 Offen"),
        ("angenommen", "🟩 Angenommen"),
        ("bearbeitung", "🟨 In Bearbeitung"),
        ("abgelehnt", "🟥 Abgelehnt"),
        ("geschlossen", "🛑 Geschlossen"),
    ]

    def __init__(self, cog, data, thread_channel):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.status = discord.ui.TextInput(
            label="Neuer Status",
            placeholder="offen / angenommen / bearbeitung / abgelehnt / geschlossen",
            max_length=20,
            required=True
        )
        self.add_item(self.status)

    async def on_submit(self, interaction: Interaction):
        new_status = self.status.value.lower()
        if new_status not in STATUS_COLORS:
            return await utils.send_error(interaction, "Ungültiger Status!")
        # Titel und Embed updaten
        self.data['status'] = new_status
        nr = self.data.get('nr', 0)
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        await self.thread_channel.send(content=f"Status von {interaction.user.mention} geändert:", embed=embed)
        # DM an Ersteller bei Änderung
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!"
                )
            except Exception:
                pass
        await utils.send_success(interaction, f"Status geändert zu {STATUS_DISPLAY[new_status]}.")

# Anfrage schließen (nur Lead oder Ersteller)
class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        # Nur Lead oder Ersteller darf schließen
        leads = await get_leads()
        reqtype = self.data['type']
        allowed_leads = leads["custom"] if reqtype == "custom" else leads["ai"]
        is_lead = interaction.user.id in allowed_leads
        is_creator = interaction.user.id == self.data['erstellerid']
        if not (is_lead or is_creator):
            return await utils.send_error(interaction, "Nur der zuständige Lead oder der Ersteller kann schließen!")
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        closed_thread_with_msg = await done_forum.create_thread(
            name=build_thread_title("geschlossen", self.data['streamer'], self.data['erstellername'], self.data['type'], nr),
            content="Abgeschlossene Anfrage.",
            applied_tags=[],
        )
        closed_channel = closed_thread_with_msg.thread
        embed = build_embed(self.data, status="geschlossen")
        # Chatverlauf sichern und posten
        backup_msgs = self.cog.chat_backups.get(self.thread_channel.id, [])
        backup_text = "\n".join([f"**{author}:** {content}" for author, content in backup_msgs])
        if backup_text:
            await closed_channel.send("**Chatverlauf:**\n" + backup_text)
        await closed_channel.send(embed=embed)
        await self.thread_channel.edit(archived=True, locked=True)
        await utils.send_success(interaction, "Anfrage als erledigt verschoben.")

# Lead-DM-Aktionen
class RequestActionView(discord.ui.View):
    def __init__(self, cog, data, thread_channel, lead_user):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.lead_user = lead_user

    @discord.ui.button(label="Genehmigen", style=discord.ButtonStyle.success)
    async def approve(self, interaction: Interaction, button: discord.ui.Button):
        await self.change_status(interaction, "angenommen")

    @discord.ui.button(label="Bearbeitung", style=discord.ButtonStyle.primary)
    async def processing(self, interaction: Interaction, button: discord.ui.Button):
        await self.change_status(interaction, "bearbeitung")

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: discord.ui.Button):
        modal = DeclineReasonModal(self.cog, self.data, self.thread_channel)
        await interaction.response.send_modal(modal)

    async def change_status(self, interaction, status):
        self.data['status'] = status
        nr = self.data.get('nr', 0)
        new_title = build_thread_title(status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=status)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        # DM an Ersteller
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[status]}**!"
                )
            except Exception:
                pass
        await utils.send_success(interaction, f"Status zu **{STATUS_DISPLAY[status]}** geändert.")

class DeclineReasonModal(discord.ui.Modal, title="Ablehnungsgrund angeben"):
    def __init__(self, cog, data, thread_channel):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.reason = discord.ui.TextInput(
            label="Grund für Ablehnung",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        self.data['status'] = "abgelehnt"
        nr = self.data.get('nr', 0)
        new_title = build_thread_title("abgelehnt", self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status="abgelehnt")
        embed.add_field(name="Ablehnungsgrund", value=self.reason.value, inline=False)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        # DM an Ersteller
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** wurde abgelehnt!\n\n**Grund:** {self.reason.value}"
                )
            except Exception:
                pass
        await utils.send_success(interaction, "Anfrage abgelehnt und Grund gepostet.")

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
