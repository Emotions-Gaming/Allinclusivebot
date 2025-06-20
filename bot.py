import os
import json
import aiohttp
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

# ========== ENV/CONFIG ==========
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

PROFILES_FILE = "profiles.json"
MENU_FILE = "translator_menu.json"
PROMPT_FILE = "translator_prompt.json"
TRANS_CAT_FILE = "trans_category.json"

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

# ========== BOT-SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== Gemini API Call ==========
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

# ========== Translation MENU ==========
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
        # Dropdown reset (fix: view/tuple problem)
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

# ========== Session-Handling ==========
async def start_session(interaction: discord.Interaction, prof: str):
    user = interaction.user
    style = profiles[prof]
    key = (user.id, prof)
    # Clean up old
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
        # Log nur wenn Channel gesetzt
        log_channel_id = load_json(MENU_FILE, {}).get("log_channel_id", None)
        if log_channel_id:
            log_channel = bi.guild.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(embed=log_embed)
        await bi.response.send_message("Session beendet & Verlauf wurde an den Log gesendet.", ephemeral=True)
        await ch.delete()
        # Clean up
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

# ========== MESSAGE EVENT (nur im eigenen Session-Channel) ==========
@bot.event
async def on_message(message: discord.Message):
    # Übersetzer nur in privaten Übersetzungschannels!
    if message.author.bot or message.guild is None:
        return
    info = channel_info.get(message.channel.id)
    if not info or message.author.id != info[0]:
        return
    txt = message.content.strip()
    if not txt:
        return
    # Prompt bauen
    base_prompt = (
        "Erkenne die Sprache des folgenden OnlyFans-Chat-Textes."
        " Wenn es Deutsch ist, übersetze ihn nuanciert ins Englische im Stil: {style}."
        " Wenn es Englisch ist, übersetze ihn nuanciert ins Deutsche im Stil: {style}."
        " Verwende echten Slang, Chat-Sprache, keine Emojis, keine Smileys, keine Abkürzungen wie :), ;), etc."
        " KEINE Emojis, keine Icons, keine GIFs. Es soll spontan, natürlich, aber menschlich klingen, nicht KI-generiert."
        " Finde echte Äquivalente für kulturelle Referenzen."
        " Antworte NUR mit der Übersetzung und nichts anderem."
    )
    # Erweiterung einbauen
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
    # Verlauf loggen
    channel_logs[message.channel.id].append((message.author.display_name, txt, translation))
    await bot.process_commands(message)

# ========== SLASH-BEFEHLE ==========
def owner_or_admin_check(interaction):
    return interaction.user.guild_permissions.administrator or (hasattr(bot, "owner_id") and interaction.user.id == bot.owner_id)

@bot.tree.command(name="translatormenu", description="Postet das Übersetzungsmenü im aktuellen Kanal")
async def translatormenu(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_translation_menu()
    msg = await interaction.channel.send(embed=embed, view=view)
    global menu_channel_id, menu_message_id
    menu_channel_id = interaction.channel.id
    menu_message_id = msg.id
    save_json(MENU_FILE, {"channel_id": menu_channel_id, "message_id": msg.id})
    await interaction.response.send_message("Übersetzungsmenü gepostet.", ephemeral=True)

@bot.tree.command(name="translataddprofile", description="Fügt ein neues Übersetzer-Profil hinzu")
@app_commands.describe(name="Profilname", style="Stilbeschreibung")
async def translataddprofile(interaction: discord.Interaction, name: str, style: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    nm = name.strip()
    if not nm or nm in profiles:
        return await interaction.response.send_message("Ungültiger oder existierender Name.", ephemeral=True)
    profiles[nm] = style
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{nm}** hinzugefügt.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translatdelprofile", description="Löscht ein Übersetzer-Profil")
@app_commands.describe(name="Profilname")
async def translatdelprofile(interaction: discord.Interaction, name: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    if name not in profiles:
        return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
    profiles.pop(name)
    save_json(PROFILES_FILE, profiles)
    await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)
    await update_translation_menu()

@bot.tree.command(name="translatsetcategory", description="Setzt die Kategorie für Übersetzungs-Session-Channels")
@app_commands.describe(category="Kategorie")
async def translatsetcategory(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global trans_cat_id
    trans_cat_id = category.id
    save_json(TRANS_CAT_FILE, {"category_id": category.id})
    await interaction.response.send_message(f"Kategorie gesetzt: {category.name}", ephemeral=True)

@bot.tree.command(name="translatsetlog", description="Setzt den Log-Kanal für Übersetzungs-Session-Verläufe")
@app_commands.describe(channel="Text-Kanal für Logs")
async def translatsetlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    menu_cfg = load_json(MENU_FILE, {})
    menu_cfg["log_channel_id"] = channel.id
    save_json(MENU_FILE, menu_cfg)
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="translatprompt", description="Fügt eine Regel zum Haupt-Prompt hinzu (z.B. keine Ortsnamen)")
@app_commands.describe(text="Zusätzlicher Prompt-Text")
async def translatprompt(interaction: discord.Interaction, text: str):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_json(PROMPT_FILE, {"addition": text})
    await interaction.response.send_message(f"Prompt-Erweiterung gesetzt: **{text}**", ephemeral=True)

@bot.tree.command(name="translatpromptdelete", description="Entfernt die zusätzliche Prompt-Regel")
async def translatpromptdelete(interaction: discord.Interaction):
    if not owner_or_admin_check(interaction):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_json(PROMPT_FILE, {"addition": ""})
    await interaction.response.send_message("Prompt-Erweiterung entfernt.", ephemeral=True)
import datetime

STRIKE_FILE        = "strike_data.json"
STRIKE_LIST_FILE   = "strike_list.json"
STRIKE_ROLES_FILE  = "strike_roles.json"
STRIKE_PUNISH_ROLE_FILE = "strike_punishrole.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---- Data Loader
strike_data         = load_json(STRIKE_FILE, {})
strike_list_cfg     = load_json(STRIKE_LIST_FILE, {})
strike_list_channel_id = strike_list_cfg.get("channel_id")
strike_roles_cfg    = load_json(STRIKE_ROLES_FILE, {})
strike_roles        = set(strike_roles_cfg.get("role_ids", []))
punish_role_cfg     = load_json(STRIKE_PUNISH_ROLE_FILE, {})
punish_role_id      = punish_role_cfg.get("role_id")

def has_strike_role(user):
    return any(r.id in strike_roles for r in user.roles) or user.guild_permissions.administrator

async def get_guild_members(guild):
    return [m for m in guild.members if not m.bot]

# ------ /strikelist setzen
@bot.tree.command(name="strikelist", description="Setzt den Channel für die Strike-Übersicht")
@app_commands.describe(channel="Channel für Strikes")
async def strikelist(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    global strike_list_channel_id
    strike_list_channel_id = channel.id
    save_json(STRIKE_LIST_FILE, {"channel_id": channel.id})
    await interaction.response.send_message(f"Strike-Übersicht wird jetzt hier gepostet: {channel.mention}", ephemeral=True)
    await update_strike_list()

# ----- Strike-Berechtigungsrollen hinzufügen/entfernen
@bot.tree.command(name="strikerole", description="Fügt eine Rolle zu Strike-Berechtigten hinzu")
@app_commands.describe(role="Discord Rolle")
async def strikerole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Nur Admins können Rollen festlegen.", ephemeral=True)
    global strike_roles
    strike_roles.add(role.id)
    save_json(STRIKE_ROLES_FILE, {"role_ids": list(strike_roles)})
    await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeroleremove", description="Entfernt eine Rolle von den Strike-Berechtigten")
@app_commands.describe(role="Discord Rolle")
async def strikeroleremove(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Nur Admins können Rollen festlegen.", ephemeral=True)
    global strike_roles
    if role.id in strike_roles:
        strike_roles.remove(role.id)
        save_json(STRIKE_ROLES_FILE, {"role_ids": list(strike_roles)})
        await interaction.response.send_message(f"Rolle **{role.name}** ist **nicht mehr** Strike-Berechtigt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Rolle **{role.name}** war nicht Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeaddrole", description="Setzt eine Rolle, die beim 3. Strike automatisch vergeben wird")
@app_commands.describe(role="Discord Rolle")
async def strikeaddrole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Nur Admins können Rollen festlegen.", ephemeral=True)
    global punish_role_id
    punish_role_id = role.id
    save_json(STRIKE_PUNISH_ROLE_FILE, {"role_id": role.id})
    await interaction.response.send_message(f"Rolle **{role.name}** wird beim 3. Strike vergeben.", ephemeral=True)

@bot.tree.command(name="strikeaddroleremove", description="Entfernt die automatische 3. Strike-Rolle")
async def strikeaddroleremove(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Nur Admins können Rollen entfernen.", ephemeral=True)
    global punish_role_id
    punish_role_id = None
    save_json(STRIKE_PUNISH_ROLE_FILE, {"role_id": None})
    await interaction.response.send_message(f"Die automatische Strike-Rolle wurde entfernt.", ephemeral=True)

# --- STRIKEMAIN mit Dropdown (sichtbar für alle, Strike vergeben nur für Berechtigte)
@bot.tree.command(name="strikemain", description="Strike-Menü im Channel posten")
async def strikemain(interaction: discord.Interaction):
    members = await get_guild_members(interaction.guild)
    options = [discord.SelectOption(label="Keinen", value="none")] + [
        discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members
    ]
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    view = discord.ui.View(timeout=None)
    async def sel_cb(inter):
        if inter.data["values"][0] == "none":
            await inter.response.defer()
            reset_embed, reset_view = make_strikemain_menu(interaction.guild)
            await inter.message.edit(embed=reset_embed, view=reset_view)
            return
        if not has_strike_role(inter.user):
            return await inter.response.send_message("Du hast keine Berechtigung für das Strike-System.", ephemeral=True)
        uid = int(inter.data["values"][0])
        modal = discord.ui.Modal(title="Strike vergeben")
        reason = discord.ui.TextInput(label="Grund", style=discord.TextStyle.long, required=True)
        imgurl = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False)
        modal.add_item(reason)
        modal.add_item(imgurl)
        async def on_submit(m_inter):
            strikes = load_json(STRIKE_FILE, {})
            entry = {
                "reason": reason.value,
                "image": imgurl.value,
                "by": inter.user.display_name,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds")
            }
            strikes.setdefault(str(uid), []).append(entry)
            save_json(STRIKE_FILE, strikes)
            strike_count = len(strikes[str(uid)])
            # ---- Strike DM je nach Anzahl ----
            msg = None
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
            elif strike_count == 3:
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
                    # Rolle geben wenn definiert
                    if strike_count == 3 and punish_role_id:
                        punish_role = interaction.guild.get_role(punish_role_id)
                        if punish_role:
                            await user.add_roles(punish_role, reason="3. Strike erreicht")
            except Exception:
                pass
            await m_inter.response.send_message(f"Strike für <@{uid}> gespeichert!", ephemeral=True)
            await update_strike_list()
        modal.on_submit = on_submit
        await inter.response.send_modal(modal)
        # Reset Dropdown damit wiederholt möglich
        reset_embed, reset_view = make_strikemain_menu(interaction.guild)
        await inter.message.edit(embed=reset_embed, view=reset_view)
    sel.callback = sel_cb
    view.add_item(sel)
    embed = discord.Embed(
        title="🚨 Strike System",
        description="Wähle einen User für einen Strike:",
        color=discord.Color.red()
    )
    return embed, view

@bot.tree.command(name="strikemainmenu", description="Postet das Strike Menü im aktuellen Channel")
async def strikemainmenu(interaction: discord.Interaction):
    embed, view = make_strikemain_menu(interaction.guild)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Strike-Menü gepostet.", ephemeral=True)

def make_strikemain_menu(guild):
    members = [m for m in guild.members if not m.bot]
    options = [discord.SelectOption(label="Keinen", value="none")] + [
        discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members
    ]
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    view = discord.ui.View(timeout=None)
    async def sel_cb(inter):
        if inter.data["values"][0] == "none":
            await inter.response.defer()
            reset_embed, reset_view = make_strikemain_menu(guild)
            await inter.message.edit(embed=reset_embed, view=reset_view)
            return
    sel.callback = sel_cb
    view.add_item(sel)
    embed = discord.Embed(
        title="🚨 Strike System",
        description="Wähle einen User für einen Strike:",
        color=discord.Color.red()
    )
    return embed, view

# --- STRIKELIST (schönes Design, Buttons, Private-Infos) ---
async def update_strike_list():
    global strike_list_channel_id
    if not strike_list_channel_id:
        return
    ch = bot.get_channel(strike_list_channel_id)
    if not ch:
        return
    strikes = load_json(STRIKE_FILE, {})
    async for msg in ch.history(limit=100):
        if msg.author == bot.user:
            await msg.delete()
    if not strikes:
        await ch.send("⚡️ Aktuell keine Strikes.")
        return
    await ch.send("**Strikeliste**\n-----------------")
    for uid, strike_list in strikes.items():
        if not strike_list:
            continue
        user = ch.guild.get_member(int(uid))
        uname = user.mention if user else f"<@{uid}>"
        n = len(strike_list)
        btn = discord.ui.Button(label=f"{'X'*n}", style=discord.ButtonStyle.primary)
        async def btn_cb(inter, uid=uid, uname=uname):
            strikes = load_json(STRIKE_FILE, {})
            entrys = strikes.get(uid, [])
            lines = []
            for i, entry in enumerate(entrys, 1):
                s = f"{i}. {entry['reason']} | {entry['image']}" if entry['image'] else f"{i}. {entry['reason']}"
                lines.append(s)
            msg_txt = f"{uname} hat folgende Strikes =>\n" + "\n".join(lines)
            await inter.response.send_message(msg_txt, ephemeral=True)
        btn.callback = btn_cb
        v = discord.ui.View(timeout=None)
        v.add_item(btn)
        await ch.send(f"{uname}", view=v)
        await ch.send("-----------------")

@bot.tree.command(name="strikedelete", description="Alle Strikes von User entfernen")
@app_commands.describe(user="User zum Löschen")
async def strikedelete(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    strikes = load_json(STRIKE_FILE, {})
    if str(user.id) in strikes:
        strikes.pop(str(user.id))
        save_json(STRIKE_FILE, strikes)
        await update_strike_list()
        await interaction.response.send_message(f"Alle Strikes für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeremove", description="Entfernt einen Strike")
@app_commands.describe(user="User für Strike-Abbau")
async def strikeremove(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    strikes = load_json(STRIKE_FILE, {})
    entrys = strikes.get(str(user.id), [])
    if entrys:
        entrys.pop()
        if not entrys:
            strikes.pop(str(user.id))
        else:
            strikes[str(user.id)] = entrys
        save_json(STRIKE_FILE, strikes)
        await update_strike_list()
        await interaction.response.send_message(f"Ein Strike für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeview", description="Zeigt dir, wie viele Strikes du hast (nur für dich selbst).")
async def strikeview(interaction: discord.Interaction):
    strikes = load_json(STRIKE_FILE, {})
    user_id = str(interaction.user.id)
    count = len(strikes.get(user_id, []))
    msg = (
        f"👮‍♂️ **Strike-Übersicht** für {interaction.user.mention}:\n\n"
        f"Du hast aktuell **{count} Strike{'s' if count!=1 else ''}**.\n"
        f"{'Wenn du mehr wissen willst, schreibe dem Bot einfach eine DM.' if count else 'Du hast aktuell keine Strikes.'}"
    )
    await interaction.response.send_message(msg, ephemeral=True)
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

# -------- Dropdown-Menü bauen --------
def make_wiki_menu_embed_and_view():
    pages = load_wiki_pages()
    embed = discord.Embed(
        title="📚 Space-Guide Wiki",
        description="Wähle eine Seite aus, um den Infotext per privater Nachricht zu erhalten:",
        color=discord.Color.green()
    )
    view = discord.ui.View(timeout=None)
    if not pages:
        embed.add_field(name="(Keine Wiki-Seiten)", value="Erstelle zuerst Seiten mit `/wiki_page`", inline=False)
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
        # Dropdown wieder resetten
        reset_embed, reset_view = make_wiki_menu_embed_and_view()
        await inter.message.edit(embed=reset_embed, view=reset_view)
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

# -------- Menü aktualisieren --------
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

# -------- /wikimain --------
@bot.tree.command(name="wikimain", description="Postet das Wiki-Dropdown-Menü im aktuellen Channel")
async def wikimain(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_wiki_menu_embed_and_view()
    msg = await interaction.channel.send(embed=embed, view=view)
    global wiki_menu_channel_id, wiki_menu_message_id
    wiki_menu_channel_id = interaction.channel.id
    wiki_menu_message_id = msg.id
    save_wiki_menu({"channel_id": wiki_menu_channel_id, "message_id": wiki_menu_message_id})
    await interaction.response.send_message("Wiki-Menü gepostet.", ephemeral=True)

# -------- /wiki_page --------
@bot.tree.command(name="wiki_page", description="Legt den aktuellen Channel als Wiki-Seite an")
async def wiki_page(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    channel = interaction.channel
    # Sammle alle Nachrichten (ohne Bot)
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
    await interaction.response.send_message(f"Seite **{title}** gespeichert!", ephemeral=True)
    await update_wiki_menu()

# -------- /wiki_undo --------
@bot.tree.command(name="wiki_undo", description="Setzt die Wiki-Pages aus dem letzten Backup zurück")
async def wiki_undo(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    backup = load_wiki_backup()
    if not backup:
        return await interaction.response.send_message("Kein Backup vorhanden.", ephemeral=True)
    save_wiki_pages(backup)
    await interaction.response.send_message("Backup wiederhergestellt!", ephemeral=True)
    await update_wiki_menu()
