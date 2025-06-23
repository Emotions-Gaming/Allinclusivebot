import os
import discord
from discord.ext import commands
from discord import app_commands, Member, TextChannel, CategoryChannel, Embed
from utils import is_admin, load_json, save_json
from permissions import has_permission_for
from discord import Interaction


# KEIN from discord import Interaction !

GUILD_ID = int(os.environ.get("GUILD_ID"))
PROFILES_JSON = "persistent_data/profiles.json"
MENU_JSON = "persistent_data/translator_menu.json"
CATEGORY_JSON = "persistent_data/trans_category.json"
PROMPT_JSON = "persistent_data/translator_prompt.json"
LOG_JSON = "persistent_data/translation_log.json"

def _load_profiles():
    return load_json(PROFILES_JSON, {})

def _save_profiles(profiles):
    save_json(PROFILES_JSON, profiles)

def _load_menu():
    return load_json(MENU_JSON, {})

def _save_menu(menu):
    save_json(MENU_JSON, menu)

def _load_category():
    return load_json(CATEGORY_JSON, None)

def _save_category(cat_id):
    save_json(CATEGORY_JSON, cat_id)

def _load_prompt():
    return load_json(PROMPT_JSON, "")

def _save_prompt(text):
    save_json(PROMPT_JSON, text)

def _load_log():
    return load_json(LOG_JSON, {})

def _save_log(log):
    save_json(LOG_JSON, log)

def _get_session_channel_name(profil, member):
    return f"translat-{profil.lower().replace(' ', '-')}-{member.name.lower()}"

async def dummy_translate(text, prompt):
    await discord.utils.sleep_until(discord.utils.utcnow())  # Dummy
    return f"{text[::-1]} [Style:{prompt}]"

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==== Menü posten (reload_menu für setupbot.py) ====
    async def reload_menu(self):
        menu = _load_menu()
        channel_id = menu.get("main_channel_id")
        if not channel_id:
            return
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        async for msg in channel.history(limit=30):
            if msg.author == self.bot.user and msg.embeds and "Übersetzungsmenü" in (msg.embeds[0].title or ""):
                try:
                    await msg.delete()
                except Exception:
                    pass
        embed = Embed(
            title="🌐 Übersetzungsmenü",
            description="Wähle einen Übersetzer-Stil aus, um deine Session zu starten.",
            color=0x2ecc71
        )
        profiles = _load_profiles()
        view = ProfileSelectView(self, profiles)
        await channel.send(embed=embed, view=view)

    @app_commands.command(
        name="translatorpost",
        description="Postet das Übersetzungsmenü ins Channel (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatorpost")
    async def translatorpost(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        menu = _load_menu()
        menu["main_channel_id"] = interaction.channel.id
        _save_menu(menu)
        await self.reload_menu()
        await interaction.response.send_message("✅ Übersetzungsmenü gepostet!", ephemeral=True)

    @app_commands.command(
        name="translatoraddprofile",
        description="Neues Übersetzer-Profil hinzufügen (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatoraddprofile")
    async def translatoraddprofile(self, interaction: discord.Interaction, name: str, stil: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        profiles = _load_profiles()
        if name in profiles:
            await interaction.response.send_message("❌ Profil existiert schon.", ephemeral=True)
            return
        profiles[name] = stil
        _save_profiles(profiles)
        await interaction.response.send_message(f"✅ Profil **{name}** hinzugefügt.", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="translatordeleteprofile",
        description="Entfernt ein Übersetzer-Profil (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatordeleteprofile")
    async def translatordeleteprofile(self, interaction: discord.Interaction, name: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        profiles = _load_profiles()
        if name not in profiles:
            await interaction.response.send_message("❌ Profil nicht gefunden.", ephemeral=True)
            return
        del profiles[name]
        _save_profiles(profiles)
        await interaction.response.send_message(f"✅ Profil **{name}** entfernt.", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="translatorsetcategorie",
        description="Setzt die Kategorie für Übersetzungs-Sessions (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatorsetcategorie")
    async def translatorsetcategorie(self, interaction: discord.Interaction, category: CategoryChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_category(category.id)
        await interaction.response.send_message(f"✅ Kategorie für Sessions: {category.mention}", ephemeral=True)

    @app_commands.command(
        name="translatorlog",
        description="Setzt den Log-Channel für Übersetzungen (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatorlog")
    async def translatorlog(self, interaction: discord.Interaction, channel: TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        menu = _load_menu()
        menu["log_channel_id"] = channel.id
        _save_menu(menu)
        await interaction.response.send_message(f"✅ Log-Channel für Übersetzungen: {channel.mention}", ephemeral=True)

    @app_commands.command(
        name="translatorprompt",
        description="Setzt eine Zusatzregel für den Übersetzungs-Prompt (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatorprompt")
    async def translatorprompt(self, interaction: discord.Interaction, regel: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_prompt(regel)
        await interaction.response.send_message("✅ Prompt-Zusatz gesetzt!", ephemeral=True)

    @app_commands.command(
        name="translatorpromptdelete",
        description="Löscht den Prompt-Zusatz (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("translatorpromptdelete")
    async def translatorpromptdelete(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_prompt("")
        await interaction.response.send_message("✅ Prompt-Zusatz entfernt!", ephemeral=True)

# ==== Views und Session-Handling ====

class ProfileSelectView(discord.ui.View):
    def __init__(self, cog, profiles):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label=name, description=stil[:80])
            for name, stil in list(profiles.items())[:25]
        ]
        self.add_item(ProfileSelect(cog, options))

class ProfileSelect(discord.ui.Select):
    def __init__(self, cog, options):
        super().__init__(placeholder="Profil auswählen…", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        profil = self.values[0]
        member = interaction.user
        category_id = _load_category()
        if not category_id:
            await interaction.response.send_message("❌ Kategorie für Sessions nicht gesetzt. Bitte Admin kontaktieren!", ephemeral=True)
            return
        guild = interaction.guild or self.cog.bot.get_guild(GUILD_ID)
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, CategoryChannel):
            await interaction.response.send_message("❌ Kategorie existiert nicht mehr.", ephemeral=True)
            return

        ch_name = _get_session_channel_name(profil, member)
        for channel in category.channels:
            if channel.name == ch_name:
                try:
                    await channel.delete()
                except Exception:
                    pass

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        session_channel = await guild.create_text_channel(ch_name, category=category, overwrites=overwrites)
        embed = Embed(
            title=f"Übersetzungssession ({profil})",
            description="Schreibe hier deine Nachricht. Jede Nachricht wird automatisch übersetzt und als Embed gepostet. Klicke auf 'Session beenden', um deinen Verlauf zu speichern.",
            color=0x2ecc71
        )
        view = SessionEndView(self.cog, session_channel, member, profil)
        await session_channel.send(f"{member.mention}", embed=embed, view=view)
        await interaction.response.send_message(f"✅ Session erstellt: {session_channel.mention}", ephemeral=True)

class SessionEndView(discord.ui.View):
    def __init__(self, cog, channel, member, profil):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel = channel
        self.member = member
        self.profil = profil

    @discord.ui.button(label="Session beenden & Verlauf senden", style=discord.ButtonStyle.red)
    async def end_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = [msg async for msg in self.channel.history(limit=50) if msg.author == self.cog.bot.user and msg.embeds]
        last = messages[:10]
        menu = _load_menu()
        log_channel_id = menu.get("log_channel_id")
        guild = interaction.guild or self.cog.bot.get_guild(GUILD_ID)
        log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

        if last and log_channel:
            embed = Embed(
                title=f"Übersetzungsverlauf von {self.member.display_name} ({self.profil})",
                color=0x2980b9
            )
            txt = ""
            for msg in reversed(last):
                txt += f"• {msg.embeds[0].description}\n"
            embed.description = txt[:4096]
            await log_channel.send(embed=embed)
        await interaction.response.send_message("✅ Verlauf gesendet, Session wird beendet.", ephemeral=True)
        try:
            await self.channel.delete()
        except Exception:
            pass

# ==== Übersetzungs-Event ==== 

@commands.Cog.listener()
async def on_message(self, message):
    if message.author.bot or not message.guild or not message.channel.category:
        return
    category_id = _load_category()
    if not category_id or message.channel.category_id != category_id:
        return
    # Session-User/Admin dürfen posten
    # Falls du `recipient` im Channel verwendest: Discord.py hat das nicht nativ! 
    # Alternative: Überprüfe channel.overwrites für message.author, falls nötig!
    # Oder lass nur den Session-Ersteller schreiben, sonst Admin.
    # (Hier Beispiel bleibt wie im Original, ggf. anpassen!)
    if not is_admin(message.author):
        # Option: 
        # if message.author != ... : return
        pass

    parts = message.channel.name.split("-")
    if len(parts) < 3:
        return
    profil = parts[1].replace("-", " ").capitalize()
    profiles = _load_profiles()
    if profil not in profiles:
        return
    prompt = profiles[profil] + "\n" + (_load_prompt() or "")
    translated = await dummy_translate(message.content, prompt)
    embed = Embed(
        title="Übersetzung",
        description=translated,
        color=0x95a5a6
    )
    await message.channel.send(embed=embed)
    log = _load_log()
    uid = str(message.author.id)
    if uid not in log:
        log[uid] = []
    log[uid].append({"orig": message.content, "translated": translated})
    _save_log(log)

TranslationCog.on_message = on_message

# === Extension Loader ===
async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
