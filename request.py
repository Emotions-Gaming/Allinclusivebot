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
    "geschlossen": discord.Color.dark_grey()
}

# Lead DM Tracking (RAM only)
lead_dm_messages = {}  # {thread_id: {lead_id: message_id}}

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen"):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data['streamer']}" if data.get("streamer") else "Anfrage"
    desc = ""
    if data["type"] == "custom":
        desc = (
            f"**Preis:** {data['preis']}\n"
            f"**Bezahlt?** {data['bezahlt']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "ai":
        desc = (
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    status_str = {
        "offen": "🟦 Offen",
        "angenommen": "🟩 Angenommen",
        "bearbeitung": "🟨 In Bearbeitung",
        "abgelehnt": "🟥 Abgelehnt",
        "geschlossen": "🛑 Geschlossen"
    }[status]
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {status_str}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

def format_backup(messages):
    # Macht aus Message-Log ein ordentliches kompaktes Backup mit Markdown und Zeit
    out = []
    for m in messages:
        author = f"**{m.author.display_name}**"
        t = m.created_at.strftime("%d.%m.%Y, %H:%M")
        if m.embeds and m.embeds[0].description:
            content = f"{m.content}\n{m.embeds[0].description}".strip()
        else:
            content = m.content
        content = content or "_(leer)_"
        out.append(f"> {author} `{t}`:\n{content}")
    return "\n\n".join(out) if out else "_Keine Nachrichten_"

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_menu_messages = {}  # {channel_id: message_id}

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
        view = RequestMenuView(self, channel)
        msg = await channel.send(embed=embed, view=view)
        self.active_menu_messages[channel.id] = msg.id
        await utils.send_success(interaction, f"Anfrage-Menü in {channel.mention} gepostet!")

    async def refresh_request_menu(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="📩 Anfrage-System",
            description="Wähle eine Option, um eine neue Anfrage zu stellen.",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self, channel)
        msg_id = self.active_menu_messages.get(channel.id)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
            except Exception:
                msg = await channel.send(embed=embed, view=view)
                self.active_menu_messages[channel.id] = msg.id
        else:
            msg = await channel.send(embed=embed, view=view)
            self.active_menu_messages[channel.id] = msg.id

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
    async def post_request(self, interaction, data, reqtype, menu_channel=None):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        title = f"{data['streamer'][:MAX_TITLE_LEN]}"
        thread = await forum.create_thread(
            name=title,
            content="Neue Anfrage erstellt.",
            applied_tags=[],
        )
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        embed = build_embed(data, status="offen")
        view = CloseRequestView(self, data, thread)
        first_msg = await thread.fetch_message(thread.id)
        await first_msg.edit(embed=embed, view=view)
        data["thread_id"] = thread.id
        await self.send_lead_dm(interaction, data, thread, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")
        # Menu refresher nach Modal!
        if menu_channel:
            await self.refresh_request_menu(menu_channel)

    async def send_lead_dm(self, interaction, data, thread, reqtype):
        leads = await get_leads()
        ids = leads["custom"] if reqtype == "custom" else leads["ai"]
        lead_dm_messages[thread.id] = {}
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    view = RequestActionView(self, data, thread)
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
                            f"**Audio Wunsch:** {data['audiowunsch']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    msg += f"[Zum Thread]({thread.jump_url})"
                    dm = await lead.send(msg, view=view)
                    lead_dm_messages[thread.id][uid] = dm.id
                except Exception:
                    pass

    async def move_to_done(self, guild, thread, data):
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return False
        done_forum = guild.get_channel(done_forum_id)
        # Backup: Nachrichten holen
        messages = []
        async for msg in thread.history(limit=100, oldest_first=True):
            messages.append(msg)
        log_text = format_backup(messages)
        closed_thread = await done_forum.create_thread(
            name=thread.name,
            content=f"__**Abgeschlossene Anfrage:**__\n\n{log_text}",
            applied_tags=[],
        )
        return closed_thread

class RequestMenuView(discord.ui.View):
    def __init__(self, cog, menu_channel=None):
        super().__init__(timeout=None)
        self.cog = cog
        self.menu_channel = menu_channel

    @discord.ui.select(
        placeholder="Wähle eine Anfrage-Art…",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen"),
        ]
    )
    async def select_callback(self, interaction: Interaction, select: discord.ui.Select):
        if select.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog, self.menu_channel))
        elif select.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal(self.cog, self.menu_channel))

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog, menu_channel=None):
        super().__init__()
        self.cog = cog
        self.menu_channel = menu_channel
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
        await self.cog.post_request(interaction, data, "custom", self.menu_channel)

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog, menu_channel=None):
        super().__init__()
        self.cog = cog
        self.menu_channel = menu_channel
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
        await self.cog.post_request(interaction, data, "ai", self.menu_channel)

class RequestActionView(discord.ui.View):
    def __init__(self, cog, data, thread):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread = thread

    @discord.ui.button(label="Genehmigen", style=discord.ButtonStyle.success)
    async def approve(self, interaction: Interaction, button: discord.ui.Button):
        await self.change_status(interaction, "angenommen")

    @discord.ui.button(label="Bearbeitung", style=discord.ButtonStyle.primary)
    async def processing(self, interaction: Interaction, button: discord.ui.Button):
        await self.change_status(interaction, "bearbeitung")

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: discord.ui.Button):
        modal = DeclineReasonModal(self.cog, self.data, self.thread, interaction.user.id)
        await interaction.response.send_modal(modal)

    async def change_status(self, interaction, status):
        embed = build_embed(self.data, status=status)
        # Post in Thread
        await self.thread.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        # DM an den Antragsteller
        creator = self.thread.guild.get_member(self.data["erstellerid"])
        if creator:
            try:
                await creator.send(f"Deine Anfrage **{self.data['streamer']}** hat jetzt den Status: **{status.capitalize()}**.")
            except Exception:
                pass
        await interaction.response.send_message(f"Status zu **{status}** geändert.", ephemeral=True)

class DeclineReasonModal(discord.ui.Modal, title="Ablehnungsgrund angeben"):
    def __init__(self, cog, data, thread, lead_user_id):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread = thread
        self.lead_user_id = lead_user_id
        self.reason = discord.ui.TextInput(
            label="Grund für Ablehnung",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        embed = build_embed(self.data, status="abgelehnt")
        embed.add_field(name="Ablehnungsgrund", value=self.reason.value, inline=False)
        await self.thread.send(
            content=f"Status geändert von {interaction.user.mention}:",
            embed=embed
        )
        creator = self.thread.guild.get_member(self.data["erstellerid"])
        if creator:
            try:
                await creator.send(f"Deine Anfrage **{self.data['streamer']}** wurde **abgelehnt**.\nGrund: {self.reason.value}")
            except Exception:
                pass
        # Lösche Lead-DM, wenn vorhanden
        try:
            msg_id = lead_dm_messages.get(self.thread.id, {}).get(self.lead_user_id)
            if msg_id:
                lead = self.thread.guild.get_member(self.lead_user_id)
                if lead:
                    dm = await lead.create_dm()
                    msg = await dm.fetch_message(msg_id)
                    await msg.delete()
        except Exception:
            pass
        await interaction.response.send_message("Anfrage abgelehnt und Grund gepostet.", ephemeral=True)

class CloseRequestView(discord.ui.View):
    def __init__(self, cog, data, thread):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread = thread

    @discord.ui.button(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        is_creator = user_id == self.data["erstellerid"]
        leads = await get_leads()
        is_lead = user_id in leads["custom"] or user_id in leads["ai"]
        if not (is_creator or is_lead):
            return await interaction.response.send_message("Nur der Ersteller oder ein Lead darf schließen.", ephemeral=True)
        done_thread = await self.cog.move_to_done(interaction.guild, self.thread, self.data)
        # Chatverlauf-Backup ist im Thread in "done"!
        await self.thread.edit(archived=True, locked=True)
        try:
            await interaction.response.send_message("Anfrage als erledigt verschoben.", ephemeral=True)
        except Exception:
            pass

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
