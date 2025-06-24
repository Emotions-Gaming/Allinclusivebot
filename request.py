# request.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
REQUEST_CONFIG_PATH = os.path.join("persistent_data", "request_config.json")
REQUEST_LOG_PATH = os.path.join("persistent_data", "request_log.json")

COLOR_NEW = discord.Color.blurple()
COLOR_ACCEPTED = discord.Color.green()
COLOR_DECLINED = discord.Color.red()
COLOR_WORKING = discord.Color.gold()

# ========== Hilfsfunktionen (persistente Daten) ==========

async def get_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {
        "aktiv_id": None,
        "done_id": None,
        "log_id": None,
        "custom_leads": [],
        "ai_leads": []
    })

async def save_config(cfg):
    await utils.save_json(REQUEST_CONFIG_PATH, cfg)

async def get_log():
    return await utils.load_json(REQUEST_LOG_PATH, {})

async def save_log(log):
    await utils.save_json(REQUEST_LOG_PATH, log)

# ========== Buttons & Modals für DM ==========

class DecisionView(discord.ui.View):
    def __init__(self, post_id, decision_callback):
        super().__init__(timeout=300)
        self.post_id = post_id
        self.decision_callback = decision_callback

    @discord.ui.button(label="✅ Ja, wird gemacht", style=discord.ButtonStyle.green)
    async def accept_btn(self, interaction: Interaction, button: discord.ui.Button):
        await self.decision_callback(interaction, self.post_id, "accepted")

    @discord.ui.button(label="🟡 Wird bearbeitet", style=discord.ButtonStyle.primary)
    async def work_btn(self, interaction: Interaction, button: discord.ui.Button):
        modal = WorkModal(self.post_id, self.decision_callback)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def decline_btn(self, interaction: Interaction, button: discord.ui.Button):
        modal = DeclineModal(self.post_id, self.decision_callback)
        await interaction.response.send_modal(modal)

class WorkModal(discord.ui.Modal, title="Wird bearbeitet – Info"):
    def __init__(self, post_id, decision_callback):
        super().__init__()
        self.post_id = post_id
        self.decision_callback = decision_callback
        self.work_input = discord.ui.TextInput(
            label="Was wird gemacht?",
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True
        )
        self.add_item(self.work_input)

    async def on_submit(self, interaction: Interaction):
        await self.decision_callback(interaction, self.post_id, "working", self.work_input.value)

class DeclineModal(discord.ui.Modal, title="Ablehnen – Grund angeben"):
    def __init__(self, post_id, decision_callback):
        super().__init__()
        self.post_id = post_id
        self.decision_callback = decision_callback
        self.reason_input = discord.ui.TextInput(
            label="Grund für Ablehnung",
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: Interaction):
        await self.decision_callback(interaction, self.post_id, "declined", self.reason_input.value)

# ========== Main Cog ==========

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========== SETUP KOMMANDOS ==========

    @app_commands.command(name="requestsetaktiv", description="Setzt den Forum-Kanal für 'Aktiv'.")
    @app_commands.guilds(MY_GUILD)
    async def set_aktiv(self, interaction: Interaction, channel: discord.ForumChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["aktiv_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"'Aktiv'-Forum-Kanal gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetdone", description="Setzt den Forum-Kanal für 'Done'.")
    @app_commands.guilds(MY_GUILD)
    async def set_done(self, interaction: Interaction, channel: discord.ForumChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["done_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"'Done'-Forum-Kanal gesetzt: {channel.mention}")

    @app_commands.command(name="requestsetlog", description="Setzt den Log-Kanal.")
    @app_commands.guilds(MY_GUILD)
    async def set_log(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        cfg["log_id"] = channel.id
        await save_config(cfg)
        await utils.send_success(interaction, f"Log-Kanal gesetzt: {channel.mention}")

    @app_commands.command(name="requestcustomlead", description="Fügt einen User als Custom-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def custom_lead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        if user.id not in cfg["custom_leads"]:
            cfg["custom_leads"].append(user.id)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist jetzt Custom-Lead.")

    @app_commands.command(name="requestcustomremovelead", description="Entfernt einen User als Custom-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def custom_remove_lead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        if user.id in cfg["custom_leads"]:
            cfg["custom_leads"].remove(user.id)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist kein Custom-Lead mehr.")

    @app_commands.command(name="requestailead", description="Fügt einen User als AI-Lead hinzu.")
    @app_commands.guilds(MY_GUILD)
    async def ai_lead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        if user.id not in cfg["ai_leads"]:
            cfg["ai_leads"].append(user.id)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist jetzt AI-Lead.")

    @app_commands.command(name="requestairemovelead", description="Entfernt einen User als AI-Lead.")
    @app_commands.guilds(MY_GUILD)
    async def ai_remove_lead(self, interaction: Interaction, user: discord.User):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        if user.id in cfg["ai_leads"]:
            cfg["ai_leads"].remove(user.id)
        await save_config(cfg)
        await utils.send_success(interaction, f"{user.mention} ist kein AI-Lead mehr.")

    # ========== ANFRAGE-MENÜ POSTEN ==========

    @app_commands.command(name="requestmain", description="Postet das Anfrage-Menü (nur Admins).")
    @app_commands.guilds(MY_GUILD)
    async def request_main(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await get_config()
        aktiv_id = cfg["aktiv_id"]
        if not aktiv_id:
            return await utils.send_error(interaction, "Setze zuerst den Aktiv-Kanal mit /requestsetaktiv!")
        channel = interaction.guild.get_channel(aktiv_id)
        view = RequestTypeView(self)
        embed = discord.Embed(
            title="📬 Neue Anfrage",
            description="Wähle unten den Typ deiner Anfrage aus:",
            color=COLOR_NEW
        )
        await channel.send(embed=embed, view=view)
        await utils.send_success(interaction, "Menü für Anfragen gepostet.")

# ========== Dynamische Views & Popups ==========

class RequestTypeView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="🎨 Custom", style=discord.ButtonStyle.primary)
    async def custom_btn(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomRequestModal(self.cog))

    @discord.ui.button(label="🤖 AI-Voice", style=discord.ButtonStyle.secondary)
    async def ai_btn(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AiRequestModal(self.cog))

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=50, required=True)
        self.preis = discord.ui.TextInput(label="Preis ($)", max_length=10, required=True)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt? (ja/nein)", max_length=10, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=500, required=True)
        self.zeit = discord.ui.TextInput(label="Zeitgrenze", max_length=50, required=True)
        self.add_item(self.streamer)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.zeit)

    async def on_submit(self, interaction: Interaction):
        cfg = await get_config()
        forum = interaction.guild.get_channel(cfg["aktiv_id"])
        embed = discord.Embed(
            title=self.streamer.value,
            color=COLOR_NEW,
            description=f"**Preis:** {self.preis.value}\n**Bezahlt:** {self.bezahlt.value}\n**Zeit:** {self.zeit.value}\n**Anfrage:**\n{self.anfrage.value}"
        )
        embed.set_footer(text=f"Erstellt von {interaction.user.display_name} | {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        # Thread/Post anlegen (Forum-Post)
        post = await forum.create_thread(
            name=self.streamer.value,
            content=None,
            embed=embed
        )
        # Leads pingen
        cfg = await get_config()
        mentions = " ".join(f"<@{uid}>" for uid in cfg["custom_leads"])
        if mentions:
            try:
                await post.send(f"{mentions} – Neue Custom-Anfrage! Bitte entscheide.", view=DecisionView(post.id, decision_callback_factory(post, interaction.user, "custom")))
            except Exception as e:
                print(e)
        await utils.send_success(interaction, "Custom-Anfrage wurde erstellt!")

class AiRequestModal(discord.ui.Modal, title="AI-Voice Anfrage"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=50, required=True)
        self.audio = discord.ui.TextInput(label="Audio-Wunsch", style=discord.TextStyle.paragraph, max_length=300, required=True)
        self.zeit = discord.ui.TextInput(label="Bis wann gebraucht?", max_length=50, required=True)
        self.add_item(self.streamer)
        self.add_item(self.audio)
        self.add_item(self.zeit)

    async def on_submit(self, interaction: Interaction):
        cfg = await get_config()
        forum = interaction.guild.get_channel(cfg["aktiv_id"])
        embed = discord.Embed(
            title=self.streamer.value,
            color=COLOR_NEW,
            description=f"**AI Voice Anfrage für:** {self.streamer.value}\n**Audio-Wunsch:**\n{self.audio.value}\n**Bis wann:** {self.zeit.value}"
        )
        embed.set_footer(text=f"Erstellt von {interaction.user.display_name} | {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        post = await forum.create_thread(
            name=self.streamer.value,
            content=None,
            embed=embed
        )
        # Leads pingen
        cfg = await get_config()
        mentions = " ".join(f"<@{uid}>" for uid in cfg["ai_leads"])
        if mentions:
            try:
                await post.send(f"{mentions} – Neue AI-Voice-Anfrage! Bitte entscheide.", view=DecisionView(post.id, decision_callback_factory(post, interaction.user, "ai")))
            except Exception as e:
                print(e)
        await utils.send_success(interaction, "AI-Voice-Anfrage wurde erstellt!")

# ========== Entscheidungscallback ==========

def decision_callback_factory(post, requester, typ):
    async def callback(interaction, post_id, decision, info=None):
        # Hole Konfigurationen
        cfg = await get_config()
        done_forum = interaction.guild.get_channel(cfg["done_id"])
        # Thread holen
        thread = post
        # Status, Farbe, Kommentar bauen
        if decision == "accepted":
            color = COLOR_ACCEPTED
            status = "✅ Genehmigt"
            info_text = ""
        elif decision == "declined":
            color = COLOR_DECLINED
            status = "❌ Abgelehnt"
            info_text = f"**Begründung:** {info}"
        else:
            color = COLOR_WORKING
            status = "🟡 In Bearbeitung"
            info_text = f"**Info:** {info}"

        # Ursprungs-Embed übernehmen, modifizieren
        orig = None
        async for msg in thread.history(limit=10):
            if msg.embeds:
                orig = msg.embeds[0]
                break

        embed = discord.Embed(
            title=orig.title if orig else "Anfrage",
            color=color,
            description=f"{orig.description if orig else ''}\n\n**Status:** {status}\n{info_text}"
        )
        embed.set_footer(text=f"Bearbeitet von {interaction.user.display_name} am {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        await thread.send(embed=embed)
        # Ersteller benachrichtigen
        try:
            await requester.send(
                f"Deine Anfrage **{orig.title if orig else 'Anfrage'}** wurde **{status}**.\n{info_text}"
            )
        except Exception:
            pass
        # In Done moven: neuen Post, alten schließen/löschen
        if decision in ["accepted", "declined"]:
            post_done = await done_forum.create_thread(
                name=orig.title if orig else "Anfrage",
                content=None,
                embed=embed
            )
            await thread.edit(locked=True, archived=True, reason="Erledigt")
        await interaction.response.send_message(f"Entscheidung: {status} gespeichert!", ephemeral=True)
    return callback

# ========== Setup ==========

async def setup(bot):
    await bot.add_cog(RequestCog(bot))

