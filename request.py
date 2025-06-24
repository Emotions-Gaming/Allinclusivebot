import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
MAX_TITLE_LEN = 80
MAX_DESC_LEN = 500
MAX_COMMENT_LEN = 200

# ======= Helper =======
async def get_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

def make_status_color(status):
    # "active", "done", "rejected", "progress"
    colors = {
        "active": discord.Color.yellow(),
        "done": discord.Color.green(),
        "progress": discord.Color.orange(),
        "rejected": discord.Color.red()
    }
    return colors.get(status, discord.Color.greyple())

def make_request_embed(data, status="active", extra_comment=None):
    embed = discord.Embed(
        title=data.get("streamer", "Anfrage"),
        description=data.get("desc", ""),
        color=make_status_color(status)
    )
    if data.get("type") == "custom":
        embed.add_field(name="Preis", value=f"{data['preis']} €", inline=True)
        embed.add_field(name="Bezahlt?", value=data["bezahlt"], inline=True)
        embed.add_field(name="Deadline", value=data["deadline"], inline=True)
        embed.add_field(name="Anfrage", value=data["anfrage"], inline=False)
    else: # ai
        embed.add_field(name="Streamer", value=data["streamer"], inline=True)
        embed.add_field(name="Audio-Wunsch", value=data["audio"], inline=False)
        embed.add_field(name="Deadline", value=data["deadline"], inline=True)
    embed.set_footer(text=f"Status: {status.capitalize()}")
    if extra_comment:
        embed.add_field(name="Kommentar", value=extra_comment, inline=False)
    return embed

# ======= Views =======
class CloseRequestButton(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=None)
        self.callback_func = callback

    @discord.ui.button(label="Anfrage schließen", style=discord.ButtonStyle.grey, emoji="📦")
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        await self.callback_func(interaction)

class LeadDMView(discord.ui.View):
    def __init__(self, accept_cb, reject_cb, progress_cb):
        super().__init__(timeout=None)
        self.accept_cb = accept_cb
        self.reject_cb = reject_cb
        self.progress_cb = progress_cb

    @discord.ui.button(label="✅ Genehmigen", style=discord.ButtonStyle.green)
    async def approve(self, interaction: Interaction, button: discord.ui.Button):
        await self.accept_cb(interaction)

    @discord.ui.button(label="🟡 In Bearbeitung", style=discord.ButtonStyle.blurple)
    async def progress(self, interaction: Interaction, button: discord.ui.Button):
        await self.progress_cb(interaction)

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def deny(self, interaction: Interaction, button: discord.ui.Button):
        await self.reject_cb(interaction)

# ======= Cog =======
class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== Setup-Kommandos ==========
    @app_commands.command(name="requestsetactive", description="Setze den Channel für aktive Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetactive(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["active_channel"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Aktiv-Channel gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetdone", description="Setze den Channel für erledigte Anfragen.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetdone(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["done_channel"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Done-Channel gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetcustomlead", description="Füge einen Lead für Customs hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetcustomlead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = cfg.get("custom_leads", [])
        if user.id not in leads:
            leads.append(user.id)
        cfg["custom_leads"] = leads
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist nun Custom-Lead.")

    @app_commands.command(name="requestsetailead", description="Füge einen Lead für AI Voice hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def requestsetailead(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        leads = cfg.get("ai_leads", [])
        if user.id not in leads:
            leads.append(user.id)
        cfg["ai_leads"] = leads
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist nun AI-Voice-Lead.")

    # ========== Main Panel ==========
    @app_commands.command(name="requestmain", description="Postet das Anfrage-Menü")
    @app_commands.guilds(MY_GUILD)
    async def requestmain(self, interaction: Interaction):
        cfg = await get_config()
        active_channel = interaction.guild.get_channel(cfg.get("active_channel", 0))
        if not active_channel:
            return await utils.send_error(interaction, "Kein Aktiv-Channel gesetzt.")
        embed = discord.Embed(
            title="🎙️ Anfrage-System",
            description="Wähle eine Anfrageart aus, um eine neue Anfrage zu stellen!",
            color=discord.Color.blurple()
        )
        view = RequestMenuView(self)
        await active_channel.send(embed=embed, view=view)
        await utils.send_success(interaction, "Anfrage-Menü wurde gepostet.")

    # ========== Handling der Anfragen ==========
    async def handle_custom_submit(self, interaction, data):
        cfg = await get_config()
        active_channel = interaction.guild.get_channel(cfg.get("active_channel", 0))
        done_channel = interaction.guild.get_channel(cfg.get("done_channel", 0))
        leads = [interaction.guild.get_member(uid) for uid in cfg.get("custom_leads", []) if interaction.guild.get_member(uid)]
        # Post im Aktiv-Channel
        embed = make_request_embed(data, status="active")
        view = CloseRequestButton(lambda i: self.handle_close_request(i, data, embed))
        msg = await active_channel.send(embed=embed, view=view)
        data["msg_id"] = msg.id
        # DM an alle Leads
        for lead in leads:
            try:
                await lead.send(
                    f"**Neue Custom Anfrage von {interaction.user.mention}:**",
                    embed=embed,
                    view=LeadDMView(
                        lambda i: self.lead_decide(i, data, embed, "done", msg, interaction.user, done_channel),
                        lambda i: self.lead_decide(i, data, embed, "rejected", msg, interaction.user, done_channel),
                        lambda i: self.lead_decide(i, data, embed, "progress", msg, interaction.user, done_channel)
                    )
                )
            except Exception:
                continue
        await interaction.response.send_message("Custom Anfrage erstellt!", ephemeral=True)

    async def handle_ai_submit(self, interaction, data):
        cfg = await get_config()
        active_channel = interaction.guild.get_channel(cfg.get("active_channel", 0))
        done_channel = interaction.guild.get_channel(cfg.get("done_channel", 0))
        leads = [interaction.guild.get_member(uid) for uid in cfg.get("ai_leads", []) if interaction.guild.get_member(uid)]
        # Post im Aktiv-Channel
        embed = make_request_embed(data, status="active")
        view = CloseRequestButton(lambda i: self.handle_close_request(i, data, embed))
        msg = await active_channel.send(embed=embed, view=view)
        data["msg_id"] = msg.id
        # DM an alle Leads
        for lead in leads:
            try:
                await lead.send(
                    f"**Neue AI-Voice Anfrage von {interaction.user.mention}:**",
                    embed=embed,
                    view=LeadDMView(
                        lambda i: self.lead_decide(i, data, embed, "done", msg, interaction.user, done_channel),
                        lambda i: self.lead_decide(i, data, embed, "rejected", msg, interaction.user, done_channel),
                        lambda i: self.lead_decide(i, data, embed, "progress", msg, interaction.user, done_channel)
                    )
                )
            except Exception:
                continue
        await interaction.response.send_message("AI-Voice Anfrage erstellt!", ephemeral=True)

    async def lead_decide(self, interaction, data, old_embed, status, msg, anfrager, done_channel):
        # Status/Farbe/Kommentar bestimmen
        if status == "progress":
            modal = StatusModal("progress", self, data, msg, old_embed, anfrager, done_channel)
            return await interaction.response.send_modal(modal)
        elif status == "rejected":
            modal = StatusModal("rejected", self, data, msg, old_embed, anfrager, done_channel)
            return await interaction.response.send_modal(modal)
        else:  # done
            embed = make_request_embed(data, status="done")
            await msg.edit(embed=embed)
            await done_channel.send(embed=embed)
            await anfrager.send(f"✅ Deine Anfrage **{data['streamer']}** wurde genehmigt!")
            await interaction.response.send_message("Genehmigt & in Done verschoben.", ephemeral=True)

    async def handle_close_request(self, interaction, data, old_embed):
        cfg = await get_config()
        done_channel = interaction.guild.get_channel(cfg.get("done_channel", 0))
        embed = make_request_embed(data, status="done")
        await interaction.message.delete()
        await done_channel.send(embed=embed)
        await utils.send_success(interaction, "Anfrage geschlossen und nach Done verschoben.")

# ======= Modals & Menu =======
class RequestMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Custom Anfrage", style=discord.ButtonStyle.green, emoji="📝")
    async def custom(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomModal(self.cog))

    @discord.ui.button(label="AI Voice Anfrage", style=discord.ButtonStyle.blurple, emoji="🔊")
    async def ai(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AIVoiceModal(self.cog))

class CustomModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.preis = discord.ui.TextInput(label="Preis (€)", max_length=20)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt? (Ja/Nein)", max_length=5)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_DESC_LEN)
        self.deadline = discord.ui.TextInput(label="Zeitgrenze", max_length=30)
        self.add_item(self.streamer)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.deadline)

    async def on_submit(self, interaction: Interaction):
        data = {
            "type": "custom",
            "streamer": self.streamer.value,
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "anfrage": self.anfrage.value,
            "deadline": self.deadline.value,
            "desc": f"Custom Anfrage für {self.streamer.value}"
        }
        await self.cog.handle_custom_submit(interaction, data)

class AIVoiceModal(discord.ui.Modal, title="AI Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN)
        self.audio = discord.ui.TextInput(label="Audio Wunsch", style=discord.TextStyle.paragraph, max_length=MAX_DESC_LEN)
        self.deadline = discord.ui.TextInput(label="Bis wann gebraucht", max_length=30)
        self.add_item(self.streamer)
        self.add_item(self.audio)
        self.add_item(self.deadline)

    async def on_submit(self, interaction: Interaction):
        data = {
            "type": "ai",
            "streamer": self.streamer.value,
            "audio": self.audio.value,
            "deadline": self.deadline.value,
            "desc": f"AI-Voice Anfrage für {self.streamer.value}"
        }
        await self.cog.handle_ai_submit(interaction, data)

class StatusModal(discord.ui.Modal):
    def __init__(self, status, cog, data, msg, old_embed, anfrager, done_channel):
        super().__init__(title=f"Status: {status.capitalize()}")
        self.status = status
        self.cog = cog
        self.data = data
        self.msg = msg
        self.old_embed = old_embed
        self.anfrager = anfrager
        self.done_channel = done_channel
        self.comment = discord.ui.TextInput(
            label="Kommentar/Begründung", style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN, required=True
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: Interaction):
        embed = make_request_embed(self.data, status=self.status, extra_comment=self.comment.value)
        await self.msg.edit(embed=embed)
        await self.done_channel.send(embed=embed)
        await self.anfrager.send(
            f"Deine Anfrage **{self.data['streamer']}** wurde {'abgelehnt' if self.status=='rejected' else 'auf in Bearbeitung gesetzt'}!\nKommentar: {self.comment.value}"
        )
        await interaction.response.send_message("Entscheidung gespeichert!", ephemeral=True)

# ========== Cog-Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
