import os
import json
import aiohttp
import asyncio
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# === Konfiguration & Daten ===
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID", "1374724357741609041"))

PROFILES_FILE      = "profiles.json"
LOG_FILE           = "translation_log.json"
MENU_FILE          = "translator_menu.json"
TRANS_SECTION_FILE = "translation_section.json"
STRIKE_FILE        = "strike_data.json"
STRIKE_ROLE_FILE   = "strike_reward_role.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

profiles   = load_json(PROFILES_FILE, {"Normal":"neutraler professioneller Stil","Flirty":"junger koketter Ton"})
log_cfg    = load_json(LOG_FILE, {})
log_channel_id  = log_cfg.get("log_channel_id")
trans_section   = load_json(TRANS_SECTION_FILE, {})
trans_category_id = trans_section.get("category_id")
strike_data = load_json(STRIKE_FILE, {})
strike_reward = load_json(STRIKE_ROLE_FILE, {}).get("role_id")

active_sessions = {}  # (user_id, profile) -> channel_id
channel_info    = {}  # channel_id -> (user_id, profile, style)
strike_roles    = set(strike_data.get("roles", []))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(user):
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if hasattr(bot, "owner_id") and user.id == bot.owner_id:
        return True
    return False

async def setup_owner_id():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id

def has_strike_permission(user):
    if is_admin(user): return True
    reward = load_json(STRIKE_ROLE_FILE, {}).get("role_id")
    return reward and any(r.id == int(reward) for r in user.roles)

async def get_guild_members(guild):
    return [m for m in guild.members if not m.bot]

# ==== GOOGLE GEMINI DUMMY (ersetze durch echte API) ====
async def call_gemini(prompt: str) -> str:
    # Hier deine echte Gemini API, hier nur Dummy!
    return f"*Übersetzung:* {prompt[:60]}..."

# === TRANSLATOR SYSTEM ===
@bot.tree.command(name="translationsection", description="Setzt die Kategorie für Übersetzungskanäle")
@app_commands.describe(kategorie="Kategorie für Übersetzungen")
async def translationsection(interaction: discord.Interaction, kategorie: discord.CategoryChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Nur Admins/Owner!", ephemeral=True)
    save_json(TRANS_SECTION_FILE, {"category_id": kategorie.id})
    global trans_category_id
    trans_category_id = kategorie.id
    await interaction.response.send_message(f"Kategorie gesetzt: {kategorie.name}", ephemeral=True)

def make_translation_menu():
    embed = discord.Embed(
        title="📝 Translation Support",
        description="Wähle dein Profil aus, um eine private Übersetzungs-Session zu starten:",
        color=discord.Color.teal()
    )
    view = discord.ui.View(timeout=None)
    options = [discord.SelectOption(label=nm, description=profiles[nm]) for nm in profiles]
    sel = discord.ui.Select(placeholder="Profil wählen...", options=options, max_values=1)
    async def sel_cb(inter):
        prof = inter.data["values"][0]
        await start_session(inter, prof)
        # Reset Dropdown nach Auswahl (erneut auswählbar)
        await inter.message.edit(embed=embed, view=make_translation_menu())
    sel.callback = sel_cb
    view.add_item(sel)
    return embed, view

async def start_session(interaction: discord.Interaction, prof: str):
    user = interaction.user
    style = profiles[prof]
    key = (user.id, prof)
    cat_id = trans_category_id or load_json(TRANS_SECTION_FILE, {}).get("category_id")
    guild = interaction.guild
    category = guild.get_channel(cat_id) if cat_id else None
    if not category or category.type != discord.ChannelType.category:
        return await interaction.response.send_message("Kategorie nicht gesetzt oder ungültig.", ephemeral=True)
    chan_name = f"translate-{prof.lower()}-{user.display_name.lower()}".replace(" ", "-")
    ch = await guild.create_text_channel(chan_name, category=category)
    await ch.set_permissions(guild.default_role, view_channel=False)
    await ch.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
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

@bot.tree.command(name="translatorpost", description="Postet das Übersetzungsmenü im aktuellen Kanal")
async def translatorpost(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Nur Admins/Owner!", ephemeral=True)
    embed, view = make_translation_menu()
    msg = await interaction.channel.send(embed=embed, view=view)
    save_json(MENU_FILE, {"channel_id": interaction.channel.id, "message_id": msg.id})
    await interaction.response.send_message("Übersetzungsmenü gepostet.", ephemeral=True)

@bot.tree.command(name="translationlog", description="Setzt den Log-Kanal")
@app_commands.describe(channel="Text-Kanal für Logs")
async def translationlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Nur Admins/Owner!", ephemeral=True)
    save_json(LOG_FILE, {"log_channel_id": channel.id})
    await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None or not message.channel.category_id:
        return
    cat_id = trans_category_id or load_json(TRANS_SECTION_FILE, {}).get("category_id")
    if message.channel.category_id != cat_id:
        return
    info = channel_info.get(message.channel.id)
    if not info or message.author.id != info[0]:
        return
    txt = message.content.strip()
    if not txt:
        return
    prompt = (
        f"Erkenne Sprache. Wenn Deutsch, übersetze ins Englische im Stil: {info[2]}. "
        f"Wenn Englisch, übersetze ins Deutsche im Stil: {info[2]}. "
        "Antworte NUR mit der Übersetzung:\n"
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
    # Logging mit Username
    log_cfg = load_json(LOG_FILE, {})
    log_channel_id = log_cfg.get("log_channel_id")
    if log_channel_id:
        log_channel = message.guild.get_channel(log_channel_id)
        if log_channel:
            log_e = discord.Embed(title="Übersetzung", color=discord.Color.orange())
            log_e.add_field(name="Profil", value=info[1], inline=False)
            log_e.add_field(name="Von", value=message.author.display_name, inline=False)
            log_e.add_field(name="Original", value=txt, inline=False)
            log_e.add_field(name="Übersetzung", value=translation, inline=False)
            await log_channel.send(embed=log_e)
    await bot.process_commands(message)

# ==== STRIKE SYSTEM (Vollständig) ====
def get_strikes():
    return load_json(STRIKE_FILE, {}).get("strikes", {})

def save_strikes(strikes):
    data = load_json(STRIKE_FILE, {})
    data["strikes"] = strikes
    save_json(STRIKE_FILE, data)

def load_strike_reward():
    return load_json(STRIKE_ROLE_FILE, {}).get("role_id")

def save_strike_reward(role_id):
    save_json(STRIKE_ROLE_FILE, {"role_id": role_id})

@bot.tree.command(name="strikeaddrole", description="Rolle, die bei 3 Strikes automatisch vergeben wird")
@app_commands.describe(role="Rolle für 3. Strike")
async def strikeaddrole(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    save_strike_reward(role.id)
    await interaction.response.send_message(f"Die Rolle {role.mention} wird bei 3 Strikes automatisch vergeben.", ephemeral=True)

def make_strike_menu(guild):
    strikes = get_strikes()
    embed = discord.Embed(
        title="Strike System",
        description="Wähle einen User um einen Strike zu vergeben:",
        color=discord.Color.red()
    )
    view = discord.ui.View(timeout=None)
    members = [m for m in guild.members if not m.bot]
    options = [discord.SelectOption(label="Keinen", value="none")] + [
        discord.SelectOption(label=f"{m.display_name}", value=str(m.id)) for m in members
    ]
    sel = discord.ui.Select(placeholder="User wählen", options=options, max_values=1)
    async def sel_cb(inter):
        if not has_strike_permission(inter.user):
            return await inter.response.send_message("Keine Berechtigung.", ephemeral=True)
        value = inter.data["values"][0]
        if value == "none":
            await inter.response.send_message("Abgebrochen.", ephemeral=True)
            # Dropdown-Reset
            await inter.message.edit(embed=embed, view=make_strike_menu(guild))
            return
        uid = int(value)
        modal = discord.ui.Modal(title="Strike vergeben")
        reason = discord.ui.TextInput(label="Grund", style=discord.TextStyle.long, required=True)
        imgurl = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False)
        modal.add_item(reason)
        modal.add_item(imgurl)
        async def on_submit(m_inter):
            strikes = get_strikes()
            entry = {
                "reason": reason.value,
                "image": imgurl.value,
                "by": inter.user.display_name,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds")
            }
            user_strikes = strikes.get(str(uid), [])
            user_strikes.append(entry)
            strikes[str(uid)] = user_strikes
            save_strikes(strikes)
            strike_count = len(user_strikes)
            reward_role_id = load_strike_reward()
            try:
                user = guild.get_member(uid)
                if strike_count == 3 and reward_role_id:
                    role = guild.get_role(int(reward_role_id))
                    if role:
                        await user.add_roles(role, reason="Automatisch durch 3 Strikes")
                # DM an User
                msg = ""
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
                if user:
                    await user.send(msg)
            except Exception:
                pass
            await m_inter.response.send_message(f"Strike für <@{uid}> gespeichert!", ephemeral=True)
            await update_strike_list_msg(guild, inter.message.channel)
        modal.on_submit = on_submit
        await inter.response.send_modal(modal)
        # Reset Dropdown (erneut auswählbar)
        await inter.message.edit(embed=embed, view=make_strike_menu(guild))
    sel.callback = sel_cb
    view.add_item(sel)
    # Strike-Liste unten drunter
    text = "\n-----------------\n".join(
        [f"<@{uid}>\n(Strikes: {len(entries)})"
         for uid, entries in strikes.items() if entries]
    ) or "(Noch keine Strikes vergeben.)"
    embed.add_field(name="Strikeliste", value=text, inline=False)
    return embed, view

async def update_strike_list_msg(guild, channel):
    embed, view = make_strike_menu(guild)
    async for msg in channel.history(limit=15):
        if msg.author == bot.user and "Strike System" in (msg.embeds[0].title if msg.embeds else ""):
            await msg.edit(embed=embed, view=view)

@bot.tree.command(name="strikemain", description="Strike-Menü im Channel posten")
async def strikemain(interaction: discord.Interaction):
    if not has_strike_permission(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    embed, view = make_strike_menu(interaction.guild)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="strikelist", description="Listet alle aktuellen Strikes auf")
async def strikelist(interaction: discord.Interaction):
    strikes = get_strikes()
    text = "\n-----------------\n".join(
        [f"<@{uid}>\n(Strikes: {len(entries)})"
         for uid, entries in strikes.items() if entries]
    ) or "(Noch keine Strikes vergeben.)"
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="strikeview", description="Zeigt dir deine eigenen Strikes per DM")
async def strikeview(interaction: discord.Interaction):
    strikes = get_strikes()
    user_strikes = strikes.get(str(interaction.user.id), [])
    await interaction.response.send_message(
        f"Du hast aktuell **{len(user_strikes)}** von 3 möglichen Strikes.\nFür Details schreibe dem Bot per DM.", ephemeral=True
    )

@bot.tree.command(name="strikeremove", description="Entfernt einen Strike von einem User")
@app_commands.describe(user="User mit Strike")
async def strikeremove(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_permission(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    strikes = get_strikes()
    user_strikes = strikes.get(str(user.id), [])
    if user_strikes:
        user_strikes.pop()
        strikes[str(user.id)] = user_strikes
        save_strikes(strikes)
        await interaction.response.send_message(f"Ein Strike bei {user.mention} entfernt. Jetzt: {len(user_strikes)}", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keinen Strike.", ephemeral=True)

@bot.tree.command(name="strikedelete", description="Entfernt alle Strikes von einem User")
@app_commands.describe(user="User mit Strikes")
async def strikedelete(interaction: discord.Interaction, user: discord.Member):
    if not has_strike_permission(interaction.user):
        return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
    strikes = get_strikes()
    if str(user.id) in strikes:
        strikes.pop(str(user.id))
        save_strikes(strikes)
        await interaction.response.send_message(f"Alle Strikes bei {user.mention} gelöscht.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

# --- Bot Starten -----------------------------------
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
    print(f"✅ Bot bereit als {bot.user}")

bot.run(DISCORD_TOKEN)
