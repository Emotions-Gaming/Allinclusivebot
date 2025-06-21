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

# STRIKE SYSTEM MIT MODAL FÜR GRUND/BILD – SICHER UND UNBEGRENZTE USER

import json
import datetime
import discord
from discord import app_commands

GUILD_ID = 1249813174731931740  # Deine Server-ID

STRIKE_FILE        = "strike_data.json"
STRIKE_LIST_FILE   = "strike_list.json"
STRIKE_ROLES_FILE  = "strike_roles.json"
STRIKE_AUTOROLE_FILE = "strike_autorole.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user):
    return user.guild_permissions.administrator or getattr(user, "id", None) == getattr(getattr(user, "guild", None), "owner_id", None)

def has_strike_role(user):
    strike_roles = set(load_json(STRIKE_ROLES_FILE, {}).get("role_ids", []))
    return any(r.id in strike_roles for r in getattr(user, "roles", [])) or is_admin(user)

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

def load_autorole():
    return load_json(STRIKE_AUTOROLE_FILE, {}).get("role_id", None)

def save_autorole(role_id):
    save_json(STRIKE_AUTOROLE_FILE, {"role_id": role_id})

async def update_strike_list(guild):
    strike_list_cfg = load_strike_list_cfg()
    ch_id = strike_list_cfg.get("channel_id")
    if not ch_id:
        return
    ch = guild.get_channel(ch_id)
    if not ch:
        return
    strikes = load_strikes()
    # Bestehende Bot-Nachrichten löschen
    async for msg in ch.history(limit=100):
        if msg.author == guild.me:
            await msg.delete()
    if not strikes:
        await ch.send("⚡️ Aktuell keine Strikes.")
        return
    await ch.send("Strikeliste\n-----------------")
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
            lines = []
            for i, entry in enumerate(entrys, 1):
                s = f"{i}. {entry['reason']} | {entry['image']}" if entry['image'] else f"{i}. {entry['reason']}"
                lines.append(s)
            msg_txt = f"{uname} hat folgende Strikes =>\n" + "\n".join(lines)
            # Wenn zu lang, splitten
            while len(msg_txt) > 1900:
                await inter.response.send_message(msg_txt[:1900], ephemeral=True)
                msg_txt = msg_txt[1900:]
            await inter.response.send_message(msg_txt, ephemeral=True)
        btn.callback = btn_cb
        v = discord.ui.View(timeout=None)
        v.add_item(btn)
        await ch.send(f"{uname}\n", view=v)
        await ch.send("-----------------")

# ----- STRIKE SLASH-COMMANDS -----

@bot.tree.command(name="strikemaininfo", description="Strike-Info für Teamleads/Mods posten", guild=discord.Object(id=GUILD_ID))
async def strikemaininfo(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed = discord.Embed(
        title="🛑 Strike System – Vergabe von Strikes",
        description=(
            "Vergib Strikes jetzt mit `/strikegive` direkt an einen Nutzer!\n"
            "Nach der Auswahl öffnet sich ein Fenster für Grund und Bildlink.\n\n"
            "**Nur Teamleads/Admins** können Strikes vergeben."
        ),
        color=discord.Color.red()
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("Strike-Hinweis für Mods/Admins gepostet!", ephemeral=True)

@bot.tree.command(name="strikegive", description="Vergibt einen Strike an einen User", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User der einen Strike bekommt")
async def strikegive(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    # MODAL
    class StrikeModal(discord.ui.Modal, title="Strike vergeben"):
        reason = discord.ui.TextInput(label="Grund für Strike", style=discord.TextStyle.long, required=True, max_length=256)
        image = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False, max_length=256)
        async def on_submit(self, modal_inter: discord.Interaction):
            strikes = load_strikes()
            entry = {
                "reason": self.reason.value,
                "image": self.image.value,
                "by": interaction.user.display_name,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds")
            }
            strikes.setdefault(str(user.id), []).append(entry)
            save_strikes(strikes)
            strike_count = len(strikes[str(user.id)])
            # ---- Strike DM je nach Anzahl ----
            msg = ""
            if strike_count == 1:
                msg = (
                    f"Du hast einen **Strike** bekommen wegen:\n```{self.reason.value}```"
                    f"{f'\n\nBild: {self.image.value}' if self.image.value else ''}\n"
                    "\nBitte melde dich bei einem Operation Lead!"
                )
            elif strike_count == 2:
                msg = (
                    f"Du hast jetzt schon deinen **2ten Strike** bekommen, schau dir die Regeln nochmal an.\n"
                    f"Du hast ihn erhalten:\n```{self.reason.value}```"
                    f"{f'\n\nBild: {self.image.value}' if self.image.value else ''}\n"
                    "\nMeld dich bei einem Teamlead um darüber zu sprechen!"
                )
            else:
                msg = (
                    f"Es ist soweit... du hast deinen **3ten Strike** gesammelt...\n"
                    f"```{self.reason.value}```"
                    f"{f'\n\nBild: {self.image.value}' if self.image.value else ''}\n"
                    "Jetzt muss leider eine Bestrafung folgen, darum melde dich schnellstmöglich bei einem TeamLead."
                )
                # Auto-Role beim 3. Strike
                auto_role_id = load_autorole()
                if auto_role_id:
                    role = interaction.guild.get_role(auto_role_id)
                    if role:
                        await user.add_roles(role, reason="Automatisch zugewiesen nach 3 Strikes.")
            try:
                await user.send(msg)
            except Exception:
                pass
            await modal_inter.response.send_message(f"Strike für {user.mention} vergeben und DM gesendet! (Strike-Zahl: {strike_count})", ephemeral=True)
            await update_strike_list(interaction.guild)
    await interaction.response.send_modal(StrikeModal())

# --- Rest: Rollen, Liste, Delete, Remove, View (wie oben) ---

@bot.tree.command(name="strikelist", description="Setzt den Channel für die Strike-Übersicht", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Channel für Strikes")
async def strikelist(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_strike_list_cfg({"channel_id": channel.id})
    await interaction.response.send_message(f"Strike-Übersicht wird jetzt hier gepostet: {channel.mention}", ephemeral=True)
    await update_strike_list(interaction.guild)

@bot.tree.command(name="strikerole", description="Fügt eine Rolle zu den Strike-Berechtigten hinzu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikerole(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    strike_roles = load_strike_roles()
    strike_roles.add(role.id)
    save_strike_roles(strike_roles)
    await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikerole_remove", description="Entfernt eine Rolle von den Strike-Berechtigten", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def strikerole_remove(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    strike_roles = load_strike_roles()
    if role.id in strike_roles:
        strike_roles.remove(role.id)
        save_strike_roles(strike_roles)
        await interaction.response.send_message(f"Rolle **{role.name}** ist **nicht mehr** Strike-Berechtigt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Rolle **{role.name}** war nicht Strike-Berechtigt.", ephemeral=True)

@bot.tree.command(name="strikeaddrole", description="Setzt die automatische Rolle beim 3. Strike", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Rolle für automatisches Vergeben beim 3. Strike")
async def strikeaddrole(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_autorole(role.id)
    await interaction.response.send_message(f"Die Rolle {role.mention} wird beim 3. Strike automatisch vergeben.", ephemeral=True)

@bot.tree.command(name="strikeaddrole_remove", description="Entfernt die automatische Strike-Rolle", guild=discord.Object(id=GUILD_ID))
async def strikeaddrole_remove(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_autorole(None)
    await interaction.response.send_message("Die automatische Strike-Rolle wurde entfernt.", ephemeral=True)

@bot.tree.command(name="strikedelete", description="Alle Strikes von User entfernen", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User zum Löschen")
async def strikedelete(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
    strikes = load_strikes()
    if str(user.id) in strikes:
        strikes.pop(str(user.id))
        save_strikes(strikes)
        await update_strike_list(interaction.guild)
        await interaction.response.send_message(f"Alle Strikes für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeremove", description="Entfernt einen Strike", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User für Strike-Abbau")
async def strikeremove(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_role(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    strikes = load_strikes()
    entrys = strikes.get(str(user.id), [])
    if entrys:
        entrys.pop()
        if not entrys:
            strikes.pop(str(user.id))
        else:
            strikes[str(user.id)] = entrys
        save_strikes(strikes)
        await update_strike_list(interaction.guild)
        await interaction.response.send_message(f"Ein Strike für {user.mention} entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

@bot.tree.command(name="strikeview", description="Zeigt dir, wie viele Strikes du hast (privat)", guild=discord.Object(id=GUILD_ID))
async def strikeview(interaction: discord.Interaction):
    strikes = load_strikes()
    user_id = str(interaction.user.id)
    count = len(strikes.get(user_id, []))
    msg = (
        f"👮‍♂️ **Strike-Übersicht** für {interaction.user.mention}:\n\n"
        f"Du hast aktuell **{count} Strike{'s' if count!=1 else ''}**.\n"
        f"{'Wenn du mehr wissen willst, schreibe dem Bot einfach eine DM.' if count else 'Du hast aktuell keine Strikes.'}"
    )
    await interaction.response.send_message(msg, ephemeral=True)

# --- Ende Strike-System ---

# ───── WIKI SYSTEM (final mit DM-Backup an Admin) ──────────────────────────────

# ====================== WIKI SYSTEM ==============================
import os
import json
import discord
from discord import app_commands

WIKI_DATA_FILE = "wiki_pages.json"
WIKI_BACKUP_FILE = "wiki_backup.json"
wiki_pages = {}
wiki_backup = {}
wiki_main_channel_id = None

# --------- Daten laden & speichern (bleibt erhalten bei Railway, wenn im Volume/Root!) ----
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

wiki_pages = load_json(WIKI_DATA_FILE, {})
wiki_backup = load_json(WIKI_BACKUP_FILE, {})

def backup_all_pages():
    """Sichere alle Wiki-Seiten ins Backup (nur einmal beim Start oder mit /wiki_backup)."""
    for title, content in wiki_pages.items():
        wiki_backup[title] = content
    save_json(WIKI_BACKUP_FILE, wiki_backup)

backup_all_pages()  # Einmal zu Beginn

# --------- Slash-Commands ---------
@bot.tree.command(name="wikimain", description="Setzt den Hauptkanal für das Wiki-Menü")
@app_commands.describe(channel="Textkanal für das Wiki-Menü")
async def wikimain(interaction: discord.Interaction, channel: discord.TextChannel):
    global wiki_main_channel_id
    wiki_main_channel_id = channel.id
    await interaction.response.send_message(f"Wiki-Main-Channel gesetzt: {channel.mention}", ephemeral=True)
    await post_wiki_menu()

@bot.tree.command(name="wiki_page", description="Speichert den aktuellen Channel als Wiki-Seite und löscht ihn")
async def wiki_page(interaction: discord.Interaction):
    ch = interaction.channel
    title = ch.name.replace("-", " ").capitalize()
    # Den ersten echten User-Post als Seiteninhalt nehmen (max 30 Nachrichten scannen)
    async for msg in ch.history(limit=30, oldest_first=True):
        if msg.author.bot:
            continue
        content = msg.content.strip()
        if not content:
            continue
        wiki_pages[title] = content
        save_json(WIKI_DATA_FILE, wiki_pages)
        wiki_backup[title] = content
        save_json(WIKI_BACKUP_FILE, wiki_backup)
        # Backup per DM an Command-User
        try:
            await interaction.user.send(
                f"**Wiki-Backup:**\nTitel: `{title}`\n\n{content[:1800]}" +
                (f"\n\n[Text gekürzt]" if len(content) > 1800 else "")
            )
        except Exception:
            pass
        await ch.delete()
        await interaction.response.send_message(
            f"Wiki-Seite '{title}' gespeichert, Channel gelöscht. Backup wurde dir per DM geschickt!", ephemeral=True)
        await post_wiki_menu()
        return
    await interaction.response.send_message(
        "Keine passende Nachricht im Channel gefunden. Seite nicht gespeichert.", ephemeral=True)

@bot.tree.command(name="wiki_delete", description="Löscht eine Wiki-Seite")
async def wiki_delete(interaction: discord.Interaction):
    if not wiki_pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in list(wiki_pages)[:25]]
    sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        wiki_pages.pop(title, None)
        save_json(WIKI_DATA_FILE, wiki_pages)
        await inter.response.send_message(f"Seite '{title}' gelöscht.", ephemeral=True)
        await post_wiki_menu()
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Seite zum Löschen:", view=view, ephemeral=True)

@bot.tree.command(name="wiki_edit", description="Bearbeite eine gespeicherte Wiki-Seite")
async def wiki_edit(interaction: discord.Interaction):
    if not wiki_pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in list(wiki_pages)[:25]]
    sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        modal = discord.ui.Modal(title=f"Wiki-Seite bearbeiten: {title}")
        content_box = discord.ui.TextInput(label="Inhalt", style=discord.TextStyle.long, default=wiki_pages[title], required=True, max_length=1800)
        modal.add_item(content_box)
        async def on_submit(m_inter):
            wiki_pages[title] = content_box.value
            save_json(WIKI_DATA_FILE, wiki_pages)
            wiki_backup[title] = content_box.value
            save_json(WIKI_BACKUP_FILE, wiki_backup)
            await m_inter.response.send_message(f"Seite '{title}' aktualisiert!", ephemeral=True)
            await post_wiki_menu()
        modal.on_submit = on_submit
        await inter.response.send_modal(modal)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Seite zum Bearbeiten:", view=view, ephemeral=True)

@bot.tree.command(name="wiki_backup", description="Stellt einzelne Wiki-Seiten als Channel wieder her")
async def wiki_backup_cmd(interaction: discord.Interaction):
    if not wiki_backup:
        return await interaction.response.send_message("Keine Backups vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in list(wiki_backup)[:25]]
    sel = discord.ui.Select(placeholder="Backup-Seite wiederherstellen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        cat = interaction.channel.category
        ch = await interaction.guild.create_text_channel(title.replace(" ", "-").lower(), category=cat)
        text = wiki_backup[title]
        # In 1800er Blöcke splitten
        chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
        for chunk in chunks:
            await ch.send(chunk)
        await inter.response.send_message(f"Channel `{title}` wiederhergestellt!", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle ein Backup zum Wiederherstellen:", view=view, ephemeral=True)

# ---- WIKI MENU/Dropdown posten (immer max. 25 Seiten pro View, Discord-Limit) ----
async def post_wiki_menu():
    if not wiki_main_channel_id:
        return
    ch = bot.get_channel(wiki_main_channel_id)
    if not ch:
        return
    async for msg in ch.history(limit=50):
        if msg.author == bot.user:
            try:
                await msg.delete()
            except Exception:
                pass
    if not wiki_pages:
        await ch.send("Keine Wiki-Seiten verfügbar.")
        return
    view = discord.ui.View(timeout=None)
    options = [
        discord.SelectOption(label=title, value=title)
        for title in list(wiki_pages)[:25]
    ]
    sel = discord.ui.Select(placeholder="Wiki-Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        text = wiki_pages.get(title, "")
        chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
        for chunk in chunks:
            await inter.response.send_message(f"**{title}**\n{chunk}", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await ch.send("📚 **Wiki-Auswahl:**", view=view)

# ---- Beim Bot-Start: Slash-Commands neu synchronisieren ----
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("Slash-Commands synchronisiert!")
    except Exception as e:
        print(f"Fehler bei der Command-Synchronisierung: {e}")

# ================= SCHICHTÜBERGABE SYSTEM ======================
import asyncio
import discord
from discord import app_commands

SCHICHT_CHANNEL_FILE = "schicht_channel.json"
SCHICHT_LOG_FILE = "schicht_log.json"
SCHICHT_VOICE_FILE = "schicht_voice.json"
SCHICHT_ROLES_FILE = "schicht_roles.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

schicht_channel_id = load_json(SCHICHT_CHANNEL_FILE, {}).get("channel_id")
schicht_log_channel_id = load_json(SCHICHT_LOG_FILE, {}).get("channel_id")
schicht_voice_id = load_json(SCHICHT_VOICE_FILE, {}).get("voice_id")
schicht_roles = set(load_json(SCHICHT_ROLES_FILE, {}).get("role_ids", []))

# --- Admin-Befehle zur Konfiguration ---
@bot.tree.command(name="schichtwechsel", description="Setzt den Hauptkanal für Schichtübergaben", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Textkanal für Schichtwechsel")
async def schichtwechsel(interaction: discord.Interaction, channel: discord.TextChannel):
    global schicht_channel_id
    schicht_channel_id = channel.id
    save_json(SCHICHT_CHANNEL_FILE, {"channel_id": channel.id})
    await interaction.response.send_message(f"Schichtübergabe-Channel gesetzt: {channel.mention}", ephemeral=True)
    await post_schicht_button()

@bot.tree.command(name="schicht_voiceid", description="Setzt den VoiceMaster-Eingangskanal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(voice_id="Voice Channel ID")
async def schicht_voiceid(interaction: discord.Interaction, voice_id: str):
    global schicht_voice_id
    schicht_voice_id = int(voice_id)
    save_json(SCHICHT_VOICE_FILE, {"voice_id": schicht_voice_id})
    await interaction.response.send_message(f"VoiceMaster-Eingangskanal gesetzt: <#{schicht_voice_id}>", ephemeral=True)

@bot.tree.command(name="schichtlog", description="Setzt den Log-Kanal für Schichtübergaben", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Textkanal für Logs")
async def schichtlog(interaction: discord.Interaction, channel: discord.TextChannel):
    global schicht_log_channel_id
    schicht_log_channel_id = channel.id
    save_json(SCHICHT_LOG_FILE, {"channel_id": channel.id})
    await interaction.response.send_message(f"Log-Channel für Schichtübergaben gesetzt: {channel.mention}", ephemeral=True)

@bot.tree.command(name="schichtrollen", description="Fügt eine Rolle hinzu, deren Mitglieder Schichtübergabe machen können", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def schichtrollen(interaction: discord.Interaction, role: discord.Role):
    global schicht_roles
    schicht_roles.add(role.id)
    save_json(SCHICHT_ROLES_FILE, {"role_ids": list(schicht_roles)})
    await interaction.response.send_message(f"Rolle **{role.name}** kann jetzt Schichtübergabe!", ephemeral=True)

@bot.tree.command(name="schichtrollen_remove", description="Entfernt eine Schicht-Rolle", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="Discord Rolle")
async def schichtrollen_remove(interaction: discord.Interaction, role: discord.Role):
    global schicht_roles
    schicht_roles.discard(role.id)
    save_json(SCHICHT_ROLES_FILE, {"role_ids": list(schicht_roles)})
    await interaction.response.send_message(f"Rolle **{role.name}** kann nun keine Schichtübergabe mehr.", ephemeral=True)

# --- Nutzer-Prüfung ---
def user_has_schicht_role(member):
    if member.guild_permissions.administrator:
        return True
    return any(r.id in schicht_roles for r in member.roles)

# --- Schichtübergabe Hauptbutton posten ---
async def post_schicht_button():
    if not schicht_channel_id:
        return
    ch = bot.get_channel(schicht_channel_id)
    if not ch:
        return
    async for msg in ch.history(limit=30):
        if msg.author == bot.user:
            try: await msg.delete()
            except: pass
    embed = discord.Embed(
        title="🔄 Schichtübergabe starten",
        description=(
            "Klicke auf **Schichtübergabe starten**.\n"
            "Du kannst dann `/schichtuebergabe @User` ausführen (nur Berechtigte).\n\n"
            "**Voraussetzung:** Du bist in einem Voice-Channel & Nutzer online."
        ),
        color=discord.Color.teal()
    )
    await ch.send(embed=embed)

# --- Schichtübergabe-Befehl mit Übergabe & Checks ---
@bot.tree.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Nutzer (Taggen mit @...)")
async def schichtuebergabe(interaction: discord.Interaction, user: discord.Member):
    # Rechte prüfen
    if not user_has_schicht_role(interaction.user):
        return await interaction.response.send_message("Du hast keine Berechtigung für Schichtübergaben!", ephemeral=True)

    # Ist Initiator im Voice-Channel?
    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("Du musst dich in einem Voice-Channel befinden!", ephemeral=True)
    # Ist Zielnutzer online?
    if not user.status == discord.Status.online and not user.voice:
        # Try: Not online & nicht im Voice = DM und Fehler
        try:
            await user.send(f"{interaction.user.mention} wollte dir die Schicht übergeben, du bist aber offline. Bitte melde dich asap!")
            await interaction.response.send_message(
                f"{user.display_name} ist offline/weg – wurde per DM informiert!", ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("Nutzer ist offline und DMs deaktiviert.", ephemeral=True)
            return

    # Moven in VoiceMaster Eingangschannel
    if not schicht_voice_id:
        return await interaction.response.send_message("Kein VoiceMaster-Eingangskanal gesetzt! Nutze `/schicht_voiceid ...`", ephemeral=True)

    try:
        vc_start = bot.get_channel(schicht_voice_id)
        await interaction.user.move_to(vc_start)
    except Exception:
        return await interaction.response.send_message("Fehler beim Moven in VoiceMaster-Eingangskanal.", ephemeral=True)
    await asyncio.sleep(5)  # Zeit für VoiceMaster, neuen Temp-Channel zu erstellen

    # Suche aktuellen Voice-Channel (könnte schon temp sein)
    new_vc = interaction.user.voice.channel if interaction.user.voice else vc_start
    try:
        await user.move_to(new_vc)
    except Exception:
        await interaction.response.send_message("Fehler beim Moven des Nutzers – ist er noch im Voice?", ephemeral=True)
        return

    # Erfolgs-Info & Logging
    await interaction.response.send_message(
        f"✅ Schichtübergabe erfolgreich! {user.mention} wurde zu dir in <#{new_vc.id}> verschoben.",
        ephemeral=True
    )
    if schicht_log_channel_id:
        log_ch = bot.get_channel(schicht_log_channel_id)
        if log_ch:
            await log_ch.send(
                f"🟢 **Schichtübergabe:** {interaction.user.mention} → {user.mention} | Channel: <#{new_vc.id}>"
            )

# --- On Bot Ready: Slash-Commands sync ---
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("Slash-Commands für Guild taskt synchronisiert!")
    except Exception as e:
        print(f"Fehler bei Slash-Command-Sync: {e}")
# =================== RAILWAY-PERSISTENZ/LOADER ====================
import os
import shutil

# ---- Nutze einen festen Speicherort im Project Root für alle wichtigen JSON-Dateien ----
DATA_FILES = [
    "profiles.json", "translation_log.json", "translator_menu.json",
    "strike_data.json", "strike_list.json", "strike_roles.json",
    "wiki_pages.json", "wiki_backup.json",
    "schicht_channel.json", "schicht_log.json", "schicht_voice.json", "schicht_roles.json"
]

DATA_BACKUP_DIR = "railway_data_backup"

def railway_ensure_persistence():
    # Prüfe ob Daten existieren – falls ja, sichere sie, falls nein, kopiere sie zurück
    if not os.path.isdir(DATA_BACKUP_DIR):
        os.mkdir(DATA_BACKUP_DIR)
    # Backup vorhandener Daten (beim Herunterfahren/Speichern)
    for f in DATA_FILES:
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(DATA_BACKUP_DIR, f))
    # Restore falls Dateien fehlen (beim Neustart/Update)
    for f in DATA_FILES:
        src = os.path.join(DATA_BACKUP_DIR, f)
        if not os.path.exists(f) and os.path.exists(src):
            shutil.copy2(src, f)

# Railway: Backup bei Bot-Stop & Restore bei Start
@bot.event
async def on_ready():
    railway_ensure_persistence()
    try:
        await bot.tree.sync()
        print("Slash-Commands synchronisiert!")
    except Exception as e:
        print(f"Fehler bei Command-Sync: {e}")

import atexit
atexit.register(railway_ensure_persistence)


# NUR EINMAL GANZ UNTEN!
bot.run(DISCORD_TOKEN)

