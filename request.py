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

def make_status_embed(data, status="active", comment=None):
    color = {
        "active": discord.Color.yellow(),
        "in_progress": discord.Color.orange(),
        "done": discord.Color.green(),
        "rejected": discord.Color.red()
    }[status]
    title = f"{data['streamer']} - {'Aktiv' if status == 'active' else 'In Bearbeitung' if status=='in_progress' else 'Erledigt' if status=='done' else 'Abgelehnt'}"
    desc = data['body']
    embed = discord.Embed(title=title, description=desc, color=color)
    if comment:
        embed.add_field(name="Kommentar", value=comment, inline=False)
    return embed

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

    # ========== POST-SYSTEM MIT STATUS ==========
    async def post_request(self, interaction, data, typ):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        done_forum_id = config.get("done_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        done_forum = interaction.guild.get_channel(done_forum_id) if done_forum_id else None

        embed = make_status_embed(data, "active")
        post = await forum.create_thread(
            name=data["streamer"][:MAX_TITLE_LEN],
            content=None,
        )
        msg = await post.send(embed=embed, view=CloseRequestView(self, post, data, done_forum))
        data["body"] = embed.description

        # LEAD DMs mit Button
        leads = await get_leads()
        key = "custom" if typ == "custom" else "ai"
        for uid in leads[key]:
            lead = interaction.guild.get_member(uid)
            if lead:
                try:
                    await lead.send(
                        f"Neue **{'Custom' if typ=='custom' else 'AI Voice'} Anfrage** von {interaction.user.mention}:\n\n{embed.description}\n\n[Zum Thread]({post.jump_url})",
                        embed=embed,
                        view=LeadActionView(self, post, data, interaction.user, done_forum)
                    )
                except Exception:
                    pass

        await utils.send_success(interaction, "Deine Anfrage wurde erstellt!")

    async def change_status(self, post, data, status, user, done_forum, comment=None):
        embed = make_status_embed(data, status, comment=comment)
        msgs = [m async for m in post.history(limit=10)]
        if msgs:
            await msgs[0].edit(embed=embed)
        if status in ["done", "rejected"] and done_forum:
            new_post = await done_forum.create_thread(
                name=data["streamer"][:MAX_TITLE_LEN],
                content=None,
            )
            await new_post.send(embed=embed)
            await post.edit(archived=True, locked=True)
        if user:
            try:
                await user.send(
                    f"Status deiner Anfrage **{data['streamer']}**: {'Erledigt' if status=='done' else 'Abgelehnt' if status=='rejected' else 'In Bearbeitung'}\n{f'Kommentar: {comment}' if comment else ''}"
                )
            except Exception:
                pass

class CloseRequestView(discord.ui.View):
    def __init__(self, cog, post, data, done_forum):
        super().__init__(timeout=None)
        self.cog = cog
        self.post = post
        self.data = data
        self.done_forum = done_forum

    @discord.ui.button(label="Anfrage schließen", style=discord.ButtonStyle.grey, emoji="📦")
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.change_status(self.post, self.data, "done", None, self.done_forum)
        await utils.send_success(interaction, "Anfrage wurde geschlossen und nach Done verschoben.")

class LeadActionView(discord.ui.View):
    def __init__(self, cog, post, data, anfrager, done_forum):
        super().__init__(timeout=None)
        self.cog = cog
        self.post = post
        self.data = data
        self.anfrager = anfrager
        self.done_forum = done_forum

    @discord.ui.button(label="✅ Genehmigen", style=discord.ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.change_status(self.post, self.data, "done", self.anfrager, self.done_forum)
        await utils.send_success(interaction, "Genehmigt & nach Done verschoben.")

    @discord.ui.button(label="🟡 In Bearbeitung", style=discord.ButtonStyle.blurple)
    async def progress(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StatusModal(self.cog, self.post, self.data, self.anfrager, self.done_forum, "in_progress"))

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def reject(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StatusModal(self.cog, self.post, self.data, self.anfrager, self.done_forum, "rejected"))

class StatusModal(discord.ui.Modal, title="Status ändern"):
    def __init__(self, cog, post, data, anfrager, done_forum, status):
        super().__init__()
        self.cog = cog
        self.post = post
        self.data = data
        self.anfrager = anfrager
        self.done_forum = done_forum
        self.status = status
        self.comment = discord.ui.TextInput(
            label="Kommentar/Begründung (max 200 Zeichen)",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: Interaction):
        await self.cog.change_status(self.post, self.data, self.status, self.anfrager, self.done_forum, self.comment.value)
        await utils.send_success(interaction, "Status & Kommentar gespeichert.")

class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(RequestTypeDropdown(self.cog))

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
            "body": (
                f"**Streamer:** {self.streamer.value}\n"
                f"**Preis:** {self.preis.value}\n"
                f"**Bezahlt?** {self.bezahlt.value}\n"
                f"**Anfrage:** {self.anfrage.value}\n"
                f"**Zeitgrenze:** {self.zeitgrenze.value}"
            ),
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
            "body": (
                f"**Streamer:** {self.streamer.value}\n"
                f"**Audio Wunsch:** {self.audiowunsch.value}\n"
                f"**Zeitgrenze:** {self.zeitgrenze.value}"
            ),
        }
        await self.cog.post_request(interaction, data, "ai")

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
