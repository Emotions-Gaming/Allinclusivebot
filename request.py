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

# Farben für Status
COLOR_ACTIVE = discord.Color.blurple()
COLOR_ACCEPTED = discord.Color.green()
COLOR_INPROGRESS = discord.Color.yellow()
COLOR_DECLINED = discord.Color.red()
COLOR_DONE = discord.Color.dark_grey()

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

# ========== Menü-View ==========
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
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal())
        elif self.values[0] == "ai":
            await interaction.response.send_modal(AIRequestModal())

# ========== Modals & Workflow ==========

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
        title = f"{self.streamer.value[:MAX_TITLE_LEN]}"
        body = (
            f"**Streamer:** {self.streamer.value}\n"
            f"**Preis:** {self.preis.value}\n"
            f"**Bezahlt?** {self.bezahlt.value}\n"
            f"**Anfrage:** {self.anfrage.value}\n"
            f"**Zeitgrenze:** {self.zeitgrenze.value}"
        )
        # Schönes Embed für Thread!
        embed = discord.Embed(
            title=title,
            description=body,
            color=COLOR_ACTIVE
        )
        embed.set_footer(text="Status: Offen")
        # Thread/Post erstellen im Forum (content muss gesetzt werden, aber Embed ist schöner)
        thread = await forum.create_thread(
            name=title,
            content=" ",  # muss gesetzt sein
            applied_tags=[],
        )
        # Initiale Embed-Nachricht im Thread + Schließen-Button
        view = CloseRequestView(thread, interaction.user, is_ai=False)
        post_message = await thread.send(embed=embed, view=view)
        # Leads pingen (DM mit Buttons)
        leads = await get_leads()
        for uid in leads["custom"]:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    await lead.send(
                        embed=discord.Embed(
                            title="Neue Custom Anfrage",
                            description=f"Von: {interaction.user.mention}\n\n{body}\n\n[Zum Thread]({thread.jump_url})",
                            color=COLOR_ACTIVE
                        ),
                        view=LeadActionView(post_message, thread, interaction.user, is_ai=False)
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
        embed = discord.Embed(
            title=title,
            description=body,
            color=COLOR_ACTIVE
        )
        embed.set_footer(text="Status: Offen")
        thread = await forum.create_thread(
            name=title,
            content=" ",  # muss gesetzt sein!
            applied_tags=[],
        )
        view = CloseRequestView(thread, interaction.user, is_ai=True)
        post_message = await thread.send(embed=embed, view=view)
        leads = await get_leads()
        for uid in leads["ai"]:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    await lead.send(
                        embed=discord.Embed(
                            title="Neue AI Voice Anfrage",
                            description=f"Von: {interaction.user.mention}\n\n{body}\n\n[Zum Thread]({thread.jump_url})",
                            color=COLOR_ACTIVE
                        ),
                        view=LeadActionView(post_message, thread, interaction.user, is_ai=True)
                    )
                except Exception:
                    pass
        await utils.send_success(interaction, "Deine AI Voice Anfrage wurde erstellt!")

# ========== Button-Views ==========

class CloseRequestView(discord.ui.View):
    def __init__(self, thread, requester, is_ai):
        super().__init__(timeout=None)
        self.thread = thread
        self.requester = requester
        self.is_ai = is_ai

    @discord.ui.button(label="❌ Anfrage schließen", style=discord.ButtonStyle.red)
    async def close_btn(self, interaction: Interaction, button: discord.ui.Button):
        # Markiere Thread als erledigt (optional: ins Done-Forum verschieben)
        embed = interaction.message.embeds[0].copy()
        embed.color = COLOR_DONE
        embed.set_footer(text="Status: Geschlossen")
        await interaction.message.edit(embed=embed, view=None)
        await self.thread.send("Anfrage wurde als **geschlossen** markiert.")
        await utils.send_success(interaction, "Anfrage geschlossen!")

class LeadActionView(discord.ui.View):
    def __init__(self, post_message, thread, requester, is_ai):
        super().__init__(timeout=600)
        self.post_message = post_message
        self.thread = thread
        self.requester = requester
        self.is_ai = is_ai

    @discord.ui.button(label="✅ Annehmen", style=discord.ButtonStyle.green)
    async def accept_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.update_status(interaction, "Angenommen", COLOR_ACCEPTED, "Anfrage wurde **angenommen**.")
    @discord.ui.button(label="⏳ In Bearbeitung", style=discord.ButtonStyle.blurple)
    async def progress_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.ask_for_reason(interaction, "In Bearbeitung", COLOR_INPROGRESS)
    @discord.ui.button(label="🚫 Ablehnen", style=discord.ButtonStyle.red)
    async def decline_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.ask_for_reason(interaction, "Abgelehnt", COLOR_DECLINED)

    async def ask_for_reason(self, interaction, status_text, color):
        modal = ReasonModal(self, status_text, color)
        await interaction.response.send_modal(modal)

    async def update_status(self, interaction, status_text, color, reason_msg=None):
        embed = self.post_message.embeds[0].copy()
        embed.color = color
        embed.set_footer(text=f"Status: {status_text}")
        await self.post_message.edit(embed=embed)
        await self.thread.send(f"{reason_msg or status_text} – entschieden von {interaction.user.mention}")
        try:
            await self.requester.send(f"Deine Anfrage `{self.thread.name}` wurde als **{status_text}** markiert.")
        except Exception:
            pass
        await utils.send_success(interaction, f"Status gesetzt: {status_text}")

class ReasonModal(discord.ui.Modal, title="Begründung angeben"):
    reason = discord.ui.TextInput(label="Begründung", max_length=MAX_COMMENT_LEN, required=True)
    def __init__(self, view, status_text, color):
        super().__init__()
        self.view = view
        self.status_text = status_text
        self.color = color
    async def on_submit(self, interaction: Interaction):
        await self.view.update_status(
            interaction,
            self.status_text,
            self.color,
            f"Status geändert: **{self.status_text}**\nBegründung: {self.reason.value}"
        )

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
