import os
import json
import aiohttp
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

# === ENV + CONFIG ===
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID") or "1249813174731931740")   # dev/test server-id

MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

PROFILES_FILE   = "profiles.json"
MENU_FILE       = "translator_menu.json"
PROMPT_FILE     = "translator_prompt.json"
TRANS_CAT_FILE  = "trans_category.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

profiles      = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil", "Flirty": "junger, koketter, aber KEINE Emojis"})
menu_cfg      = load_json(MENU_FILE, {})
menu_channel_id = menu_cfg.get("channel_id")
menu_message_id = menu_cfg.get("message_id")
prompt_cfg    = load_json(PROMPT_FILE, {})
prompt_add    = prompt_cfg.get("addition", "")
trans_cat_cfg = load_json(TRANS_CAT_FILE, {})
trans_cat_id  = trans_cat_cfg.get("category_id", None)

active_sessions = {}      # (user_id, profile) -> channel_id
channel_info     = {}     # channel_id -> (user_id, profile, style)
channel_logs     = {}     # channel_id -> [ (user, text, translation) ]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(user):
    return getattr(user, "guild_permissions", None) and user.guild_permissions.administrator

async def call_gemini(prompt: str) -> str:
    payload = {
        "system_instruction": {"role": "system", "parts": [{"text": prompt}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    params = {"key": GOOGLE_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.post(MODEL_ENDPOINT, params=params, json=payload) as resp:
            if resp.status != 200:
                await resp.text()
                return "*Fehler bei Übersetzung*"
            data = await resp.json()
    cands = data.get("candidates", [])
    if not cands:
        return "*Fehler bei Übersetzung*"
    parts = cands[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()

def make_translation_menu():
    embed = discord.Embed(
        title="📝 Translation Support",
        description="Wähle ein Profil aus, um eine private Übersetzungs-Session zu starten:",
        color=discord.Color.teal()
    )
    view = discord.ui.View(timeout=None)
    options = [discord.SelectOption(label=nm, description=profiles[nm]) for nm in profiles]
    sel = discord.ui.Select(placeholder="Profil wählen...", options=options, max_values=1)
    async def sel_cb(inter: discord.Interaction):
        prof = inter.data["values"][0]
        await start_session(inter, prof)
        # Reset dropdown
        reset_embed, reset_view = make_translation_menu()
        await inter.message.edit(embed=reset_embed, view=reset_view)
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

async def update_translation_menu():
    global menu_channel_id, menu_message_id
    if not (menu_channel_id and menu_message_id):
        return
    ch = bot.get_channel(menu_channel_id)
    if not ch:
        return
    try:
        msg = await ch.fetch_message(menu_message_id)
        embed, view = make_translation_menu()
        await msg.edit(embed=embed, view=view)
    except Exception:
        pass

async def start_session(interaction: discord.Interaction, prof: str):
    user = interaction.user
    style = profiles[prof]
    key = (user.id, prof)
    if key in active_sessions:
        old = active_sessions[key]
        if not bot.get_channel(old):
            del active_sessions[key]
    if key in active_sessions:
        return await interaction.response.send_message("Du hast bereits eine aktive Session.", ephemeral=True)
    guild = interaction.guild
    cat = bot.get_channel(trans_cat_id) if trans_cat_id else None
    if not cat or cat.type != discord.ChannelType.category:
        cat = None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }
    chan_name = f"translat-{prof.lower()}-{user.display_name.lower()}".replace(" ", "-")
    old = None
    channels = cat.text_channels if cat else guild.text_channels
    for c in channels:
        if c.name == chan_name:
            old = c
            break
    if old:
        await old.delete()
    ch = await guild.create_text_channel(chan_name, category=cat, overwrites=overwrites)
    active_sessions[key] = ch.id
    channel_info[ch.id] = (user.id, prof, style)
    channel_logs[ch.id] = []

    btn = discord.ui.Button(label="Session beenden & Verlauf senden", style=discord.ButtonStyle.danger)
    async def end_cb(bi: discord.Interaction):
        info = channel_info.get(ch.id)
        if not info or bi.user.id != info[0]:
            return await bi.response.send_message("Nur der Besitzer kann beenden.", ephemeral=True)
        log = channel_logs.get(ch.id, [])
        log_embed = discord.Embed(
            title=f"Übersetzungs-Session Verlauf ({prof})",
            color=discord.Color.orange(),
            description=f"User: {bi.user.display_name}\nProfil: {prof}\nAnzahl Übersetzungen: {len(log)}"
        )
        for i, (uname, text, trans) in enumerate(log[-10:], 1):
            log_embed.add_field(
                name=f"{i}. {uname}:",
                value=f"**Input:** {text}\n**Output:** {trans}",
                inline=False
            )
        log_channel_id = load_json(MENU_FILE, {}).get("log_channel_id", None)
        if log_channel_id:
            log_channel = bi.guild.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(embed=log_embed)
        await bi.response.send_message("Session beendet & Verlauf wurde an den Log gesendet.", ephemeral=True)
        await ch.delete()
        try: del channel_info[ch.id]
        except: pass
        try: del active_sessions[key]
        except: pass
        try: del channel_logs[ch.id]
        except: pass
    btn.callback = end_cb
    v = discord.ui.View(timeout=None)
    v.add_item(btn)
    await ch.send(f"Session **{prof}** gestartet. Schreibe hier zum Übersetzen.", view=v)
    await interaction.response.send_message(f"Session erstellt: {ch.mention}", ephemeral=True)

@bot.event
async def on_ready():
    # Slash-Befehle schnell synchronisieren für DEV-Server
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Sync-Error:", e)
    print(f'Bot ist online als {bot.user}.')

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    info = channel_info.get(message.channel.id)
    if not info or message.author.id != info[0]:
        return
    txt = message.content.strip()
    if not txt:
        return
    base_prompt = (
        "Erkenne die Sprache des folgenden OnlyFans-Chat-Textes."
        " Wenn es Deutsch ist, übersetze ihn nuanciert ins Englische im Stil: {style}."
        " Wenn es Englisch ist, übersetze ihn nuanciert ins Deutsche im Stil: {style}."
        " Verwende echten Slang, Chat-Sprache, keine Emojis, keine Smileys, keine Abkürzungen wie :), ;), etc."
        " KEINE Emojis, keine Icons, keine GIFs. Es soll spontan, natürlich, aber menschlich klingen, nicht KI-generiert."
        " Finde echte Äquivalente für kulturelle Referenzen."
        " Antworte NUR mit der Übersetzung und nichts anderem."
    )
    prompt_extension = load_json(PROMPT_FILE, {}).get("addition", "")
    prompt = base_prompt.format(style=info[2])
    if prompt_extension:
        prompt += "\nZusätzliche Regel: " + prompt_extension
    prompt += f"\n{txt}"

    try:
        translation = await asyncio.wait_for(call_gemini(prompt), timeout=25)
    except Exception:
        translation = "*Fehler bei Übersetzung*"

    emb = discord.Embed(description=f"```{translation}```", color=discord.Color.blue())
    emb.set_footer(text="Auto-Detected Translation")
    await message.channel.send(embed=emb)
    channel_logs[message.channel.id].append((message.author.display_name, txt, translation))
    await bot.process_commands(message)

def owner_or_admin_check(interaction):
    return interaction.user.guild_permissions.administrator or (hasattr(bot, "owner_id") and interaction.user.id == bot.owner_id)

@bot.tree.command(name="translatorpost", description="Postet das Übersetzungsmenü im aktuellen Kanal", guild=discord.Object(id=GUILD_ID))
async def translatorpost(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_translation_menu()
    msg = await interaction.channel.send(embed=embed, view=view)
    global menu_channel_id, menu_message_id
    menu_channel_id = interaction.channel.id
    menu_message_id = msg.id
    save_json(MENU_FILE, {"channel_id": menu_channel_id, "message_id": msg.id})
    await interaction.response.send_message("Übersetzungsmenü gepostet.", ephemeral=True)

@bot.tree.command(name="translatoraddprofile", description="Fügt ein neues Übersetzer-Profil hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Profilname", style="Stilbeschreibung")
async def translatoraddprofile(interaction: discord.Interaction, name: str, style: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    nm = name.strip()
    if not nm or nm in profiles:
        return await interaction.response.send_message("Ungültiger oder existierender Name.", ephemeral=True)
    profiles[nm] = style
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{nm}** hinzugefügt.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translatordeleteprofile", description="Löscht ein Übersetzer-Profil", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Profilname")
async def translatordeleteprofile(interaction: discord.Interaction, name: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if name not in profiles:
        return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
    profiles.pop(name)
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translatorsetcategorie", description="Setzt die Kategorie für Übersetzungs-Session-Channels", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(category="Kategorie")
async def translatorsetcategorie(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global trans_cat_id
    trans_cat_id = category.id
    save_json(TRANS_CAT_FILE, {"category_id": category.id})
    await interaction.response.send_message(f"Kategorie gesetzt: {category.name}", ephemeral=True)

@bot.tree.command(name="translatorlog", description="Setzt den Log-Kanal für Übersetzungs-Session-Verläufe", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Text-Kanal für Logs")
async def translatorlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    menu_cfg = load_json(MENU_FILE, {})
    menu_cfg["log_channel_id"] = channel.id
    save_json(MENU_FILE, menu_cfg)
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="translatorprompt", description="Fügt eine Regel zum Haupt-Prompt hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="Zusätzlicher Prompt-Text")
async def translatorprompt(interaction: discord.Interaction, text: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_json(PROMPT_FILE, {"addition": text})
    await interaction.response.send_message(f"Prompt-Erweiterung gesetzt: **{text}**", ephemeral=True)

@bot.tree.command(name="translatorpromptdelete", description="Entfernt die zusätzliche Prompt-Regel", guild=discord.Object(id=GUILD_ID))
async def translatorpromptdelete(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_json(PROMPT_FILE, {"addition": ""})
    await interaction.response.send_message("Prompt-Erweiterung entfernt.", ephemeral=True)

# ───── SCHICHTÜBERGABE SYSTEM ──────────────────────────────────────────────────────────────

SCHICHT_CONFIG_FILE = "schicht_config.json"

def load_schicht_cfg():
    try:
        with open(SCHICHT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_schicht_cfg(data):
    with open(SCHICHT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

schicht_cfg = load_schicht_cfg()
schicht_channel_id = schicht_cfg.get("channel_id")
schicht_voicemaster_id = schicht_cfg.get("voicemaster_id")
schicht_log_id = schicht_cfg.get("log_id")
schicht_allowed_roles = set(schicht_cfg.get("allowed_roles", []))

# Hilfsfunktion: Rechtecheck für Schichtübergabe (Admin oder erlaubte Rolle)
def is_schicht_admin(user):
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if hasattr(user, "id") and user.id == bot.owner_id:
        return True
    return False

def has_schicht_role(user):
    return any(r.id in schicht_allowed_roles for r in user.roles) or is_schicht_admin(user)

# Befehl: Schicht-Kanal festlegen
@bot.tree.command(name="schichtwechsel", description="Setzt den Schichtwechsel-Channel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Text-Channel für Schichtwechsel")
async def schichtwechsel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_schicht_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global schicht_channel_id
    schicht_channel_id = channel.id
    schicht_cfg["channel_id"] = schicht_channel_id
    save_schicht_cfg(schicht_cfg)
    await interaction.response.send_message(f"Schichtwechsel-Channel gesetzt: {channel.mention}", ephemeral=True)
    await post_schicht_info()

# Befehl: VoiceMaster Eingangskanal festlegen
@bot.tree.command(name="schichtvoiceid", description="Setzt den Eingangskanal für VoiceMaster", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(voice_id="Channel-ID für VoiceMaster-Eingang")
async def schichtvoiceid(interaction: discord.Interaction, voice_id: str):
    if not is_schicht_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global schicht_voicemaster_id
    schicht_voicemaster_id = int(voice_id)
    schicht_cfg["voicemaster_id"] = schicht_voicemaster_id
    save_schicht_cfg(schicht_cfg)
    await interaction.response.send_message(f"VoiceMaster-Eingangskanal gesetzt: `{voice_id}`", ephemeral=True)

# Befehl: Log-Channel festlegen
@bot.tree.command(name="schichtlog", description="Setzt den Log-Channel für Schichtübergaben", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Text-Channel für Schicht-Logs")
async def schichtlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_schicht_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global schicht_log_id
    schicht_log_id = channel.id
    schicht_cfg["log_id"] = schicht_log_id
    save_schicht_cfg(schicht_cfg)
    await interaction.response.send_message(f"Schicht-Log-Channel gesetzt: {channel.mention}", ephemeral=True)

# Rollen erlauben/entfernen
@bot.tree.command(name="schichtrollen", description="Erlaubt eine Rolle für Schichtübergabe", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Rolle für Schichtübergabe freischalten")
async def schichtrollen(interaction: discord.Interaction, role: discord.Role):
    if not is_schicht_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    schicht_allowed_roles.add(role.id)
    schicht_cfg["allowed_roles"] = list(schicht_allowed_roles)
    save_schicht_cfg(schicht_cfg)
    await interaction.response.send_message(f"Rolle {role.mention} kann jetzt als Ziel gewählt werden.", ephemeral=True)

@bot.tree.command(name="schichtrollenremove", description="Entfernt eine erlaubte Rolle", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Rolle für Schichtübergabe entfernen")
async def schichtrollenremove(interaction: discord.Interaction, role: discord.Role):
    if not is_schicht_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if role.id in schicht_allowed_roles:
        schicht_allowed_roles.remove(role.id)
        schicht_cfg["allowed_roles"] = list(schicht_allowed_roles)
        save_schicht_cfg(schicht_cfg)
        await interaction.response.send_message(f"Rolle {role.mention} ist entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Rolle {role.mention} war nicht freigeschaltet.", ephemeral=True)

# Die Haupt-Info/Botnachricht im Schicht-Channel posten
async def post_schicht_info():
    if not schicht_channel_id:
        return
    ch = bot.get_channel(schicht_channel_id)
    if not ch:
        return
    embed = discord.Embed(
        title="⏰ Schichtübergabe starten",
        description=(
            "**So funktioniert es:**\n"
            "• Tippe `/schichtuebergabe nutzer:<name>` in den Chat\n"
            "• Wähle den gewünschten Nutzer (mit passender Rolle!) aus der Liste aus\n"
            "• Fertig! Die Schichtübergabe läuft automatisch ab.\n\n"
            "**Der Befehl:**\n"
            "```/schichtuebergabe nutzer:<name>```\n"
            "_Der Nutzer muss aktuell in einem Sprachkanal sein und eine erlaubte Rolle haben._\n"
            "_Du musst dich in einem Sprachkanal befinden._"
        ),
        color=discord.Color.purple()
    )
    await ch.send(embed=embed)

# Befehl: Schichtübergabe durchführen
@bot.tree.command(name="schichtuebergabe", description="Starte eine Schichtübergabe", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nutzer="Discord-Benutzername (autocomplete möglich)")
async def schichtuebergabe(interaction: discord.Interaction, nutzer: str):
    # Prüfe, ob User die Berechtigung hat (Admin, allowed Role)
    if not has_schicht_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung für die Schichtübergabe.", ephemeral=True)

    # Prüfe, ob User selbst in einem Sprachkanal ist
    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("Du musst dich in einem Sprachkanal befinden!", ephemeral=True)

    # Finde den Ziel-User
    target = discord.utils.find(
        lambda m: m.display_name.lower() == nutzer.lower() or m.name.lower() == nutzer.lower(), interaction.guild.members
    )
    if not target:
        return await interaction.response.send_message(f"Nutzer `{nutzer}` nicht gefunden.", ephemeral=True)
    if target.bot:
        return await interaction.response.send_message("Bots können nicht als Ziel gewählt werden!", ephemeral=True)
    if not any(r.id in schicht_allowed_roles for r in target.roles):
        return await interaction.response.send_message(f"{target.mention} hat keine erlaubte Rolle für die Schichtübergabe!", ephemeral=True)
    # Prüfe, ob Ziel im Voice ist
    if not target.voice or not target.voice.channel:
        # Versuch, DM zu schicken
        try:
            await target.send(f"{interaction.user.mention} möchte dir die Schicht übergeben! Komm bitte ASAP online/in den Sprachkanal.")
            await interaction.response.send_message(
                f"{target.mention} ist nicht im Sprachkanal. Er wurde per DM benachrichtigt.", ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                f"{target.mention} ist nicht im Sprachkanal **und** hat DMs deaktiviert – bitte kontaktiere ihn persönlich.",
                ephemeral=True)
        return

    # Starte den Move-Prozess
    voicemaster_channel = bot.get_channel(schicht_voicemaster_id) if schicht_voicemaster_id else None
    if not voicemaster_channel:
        return await interaction.response.send_message("VoiceMaster-Eingangskanal ist nicht gesetzt.", ephemeral=True)
    # Move den anfragenden User in den Eingangskanal (VoiceMaster)
    try:
        await interaction.user.move_to(voicemaster_channel)
        await interaction.response.send_message(
            f"{interaction.user.mention} wird in den VoiceMaster-Eingang verschoben, Schichtübergabe läuft!", ephemeral=True)
        await asyncio.sleep(5)  # Warten bis temporärer Channel erstellt wird
        # Finde den Channel, in dem der anfragende User jetzt sitzt (könnte neu sein)
        after_channel = interaction.user.voice.channel
        await target.move_to(after_channel)
        # Log-Eintrag
        if schicht_log_id:
            logch = bot.get_channel(schicht_log_id)
            if logch:
                await logch.send(f"**Schichtwechsel**: {interaction.user.mention} → {target.mention} ✅ (Voice: {after_channel.name})")
    except Exception as e:
        await interaction.followup.send(f"Fehler beim Verschieben: {e}", ephemeral=True)

# Beim Bot-Start ggf. Info-Nachricht erneut posten
@bot.event
async def on_ready():
    global schicht_cfg, schicht_channel_id, schicht_voicemaster_id, schicht_log_id, schicht_allowed_roles
    schicht_cfg = load_schicht_cfg()
    schicht_channel_id = schicht_cfg.get("channel_id")
    schicht_voicemaster_id = schicht_cfg.get("voicemaster_id")
    schicht_log_id = schicht_cfg.get("log_id")
    schicht_allowed_roles = set(schicht_cfg.get("allowed_roles", []))
    await post_schicht_info()



WIKI_PAGES_FILE = "wiki_pages.json"
WIKI_MENU_FILE  = "wiki_menu.json"
WIKI_BACKUP_FILE = "wiki_backup.json"

def load_wiki_pages():
    return load_json(WIKI_PAGES_FILE, {})

def save_wiki_pages(data):
    save_json(WIKI_PAGES_FILE, data)

def load_wiki_menu():
    return load_json(WIKI_MENU_FILE, {})

def save_wiki_menu(data):
    save_json(WIKI_MENU_FILE, data)

def save_wiki_backup(data):
    save_json(WIKI_BACKUP_FILE, data)

def load_wiki_backup():
    return load_json(WIKI_BACKUP_FILE, {})

wiki_menu_cfg = load_wiki_menu()
wiki_menu_channel_id = wiki_menu_cfg.get("channel_id")
wiki_menu_message_id = wiki_menu_cfg.get("message_id")

def split_long_text(text, prefix=""):
    maxlen = 2000 - len(prefix)
    parts = []
    while text:
        chunk = text[:maxlen]
        # Am besten an einem Zeilenumbruch trennen
        if len(chunk) == maxlen and "\n" in chunk:
            last_n = chunk.rfind("\n")
            if last_n > 0:
                chunk = chunk[:last_n]
        parts.append(chunk)
        text = text[len(chunk):]
    return parts

def make_wiki_menu_embed_and_view():
    pages = load_wiki_pages()
    embed = discord.Embed(
        title="📚 Space-Guide Wiki",
        description="Wähle eine Seite aus, um den Infotext **privat** hier angezeigt zu bekommen:",
        color=discord.Color.green()
    )
    view = discord.ui.View(timeout=None)
    if not pages:
        embed.add_field(name="(Keine Wiki-Seiten)", value="Erstelle zuerst Seiten mit `/wiki_page`", inline=False)
        return embed, view
    options = [discord.SelectOption(label=title, value=title) for title in pages]
    sel = discord.ui.Select(placeholder="Seite wählen...", options=options, max_values=1)
    async def sel_cb(inter: discord.Interaction):
        page = inter.data["values"][0]
        text = pages.get(page, "**Seite leer**")
        # Text splitten falls zu lang
        parts = split_long_text(text)
        total = len(parts)
        # Discord Ephemeral: Erste Nachricht via response, Rest via followup!
        if total > 0:
            prefix = f"**{page}**\n" if total == 1 else f"**{page}**\n**Seitenauszug [1/{total}]**\n"
            await inter.response.send_message(f"{prefix}{parts[0]}", ephemeral=True)
            for i, chunk in enumerate(parts[1:], start=2):
                head = f"**Seitenauszug [{i}/{total}]**\n"
                await inter.followup.send(f"{head}{chunk}", ephemeral=True, wait=True)
        else:
            await inter.response.send_message(f"**{page}**\n*(leer)*", ephemeral=True)
        # Menü zurücksetzen
        reset_embed, reset_view = make_wiki_menu_embed_and_view()
        try:
            await inter.message.edit(embed=reset_embed, view=reset_view)
        except:
            pass
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

async def update_wiki_menu():
    global wiki_menu_channel_id, wiki_menu_message_id
    if not (wiki_menu_channel_id and wiki_menu_message_id):
        return
    ch = bot.get_channel(wiki_menu_channel_id)
    if not ch:
        return
    try:
        msg = await ch.fetch_message(wiki_menu_message_id)
        embed, view = make_wiki_menu_embed_and_view()
        await msg.edit(embed=embed, view=view)
    except:
        pass

@bot.tree.command(name="wikimain", description="Postet das Wiki-Dropdown-Menü im aktuellen Channel", guild=discord.Object(id=GUILD_ID))
async def wikimain(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_wiki_menu_embed_and_view()
    msg = await interaction.channel.send(embed=embed, view=view)
    global wiki_menu_channel_id, wiki_menu_message_id
    wiki_menu_channel_id = interaction.channel.id
    wiki_menu_message_id = msg.id
    save_wiki_menu({"channel_id": wiki_menu_channel_id, "message_id": wiki_menu_message_id})
    await interaction.response.send_message("Wiki-Menü gepostet.", ephemeral=True)

@bot.tree.command(name="wiki_page", description="Legt den aktuellen Channel als Wiki-Seite an und löscht ihn dann", guild=discord.Object(id=GUILD_ID))
async def wiki_page(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    channel = interaction.channel
    msgs = [m async for m in channel.history(limit=30, oldest_first=True) if not m.author.bot]
    text = "\n".join([f"{m.author.display_name}: {m.content}" for m in msgs if m.content.strip()])
    title = channel.name
    # Backup speichern
    pages = load_wiki_pages()
    backup = load_wiki_backup()
    backup[title] = pages.get(title, "")
    save_wiki_backup(backup)
    # Jetzt speichern
    pages[title] = text if text else "(keine Nachrichten gefunden)"
    save_wiki_pages(pages)
    await interaction.response.send_message(f"Seite **{title}** gespeichert und Channel wird gelöscht!", ephemeral=True)
    await update_wiki_menu()
    await asyncio.sleep(2)
    try:
        await channel.delete(reason="Als Wiki-Seite gespeichert.")
    except Exception:
        pass

@bot.tree.command(name="wiki_undo", description="Stellt eine Backup-Wiki-Seite wieder als Channel her", guild=discord.Object(id=GUILD_ID))
async def wiki_undo(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    backup = load_wiki_backup()
    if not backup:
        return await interaction.response.send_message("Kein Backup vorhanden.", ephemeral=True)
    options = [discord.SelectOption(label=title, value=title) for title in backup]
    if not options:
        return await interaction.response.send_message("Backup ist leer.", ephemeral=True)
    sel = discord.ui.Select(placeholder="Seite wählen...", options=options, max_values=1)
    view = discord.ui.View(timeout=60)
    async def sel_cb(inter):
        page = inter.data["values"][0]
        text = backup.get(page, "")
        # Channel erstellen, falls nicht vorhanden
        guild = interaction.guild
        chan_name = page.replace(" ", "-")[:30]
        exists = discord.utils.get(guild.text_channels, name=chan_name)
        if exists:
            await inter.response.send_message("Channel existiert bereits!", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        ch = await guild.create_text_channel(chan_name, overwrites=overwrites, reason="Wiki-Restore aus Backup")
        # Text splitten falls zu lang
        parts = split_long_text(text)
        for chunk in parts:
            await ch.send(chunk)
        await inter.response.send_message(f"Backup-Seite **{page}** wurde als Channel `{chan_name}` wiederhergestellt!", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Seite aus dem Backup zum Wiederherstellen:", view=view, ephemeral=True)

@bot.tree.command(name="wiki_edit", description="Bearbeite eine Wiki-Seite per Dropdown", guild=discord.Object(id=GUILD_ID))
async def wiki_edit(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    pages = load_wiki_pages()
    if not pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    options = [discord.SelectOption(label=title, value=title) for title in pages]
    sel = discord.ui.Select(placeholder="Seite wählen...", options=options, max_values=1)
    view = discord.ui.View(timeout=60)
    async def sel_cb(inter):
        page = inter.data["values"][0]
        old_text = pages.get(page, "")
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            inter.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        chan_name = f"wiki-edit-{page}".replace(" ", "-")[:30]
        for ch in guild.text_channels:
            if ch.name == chan_name and inter.user in ch.members:
                await ch.delete()
        ch = await guild.create_text_channel(chan_name, overwrites=overwrites, reason="Wiki-Edit")
        await ch.send(f"**Bearbeite die Wiki-Seite:** `{page}`\n\nAktueller Text:\n```{old_text}```\n\n**Sende jetzt die neue Version als eine Nachricht.**")
        def check(msg):
            return msg.channel == ch and msg.author == inter.user and not msg.author.bot
        try:
            msg = await bot.wait_for('message', timeout=300, check=check)
            button = discord.ui.Button(label="Speichern & Schließen", style=discord.ButtonStyle.success)
            async def btn_cb(button_inter):
                pages2 = load_wiki_pages()
                pages2[page] = msg.content
                save_wiki_pages(pages2)
                await update_wiki_menu()
                await button_inter.response.send_message("Gespeichert & Channel wird geschlossen.", ephemeral=True)
                await ch.delete()
            button.callback = btn_cb
            v = discord.ui.View(timeout=120)
            v.add_item(button)
            await ch.send("Klicke **Speichern & Schließen** zum Übernehmen.", view=v)
        except asyncio.TimeoutError:
            await ch.send("Zeit abgelaufen, Channel wird gelöscht.")
            await asyncio.sleep(2)
            await ch.delete()
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Wiki-Seite zum Bearbeiten:", view=view, ephemeral=True)

@bot.tree.command(name="wiki_delete", description="Löscht eine Wiki-Seite per Dropdown", guild=discord.Object(id=GUILD_ID))
async def wiki_delete(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    pages = load_wiki_pages()
    if not pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    options = [discord.SelectOption(label=title, value=title) for title in pages]
    sel = discord.ui.Select(placeholder="Seite wählen...", options=options, max_values=1)
    view = discord.ui.View(timeout=60)
    async def sel_cb(inter):
        page = inter.data["values"][0]
        pages2 = load_wiki_pages()
        if page in pages2:
            pages2.pop(page)
            save_wiki_pages(pages2)
            await update_wiki_menu()
            await inter.response.send_message(f"**{page}** gelöscht.", ephemeral=True)
        else:
            await inter.response.send_message("Seite nicht gefunden.", ephemeral=True)
        reset_embed, reset_view = make_wiki_menu_embed_and_view()
        try:
            await interaction.message.edit(embed=reset_embed, view=reset_view)
        except:
            pass
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Wiki-Seite zum **Löschen**:", view=view, ephemeral=True)
 
# SCHICHTSYSTEM: Schichtübergabe ohne Button – nur Hinweis zum Command

SCHICHT_CONFIG_FILE = "schicht_config.json"
GUILD_ID = 1249813174731931740

def load_schicht_config():
    return load_json(SCHICHT_CONFIG_FILE, {
        "wechsel_channel_id": None,
        "voice_channel_id": 1381587186469568545,
        "log_channel_id": None,
        "rollen": []
    })

def save_schicht_config(data):
    save_json(SCHICHT_CONFIG_FILE, data)

schicht_cfg = load_schicht_config()

def get_schichtrollen(guild):
    return [guild.get_role(rid) for rid in schicht_cfg.get("rollen", []) if guild.get_role(rid)]

async def post_schicht_message():
    ch_id = schicht_cfg.get("wechsel_channel_id")
    if not ch_id:
        return
    ch = bot.get_channel(ch_id)
    if not ch:
        return
    async for m in ch.history(limit=10):
        if m.author == bot.user and (m.embeds or m.components):
            await m.delete()
    embed = discord.Embed(
        title="🕒 Schichtübergabe starten",
        description=(
            "**So funktioniert es:**\n"
            "• Tippe `/schichtuebergabe` in den Chat\n"
            "• Wähle den gewünschten Nutzer (mit passender Rolle!) aus der Liste\n"
            "• Fertig! Die Schichtübergabe läuft automatisch ab.\n\n"
            "**Der Befehl:**\n"
            "`/schichtuebergabe nutzer:<name>`\n\n"
            "> Der Nutzer muss aktuell online sein und eine erlaubte Rolle haben.\n"
            "> Du musst dich in einem Sprachkanal befinden."
        ),
        color=discord.Color.purple()
    )
    await ch.send(embed=embed)

# ----------- Setup-Befehle (alle nur Admin) -----------

@bot.tree.command(name="schichtwechsel", description="Setzt den Schichtwechsel-Textkanal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Textkanal für Schichtübergabe")
async def schichtwechsel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    schicht_cfg["wechsel_channel_id"] = channel.id
    save_schicht_config(schicht_cfg)
    await post_schicht_message()
    await interaction.response.send_message(f"Schichtwechsel-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="schicht_voiceid", description="Setzt den VoiceMaster-Eingangskanal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(voice_id="ID des VoiceMaster-Eingangskanals")
async def schicht_voiceid(interaction: discord.Interaction, voice_id: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    schicht_cfg["voice_channel_id"] = int(voice_id)
    save_schicht_config(schicht_cfg)
    await interaction.response.send_message(f"VoiceMaster-Eingangskanal gesetzt: <#{voice_id}>", ephemeral=True)

@bot.tree.command(name="schichtlog", description="Setzt den Logkanal für Schichtwechsel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Textkanal für Log")
async def schichtlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    schicht_cfg["log_channel_id"] = channel.id
    save_schicht_config(schicht_cfg)
    await interaction.response.send_message(f"Schicht-Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="schichtrollen", description="Fügt eine Rolle zur Schichtübergabe-Auswahl hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def schichtrollen(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if role.id not in schicht_cfg["rollen"]:
        schicht_cfg["rollen"].append(role.id)
        save_schicht_config(schicht_cfg)
    await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt für Schichtwechsel auswählbar.", ephemeral=True)

@bot.tree.command(name="schichtrollen_remove", description="Entfernt eine Rolle aus der Schichtübergabe-Auswahl", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def schichtrollen_remove(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if role.id in schicht_cfg["rollen"]:
        schicht_cfg["rollen"].remove(role.id)
        save_schicht_config(schicht_cfg)
    await interaction.response.send_message(f"Rolle **{role.name}** wurde entfernt.", ephemeral=True)

# ----------- Haupt-Command mit User-Autocomplete -----------

async def schicht_autocomplete(interaction, current):
    guild = interaction.guild
    rollen = get_schichtrollen(guild)
    member_ids = set()
    for r in rollen:
        if r: member_ids.update([m.id for m in r.members])
    if not member_ids:
        members = [m for m in guild.members if not m.bot]
    else:
        members = [m for m in guild.members if m.id in member_ids and not m.bot]
    filtered = []
    current_lower = current.lower()
    for m in members:
        if current_lower in m.display_name.lower() or current_lower in m.name.lower():
            filtered.append(app_commands.Choice(name=m.display_name, value=str(m.id)))
        if len(filtered) >= 25:
            break
    return filtered

@bot.tree.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nutzer="Nutzer für Übergabe")
@app_commands.autocomplete(nutzer=schicht_autocomplete)
async def schichtuebergabe(interaction: discord.Interaction, nutzer: str):
    member = interaction.guild.get_member(int(nutzer))
    anfragender = interaction.user
    if not anfragender.voice or not anfragender.voice.channel:
        return await interaction.response.send_message("❌ Du musst in einem Sprachkanal sein für Schichtwechsel.", ephemeral=True)
    if not member:
        return await interaction.response.send_message("❌ Nutzer nicht gefunden.", ephemeral=True)
    if not member.status in [discord.Status.online, discord.Status.idle, discord.Status.dnd]:
        try:
            await member.send(f"{anfragender.mention} möchte Schicht übergeben! Bitte melde dich asap für den Schichtwechsel.")
            await interaction.response.send_message(f"{member.mention} ist offline. Er wurde per DM benachrichtigt.", ephemeral=True)
        except:
            await interaction.response.send_message(f"{member.mention} ist offline und hat DMs deaktiviert. Bitte kontaktiere ihn manuell.", ephemeral=True)
        return
    guild = interaction.guild
    voice_kanal = guild.get_channel(schicht_cfg["voice_channel_id"])
    if not voice_kanal:
        return await interaction.response.send_message("❌ VoiceMaster-Eingangskanal nicht gefunden!", ephemeral=True)
    try:
        await anfragender.move_to(voice_kanal)
        await interaction.response.send_message("Du wurdest in den VoiceMaster-Eingang verschoben. Starte Schichtübergabe...", ephemeral=True)
    except Exception as e:
        return await interaction.response.send_message("❌ Verschieben fehlgeschlagen (Prüfe Rechte)!", ephemeral=True)
    await asyncio.sleep(5)
    new_channel = anfragender.voice.channel if anfragender.voice else None
    if not new_channel or new_channel.id == voice_kanal.id:
        return await interaction.followup.send("❌ Temporärer Channel wurde nicht erkannt! Bitte manuell checken.", ephemeral=True)
    try:
        await member.move_to(new_channel)
        await interaction.followup.send(f"{member.mention} wurde zu dir verschoben! Schichtübergabe läuft.", ephemeral=True)
        log_id = schicht_cfg.get("log_channel_id")
        if log_id:
            log_ch = guild.get_channel(log_id)
            if log_ch:
                await log_ch.send(
                    f"**Schichtwechsel**: {anfragender.mention} ➡️ {member.mention}\n"
                    f"Channel: `{new_channel.name}`\nZeit: <t:{int(discord.utils.utcnow().timestamp())}:F>")
    except Exception:
        await interaction.followup.send(f"{member.mention} konnte nicht verschoben werden (Prüfe Rechte/DND/AFK).", ephemeral=True)

# ----------- On ready: Message & Commands synchronisieren -----------

@bot.event
async def on_ready():
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            await bot.tree.sync(guild=guild)
            print(f"Slash-Commands für Guild {guild.name} synchronisiert!")
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Sync-Error:", e)
    await post_schicht_message()


# --- Script-Ende für diesen Part ---
# NUR EINMAL GANZ UNTEN!
bot.run(DISCORD_TOKEN)

