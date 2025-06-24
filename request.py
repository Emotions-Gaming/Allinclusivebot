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

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        view = RequestMenuView()
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

class RequestMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RequestTypeDropdown())

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Custom Anfrage", value="custom", description="Stelle eine individuelle Anfrage"),
            discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice Custom anfragen"),
        ]
        super().__init__(placeholder="Wähle eine Anfrage-Art…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        # Show Modal je nach Anfrage-Typ
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal())
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal())

# ========== Modals ==========

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
    preis = discord.ui.TextInput(label="Preis (z. B. 400€)", max_length=20, required=True)
    bezahlt = discord.ui.TextInput(label="Bezahlt?", placeholder="Ja/Nein", max_length=10, required=True)
    anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
    zeitgrenze = discord.ui.TextInput(label="Zeitgrenze (z. B. bis Sonntag)", max_length=40, required=True)

    async def on_submit(self, interaction: Interaction):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        # Thread/Post erstellen im Forum
        title = f"{self.streamer.value[:MAX_TITLE_LEN]}"
        body = (
            f"**Streamer:** {self.streamer.value}\n"
            f"**Preis:** {self.preis.value}\n"
            f"**Bezahlt?** {self.bezahlt.value}\n"
            f"**Anfrage:** {self.anfrage.value}\n"
            f"**Zeitgrenze:** {self.zeitgrenze.value}"
        )
        # ==== FIX: content=body (vorher fehlte content oder war None!) ====
        thread = await forum.create_thread(
            name=title,
            content=body,    # <--- FIX HIER!
            applied_tags=[],
        )
        # Leads pingen (DM)
        leads = await get_leads()
        mentions = [interaction.guild.get_member(uid).mention for uid in leads["custom"] if interaction.guild.get_member(uid)]
        if mentions:
            for uid in leads["custom"]:
                lead = interaction.guild.get_member(uid)
                if lead:
                    try:
                        await lead.send(
                            f"Neue **Custom Anfrage** von {interaction.user.mention}:\n\n{body}\n\n"
                            f"[Zum Thread]({thread.jump_url})"
                        )
                    except Exception:
                        pass
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
    audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
    zeitgrenze = discord.ui.TextInput(label="Zeitgrenze", max_length=40, required=True)

    async def on_submit(self, interaction: Interaction):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        title = f"{self.streamer.value[:MAX_TITLE_LEN]}"
        body = (
            f"**Streamer:** {self.streamer.value}\n"
            f"**Audio Wunsch:** {self.audiowunsch.value}\n"
            f"**Zeitgrenze:** {self.zeitgrenze.value}"
        )
        # ==== FIX: content=body ====
        thread = await forum.create_thread(
            name=title,
            content=body,     # <--- FIX HIER!
            applied_tags=[],
        )
        leads = await get_leads()
        if leads["ai"]:
            for uid in leads["ai"]:
                lead = interaction.guild.get_member(uid)
                if lead:
                    try:
                        await lead.send(
                            f"Neue **AI Voice Anfrage** von {interaction.user.mention}:\n\n{body}\n\n"
                            f"[Zum Thread]({thread.jump_url})"
                        )
                    except Exception:
                        pass
        await utils.send_success(interaction, "Deine AI Voice Anfrage wurde erstellt!")

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
