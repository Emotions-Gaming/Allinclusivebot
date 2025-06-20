import os
import json
import aiohttp
import asyncio
import datetime

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ====== Umgebungsvariablen und Konstanten ======
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID", "1374724357741609041"))
TEMP_CATEGORY_ID = int(os.getenv("TEMP_CATEGORY_ID", "1374724358932664330"))
MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

PROFILES_FILE = "profiles.json"
LOG_FILE = "translation_log.json"
MENU_FILE = "translator_menu.json"
PROMPT_FILE = "translation_prompt.json"
TRANS_CAT_FILE = "trans_category.json"

STRIKE_FILE = "strike_data.json"
STRIKE_LIST_FILE = "strike_list.json"
STRIKE_ROLES_FILE = "strike_roles.json"
STRIKE_REWARD_FILE = "strike_reward.json"

# ====== JSON Helper ======
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== Daten laden ======
profiles = load_json(PROFILES_FILE, {"Normal":"neutraler professioneller Stil","Flirty":"junger koketter Ton"})
prompt_cfg = load_json(PROMPT_FILE, {})
prompt_add = prompt_cfg.get("addition", "")
trans_cat_cfg = load_json(TRANS_CAT_FILE, {})
trans_cat_id = trans_cat_cfg.get("category_id", TEMP_CATEGORY_ID)

log_cfg = load_json(LOG_FILE, {})
log_channel_id = log_cfg.get("log_channel_id")
menu_cfg = load_json(MENU_FILE, {})
menu_channel_id = menu_cfg.get("channel_id")
menu_message_id = menu_cfg.get("message_id")

strike_data = load_json(STRIKE_FILE, {})
strike_list_cfg = load_json(STRIKE_LIST_FILE, {})
strike_list_channel_id = strike_list_cfg.get("channel_id")
strike_roles_cfg = load_json(STRIKE_ROLES_FILE, {})
strike_roles = set(strike_roles_cfg.get("role_ids", []))
strike_reward_cfg = load_json(STRIKE_REWARD_FILE, {})
strike_reward_role_id = strike_reward_cfg.get("role_id")

active_sessions = {}  # (user_id, profile) -> channel_id
channel_info = {}     # channel_id -> (user_id, profile, style)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== Hilfsfunktionen: Rechte & Owner ======
def is_admin(user):
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if hasattr(bot, "owner_id") and user.id == bot.owner_id:
        return True
    return False

async def setup_owner_id():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id

def has_strike_role(user):
    return any(r.id in strike_roles for r in user.roles) or is_admin(user)

# ====== Google Gemini API ======
async def call_gemini(prompt: str) -> str:
    payload = {
        "system_instruction": {"role":"system","parts":[{"text":prompt}]},
        "contents": [{"role":"user","parts":[{"text":prompt}]}]
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
    return "".join(p.get("text","") for p in parts).strip()

# ====== Übersetzer: Menü ======
def make_translation_menu():
    embed = discord.Embed(
        title="📝 Translation Support",
        description="Wähle dein Profil aus, um eine private Übersetzungs-Session zu starten:",
        color=discord.Color.teal()
    )
    view = discord.ui.View(timeout=None)
    options = [discord.SelectOption(label=nm, description=profiles[nm]) for nm in profiles]
    sel = discord.ui.Select(placeholder="Profil wählen...", options=options, max_values=1)
    async def sel_cb(inter: discord.Interaction):
        prof = inter.data["values"][0]
        await start_session(inter, prof)
        # Dropdown reset
        await inter.message.edit(embed=embed, view=make_translation_menu())
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

# ====== Übersetzer: Session-Handling ======
async def start_session(interaction: discord.Interaction, prof: str):
    user = interaction.user
    style = profiles[prof]
    key = (user.id, prof)
    # Clean old
    if key in active_sessions:
        old = active_sessions[key]
        if not bot.get_channel(old):
            del active_sessions[key]
    if key in active_sessions:
        return await interaction.response.send_message("Du hast bereits eine aktive Session.", ephemeral=True)
    guild = interaction.guild
    cat = bot.get_channel(trans_cat_id)
    if not cat or cat.type != discord.ChannelType.category:
        cat = bot.get_channel(TEMP_CATEGORY_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }
    chan_name = f"translate-{prof.lower()}-{user.display_name.lower()}".replace(" ", "-")
    old = discord.utils.get(cat.text_channels, name=chan_name)
    if old:
        await old.delete()
    ch = await guild.create_text_channel(chan_name, category=cat, overwrites=overwrites)
    active_sessions[key] = ch.id
    channel_info[ch.id] = (user.id, prof, style)

    btn = discord.ui.Button(label="Beenden", style=discord.ButtonStyle.danger)
    async def end_cb(bi: discord.Interaction):
        info = channel_info.get(ch.id)
        if not info or bi.user.id != info[0]:
            return await bi.response.send_message("Nur der Besitzer kann beenden.", ephemeral=True)
        await bi.response.send_message("Session beendet.", ephemeral=True)
        await ch.delete()
    btn.callback = end_cb
    v = discord.ui.View(timeout=None)
    v.add_item(btn)

    await ch.send(f"Session **{prof}** gestartet. Schreibe hier zum Übersetzen.", view=v)
    await interaction.response.send_message(f"Session erstellt: {ch.mention}", ephemeral=True)

# ====== Übersetzer: on_message Event ======
@bot.event
async def on_message(message: discord.Message):
    # Übersetzer nur in privaten Übersetzungschannels!
    if message.author.bot or message.guild is None or message.channel.category_id != trans_cat_id:
        return
    info = channel_info.get(message.channel.id)
    if not info or message.author.id != info[0]:
        return
    txt = message.content.strip()
    if not txt:
        return
    # Prompt mit Erweiterung
    prompt = (
        f"Erkenne die Sprache des folgenden OnlyFans-Chat-Textes. "
        f"Wenn es Deutsch ist, übersetze ihn nuanciert ins Englische im Stil: {info[2]}. "
        f"Wenn es Englisch ist, übersetze ihn nuanciert ins Deutsche im Stil: {info[2]}. "
        "Verwende authentischen Slang, Chat-Sprache, keine Emojis. "
        "Es soll spontan, emotional und natürlich klingen, nicht KI-generiert. "
        "Finde echte Äquivalente für kulturelle Referenzen. "
        "Antworte NUR mit der Übersetzung und nichts anderem."
    )
    if prompt_add:
        prompt += "\n" + prompt_add
    prompt += f"\n{txt}"
    footer = "Auto-Detected Translation"
    try:
        translation = await asyncio.wait_for(call_gemini(prompt), timeout=20)
    except:
        translation = "*Fehler bei Übersetzung*"
    emb = discord.Embed(description=f"```{translation}```", color=discord.Color.blue())
    emb.set_footer(text=footer)
    await message.channel.send(embed=emb)

    # Logging
    if log_channel_id:
        log_ch = message.guild.get_channel(log_channel_id)
        if log_ch:
            log_e = discord.Embed(title="Übersetzung", color=discord.Color.orange())
            log_e.add_field(name="Profil", value=info[1], inline=False)
            log_e.add_field(name="User", value=message.author.display_name, inline=False)
            log_e.add_field(name="Original", value=txt, inline=False)
            log_e.add_field(name="Übersetzung", value=translation, inline=False)
            await log_ch.send(embed=log_e)
    await bot.process_commands(message)

# ====== Übersetzer: Slash-Commands ======
def owner_or_admin_check(interaction):
    return is_admin(interaction.user) or (hasattr(bot, "owner_id") and interaction.user.id == bot.owner_id)

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

@bot.tree.command(name="addprofile", description="Fügt ein neues Profil hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Profilname", style="Stilbeschreibung")
async def addprofile(interaction: discord.Interaction, name: str, style: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    nm = name.strip()
    if not nm or nm in profiles:
        return await interaction.response.send_message("Ungültiger oder existierender Name.", ephemeral=True)
    profiles[nm] = style
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{nm}** hinzugefügt.", ephemeral=True)
    # Menü ggf. aktualisieren
    await update_translation_menu()

@bot.tree.command(name="delprofile", description="Löscht ein Profil", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Profilname")
async def delprofile(interaction: discord.Interaction, name: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if name not in profiles:
        return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
    profiles.pop(name)
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translationlog", description="Setzt den Log-Kanal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Text-Kanal für Logs")
async def translationlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global log_channel_id
    log_channel_id = channel.id
    save_json(LOG_FILE, {"log_channel_id": log_channel_id})
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="translationsection", description="Setzt die Kategorie für Übersetzungs-Session-Channels", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(category="Kategorie")
async def translationsection(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global trans_cat_id
    trans_cat_id = category.id
    save_json(TRANS_CAT_FILE, {"category_id": category.id})
    await interaction.response.send_message(f"Kategorie gesetzt: {category.name}", ephemeral=True)

@bot.tree.command(name="translationmainprompt", description="Fügt eine Erweiterung zum Übersetzungsprompt hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="Zusätzlicher Prompt-Text")
async def translationmainprompt(interaction: discord.Interaction, text: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global prompt_add
    prompt_add = text
    save_json(PROMPT_FILE, {"addition": prompt_add})
    await interaction.response.send_message("Prompt-Erweiterung gesetzt!", ephemeral=True)

@bot.tree.command(name="translationresetprompt", description="Reset Prompt-Erweiterung", guild=discord.Object(id=GUILD_ID))
async def translationresetprompt(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global prompt_add
    prompt_add = ""
    save_json(PROMPT_FILE, {"addition": ""})
    await interaction.response.send_message("Prompt-Erweiterung entfernt!", ephemeral=True)

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
    except:
        pass

# ====== STRIKE SYSTEM BEGINNT HIER ======
def load_strikes():
    return load_json(STRIKE_FILE, {})

def save_strikes(data):
    save_json(STRIKE_FILE, data)

def save_strike_roles(role_ids):
    save_json(STRIKE_ROLES_FILE, {"role_ids": list(role_ids)})

def save_strike_list_cfg(data):
    save_json(STRIKE_LIST_FILE, data)

def save_strike_reward(role_id):
    save_json(STRIKE_REWARD_FILE, {"role_id": role_id})

async def get_guild_members(guild):
    return [m for m in guild.members if not m.bot]

# ====== STRIKE SYSTEM ======

# Strike-Berechtigte Rolle hinzufügen/entfernen
@bot.tree.command(name="strikerole", description="Fügt eine Rolle zu Strike-Berechtigten hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikerole(interaction: discord.Interaction, role: discord.Role):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_roles
    strike_roles.add(role.id)
    save_strike_roles(strike_roles)
    await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeroleremove", description="Entfernt eine Rolle aus Strike-Berechtigten", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikeroleremove(interaction: discord.Interaction, role: discord.Role):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_roles
    if role.id in strike_roles:
        strike_roles.remove(role.id)
        save_strike_roles(strike_roles)
        await interaction.response.send_message(f"Rolle **{role.name}** entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Rolle **{role.name}** war nicht Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeaddrole", description="Setzt die Belohnungsrolle für 3 Strikes", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikeaddrole(interaction: discord.Interaction, role: discord.Role):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_reward_role_id
    strike_reward_role_id = role.id
    save_strike_reward(role.id)
    await interaction.response.send_message(f"Rolle **{role.name}** wird nun bei 3 Strikes automatisch vergeben.", ephemeral=True)

@bot.tree.command(name="strikelist", description="Setzt den Channel für die Strike-Übersicht", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Channel für Strikes")
async def strikelist(interaction: discord.Interaction, channel: discord.TextChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_list_channel_id
    strike_list_channel_id = channel.id
    save_strike_list_cfg({"channel_id": channel.id})
    await interaction.response.send_message(f"Strike-Übersicht wird jetzt hier gepostet: {channel.mention}", ephemeral=True)
    await update_strike_list()

# STRIKEMAIN: Dropdown für Strikes, immer im Channel, reset nach Auswahl
@bot.tree.command(name="strikemain", description="Strike-Menü im Channel posten", guild=discord.Object(id=GUILD_ID))
async def strikemain(interaction: discord.Interaction):
    members = await get_guild_members(interaction.guild)
    options = [discord.SelectOption(label="Keinen auswählen", value="none")]
    for m in members:
        options.append(discord.SelectOption(label=m.display_name, value=str(m.id)))
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    view = discord.ui.View(timeout=None)
    async def sel_cb(inter):
        if not has_strike_role(inter.user):
            return await inter.response.send_message("Du hast keine Berechtigung für das Strike-System.", ephemeral=True)
        sel.disabled = False  # Falls Discord irgendwann wieder locked dropdowns
        uid_val = inter.data["values"][0]
        if uid_val == "none":
            # Reset dropdown, nichts tun
            await inter.response.edit_message(view=make_strike_select_view(members))
            return
        uid = int(uid_val)
        modal = discord.ui.Modal(title="Strike vergeben")
        reason = discord.ui.TextInput(label="Grund", style=discord.TextStyle.long, required=True)
        imgurl = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False)
        modal.add_item(reason)
        modal.add_item(imgurl)
        async def on_submit(m_inter):
            strikes = load_strikes()
            entry = {
                "reason": reason.value,
                "image": imgurl.value,
                "by": inter.user.display_name,
                "timestamp": datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
            }
            strikes.setdefault(str(uid), []).append(entry)
            save_strikes(strikes)
            strike_count = len(strikes[str(uid)])
            # ---- DM je nach Anzahl ----
            if strike_count == 1:
                msg = (
                    f"Du hast einen **Strike** bekommen wegen:\n```{reason.value}```"
                    f"{f'\n\nBild: {imgurl.value}' if imgurl.value else ''}\n"
                    "\nBitte melde dich bei einem Operation Lead!"
                )
            elif strike_count == 2:
                msg = (
                    f"Du hast jetzt schon deinen **2ten Strike** bekommen, schau dir die Regeln nochmal an.\n"
                    f"Du hast ihn erhalten:\n```{reason.value}```"
                    f"{f'\n\nBild: {imgurl.value}' if imgurl.value else ''}\n"
                    "\nMeld dich bei einem Teamlead um darüber zu sprechen!"
                )
            else:
                msg = (
                    f"Es ist soweit... du hast deinen **3ten Strike** gesammelt...\n"
                    f"```{reason.value}```"
                    f"{f'\n\nBild: {imgurl.value}' if imgurl.value else ''}\n"
                    "Jetzt muss leider eine Bestrafung folgen, darum melde dich schnellstmöglich bei einem TeamLead."
                )
            # DM an User
            try:
                user = interaction.guild.get_member(uid)
                if user:
                    await user.send(msg)
                    # Auto Rolle bei 3 Strikes
                    if strike_count == 3 and strike_reward_role_id:
                        role = interaction.guild.get_role(strike_reward_role_id)
                        if role:
                            await user.add_roles(role, reason="3 Strikes erreicht")
            except Exception:
                pass
            await m_inter.response.send_message(f"Strike für <@{uid}> gespeichert!", ephemeral=True)
            await update_strike_list()
        modal.on_submit = on_submit
        await inter.response.send_modal(modal)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.channel.send("Wähle einen User für einen Strike:", view=view)

def make_strike_select_view(members):
    options = [discord.SelectOption(label="Keinen auswählen", value="none")]
    for m in members:
        options.append(discord.SelectOption(label=m.display_name, value=str(m.id)))
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    view = discord.ui.View(timeout=None)
    view.add_item(sel)
    async def sel_cb(inter):
        # gleiche callback wie oben
        await strikemain(inter)
    sel.callback = sel_cb
    return view

# STRIKELIST mit Buttons für Details
async def update_strike_list():
    global strike_list_channel_id
    if not strike_list_channel_id:
        return
    ch = bot.get_channel(strike_list_channel_id)
    if not ch:
        return
    strikes = load_strikes()
    async for msg in ch.history(limit=100):
        if msg.author == bot.user:
            await msg.delete()
    # Liste bauen
    if not strikes:
        await ch.send("⚡️ Aktuell keine Strikes.")
        return
    await ch.send("__**Strikeliste**__")
    for uid, strike_list in strikes.items():
        if not strike_list:
            continue
        user = ch.guild.get_member(int(uid))
        uname = user.mention if user else f"<@{uid}>"
        n = len(strike_list)
        btn = discord.ui.Button(label=f"Strikes: {n}", style=discord.ButtonStyle.primary)
        async def btn_cb(inter, uid=uid, uname=uname):
            strikes = load_strikes()
            entrys = strikes.get(uid, [])
            lines = []
            for i, entry in enumerate(entrys, 1):
                s = f"**{i}.** {entry['reason']} {f'| {entry['image']}' if entry['image'] else ''}"
                lines.append(s)
            msg_txt = f"{uname} hat folgende Strikes =>\n" + "\n".join(lines)
            await inter.response.send_message(msg_txt, ephemeral=True)
        btn.callback = btn_cb
        v = discord.ui.View(timeout=None)
        v.add_item(btn)
        await ch.send(f"{uname}\n", view=v)
        await ch.send("-----------------")

@bot.tree.command(name="strikedelete", description="Alle Strikes von User entfernen", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User zum Löschen")
async def strikedelete(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    strikes = load_strikes()
    if str(user.id) in strikes:
        strikes.pop(str(user.id))
        save_strikes(strikes)
        await update_strike_list()
        await interaction.response.send_message(f"Alle Strikes für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeremove", description="Entfernt einen Strike", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User für Strike-Abbau")
async def strikeremove(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    strikes = load_strikes()
    entrys = strikes.get(str(user.id), [])
    if entrys:
        entrys.pop()
        if not entrys:
            strikes.pop(str(user.id))
        else:
            strikes[str(user.id)] = entrys
        save_strikes(strikes)
        await update_strike_list()
        await interaction.response.send_message(f"Ein Strike für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeview", description="Zeigt dir, wie viele Strikes du hast (nur für dich selbst)", guild=discord.Object(id=GUILD_ID))
async def strikeview(interaction: discord.Interaction):
    strikes = load_strikes()
    user_id = str(interaction.user.id)
    count = len(strikes.get(user_id, []))
    if count == 0:
        txt = f"✅ Du hast aktuell **keine Strikes**."
    else:
        txt = f"👮‍♂️ Du hast aktuell **{count} Strike{'s' if count!=1 else ''}**.\nBitte halte dich an die Regeln, sonst folgen Maßnahmen!"
    await interaction.response.send_message(txt, ephemeral=True)

# ============ WIKI-SYSTEM ============

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

# -------- Hilfsfunktion für das Dropdown-Menü --------
def make_wiki_menu_embed_and_view():
    pages = load_wiki_pages()
    embed = discord.Embed(
        title="📚 Space-Guide Wiki",
        description="Wähle eine Seite aus, um den Infotext per privater Nachricht zu erhalten:",
        color=discord.Color.green()
    )
    view = discord.ui.View(timeout=None)
    if not pages:
        embed.add_field(name="(Keine Wiki-Seiten)", value="Erstelle zuerst Seiten mit `/wiki page`", inline=False)
        return embed, view
    options = [discord.SelectOption(label=title, value=title) for title in pages]
    sel = discord.ui.Select(placeholder="Seite wählen...", options=options, max_values=1)
    async def sel_cb(inter: discord.Interaction):
        sel.disabled = False
        page = inter.data["values"][0]
        text = pages.get(page, "**Seite leer**")
        try:
            await inter.user.send(f"**{page}**\n{text}")
            await inter.response.send_message("Check deine DMs! (Wenn keine ankommen: bitte DMs erlauben)", ephemeral=True)
        except:
            await inter.response.send_message("Konnte keine DM senden (evtl. deaktiviert)", ephemeral=True)
        # Dropdown wieder resetten (ausgewählt->nichts)
        await inter.message.edit(embed=embed, view=make_wiki_menu_embed_and_view())
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

# --------- Wiki-Menü posten/aktualisieren ---------
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

# -------- /wikimain: Menü im Channel posten --------
@bot.tree.command(name="wikimain", description="Postet das Wiki-Dropdown-Menü im aktuellen Channel", guild=discord.Object(id=GUILD_ID))
async def wikimain(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_wiki_menu_embed_and_view()
    msg = await interaction.channel.send(embed=embed, view=view)
    global wiki_menu_channel_id, wiki_menu_message_id
    wiki_menu_channel_id = interaction.channel.id
    wiki_menu_message_id = msg.id
    save_wiki_menu({"channel_id": wiki_menu_channel_id, "message_id": wiki_menu_message_id})
    await interaction.response.send_message("Wiki-Menü gepostet.", ephemeral=True)

# -------- /wiki page: Diese Channelpage speichern --------
@bot.tree.command(name="wiki_page", description="Legt den aktuellen Channel als Wiki-Seite an", guild=discord.Object(id=GUILD_ID))
async def wiki_page(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    channel = interaction.channel
    # Sammle alle Nachrichten (Limit einstellbar)
    msgs = [m async for m in channel.history(limit=30, oldest_first=True) if not m.author.bot]
    text = "\n".join([f"{m.author.display_name}: {m.content}" for m in msgs if m.content.strip()])
    title = channel.name
    # Backup alt speichern
    pages = load_wiki_pages()
    backup = load_wiki_backup()
    backup[title] = pages.get(title, "")
    save_wiki_backup(backup)
    # Jetzt speichern
    pages[title] = text if text else "(keine Nachrichten gefunden)"
    save_wiki_pages(pages)
    await interaction.response.send_message(f"Seite **{title}** gespeichert!", ephemeral=True)
    await update_wiki_menu()

# -------- /wiki undo: Wiki-Pages aus Backup wiederherstellen --------
@bot.tree.command(name="wiki_undo", description="Setzt die Wiki-Pages aus dem letzten Backup zurück", guild=discord.Object(id=GUILD_ID))
async def wiki_undo(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    backup = load_wiki_backup()
    if not backup:
        return await interaction.response.send_message("Kein Backup vorhanden.", ephemeral=True)
    save_wiki_pages(backup)
    await interaction.response.send_message("Backup wiederhergestellt!", ephemeral=True)
    await update_wiki_menu()

bot.run(DISCORD_TOKEN)
