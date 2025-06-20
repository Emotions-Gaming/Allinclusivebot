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
GUILD_ID = int(os.getenv("GUILD_ID") or "1374724357741609041")   # dev/test server-id

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

# --- Script-Ende für diesen Part ---
# NUR EINMAL GANZ UNTEN!
bot.run(DISCORD_TOKEN)

