import os
import json
import aiohttp
import asyncio
import datetime

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ─── Umgebungsvariablen laden ────────────────────────────────────────────────────
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not DISCORD_TOKEN or not GOOGLE_API_KEY:
    print("⚠️ Bitte setze DISCORD_TOKEN und GOOGLE_API_KEY in der .env-Datei.")
    exit(1)

# ─── Konfiguration ─────────────────────────────────────────────────────────────
GUILD_ID         = 1374724357741609041
TEMP_CATEGORY_ID = 1374724358932664330
MODEL_ENDPOINT   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

PROFILES_FILE      = "profiles.json"
LOG_FILE           = "translation_log.json"
MENU_FILE          = "translator_menu.json"
STRIKE_FILE        = "strike_data.json"
STRIKE_LIST_FILE   = "strike_list.json"
STRIKE_ROLES_FILE  = "strike_roles.json"

# ─── JSON Helfer ────────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Daten initialisieren ───────────────────────────────────────────────────────
profiles        = load_json(PROFILES_FILE, {"Normal":"neutraler professioneller Stil","Flirty":"junger koketter Ton"})
log_cfg         = load_json(LOG_FILE, {})
log_channel_id  = log_cfg.get("log_channel_id")
menu_cfg        = load_json(MENU_FILE, {})
menu_channel_id = menu_cfg.get("channel_id")
menu_message_id = menu_cfg.get("message_id")

strike_data         = load_json(STRIKE_FILE, {})
strike_list_cfg     = load_json(STRIKE_LIST_FILE, {})
strike_list_channel_id = strike_list_cfg.get("channel_id")
strike_roles_cfg    = load_json(STRIKE_ROLES_FILE, {})
strike_roles        = set(strike_roles_cfg.get("role_ids", []))

active_sessions = {}  # (user_id, profile) -> channel_id
channel_info     = {} # channel_id -> (user_id, profile, style)

# ─── Bot & Intents ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Für User-Listen!
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Hilfsfunktionen: Rechte ─────────────────────────────────────────────────────
def is_admin(user):
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if hasattr(user, "id") and user.id == bot.owner_id:
        return True
    return False

async def setup_owner_id():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id

def has_strike_role(user):
    return any(r.id in strike_roles for r in user.roles) or is_admin(user)

# ─── Google Gemini API-Aufruf ───────────────────────────────────────────────────
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

# ─── Menü mit Dropdown ───────────────────────────────────────────────────────────
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
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

# ─── Menü aktualisieren ─────────────────────────────────────────────────────────
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

# ─── Session starten ─────────────────────────────────────────────────────────────
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
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }
    chan_name = f"translate-{prof.lower()}"
    old = discord.utils.get(bot.temp_category.text_channels, name=chan_name)
    if old:
        await old.delete()
    ch = await guild.create_text_channel(chan_name, category=bot.temp_category, overwrites=overwrites)
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

# ─── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await setup_owner_id()
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Sync-Error:", e)
    bot.temp_category = bot.get_channel(TEMP_CATEGORY_ID)
    bot.log_channel   = bot.get_channel(log_channel_id) if log_channel_id else None
    print(f"✅ Bot bereit als {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None or message.channel.category_id != TEMP_CATEGORY_ID:
        return
    info = channel_info.get(message.channel.id)
    if not info or message.author.id != info[0]:
        return
    txt = message.content.strip()
    if not txt:
        return

    prompt = (
        f"Erkenne die Sprache des folgenden OnlyFans-Chat-Textes. "
        f"Wenn es Deutsch ist, übersetze ihn nuanciert ins Englische im Stil: {info[2]}. "
        f"Wenn es Englisch ist, übersetze ihn nuanciert ins Deutsche im Stil: {info[2]}. "
        "Verwende authentischen Slang, Chat-Sprache, keine Emojis. "
        "Es soll spontan, emotional und natürlich klingen, nicht KI-generiert. "
        "Finde echte Äquivalente für kulturelle Referenzen. "
        "Antworte NUR mit der Übersetzung und nichts anderem:\n"
        f"{txt}"
    )
    footer = "Auto-Detected Translation"

    try:
        translation = await asyncio.wait_for(call_gemini(prompt), timeout=20)
    except:
        translation = "*Fehler bei Übersetzung*"

    emb = discord.Embed(description=f"```{translation}```", color=discord.Color.blue())
    emb.set_footer(text=footer)
    await message.channel.send(embed=emb)

    if bot.log_channel:
        log_e = discord.Embed(title="Übersetzung", color=discord.Color.orange())
        log_e.add_field(name="Profil", value=info[1], inline=False)
        log_e.add_field(name="Original", value=txt, inline=False)
        log_e.add_field(name="Übersetzung", value=translation, inline=False)
        await bot.log_channel.send(embed=log_e)

    await bot.process_commands(message)

# ─── TRANSLATION: Slash-Commands (Owner/Admin only) ─────────────────────────────
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
    save_json(MENU_FILE, {"channel_id": menu_channel_id, "message_id": menu_message_id})
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
    bot.log_channel = channel
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

# ─── STRIKE SYSTEM ──────────────────────────────────────────────────────────────

# Hilfsfunktionen für Daten
def load_strikes():
    return load_json(STRIKE_FILE, {})
def save_strikes(data):
    save_json(STRIKE_FILE, data)
def load_strike_roles():
    return set(load_json(STRIKE_ROLES_FILE, {}).get("role_ids", []))
def save_strike_roles(role_ids):
    save_json(STRIKE_ROLES_FILE, {"role_ids": list(role_ids)})
def load_strike_list_cfg():
    return load_json(STRIKE_LIST_FILE, {})
def save_strike_list_cfg(data):
    save_json(STRIKE_LIST_FILE, data)

# ---- Guild Members ----
async def get_guild_members(guild):
    return [m for m in guild.members if not m.bot]

# ---- STRIKE LIST CHANNEL ----
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

# ---- STRIKE ROLE MANAGEMENT ----
@bot.tree.command(name="strikerole", description="Fügt eine Rolle zu den Strike-Berechtigten hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikerole(interaction: discord.Interaction, role: discord.Role):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_roles
    strike_roles.add(role.id)
    save_strike_roles(strike_roles)
    await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeroleremove", description="Entfernt eine Rolle von den Strike-Berechtigten", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikeroleremove(interaction: discord.Interaction, role: discord.Role):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_roles
    if role.id in strike_roles:
        strike_roles.remove(role.id)
        save_strike_roles(strike_roles)
        await interaction.response.send_message(f"Rolle **{role.name}** ist **nicht mehr** Strike-Berechtigt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Rolle **{role.name}** war nicht Strike-Berechtigt.", ephemeral=True)

# ---- STRIKE MAIN: Dropdown & Modal ----
@bot.tree.command(name="strikemain", description="Startet das Strike-Menü", guild=discord.Object(id=GUILD_ID))
async def strikemain(interaction: discord.Interaction):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    members = await get_guild_members(interaction.guild)
    options = [discord.SelectOption(label=f"{m.display_name}", value=str(m.id)) for m in members]
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    view = discord.ui.View(timeout=60)
    async def sel_cb(inter):
        uid = int(inter.data["values"][0])
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
                "by": interaction.user.display_name,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds")
            }
            strikes.setdefault(str(uid), []).append(entry)
            save_strikes(strikes)
            await m_inter.response.send_message(f"Strike für <@{uid}> gespeichert!", ephemeral=True)
            # DM an User
            try:
                user = interaction.guild.get_member(uid)
                if user:
                    msg = f"Du hast einen **Strike** bekommen wegen:\n```{reason.value}```"
                    if imgurl.value:
                        msg += f"\n\nBild: {imgurl.value}"
                    msg += "\n\nBitte melde dich bei einem Operation Lead!"
                    await user.send(msg)
            except Exception as e:
                pass
            await update_strike_list()
        modal.on_submit = on_submit
        await inter.response.send_modal(modal)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle einen User für einen Strike:", view=view, ephemeral=True)

# ---- UPDATE STRIKE LIST ----
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
    if not strikes:
        await ch.send("⚡️ Aktuell keine Strikes.")
        return
    for uid, strike_list in strikes.items():
        if not strike_list:
            continue
        user = ch.guild.get_member(int(uid))
        uname = user.mention if user else f"<@{uid}>"
        n = len(strike_list)
        btn = discord.ui.Button(label=f"Strikes: {n}", style=discord.ButtonStyle.primary)
        async def btn_cb(inter, uid=uid):
            strikes = load_strikes()
            entrys = strikes.get(uid, [])
            txt = ""
            for i, entry in enumerate(entrys, 1):
                txt += f"**Strike {i}:** {entry['reason']}\n"
                if entry.get("image"):
                    txt += f"Bild: {entry['image']}\n"
                txt += f"Von: {entry['by']} ({entry['timestamp']})\n---\n"
            try:
                await inter.user.send(f"Strikes von {uname}:\n{txt}")
                await inter.response.send_message("Strike-Details wurden dir privat geschickt!", ephemeral=True)
            except Exception as e:
                await inter.response.send_message("Konnte dir keine DM schicken.", ephemeral=True)
        btn.callback = btn_cb
        v = discord.ui.View(timeout=None)
        v.add_item(btn)
        await ch.send(f"{uname} [{user.display_name if user else ''}] => ", view=v)

# ---- STRIKE DELETE ----
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

# ---- STRIKE REMOVE ----
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

# ─── Bot starten ───────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
