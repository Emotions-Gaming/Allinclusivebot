# bot.py

import os
import re
import json
import aiohttp
import asyncio

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ─── Umgebungsvariablen laden ────────────────────────────────────────────────────
load_dotenv()  # .env einlesen
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not DISCORD_TOKEN or not GOOGLE_API_KEY:
    print("⚠️ Bitte setze DISCORD_TOKEN und GOOGLE_API_KEY in der .env-Datei.")
    exit(1)

# ─── Konfiguration ─────────────────────────────────────────────────────────────
GUILD_ID         = 1374724357741609041
TEMP_CATEGORY_ID = 1374724358932664330
MODEL_ENDPOINT   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

PROFILES_FILE    = "profiles.json"
LOG_FILE         = "translation_log.json"
MENU_FILE        = "translator_menu.json"

# ─── Helfer: JSON laden/speichern ────────────────────────────────────────────────
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

active_sessions = {}  # (user_id, profile) -> channel_id
channel_info     = {} # channel_id -> (user_id, profile, style)

# ─── Bot & Intents ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Spracherkennung (Heuristik) ────────────────────────────────────────────────
GERMAN_WORDS  = {" der"," die"," das"," und"," ist"," nicht"," ich"," mir"," dir"," ein"," eine"," mit"}
ENGLISH_WORDS = {" the"," and"," is"," you"," for"," this"," that"," it"," are"," not"}

def detect_language(text: str) -> str:
    tl = text.lower()
    if re.search(r"[äöüß]", tl):
        return "de"
    return "de" if sum(tl.count(w) for w in GERMAN_WORDS) >= sum(tl.count(w) for w in ENGLISH_WORDS) else "en"

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

# ─── Basis-Prompts ───────────────────────────────────────────────────────────────
BASE_PROMPT_DE_EN = (
    "Übersetze den folgenden deutschen OnlyFans-Chat-Text exakt und nuanciert ins Englische. "
    "Bewahre dabei den Tonfall einer jungen, koketten, selbstbewussten deutschen Frau. "
    "Verwende authentischen Slang, Abkürzungen, Chat-Sprache. KEINE Emojis. "
    "Es soll spontan, emotional und natürlich klingen, nicht KI-generiert. "
    "Finde echte englische Äquivalente für kulturelle Referenzen oder Ausdrücke. "
    "Keine zusätzlichen Satzzeichen am Ende, außer im Original. "
    "Antworte NUR mit der Übersetzung und nichts anderem:"
)
BASE_PROMPT_EN_DE = (
    "Übersetze den folgenden englischen OnlyFans-Chat-Text exakt und nuanciert ins Deutsche. "
    "Bewahre dabei den Tonfall einer jungen, koketten, selbstbewussten deutschen Frau. "
    "Verwende authentischen Slang, Abkürzungen, Chat-Sprache. KEINE Emojis. "
    "Es soll spontan, emotional und natürlich klingen, nicht KI-generiert. "
    "Finde echte deutsche Äquivalente für kulturelle Referenzen oder Ausdrücke. "
    "Keine zusätzlichen Satzzeichen am Ende, außer im Original. "
    "Antworte NUR mit der Übersetzung und nichts anderem:"
)

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
    # Alte Session clean
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
    # Sync
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

    lang = detect_language(txt)
    if lang == "de":
        prompt = f"{BASE_PROMPT_DE_EN}\nStil: {info[2]}\n{txt}"
        footer = "Deutsch → Englisch"
    else:
        prompt = f"{BASE_PROMPT_EN_DE}\nStil: {info[2]}\n{txt}"
        footer = "Englisch → Deutsch"

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

# ─── Slash-Commands ─────────────────────────────────────────────────────────────
@bot.tree.command(name="translatorpost", description="Postet das Übersetzungsmenü im aktuellen Kanal", guild=discord.Object(id=GUILD_ID))
async def translatorpost(interaction: discord.Interaction):
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
    if name not in profiles:
        return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
    profiles.pop(name)
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translationlog", description="Setzt den Log-Kanal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Text-Kanal für Logs")
async def translationlog(interaction: discord.Interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    save_json(LOG_FILE, {"log_channel_id": log_channel_id})
    bot.log_channel = channel
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

# ─── Bot starten ───────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
