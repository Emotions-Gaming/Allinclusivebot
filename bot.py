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

WIKI_DATA_FILE = "wiki_pages.json"
WIKI_BACKUP_FILE = "wiki_backup.json"

def load_wiki_pages():
    try:
        with open(WIKI_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_wiki_pages(data):
    with open(WIKI_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_wiki_backup():
    try:
        with open(WIKI_BACKUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_wiki_backup(data):
    with open(WIKI_BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

wiki_pages = load_wiki_pages()
wiki_backup = load_wiki_backup()
wiki_main_channel_id = None

# WIKI MAIN-CHANNEL SETZEN
@bot.tree.command(name="wikimain", description="Setzt den Hauptkanal für Wiki-Dropdown", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Textkanal für Wiki-Menü")
async def wikimain(interaction: discord.Interaction, channel: discord.TextChannel):
    global wiki_main_channel_id
    wiki_main_channel_id = channel.id
    await interaction.response.send_message(f"Wiki-Main-Channel gesetzt: {channel.mention}", ephemeral=True)
    await post_wiki_menu()

# WIKI SEITE HINZUFÜGEN (mit DM-Backup an Admin)
@bot.tree.command(name="wiki_page", description="Fügt eine Wiki-Seite aus aktuellem Channel hinzu", guild=discord.Object(id=GUILD_ID))
async def wiki_page(interaction: discord.Interaction):
    ch = interaction.channel
    title = ch.name.replace("-", " ").capitalize()
    async for msg in ch.history(limit=30, oldest_first=True):
        if msg.author.bot:
            continue
        content = msg.content.strip()
        if not content:
            continue
        wiki_pages[title] = content
        save_wiki_pages(wiki_pages)
        # Backup anlegen für Undo
        wiki_backup[title] = content
        save_wiki_backup(wiki_backup)
        # NEU: DM an Admin schicken
        try:
            await interaction.user.send(
                f"**Wiki-Backup:**\nTitel: `{title}`\n\n{content}"
            )
        except Exception:
            pass
        await ch.delete()
        await interaction.response.send_message(
            f"Wiki-Seite '{title}' gespeichert und Channel gelöscht. Backup wurde dir per DM geschickt!", ephemeral=True)
        await post_wiki_menu()
        return
    await interaction.response.send_message(
        "Keine passende Nachricht im Channel gefunden. Seite nicht gespeichert.", ephemeral=True)

# WIKI MENU POSTEN/AKTUALISIEREN
async def post_wiki_menu():
    if not wiki_main_channel_id:
        return
    ch = bot.get_channel(wiki_main_channel_id)
    if not ch:
        return
    if not wiki_pages:
        await ch.send("Keine Wiki-Seiten verfügbar.")
        return
    view = discord.ui.View(timeout=None)
    options = [
        discord.SelectOption(label=title, value=title)
        for title in wiki_pages
    ]
    sel = discord.ui.Select(placeholder="Wiki-Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        text = wiki_pages.get(title, "")
        # Falls Text zu lang, splitten
        chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
        for chunk in chunks:
            await inter.response.send_message(
                f"**{title}**\n{chunk}", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await ch.send("📚 **Wiki-Auswahl:**", view=view)

# WIKI SEITE EDITIEREN
@bot.tree.command(name="wiki_edit", description="Bearbeite eine gespeicherte Wiki-Seite", guild=discord.Object(id=GUILD_ID))
async def wiki_edit(interaction: discord.Interaction):
    if not wiki_pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in wiki_pages]
    sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        orig = wiki_pages[title]
        # Temporärer Channel erstellen
        cat = interaction.channel.category
        temp_ch = await interaction.guild.create_text_channel(f"edit-{title}", category=cat)
        await temp_ch.send(f"**Editiere die Seite `{title}`:**\n\n{orig}\n\n_Nach Änderung tippe `/wiki_save {title}`_")
        await inter.response.send_message(f"Channel zum Editieren erstellt: {temp_ch.mention}", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Seite zum Editieren:", view=view, ephemeral=True)

# WIKI SEITE SPEICHERN (nach Bearbeitung)
@bot.tree.command(name="wiki_save", description="Speichert eine bearbeitete Wiki-Seite", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(title="Seitentitel")
async def wiki_save(interaction: discord.Interaction, title: str):
    ch = interaction.channel
    async for msg in ch.history(limit=10, oldest_first=False):
        if msg.author == interaction.user and msg.content.strip():
            wiki_pages[title] = msg.content.strip()
            save_wiki_pages(wiki_pages)
            wiki_backup[title] = msg.content.strip()
            save_wiki_backup(wiki_backup)
            await ch.delete()
            await interaction.response.send_message("Seite gespeichert & Channel gelöscht!", ephemeral=True)
            await post_wiki_menu()
            return
    await interaction.response.send_message("Konnte keine Änderung erkennen!", ephemeral=True)

# WIKI SEITE LÖSCHEN
@bot.tree.command(name="wiki_delete", description="Löscht eine Wiki-Seite", guild=discord.Object(id=GUILD_ID))
async def wiki_delete(interaction: discord.Interaction):
    if not wiki_pages:
        return await interaction.response.send_message("Keine Wiki-Seiten vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in wiki_pages]
    sel = discord.ui.Select(placeholder="Seite auswählen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        wiki_pages.pop(title, None)
        save_wiki_pages(wiki_pages)
        await inter.response.send_message(f"Seite '{title}' gelöscht.", ephemeral=True)
        await post_wiki_menu()
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle eine Seite zum Löschen:", view=view, ephemeral=True)

# WIKI BACKUP UNDO: Einzel-Channel wiederherstellen
@bot.tree.command(name="wiki_backup", description="Stellt einzelne Wiki-Seiten als Channels wieder her", guild=discord.Object(id=GUILD_ID))
async def wiki_backup_cmd(interaction: discord.Interaction):
    if not wiki_backup:
        return await interaction.response.send_message("Keine Backups vorhanden.", ephemeral=True)
    view = discord.ui.View(timeout=120)
    options = [discord.SelectOption(label=title, value=title) for title in wiki_backup]
    sel = discord.ui.Select(placeholder="Backup-Seite wiederherstellen...", options=options)
    async def sel_cb(inter):
        title = inter.data["values"][0]
        cat = interaction.channel.category
        ch = await interaction.guild.create_text_channel(title.replace(" ", "-").lower(), category=cat)
        text = wiki_backup[title]
        chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
        for chunk in chunks:
            await ch.send(chunk)
        await inter.response.send_message(f"Channel `{title}` wiederhergestellt!", ephemeral=True)
    sel.callback = sel_cb
    view.add_item(sel)
    await interaction.response.send_message("Wähle ein Backup zum Wiederherstellen:", view=view, ephemeral=True)

 
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

# NUR EINMAL GANZ UNTEN!
bot.run(DISCORD_TOKEN)

