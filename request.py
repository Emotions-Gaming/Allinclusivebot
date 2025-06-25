# request.py

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
MAX_COMMENT_LEN = 200

STATUS_COLORS = {
    "offen": discord.Color.blurple(),
    "angenommen": discord.Color.green(),
    "bearbeitung": discord.Color.gold(),
    "abgelehnt": discord.Color.red(),
    "geschlossen": discord.Color.dark_grey()
}

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
    if data["type"] == "custom":
        desc = (
            f"**Preis:** {data['preis']}\n"
            f"**Bezahlt?** {data['bezahlt']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    else:
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
        description=desc + "\n\n**Status:** " + status_str,
        color=color
    )
    embed.set_footer(text=f"Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
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
        await utils.send_success(interaction, f"Aktive Anfragen-Forum gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetdone", description="Setzt das Forum für erledigte Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetdone(self, interaction: Interaction, channel: discord.ForumChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        config = await get_request_config()
        config["done_forum"] = channel.id
        await save_request_config(config)
        await utils.send_success(interaction, f"Done-Forum gesetzt: {channel.mention}")

    @app_commands.command(name="requestmain", description="Postet das Anfrage-Menü (nur Textkanäle!)")
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
        await utils.send_success(interaction, f"Anfrage-Menü gepostet in {channel.mention}")

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
        title = data["streamer"][:MAX_TITLE_LEN]
        thread = await forum.create_thread(name=title, content="Neue Anfrage erstellt.", applied_tags=[])
        data.update({
            "type": reqtype,
            "status": "offen",
            "erstellerid": interaction.user.id,
            "erstellername": str(interaction.user)
        })
        embed = build_embed(data, "offen")
        view = CloseRequestView(self, data, thread)
        # Benutze thread.send_message auf discord.py ≥2.5
        await thread.send_message(embed=embed, view=view)
        await self.send_lead_dm(interaction, data, thread, reqtype)
        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def send_lead_dm(self, interaction, data, thread, reqtype):
        leads = await get_leads()
        ids = leads["custom"] if reqtype == "custom" else leads["ai"]
        for uid in ids:
            lead = interaction.guild.get_member(uid)
            if not lead: continue
            view = RequestActionView(self, data, thread)
            content = (
                f"Neue **{'Custom' if reqtype=='custom' else 'AI Voice'}** Anfrage von {interaction.user.mention}\n"
                f"**Streamer:** {data['streamer']}\n"
            )
            if reqtype == "custom":
                content += (
                    f"**Preis:** {data['preis']}\n"
                    f"**Bezahlt?** {data['bezahlt']}\n"
                    f"**Anfrage:** {data['anfrage']}\n"
                )
            else:
                content += f"**Audio Wunsch:** {data['audiowunsch']}\n"
            content += f"**Zeitgrenze:** {data['zeitgrenze']}\n[Zum Thread]({thread.jump_url})"
            try:
                await lead.send(content, view=view)
            except:
                pass

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(RequestTypeDropdown(cog))

class RequestTypeDropdown(discord.ui.Select):
    def __init__(self, cog):
        super().__init__(
            placeholder="Wähle Anfrage-Art…",
            options=[
                discord.SelectOption(label="Custom Anfrage", value="custom", description="Individuell"),
                discord.SelectOption(label="AI Voice Anfrage", value="ai", description="AI Voice")
            ]
        )
        self.cog = cog

    async def callback(self, interaction: Interaction):
        if self.values[0] == "custom":
            await interaction.response.send_modal(CustomRequestModal(self.cog))
        else:
            await interaction.response.send_modal(AIRequestModal(self.cog))

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.preis = discord.ui.TextInput(label="Preis", max_length=20)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt?", max_length=10)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze", max_length=40)
        for item in [self.streamer, self.preis, self.bezahlt, self.anfrage, self.zeitgrenze]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "custom")

class AIRequestModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.audiowunsch = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze", max_length=40)
        for item in [self.streamer, self.audiowunsch, self.zeitgrenze]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction):
        data = {
            "streamer": self.streamer.value,
            "audiowunsch": self.audiowunsch.value,
            "zeitgrenze": self.zeitgrenze.value
        }
        await self.cog.post_request(interaction, data, "ai")

class RequestActionView(discord.ui.View):
    def __init__(self, cog, data, thread):
        super().__init__(timeout=None)
        self.cog = cog; self.data = data; self.thread = thread

    @discord.ui.button(label="✅ Genehmigen", style=discord.ButtonStyle.success)
    async def approve(self, interaction: Interaction, button):
        await self._change_status(interaction, "angenommen")

    @discord.ui.button(label="🟨 In Bearbeitung", style=discord.ButtonStyle.primary)
    async def processing(self, interaction: Interaction, button):
        await self._change_status(interaction, "bearbeitung")

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button):
        await interaction.response.send_modal(DeclineReasonModal(self.cog, self.data, self.thread))

    async def _change_status(self, interaction, status):
        embed = build_embed(self.data, status)
        await self.thread.send(content=f"Status geändert von {interaction.user.mention}", embed=embed)
        await utils.send_success(interaction, f"Status zu **{status}** geändert.")

class DeclineReasonModal(discord.ui.Modal, title="Ablehnungsgrund"):
    def __init__(self, cog, data, thread):
        super().__init__()
        self.data = data; self.thread = thread
        self.reason = discord.ui.TextInput(label="Grund", style=discord.TextStyle.paragraph, max_length=MAX_COMMENT_LEN)
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        embed = build_embed(self.data, "abgelehnt")
        embed.add_field(name="Grund", value=self.reason.value, inline=False)
        await self.thread.send(content=f"Ablehnung von {interaction.user.mention}", embed=embed)
        await utils.send_success(interaction, "Anfrage abgelehnt.")

class CloseRequestView(discord.ui.View):
    def __init__(self, cog, data, thread):
        super().__init__(timeout=None)
        self.cog = cog; self.data = data; self.thread = thread

    @discord.ui.button(label="🔒 Anfrage schließen", style=discord.ButtonStyle.danger)
    async def close(self, interaction: Interaction, button):
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        title = self.data["streamer"][:MAX_TITLE_LEN]
        closed = await done_forum.create_thread(name=title, content="Erledigte Anfrage.", applied_tags=[])
        await closed.send(embed=build_embed(self.data, "geschlossen"))
        await self.thread.edit(archived=True, locked=True)
        await utils.send_success(interaction, "Anfrage geschlossen und verschoben.")

async def setup(bot):
    await bot.add_cog(RequestCog(bot))
