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
    "uploaded": discord.Color.blue(),
    "done": discord.Color.green(),
    "geschlossen": discord.Color.dark_grey()
}
STATUS_DISPLAY = {
    "offen": "🟦 Offen",
    "angenommen": "🟩 Angenommen",
    "bearbeitung": "🟨 In Bearbeitung",
    "abgelehnt": "🟥 Abgelehnt",
    "uploaded": "🟦 Hochgeladen",
    "done": "🟩 Fertig",
    "geschlossen": "🛑 Geschlossen"
}

def build_thread_title(status, streamer, ersteller, tag, typ, nr):
    # Tag kann leer sein!
    tag_display = f"{tag} - " if tag else ""
    return f"[{status.capitalize()}] - {streamer} - {ersteller} - {tag_display}{typ.capitalize()} - #{nr}"

async def get_request_config():
    return await utils.load_json(REQUEST_CONFIG_PATH, {})

async def save_request_config(data):
    await utils.save_json(REQUEST_CONFIG_PATH, data)

async def get_leads():
    return await utils.load_json(REQUEST_LEADS_PATH, {"custom": [], "ai": []})

async def save_leads(data):
    await utils.save_json(REQUEST_LEADS_PATH, data)

def build_embed(data, status="offen", reason=None):
    color = STATUS_COLORS.get(status, discord.Color.blurple())
    title = f"📩 {data['streamer']}" if data.get("streamer") else "Anfrage"
    desc = data.get("desc", "")
    if data["type"] == "custom":
        tag_info = f"**Fan-Tag:** {data['fan_tag']}\n" if data.get("fan_tag") else ""
        desc = (
            f"{tag_info}"
            f"**Preis:** {data['preis']}\n"
            f"**Bezahlt?** {data['bezahlt']}\n"
            f"**Anfrage:** {data['anfrage']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    elif data["type"] == "ai":
        desc = (
            f":information_source: **Nur Mila und Xenia sind für AI Voice Over verfügbar!**\n"
            f":alarm_clock: **Textlänge maximal 10 Sekunden!**\n\n"
            f"**Audio Wunsch:** {data['audiowunsch']}\n"
            f"**Zeitgrenze:** {data['zeitgrenze']}"
        )
    if reason:
        desc += f"\n\n**Begründung:** {reason}"
    embed = discord.Embed(
        title=title,
        description=f"{desc}\n\n**Status:** {STATUS_DISPLAY.get(status, status)}",
        color=color
    )
    embed.set_footer(text=f"Anfrage-Typ: {data['type'].capitalize()} • Erstellt von: {data['erstellername']}")
    return embed

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_backups = {}

    # ... (Alle Setup-Kommandos bleiben identisch!)

    async def post_request(self, interaction, data, reqtype):
        config = await get_request_config()
        forum_id = config.get("active_forum")
        if not forum_id:
            return await utils.send_error(interaction, "Kein aktives Forum konfiguriert.")
        forum = interaction.guild.get_channel(forum_id)
        all_threads = forum.threads
        nr = len(all_threads) + 1
        data["nr"] = nr

        # Fan-Tag aufnehmen bei Custom
        fan_tag = data.get('fan_tag', "")
        thread_title = build_thread_title("offen", data['streamer'], str(interaction.user), fan_tag, reqtype, nr)
        thread_with_message = await forum.create_thread(
            name=thread_title,
            content="Neue Anfrage erstellt.",
            applied_tags=[],
        )
        channel = thread_with_message.thread
        data["type"] = reqtype
        data["status"] = "offen"
        data["erstellerid"] = interaction.user.id
        data["erstellername"] = str(interaction.user)
        embed = build_embed(data, status="offen")
        view = RequestThreadView(self, data, channel)
        await channel.send(embed=embed, view=view)
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
                    view = LeadActionsDropdownView(self, data, thread_channel, lead)
                    msg = (
                        f"Neue **{'Custom' if reqtype == 'custom' else 'AI Voice'} Anfrage** von {interaction.user.mention}:\n"
                        f"**Streamer:** {data['streamer']}\n"
                    )
                    if reqtype == "custom":
                        tag_info = f"**Fan-Tag:** {data.get('fan_tag','')}\n" if data.get("fan_tag") else ""
                        msg += (
                            f"{tag_info}"
                            f"**Preis:** {data['preis']}\n"
                            f"**Bezahlt?** {data['bezahlt']}\n"
                            f"**Anfrage:** {data['anfrage']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    else:
                        msg += (
                            ":information_source: Nur Mila und Xenia sind für AI Voice Over verfügbar!\n"
                            ":alarm_clock: Textlänge maximal 10 Sekunden!\n"
                            f"**Audio Wunsch:** {data['audiowunsch']}\n"
                            f"**Zeitgrenze:** {data['zeitgrenze']}\n"
                        )
                    msg += f"[Zum Thread]({thread_channel.jump_url})"
                    await lead.send(msg, view=view)
                except Exception:
                    pass

    async def on_thread_message(self, message):
        if message.channel.id in self.chat_backups:
            if not message.author.bot:
                self.chat_backups[message.channel.id].append(
                    (message.author.display_name, message.content)
                )

# ----------- RequestTypeDropdown/CustomRequestModal Änderung -----------

class CustomRequestModal(discord.ui.Modal, title="Custom Anfrage"):
    def __init__(self, cog, dropdown):
        super().__init__()
        self.cog = cog
        self.dropdown = dropdown
        self.fan_tag = discord.ui.TextInput(label="Fan Tag hinzufügen (z. B. @12hh238712)", max_length=32, required=False, placeholder="@12hh238712")
        self.streamer = discord.ui.TextInput(label="Streamer", max_length=MAX_TITLE_LEN, required=True)
        self.preis = discord.ui.TextInput(label="Preis (z. B. 400€)", max_length=20, required=True)
        self.bezahlt = discord.ui.TextInput(label="Bezahlt?", placeholder="Ja/Nein", max_length=10, required=True)
        self.anfrage = discord.ui.TextInput(label="Anfrage", style=discord.TextStyle.paragraph, max_length=MAX_BODY_LEN, required=True)
        self.zeitgrenze = discord.ui.TextInput(label="Zeitgrenze (z. B. bis Sonntag)", max_length=40, required=True)
        self.add_item(self.fan_tag)
        self.add_item(self.streamer)
        self.add_item(self.preis)
        self.add_item(self.bezahlt)
        self.add_item(self.anfrage)
        self.add_item(self.zeitgrenze)

    async def on_submit(self, interaction: Interaction):
        data = {
            "fan_tag": self.fan_tag.value,
            "streamer": self.streamer.value,
            "preis": self.preis.value,
            "bezahlt": self.bezahlt.value,
            "anfrage": self.anfrage.value,
            "zeitgrenze": self.zeitgrenze.value,
        }
        await self.cog.post_request(interaction, data, "custom")
        self.dropdown.values = []
        await interaction.message.edit(view=self.dropdown.view)

# ... AIRequestModal bleibt wie gehabt!

# ----------- StatusEditButton, StatusDropdown, Modal -----------

class StatusDropdown(discord.ui.Select):
    def __init__(self, cog, data, thread_channel):
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        options = [
            discord.SelectOption(label="Offen", value="offen"),
            discord.SelectOption(label="Angenommen", value="angenommen"),
            discord.SelectOption(label="In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Fertig", value="done"),
            discord.SelectOption(label="Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status wählen…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        self.data['status'] = new_status
        fan_tag = self.data.get('fan_tag', "")
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], fan_tag, self.data['type'], nr)
        # Grund-Popup für bestimmte Status
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status))
        else:
            await self.thread_channel.edit(name=new_title)
            embed = build_embed(self.data, status=new_status)
            await self.thread_channel.send(content=f"Status geändert von {interaction.user.mention}:", embed=embed)
            ersteller = self.thread_channel.guild.get_member(self.data['erstellerid'])
            if ersteller:
                try:
                    await ersteller.send(
                        f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                        f"👉 [Zum Post]({self.thread_channel.jump_url})"
                    )
                except Exception:
                    pass
            await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

class StatusReasonModal(discord.ui.Modal, title="Begründung angeben"):
    def __init__(self, cog, data, thread_channel, new_status):
        super().__init__()
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.new_status = new_status
        self.reason = discord.ui.TextInput(
            label="Begründung für diese Entscheidung",
            style=discord.TextStyle.paragraph,
            max_length=MAX_COMMENT_LEN,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        nr = self.data.get('nr', 0)
        fan_tag = self.data.get('fan_tag', "")
        self.data['status'] = self.new_status
        new_title = build_thread_title(self.new_status, self.data['streamer'], self.data['erstellername'], fan_tag, self.data['type'], nr)
        await self.thread_channel.edit(name=new_title)
        embed = build_embed(self.data, status=self.new_status, reason=self.reason.value)
        await self.thread_channel.send(
            content=f"Status geändert von {interaction.user.mention}:", embed=embed
        )
        ersteller = self.thread_channel.guild.get_member(self.data['erstellerid'])
        if ersteller:
            try:
                await ersteller.send(
                    f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[self.new_status]}**!\n"
                    f"**Begründung:** {self.reason.value}\n"
                    f"👉 [Zum Post]({self.thread_channel.jump_url})"
                )
            except Exception:
                pass
        await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[self.new_status]}** geändert!", ephemeral=True)

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
            discord.SelectOption(label="Status: Offen", value="offen"),
            discord.SelectOption(label="Status: Angenommen", value="angenommen"),
            discord.SelectOption(label="Status: In Bearbeitung", value="bearbeitung"),
            discord.SelectOption(label="Status: Abgelehnt", value="abgelehnt"),
            discord.SelectOption(label="Status: Hochgeladen", value="uploaded"),
            discord.SelectOption(label="Status: Fertig", value="done"),
            discord.SelectOption(label="Status: Geschlossen", value="geschlossen")
        ]
        super().__init__(placeholder="Status direkt ändern…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.lead.id:
            return await interaction.response.send_message("Nur du als Lead kannst den Status ändern!", ephemeral=True)
        new_status = self.values[0]
        nr = self.data.get('nr', 0)
        fan_tag = self.data.get('fan_tag', "")
        self.data['status'] = new_status
        new_title = build_thread_title(new_status, self.data['streamer'], self.data['erstellername'], fan_tag, self.data['type'], nr)
        if new_status in ["abgelehnt", "uploaded", "done"]:
            await interaction.response.send_modal(StatusReasonModal(self.cog, self.data, self.thread_channel, new_status))
        else:
            await self.thread_channel.edit(name=new_title)
            embed = build_embed(self.data, status=new_status)
            await self.thread_channel.send(
                content=f"Status geändert von {interaction.user.mention}:",
                embed=embed
            )
            ersteller = self.thread_channel.guild.get_member(self.data['erstellerid'])
            if ersteller:
                try:
                    await ersteller.send(
                        f"Deine Anfrage **{self.data['streamer']}** hat nun den Status: **{STATUS_DISPLAY[new_status]}**!\n"
                        f"👉 [Zum Post]({self.thread_channel.jump_url})"
                    )
                except Exception:
                    pass
            await interaction.response.send_message(f"Status wurde auf **{STATUS_DISPLAY[new_status]}** geändert!", ephemeral=True)

# ----------- RequestThreadView/Backup -----------
class RequestThreadView(discord.ui.View):
    def __init__(self, cog, data, thread_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel
        self.add_item(StatusEditButton(cog, data, thread_channel))
        self.add_item(CloseRequestButton(cog, data, thread_channel))

class CloseRequestButton(discord.ui.Button):
    def __init__(self, cog, data, thread_channel):
        super().__init__(label="Anfrage schließen", style=discord.ButtonStyle.danger, emoji="🔒")
        self.cog = cog
        self.data = data
        self.thread_channel = thread_channel

    async def callback(self, interaction: Interaction):
        config = await get_request_config()
        done_forum_id = config.get("done_forum")
        if not done_forum_id:
            return await utils.send_error(interaction, "Kein Done-Forum konfiguriert.")
        done_forum = interaction.guild.get_channel(done_forum_id)
        nr = self.data.get('nr', 0)
        fan_tag = self.data.get('fan_tag', "")
        # History filtern: Bot-Nachrichten, die "Status geändert von" enthalten, nicht in Backup
        messages = []
        async for msg in self.thread_channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                if msg.content.strip() == "":
                    continue
                messages.append(f"**{msg.author.display_name}:** {msg.content}")
        last_status = STATUS_DISPLAY.get(self.data.get('status', 'offen'), "Unbekannt")
        backup_body = f"**Finaler Status:** {last_status}\n\n" + "\n".join(messages)
        new_title = build_thread_title(self.data.get('status', 'geschlossen'), self.data['streamer'], self.data['erstellername'], fan_tag, self.data['type'], nr)
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

# ----------- Restliche Views/Dropdowns -----------

# RequestMenuView, AIRequestModal, StatusEditButton, StatusDropdownView etc. bleiben unverändert aus deinem letzten Code!

# ========== Setup ==========
async def setup(bot):
    await bot.add_cog(RequestCog(bot))
