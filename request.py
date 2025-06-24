import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)

REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
REQUEST_DATA_PATH = os.path.join("persistent_data", "request_data.json")
REQUEST_LOG_PATH = os.path.join("persistent_data", "request_log.json")

MAX_TITLE_LEN = 50
MAX_FIELD_LEN = 500
MAX_COMMENT_LEN = 200

# ====================
# Hilfsfunktionen JSON
# ====================
async def get_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_data():
    return await utils.load_json(REQUEST_DATA_PATH, {})

async def save_data(data):
    await utils.save_json(REQUEST_DATA_PATH, data)

async def get_log():
    return await utils.load_json(REQUEST_LOG_PATH, {})

async def save_log(data):
    await utils.save_json(REQUEST_LOG_PATH, data)

def nowstr():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

# ====================
# Request-Menü
# ====================

class RequestTypeSelect(discord.ui.Select):
    def __init__(self, cog):
        options = [
            discord.SelectOption(label="Custom-Anfrage", description="Individuelle Anfrage (Text, Video, Custom-Auftrag)", emoji="🎨", value="custom"),
            discord.SelectOption(label="AI Voice Anfrage", description="Künstliche Voice-Generierung (Anna/Xenia)", emoji="🗣️", value="aivoice"),
        ]
        super().__init__(placeholder="Wähle den Anfrage-Typ...", min_values=1, max_values=1, options=options)
        self.cog = cog

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        else:
            await interaction.response.send_modal(AIVoiceRequestModal(self.cog))

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(RequestTypeSelect(cog))

# ====================
# Custom Modal
# ====================

class CustomRequestModal(discord.ui.Modal, title="Neue Custom-Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            max_length=MAX_TITLE_LEN,
            required=True,
            placeholder="Name des Streamers"
        )
        self.preis = discord.ui.TextInput(
            label="Preis ($)",
            max_length=MAX_FIELD_LEN,
            required=True,
            placeholder="Wie viel gibt der Kunde?"
        )
        self.bezahlt = discord.ui.TextInput(
            label="Bezahlt?",
            max_length=20,
            required=True,
            placeholder="Ja/Nein"
        )
        self.anfrage = discord.ui.TextInput(
            label="Anfrage",
            style=discord.TextStyle.paragraph,
            max_length=MAX_FIELD_LEN,
            required=True,
            placeholder="Was soll gemacht werden?"
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Zeitgrenze",
            max_length=MAX_FIELD_LEN,
            required=True,
            placeholder="Bis wann wird es benötigt?"
        )
        self.add_item(self.streamer)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        await self.cog.create_request(
            interaction=interaction,
            typ="custom",
            streamer=self.streamer.value,
            preis=self.preis.value,
            bezahlt=self.bezahlt.value,
            anfrage=self.anfrage.value,
            zeitgrenze=self.zeitgrenze.value
        )

# ====================
# AI Voice Modal
# ====================

class AIVoiceRequestModal(discord.ui.Modal, title="Neue AI Voice-Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(
            label="Streamer",
            max_length=MAX_TITLE_LEN,
            required=True,
            placeholder="Name (z.B. Xenia, Anna)"
        )
        self.audiowunsch = discord.ui.TextInput(
            label="Audio-Wunsch",
            style=discord.TextStyle.paragraph,
            max_length=MAX_FIELD_LEN,
            required=True,
            placeholder="Was soll gesagt werden?"
        )
        self.zeitgrenze = discord.ui.TextInput(
            label="Zeitgrenze",
            max_length=MAX_FIELD_LEN,
            required=True,
            placeholder="Bis wann wird es benötigt?"
        )
        self.add_item(self.streamer)
        self.add_item(self.audiowunsch)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        await self.cog.create_request(
            interaction=interaction,
            typ="aivoice",
            streamer=self.streamer.value,
            audiowunsch=self.audiowunsch.value,
            zeitgrenze=self.zeitgrenze.value
        )

# ====================
# POST & Status Embeds
# ====================

def make_embed(data, status="active"):
    color = {
        "active": discord.Color.blurple(),
        "bearbeitet": discord.Color.yellow(),
        "abgelehnt": discord.Color.red(),
        "done": discord.Color.green(),
    }.get(status, discord.Color.default())
    title = data["streamer"][:MAX_TITLE_LEN]
    fields = []
    if data["typ"] == "custom":
        fields = [
            ("Preis", data.get("preis", "-")),
            ("Bezahlt?", data.get("bezahlt", "-")),
            ("Anfrage", data.get("anfrage", "-")),
            ("Zeitgrenze", data.get("zeitgrenze", "-")),
        ]
    else:
        fields = [
            ("Audio-Wunsch", data.get("audiowunsch", "-")),
            ("Zeitgrenze", data.get("zeitgrenze", "-")),
        ]
    embed = discord.Embed(
        title=title,
        description=f"Typ: **{'Custom' if data['typ']=='custom' else 'AI Voice'}**\nStatus: **{status.capitalize()}**\nErstellt von: <@{data['user_id']}>",
        color=color,
        timestamp=datetime.now()
    )
    for name, value in fields:
        embed.add_field(name=name, value=value[:MAX_FIELD_LEN], inline=False)
    if "kommentar" in data and data["kommentar"]:
        embed.add_field(name="Kommentar/Status", value=data["kommentar"][:MAX_COMMENT_LEN], inline=False)
    return embed

class CloseRequestView(discord.ui.View):
    def __init__(self, cog, req_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.req_id = req_id

    @discord.ui.button(label="Anfrage schließen", style=discord.ButtonStyle.red, emoji="🗑️")
    async def close_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.close_request(interaction, self.req_id)

# ========== DM Decision View ==========
class LeadDecisionView(discord.ui.View):
    def __init__(self, cog, req_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.req_id = req_id

    @discord.ui.button(label="✅ Ja, wird gemacht", style=discord.ButtonStyle.green)
    async def yes_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.update_request_status(interaction, self.req_id, "done", kommentar=None)

    @discord.ui.button(label="⚠️ Wird bearbeitet", style=discord.ButtonStyle.blurple)
    async def bearbeitet_btn(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DecisionCommentModal(self.cog, self.req_id, "bearbeitet"))

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def abgelehnt_btn(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DecisionCommentModal(self.cog, self.req_id, "abgelehnt"))

class DecisionCommentModal(discord.ui.Modal, title="Kommentar eingeben"):
    def __init__(self, cog, req_id, status):
        super().__init__()
        self.cog = cog
        self.req_id = req_id
        self.status = status
        self.kommentar = discord.ui.TextInput(
            label="Kommentar/Grund",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True,
            placeholder="Kommentar/Grund (max 200 Zeichen)"
        )
        self.add_item(self.kommentar)

    async def on_submit(self, interaction: Interaction):
        await self.cog.update_request_status(
            interaction, self.req_id, self.status, kommentar=self.kommentar.value
        )

# ====================
# Main Cog
# ====================

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========= Admin Commands =========

    @app_commands.command(name="requestmain", description="Postet das Anfrage-Panel.")
    @app_commands.guilds(MY_GUILD)
    async def requestmain(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["main_channel_id"] = channel.id
        await save_config(cfg)
        embed = discord.Embed(
            title="📝 Anfrage-System",
            description="Wähle unten eine Kategorie, um eine Anfrage zu erstellen.",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Menü gepostet in {channel.mention}!")

    @app_commands.command(name="requestaktiv", description="Setzt den Channel für aktive Requests.")
    @app_commands.guilds(MY_GUILD)
    async def requestaktiv(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["aktiv_channel_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Aktiv-Channel gesetzt: {channel.mention}")

    @app_commands.command(name="requestdone", description="Setzt den Channel für erledigte Requests.")
    @app_commands.guilds(MY_GUILD)
    async def requestdone(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["done_channel_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Done-Channel gesetzt: {channel.mention}")

    @app_commands.command(name="requestlog", description="Setzt den Logchannel für Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestlog(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["log_channel_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Logchannel gesetzt: {channel.mention}")

    @app_commands.command(name="requestcustomlead", description="Fügt einen Custom-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestcustomlead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = set(cfg.get("custom_leads", []))
        leads.add(user.id)
        cfg["custom_leads"] = list(leads)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} als Custom-Lead hinzugefügt.")

    @app_commands.command(name="requestcustomremovelead", description="Entfernt einen Custom-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestcustomremovelead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = set(cfg.get("custom_leads", []))
        if user.id in leads:
            leads.remove(user.id)
            cfg["custom_leads"] = list(leads)
            await save_config(cfg)
            await utils.send_success(interaction, f"{user.mention} als Lead entfernt.")
        else:
            await utils.send_error(interaction, "User war kein Lead.")

    @app_commands.command(name="requestailead", description="Fügt einen AI Voice-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestailead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = set(cfg.get("ai_leads", []))
        leads.add(user.id)
        cfg["ai_leads"] = list(leads)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} als AI Voice-Lead hinzugefügt.")

    @app_commands.command(name="requestairemovelead", description="Entfernt einen AI Voice-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def requestairemovelead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = set(cfg.get("ai_leads", []))
        if user.id in leads:
            leads.remove(user.id)
            cfg["ai_leads"] = list(leads)
            await save_config(cfg)
            await utils.send_success(interaction, f"{user.mention} als Lead entfernt.")
        else:
            await utils.send_error(interaction, "User war kein Lead.")

    # =====================
    # Request-Handling Core
    # =====================

    async def create_request(self, interaction: Interaction, typ, **fields):
        cfg = await get_config()
        aktiv_id = cfg.get("aktiv_channel_id")
        if not aktiv_id:
            return await utils.send_error(interaction, "Aktiv-Channel ist nicht gesetzt.")
        aktiv_channel = interaction.guild.get_channel(aktiv_id)
        if not aktiv_channel:
            return await utils.send_error(interaction, "Aktiv-Channel existiert nicht mehr.")
        # Daten speichern
        data = await get_data()
        req_id = f"{int(datetime.now().timestamp())}_{interaction.user.id}"
        request = {
            "id": req_id,
            "typ": typ,
            "status": "active",
            "user_id": interaction.user.id,
            "streamer": fields.get("streamer"),
            "zeit": nowstr(),
            "kommentar": "",
        }
        if typ == "custom":
            request.update({
                "preis": fields.get("preis"),
                "bezahlt": fields.get("bezahlt"),
                "anfrage": fields.get("anfrage"),
                "zeitgrenze": fields.get("zeitgrenze"),
            })
        else:
            request.update({
                "audiowunsch": fields.get("audiowunsch"),
                "zeitgrenze": fields.get("zeitgrenze"),
            })
        # Embed/Post
        embed = make_embed(request, status="active")
        view = CloseRequestView(self, req_id)
        msg = await aktiv_channel.send(embed=embed, view=view)
        request["message_id"] = msg.id
        data[req_id] = request
        await save_data(data)
        # Loggen
        log = await get_log()
        log.setdefault("requests", []).append({**request, "created_at": nowstr()})
        await save_log(log)
        # DM an Lead
        await self.notify_leads(interaction.guild, request)
        await interaction.response.send_message("Anfrage erstellt!", ephemeral=True)

    async def notify_leads(self, guild, request):
        cfg = await get_config()
        leads = []
        typ = request["typ"]
        if typ == "custom":
            leads = cfg.get("custom_leads", [])
        else:
            leads = cfg.get("ai_leads", [])
        if not leads:
            return
        for lead_id in leads:
            member = guild.get_member(lead_id)
            if member:
                try:
                    embed = make_embed(request, status="active")
                    await member.send(
                        content="**Neue Anfrage erhalten!**\nBitte entscheide:",
                        embed=embed,
                        view=LeadDecisionView(self, request["id"])
                    )
                except Exception:
                    pass

    async def update_request_status(self, interaction, req_id, status, kommentar=None):
        data = await get_data()
        cfg = await get_config()
        req = data.get(req_id)
        if not req:
            return await utils.send_error(interaction, "Anfrage existiert nicht mehr.")
        req["status"] = status
        if kommentar is not None:
            req["kommentar"] = kommentar
        await save_data(data)
        # Update im Aktiv/Done Channel
        aktiv_channel = interaction.guild.get_channel(cfg.get("aktiv_channel_id"))
        done_channel = interaction.guild.get_channel(cfg.get("done_channel_id"))
        # Embed+Status+Color updaten
        embed = make_embed(req, status=status)
        try:
            if "message_id" in req and aktiv_channel:
                msg = await aktiv_channel.fetch_message(req["message_id"])
                await msg.edit(embed=embed, view=CloseRequestView(self, req_id) if status != "done" else None)
        except Exception:
            pass
        # Notification an Ersteller
        user = interaction.guild.get_member(req["user_id"])
        if user:
            try:
                txt = {
                    "done": "✅ Deine Anfrage wurde **angenommen**!",
                    "bearbeitet": "⚠️ Deine Anfrage ist **in Bearbeitung**.",
                    "abgelehnt": "❌ Deine Anfrage wurde **abgelehnt**.",
                }.get(status, "Anfrage-Status geändert.")
                await user.send(
                    f"{txt}\nStreamer: **{req['streamer']}**\nKommentar: {kommentar or '-'}"
                )
            except Exception:
                pass
        # Kommentar posten (optional als Kommentar, wenn du willst)
        # Bei „done“ → In Done-Channel verschieben
        if status == "done" and done_channel:
            embed = make_embed(req, status="done")
            await done_channel.send(embed=embed)
            try:
                # Lösche aus aktiv-channel
                if "message_id" in req:
                    msg = await aktiv_channel.fetch_message(req["message_id"])
                    await msg.delete()
            except Exception:
                pass
        await utils.send_success(interaction, f"Status geändert auf {status.capitalize()}.")

    async def close_request(self, interaction, req_id):
        data = await get_data()
        cfg = await get_config()
        req = data.pop(req_id, None)
        await save_data(data)
        done_channel = interaction.guild.get_channel(cfg.get("done_channel_id"))
        if req and done_channel:
            embed = make_embed(req, status=req["status"])
            await done_channel.send(embed=embed)
        # Lösche aus aktiv-channel
        aktiv_channel = interaction.guild.get_channel(cfg.get("aktiv_channel_id"))
        try:
            if req and "message_id" in req and aktiv_channel:
                msg = await aktiv_channel.fetch_message(req["message_id"])
                await msg.delete()
        except Exception:
            pass
        await utils.send_success(interaction, "Anfrage geschlossen und archiviert.")

# ============= Setup =============
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
