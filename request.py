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
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen":      "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung":"🟨 In Bearbeitung",
    "abgelehnt":  "🟥 Abgelehnt",
    "geschlossen":"🛑 Geschlossen"
}
STATUS_ICONS = {
    "offen":      "🟦",
    "angenommen": "🟩",
    "bearbeitung":"🟨",
    "abgelehnt":  "🟥",
    "geschlossen":"🛑"
}

def build_thread_title(status, streamer, username, typ, nr):
    # [Status] - [Streamer] - [Username] - [Typ] - #Nr
    st = STATUS_DISPLAY.get(status, "Offen")
    return f"[{st.split()[1]}] - {streamer} - {username} - {typ.capitalize()} - #{nr}"

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    icon = STATUS_ICONS.get(status, "📩")
    title = f"{icon} {data['streamer']}" if data.get("streamer") else "Anfrage"
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"💰 **Preis:** `{data['preis']}`\n"
            f"💸 **Bezahlt?** `{data['bezahlt']}`\n"
            f"📝 **Anfrage:**\n> {data['anfrage']}\n"
            f"⏰ **Zeitgrenze:** `{data['zeitgrenze']}`"
        )
    elif data["type"] == "ai":
        desc = (
            f"🎤 **Audio Wunsch:**\n> {data['audiowunsch']}\n"
            f"⏰ **Zeitgrenze:** `{data['zeitgrenze']}`"
        )
    status_str = STATUS_DISPLAY.get(status, "🟦 Offen")
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {status_str}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            description=(
                "**Wähle eine Option, um eine neue Anfrage zu stellen:**\n"
                "• `Custom Anfrage`: Erstelle einen individuellen Wunsch (z.B. Video, Clip...)\n"
                "• `AI Voice Anfrage`: KI-Stimmenanfrage (⚠️ Nur für Mila & Xenia, max. 10 Sek. Text!)"
            ),
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

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

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data['nr'] = nr
        title = build_thread_title("offen", data['streamer'], str(interaction.user), reqtype, nr)
        thread_with_message = await forum.create_thread(
            name=title,
            content="Neue Anfrage erstellt.",
            applied_tags=[],
        )
        channel = thread_with_message.thread
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        embed = build_embed(data, status="offen")
        view = CloseRequestView(self, data, channel)
        await channel.send(embed=embed, view=view)
        await self.send_lead_dm(interaction, data, channel, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread_channel, reqtype):
        leads = await get_leads()
        ids = leads["custom"] if reqtype == "custom" else leads["ai"]
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"**{'📝 Custom Anfrage' if reqtype == 'custom' else '🎤 AI Voice Anfrage'}** von {interaction.user.mention}\n"
                        f"👤 **Streamer:** `{data['streamer']}`\n"
                    )
                    if reqtype == "custom":
                        msg += (
                            f"💰 **Preis:** `{data['preis']}`\n"
                            f"💸 **Bezahlt?** `{data['bezahlt']}`\n"
                            f"📝 **Anfrage:** {data['anfrage']}\n"
                            f"⏰ **Zeitgrenze:** `{data['zeitgrenze']}`\n"
                        )
                    else:
                        msg += (
                            f"🎤 **Audio Wunsch:** {data['audiowunsch']}\n"
                            f"⏰ **Zeitgrenze:** `{data['zeitgrenze']}`\n"
                        )
                    msg += f"\n[➡️ Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

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
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog))
        self.values = []  # Reset selection, damit Dropdown nach Auswahl wieder frei ist

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
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

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
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

# ========== Schließ-Button & Backup-Log ==========

class CloseRequestView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    @discord.ui.button(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        all_threads = done_forum.threads
        nr = len(all_threads) + 1
        self.data['nr'] = nr

        # Chat-Backup bauen – schön formatiert:
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            # Nur Nutzernachrichten und nur mit Inhalt
            if msg.content.strip():
                display_name = msg.author.display_name
                icon = ""
                # Farbig & fett für abgelehnt, angenommen, usw.
                if msg.author.bot:
                    continue  # Bot-Einträge ausblenden, schöneres Log!
                messages.append(f"> **{display_name}:** {msg.content}")

        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = (
            f"**{last_status} Finaler Status**\n\n"
            + "\n".join(messages) if messages else "*Kein Chatverlauf.*"
        )
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
            discord.SelectOption(label="Status: Offen", value="offen", emoji="🟦"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen", emoji="🟩"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung", emoji="🟨"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt", emoji="🟥"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen", emoji="🛑"),
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=new_status)
        await self.thread_channel.send(embed=embed)
        guild = self.thread_channel.guild
        ersteller = guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"**Update zu deiner Anfrage `{self.data['streamer']}`:**\nStatus geändert zu: **{STATUS_DISPLAY.get(new_status, new_status)}**"
                )
            except Exception:
                pass
        await interaction.response.send_message("Status wurde geändert.", ephemeral=True)

# ========== Setup ==========
async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

async def setup(bot):
    await bot.add_cog(RequestCog(bot))
