from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import json
import re
import secrets

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("GUILD_ID")

# Data file paths
TRANS_FILE = "translation_data.json"
STRIKE_FILE = "strike_data.json"
WIKI_CONFIG_FILE = "wiki_config.json"
WIKI_PAGES_FILE = "wiki_pages.json"
WIKI_BACKUP_FILE = "wiki_backup.json"

# Helper functions for JSON file operations
def load_json(file_path: str, default):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default

def save_json(file_path: str, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Ensure data files exist with initial structure
if not os.path.isfile(TRANS_FILE):
    save_json(TRANS_FILE, {"category_id": None, "log_channel_id": None, "profiles": ["Profil1", "Profil2"]})
if not os.path.isfile(STRIKE_FILE):
    save_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
if not os.path.isfile(WIKI_CONFIG_FILE):
    save_json(WIKI_CONFIG_FILE, {"main_channel_id": None, "menu_message_id": None})
if not os.path.isfile(WIKI_PAGES_FILE):
    save_json(WIKI_PAGES_FILE, {})

# Initialize Discord bot with intents for members and message content
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Translation System ----------
class TranslationMenuView(discord.ui.View):
    def __init__(self, profiles: list[str]):
        super().__init__(timeout=None)
        # Create a dropdown (Select) for translation profiles
        options = [discord.SelectOption(label=profile) for profile in profiles]
        select = discord.ui.Select(
            placeholder="Übersetzungsprofil auswählen...",
            options=options,
            custom_id="translation_profile_select"
        )
        async def select_callback(interaction: discord.Interaction):
            # Defer response to allow processing time
            await interaction.response.defer(ephemeral=True, thinking=True)
            profile = select.values[0]
            user = interaction.user
            guild = interaction.guild
            # Load translation config to get category ID and log channel
            trans_data = load_json(TRANS_FILE, {})
            category_id = trans_data.get("category_id")
            if not category_id:
                await interaction.followup.send("⚠️ Übersetzungskategorie wurde noch nicht festgelegt. Bitte zuerst `/translationsection` verwenden.", ephemeral=True)
                return
            category = guild.get_channel(int(category_id))
            if not category or category.type != discord.ChannelType.category:
                await interaction.followup.send("⚠️ Ungültige Kategorie. Bitte stelle sicher, dass die Kategorie-ID korrekt ist.", ephemeral=True)
                return
            # Generate a unique channel name for the translation channel
            base_name = f"{profile}-{user.name}".lower()
            safe_name = re.sub(r'[^a-zA-Z0-9\-]', '-', base_name).strip("-")
            if not safe_name:
                safe_name = "übersetzung"
            safe_name = safe_name[:80]
            channel_name = safe_name
            if discord.utils.get(guild.channels, name=channel_name):
                suffix = secrets.token_hex(2)  # Add random suffix if name exists
                channel_name = f"{safe_name}-{suffix}"
            # Create the private translation text channel under the specified category
            try:
                new_channel = await guild.create_text_channel(name=channel_name, category=category)
            except Exception as e:
                await interaction.followup.send(f"❌ Fehler beim Erstellen des Übersetzungskanals: {e}", ephemeral=True)
                return
            # Set channel permissions: deny everyone, allow the requesting user
            try:
                await new_channel.set_permissions(guild.default_role, read_messages=False)
            except:
                pass
            try:
                await new_channel.set_permissions(user, read_messages=True, send_messages=True)
            except:
                pass
            # Log the translation start in the log channel (if configured)
            log_channel_id = trans_data.get("log_channel_id")
            if log_channel_id:
                log_channel = guild.get_channel(int(log_channel_id))
                if log_channel:
                    await log_channel.send(f"📔 Übersetzung gestartet von **{user}** – Profil: `{profile}`, Kanal: {new_channel.mention}")
            # Notify the user that their translation channel is ready
            await interaction.followup.send(f"✅ Dein Übersetzungskanal wurde erstellt: {new_channel.mention}", ephemeral=True)
            # Reset the dropdown selection (allow reusing the same profile)
            new_profiles = load_json(TRANS_FILE, {}).get("profiles", [])
            await interaction.message.edit(view=TranslationMenuView(new_profiles))
        select.callback = select_callback
        self.add_item(select)

@bot.tree.command(name="translationsection", description="Setzt die Kategorie für Übersetzungskanäle")
@app_commands.describe(kategorie="Die Kategorie (Channel) für neue Übersetzungskanäle")
async def translationsection(interaction: discord.Interaction, kategorie: discord.CategoryChannel):
    # Save the category ID for translation channels
    trans_data = load_json(TRANS_FILE, {"category_id": None, "log_channel_id": None, "profiles": []})
    trans_data["category_id"] = str(kategorie.id)
    save_json(TRANS_FILE, trans_data)
    profiles = trans_data.get("profiles", [])
    if not profiles:
        await interaction.response.send_message(f"Übersetzungskategorie gesetzt auf **{kategorie.name}**. *(Keine Übersetzungsprofile definiert.)*", ephemeral=True)
    else:
        # Post the translation profile menu in the current channel
        view = TranslationMenuView(profiles)
        await interaction.response.send_message(f"Übersetzungskategorie **{kategorie.name}** gesetzt. Wähle ein Profil, um eine Übersetzung zu starten:", view=view)

@bot.tree.command(name="translationlog", description="Setzt den Log-Channel für Übersetzungsprotokolle")
@app_commands.describe(channel="Channel für Übersetzungs-Logs")
async def translationlog(interaction: discord.Interaction, channel: discord.TextChannel):
    # Save the log channel ID for translation events
    trans_data = load_json(TRANS_FILE, {"category_id": None, "log_channel_id": None, "profiles": []})
    trans_data["log_channel_id"] = str(channel.id)
    save_json(TRANS_FILE, trans_data)
    await interaction.response.send_message(f"✅ Log-Channel für Übersetzungen gesetzt: {channel.mention}", ephemeral=True)

# ---------- Strike System ----------
def generate_strike_list_text(strike_data: dict, guild: discord.Guild):
    strikes = strike_data.get("strikes", {})
    if not strikes:
        return "*(Noch keine Strikes vergeben.)*"
    lines = ["**Strike-Liste:**"]
    for user_id, count in strikes.items():
        member = guild.get_member(int(user_id))
        name = member.display_name if member else f"Unbekanntes Mitglied ({user_id})"
        lines.append(f"- {name}: **{count}** Strike{'s' if count != 1 else ''}")
    return "\n".join(lines)

class StrikeView(discord.ui.View):
    def __init__(self, guild: discord.Guild, strike_data: dict):
        super().__init__(timeout=None)
        # Create dropdown for selecting a member to give a strike
        options = [discord.SelectOption(label="Keinen", value="none")]
        members = [m for m in guild.members if not m.bot]
        members.sort(key=lambda m: m.display_name.lower())
        for m in members:
            label = m.display_name
            if len(label) > 25:
                label = label[:22] + "..."
            options.append(discord.SelectOption(label=label, value=str(m.id)))
            if len(options) >= 25:
                break  # Discord allows max 25 options
        select = discord.ui.Select(
            placeholder="Mitglied für einen Strike auswählen...",
            options=options,
            custom_id="strike_user_select"
        )
        async def select_callback(interaction: discord.Interaction):
            value = select.values[0]
            if value == "none":
                await interaction.response.send_message("⚠️ Kein Mitglied ausgewählt. Vorgang abgebrochen.", ephemeral=True)
                return
            guild = interaction.guild
            user_id = int(value)
            member = guild.get_member(user_id)
            if not member:
                await interaction.response.send_message("❌ Mitglied nicht gefunden (möglicherweise hat es den Server verlassen).", ephemeral=True)
                return
            # Load strike data and increment the user's strike count
            strike_data = load_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
            strikes = strike_data.get("strikes", {})
            current = strikes.get(str(user_id), 0)
            new_count = current + 1
            strikes[str(user_id)] = new_count
            strike_data["strikes"] = strikes
            save_json(STRIKE_FILE, strike_data)
            # Assign the strike role if this was the 3rd strike
            role_id = strike_data.get("strike_role_id")
            role_assigned = False
            role = None
            if role_id:
                role = guild.get_role(int(role_id))
                if new_count == 3 and role:
                    try:
                        await member.add_roles(role)
                        role_assigned = True
                    except:
                        role_assigned = False
            # Prepare feedback message for the moderator
            if new_count == 3:
                if role and role_assigned:
                    resp = f"⚠️ {member.mention} hat nun **3** Strikes und erhält automatisch die Rolle **{role.name}**."
                elif role and not role_assigned:
                    resp = f"⚠️ {member.mention} hat nun **3** Strikes. *(Rolle **{role.name}** konnte nicht zugewiesen werden.)*"
                else:
                    resp = f"⚠️ {member.mention} hat nun **3** Strikes."
            else:
                resp = f"✔️ {member.mention} hat nun **{new_count}** Strikes."
            await interaction.response.send_message(resp, ephemeral=True)
            # Update the strike panel message with new list and reset dropdown
            text = generate_strike_list_text(strike_data, guild)
            await interaction.message.edit(content=text, view=StrikeView(guild, strike_data))
        select.callback = select_callback
        self.add_item(select)

@bot.tree.command(name="strikeaddrole", description="Legt eine Rolle fest, die beim dritten Strike vergeben wird")
@app_commands.describe(role="Rolle, die ab 3 Strikes automatisch zugewiesen wird")
async def strikeaddrole(interaction: discord.Interaction, role: discord.Role):
    # Save the role ID that should be assigned at 3 strikes
    strike_data = load_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
    strike_data["strike_role_id"] = str(role.id)
    save_json(STRIKE_FILE, strike_data)
    await interaction.response.send_message(f"✅ Rolle **{role.name}** wird nun bei 3 Strikes automatisch vergeben.", ephemeral=True)

@bot.tree.command(name="strikemain", description="Zeigt das Strike-Verwaltungsmenü mit Mitglieder-Dropdown")
async def strikemain(interaction: discord.Interaction):
    # Display the strike management panel with dropdown and current strike list
    strike_data = load_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
    text = generate_strike_list_text(strike_data, interaction.guild)
    view = StrikeView(interaction.guild, strike_data)
    await interaction.response.send_message(text, view=view)

@bot.tree.command(name="strikelist", description="Listet alle aktuellen Strikes auf")
async def strikelist(interaction: discord.Interaction):
    # Show the current strike list (ephemeral to the user invoking)
    strike_data = load_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
    text = generate_strike_list_text(strike_data, interaction.guild)
    await interaction.response.send_message(text, ephemeral=True)

# ---------- Wiki System ----------
wiki_group = app_commands.Group(name="wiki", description="Wiki-Verwaltung")

@wiki_group.command(name="page", description="Speichert die Nachrichten des aktuellen Kanals als Wiki-Seite")
async def wiki_page(interaction: discord.Interaction):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("❌ Dieser Befehl kann nur in Textkanälen verwendet werden.", ephemeral=True)
        return
    page_title = channel.name
    # Defer as reading channel history might take time
    await interaction.response.defer(ephemeral=True, thinking=True)
    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
    content_lines = []
    for msg in messages:
        if msg.author.bot:
            continue
        line = msg.content
        if msg.attachments:
            for attachment in msg.attachments:
                line += f"\n[Anhang: {attachment.url}]"
        if line:
            content_lines.append(line)
    page_content = "\n".join(content_lines)
    # Backup current pages and save new/updated page
    pages = load_json(WIKI_PAGES_FILE, {})
    backup = pages.copy()
    save_json(WIKI_BACKUP_FILE, backup)
    pages[page_title] = page_content
    save_json(WIKI_PAGES_FILE, pages)
    # Update the wiki menu if it exists
    wiki_config = load_json(WIKI_CONFIG_FILE, {"main_channel_id": None, "menu_message_id": None})
    main_channel_id = wiki_config.get("main_channel_id")
    menu_message_id = wiki_config.get("menu_message_id")
    if main_channel_id and menu_message_id:
        main_channel = interaction.guild.get_channel(int(main_channel_id))
        if main_channel:
            try:
                menu_msg = await main_channel.fetch_message(int(menu_message_id))
                content_text = "📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten."
                view = WikiMenuView(pages)
                await menu_msg.edit(content=content_text, view=view)
            except:
                # If menu message was deleted, send a new one
                new_msg = await main_channel.send("📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten.", view=WikiMenuView(pages))
                wiki_config["menu_message_id"] = str(new_msg.id)
                save_json(WIKI_CONFIG_FILE, wiki_config)
    await interaction.followup.send(f"✅ Wiki-Seite **{page_title}** wurde gespeichert.", ephemeral=True)

@wiki_group.command(name="undo", description="Stellt alle gespeicherten Wiki-Seiten aus dem Backup wieder her")
async def wiki_undo(interaction: discord.Interaction):
    backup_pages = load_json(WIKI_BACKUP_FILE, None)
    if backup_pages is None:
        await interaction.response.send_message("⚠️ Kein Backup zum Wiederherstellen gefunden.", ephemeral=True)
        return
    save_json(WIKI_PAGES_FILE, backup_pages)
    # Update the wiki menu to reflect the restored pages
    wiki_config = load_json(WIKI_CONFIG_FILE, {"main_channel_id": None, "menu_message_id": None})
    main_channel_id = wiki_config.get("main_channel_id")
    menu_message_id = wiki_config.get("menu_message_id")
    if main_channel_id and menu_message_id:
        main_channel = interaction.guild.get_channel(int(main_channel_id))
        if main_channel:
            try:
                menu_msg = await main_channel.fetch_message(int(menu_message_id))
                pages = backup_pages
                content_text = "📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten." if pages else "📚 **Wiki-Menü:** *(noch keine Seiten gespeichert)*"
                view = WikiMenuView(pages)
                await menu_msg.edit(content=content_text, view=view)
            except:
                new_msg = await main_channel.send(
                    "📚 **Wiki-Menü:** *(noch keine Seiten gespeichert)*" if not backup_pages else 
                    "📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten.",
                    view=WikiMenuView(backup_pages)
                )
                wiki_config["menu_message_id"] = str(new_msg.id)
                save_json(WIKI_CONFIG_FILE, wiki_config)
    await interaction.response.send_message("♻️ Wiki-Seiten aus Backup wiederhergestellt.", ephemeral=True)

# Add the wiki command group to the bot
bot.tree.add_command(wiki_group)

class WikiMenuView(discord.ui.View):
    def __init__(self, pages: dict[str, str]):
        super().__init__(timeout=None)
        # Create dropdown for available wiki pages
        options = []
        for title in pages.keys():
            label = title[:100] if len(title) > 100 else title
            options.append(discord.SelectOption(label=label, value=title))
            if len(options) >= 25:
                break
        if not options:
            options.append(discord.SelectOption(label="Keine Seiten verfügbar", value="none", default=True))
        select = discord.ui.Select(
            placeholder="Wiki-Seite auswählen...",
            options=options,
            custom_id="wiki_page_select"
        )
        if not pages:
            select.disabled = True
        async def select_callback(interaction: discord.Interaction):
            page_title = select.values[0]
            if page_title == "none":
                await interaction.response.send_message("⚠️ Keine Wiki-Seiten verfügbar.", ephemeral=True)
                return
            pages_data = load_json(WIKI_PAGES_FILE, {})
            content = pages_data.get(page_title)
            if content is None:
                await interaction.response.send_message("❌ Seite wurde nicht gefunden.", ephemeral=True)
                return
            try:
                if content and len(content) <= 1900:
                    await interaction.user.send(f"**Wiki-Seite: {page_title}**\n{content}")
                else:
                    safe_filename = re.sub(r'[^A-Za-z0-9\-_\.]', '_', f"{page_title}.txt")
                    with open(safe_filename, "w", encoding="utf-8") as f:
                        f.write(content or "(Seite ist leer)")
                    await interaction.user.send(file=discord.File(safe_filename))
                    os.remove(safe_filename)
                await interaction.response.send_message(f"📩 Inhalt der Seite **{page_title}** wurde dir per DM geschickt.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Konnte keine DM senden. Bitte prüfe deine Einstellungen.", ephemeral=True)
        select.callback = select_callback
        self.add_item(select)

@bot.tree.command(name="wikimain", description="Setzt den Hauptkanal für das Wiki-Menü")
@app_commands.describe(channel="Textkanal, in dem das Wiki-Hauptmenü angezeigt werden soll")
async def wikimain(interaction: discord.Interaction, channel: discord.TextChannel):
    # Save the main wiki channel and post the wiki menu there
    wiki_config = load_json(WIKI_CONFIG_FILE, {"main_channel_id": None, "menu_message_id": None})
    # Remove old menu if moving to a new channel
    if wiki_config.get("menu_message_id"):
        try:
            old_channel = interaction.guild.get_channel(int(wiki_config["main_channel_id"]))
            if old_channel:
                old_msg = await old_channel.fetch_message(int(wiki_config["menu_message_id"]))
                await old_msg.delete()
        except:
            pass
    wiki_config["main_channel_id"] = str(channel.id)
    wiki_config["menu_message_id"] = None
    save_json(WIKI_CONFIG_FILE, wiki_config)
    pages = load_json(WIKI_PAGES_FILE, {})
    content_text = "📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten." if pages else "📚 **Wiki-Menü:** *(noch keine Seiten gespeichert)*"
    view = WikiMenuView(pages)
    message = await channel.send(content_text, view=view)
    # Save the new menu message ID
    wiki_config["menu_message_id"] = str(message.id)
    save_json(WIKI_CONFIG_FILE, wiki_config)
    await interaction.response.send_message(f"✅ Wiki-Hauptkanal gesetzt: {channel.mention}", ephemeral=True)

# When the bot is ready, register persistent views and sync commands
@bot.event
async def on_ready():
    try:
        if TEST_GUILD_ID:
            await bot.tree.sync(guild=discord.Object(id=int(TEST_GUILD_ID)))
        else:
            await bot.tree.sync()
    except Exception as e:
        print(f"Error syncing commands: {e}")
    # Register persistent views for menus
    trans_data = load_json(TRANS_FILE, {"category_id": None, "log_channel_id": None, "profiles": []})
    bot.add_view(TranslationMenuView(trans_data.get("profiles", [])))
    if bot.guilds:
        target_guild = discord.utils.get(bot.guilds, id=int(TEST_GUILD_ID)) if TEST_GUILD_ID else bot.guilds[0]
        strike_data = load_json(STRIKE_FILE, {"strike_role_id": None, "strikes": {}})
        bot.add_view(StrikeView(target_guild, strike_data))
    pages = load_json(WIKI_PAGES_FILE, {})
    bot.add_view(WikiMenuView(pages))
    # Optionally refresh wiki menu message to match current pages (in case of changes while offline)
    wiki_config = load_json(WIKI_CONFIG_FILE, {"main_channel_id": None, "menu_message_id": None})
    if wiki_config.get("main_channel_id") and wiki_config.get("menu_message_id"):
        main_channel = bot.get_channel(int(wiki_config["main_channel_id"]))
        if main_channel:
            try:
                menu_msg = await main_channel.fetch_message(int(wiki_config["menu_message_id"]))
                content_text = "📚 **Wiki-Menü:** Wähle eine Seite aus dem Dropdown aus, um sie per DM zu erhalten." if pages else "📚 **Wiki-Menü:** *(noch keine Seiten gespeichert)*"
                await menu_msg.edit(content=content_text, view=WikiMenuView(pages))
            except Exception as e:
                print("Wiki menu update error:", e)
    print(f"✅ Bot ist online als {bot.user}.")
# Run the bot using token from .env (uncomment the next line in production)
# bot.run(TOKEN)
