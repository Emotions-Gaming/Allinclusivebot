import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

from utils import load_json, save_json, is_admin, has_any_role

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID"))

MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
PROFILES_FILE = "profiles.json"
MENU_FILE = "translator_menu.json"
PROMPT_FILE = "translator_prompt.json"
TRANS_CAT_FILE = "trans_category.json"
TRANSLATION_LOG_FILE = "translation_log.json"

def get_profile_style(profile_name):
    profiles = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil"})
    return profiles.get(profile_name, "neutraler professioneller Stil")

def get_translation_log_channel_id():
    menu_cfg = load_json(MENU_FILE, {})
    return menu_cfg.get("log_channel_id", None)

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

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}  # (user_id, profile) -> channel_id
        self.channel_info = {}     # channel_id -> (user_id, profile, style)
        self.channel_logs = {}     # channel_id -> [ (user, text, translation) ]

    # ===============================
    # --- Übersetzungsmenü posten ---
    # ===============================
    @app_commands.command(name="translatorpost", description="Postet das Übersetzungsmenü im aktuellen Kanal")
    async def translatorpost(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        embed, view = self.make_translation_menu()
        msg = await interaction.channel.send(embed=embed, view=view)
        menu_cfg = load_json(MENU_FILE, {})
        menu_cfg["channel_id"] = interaction.channel.id
        menu_cfg["message_id"] = msg.id
        save_json(MENU_FILE, menu_cfg)
        await interaction.response.send_message("Übersetzungsmenü gepostet.", ephemeral=True)

    def make_translation_menu(self):
        profiles = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil"})
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
            await self.start_session(inter, prof)
            # Reset dropdown (optional)
            reset_embed, reset_view = self.make_translation_menu()
            await inter.message.edit(embed=reset_embed, view=reset_view)
        sel.callback = sel_cb
        view.add_item(sel)
        return embed, view

    async def start_session(self, interaction: discord.Interaction, prof: str):
        user = interaction.user
        style = get_profile_style(prof)
        key = (user.id, prof)
        # Only one session per user/profile at once
        if key in self.active_sessions:
            old = self.active_sessions[key]
            if not self.bot.get_channel(old):
                del self.active_sessions[key]
        if key in self.active_sessions:
            return await interaction.response.send_message("Du hast bereits eine aktive Session.", ephemeral=True)
        guild = interaction.guild
        trans_cat_id = load_json(TRANS_CAT_FILE, {}).get("category_id", None)
        cat = self.bot.get_channel(trans_cat_id) if trans_cat_id else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        chan_name = f"translat-{prof.lower()}-{user.display_name.lower()}".replace(" ", "-")
        # Delete old channel if exists
        for c in (cat.text_channels if cat else guild.text_channels):
            if c.name == chan_name:
                await c.delete()
        ch = await guild.create_text_channel(chan_name, category=cat, overwrites=overwrites)
        self.active_sessions[key] = ch.id
        self.channel_info[ch.id] = (user.id, prof, style)
        self.channel_logs[ch.id] = []

        btn = discord.ui.Button(label="Session beenden & Verlauf senden", style=discord.ButtonStyle.danger)
        async def end_cb(bi: discord.Interaction):
            info = self.channel_info.get(ch.id)
            if not info or bi.user.id != info[0]:
                return await bi.response.send_message("Nur der Besitzer kann beenden.", ephemeral=True)
            log = self.channel_logs.get(ch.id, [])
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
            log_channel_id = get_translation_log_channel_id()
            if log_channel_id:
                log_channel = bi.guild.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(embed=log_embed)
            await bi.response.send_message("Session beendet & Verlauf wurde an den Log gesendet.", ephemeral=True)
            await ch.delete()
            try: del self.channel_info[ch.id]
            except: pass
            try: del self.active_sessions[key]
            except: pass
            try: del self.channel_logs[ch.id]
            except: pass
        btn.callback = end_cb
        v = discord.ui.View(timeout=None)
        v.add_item(btn)
        await ch.send(f"Session **{prof}** gestartet. Schreibe hier zum Übersetzen.", view=v)
        await interaction.response.send_message(f"Session erstellt: {ch.mention}", ephemeral=True)

    # ========== Admin: Profil-Management, Log-Channel, Prompt ==========

    @app_commands.command(name="translatoraddprofile", description="Fügt ein neues Übersetzer-Profil hinzu")
    @app_commands.describe(name="Profilname", style="Stilbeschreibung")
    async def translatoraddprofile(self, interaction: discord.Interaction, name: str, style: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        profiles = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil"})
        nm = name.strip()
        if not nm or nm in profiles:
            return await interaction.response.send_message("Ungültiger oder existierender Name.", ephemeral=True)
        profiles[nm] = style
        save_json(PROFILES_FILE, profiles)
        await interaction.response.send_message(f"Profil **{nm}** hinzugefügt.", ephemeral=True)

    @app_commands.command(name="translatordeleteprofile", description="Löscht ein Übersetzer-Profil")
    @app_commands.describe(name="Profilname")
    async def translatordeleteprofile(self, interaction: discord.Interaction, name: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        profiles = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil"})
        if name not in profiles:
            return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
        profiles.pop(name)
        save_json(PROFILES_FILE, profiles)
        await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)

    @app_commands.command(name="translatorsetcategorie", description="Setzt die Kategorie für Übersetzungs-Session-Channels")
    @app_commands.describe(category="Kategorie")
    async def translatorsetcategorie(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        save_json(TRANS_CAT_FILE, {"category_id": category.id})
        await interaction.response.send_message(f"Kategorie gesetzt: {category.name}", ephemeral=True)

    @app_commands.command(name="translatorlog", description="Setzt den Log-Kanal für Übersetzungs-Session-Verläufe")
    @app_commands.describe(channel="Text-Kanal für Logs")
    async def translatorlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        menu_cfg = load_json(MENU_FILE, {})
        menu_cfg["log_channel_id"] = channel.id
        save_json(MENU_FILE, menu_cfg)
        await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="translatorprompt", description="Fügt eine Regel zum Haupt-Prompt hinzu")
    @app_commands.describe(text="Zusätzlicher Prompt-Text")
    async def translatorprompt(self, interaction: discord.Interaction, text: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        save_json(PROMPT_FILE, {"addition": text})
        await interaction.response.send_message(f"Prompt-Erweiterung gesetzt: **{text}**", ephemeral=True)

    @app_commands.command(name="translatorpromptdelete", description="Entfernt die zusätzliche Prompt-Regel")
    async def translatorpromptdelete(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        save_json(PROMPT_FILE, {"addition": ""})
        await interaction.response.send_message("Prompt-Erweiterung entfernt.", ephemeral=True)

    # ==================
    #      ON_MESSAGE
    # ==================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        chinfo = self.channel_info.get(message.channel.id)
        if not chinfo or message.author.id != chinfo[0]:
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
        prompt = base_prompt.format(style=chinfo[2])
        if prompt_extension:
            prompt += "\nZusätzliche Regel: " + prompt_extension
        prompt += f"\n{txt}"

        try:
            translation = await call_gemini(prompt)
        except Exception:
            translation = "*Fehler bei Übersetzung*"

        emb = discord.Embed(description=f"```{translation}```", color=discord.Color.blue())
        emb.set_footer(text="Auto-Detected Translation")
        await message.channel.send(embed=emb)
        self.channel_logs[message.channel.id].append((message.author.display_name, txt, translation))


    # ... dein TranslationCog-Code ...

async def reload_menu(self, config=None):
    # Lade config aus setup_config.json, falls nicht übergeben
    if config is None:
        from utils import load_json
        config = load_json("setup_config.json", {})
    channel_id = config.get("translation_menu_channel")
    if not channel_id:
        return
    channel = self.bot.get_channel(channel_id)
    if not channel:
        return
    # Alte Bot-Messages im Channel löschen (optional)
    async for msg in channel.history(limit=50):
        if msg.author == self.bot.user:
            try:
                await msg.delete()
            except:
                pass
    # Menü neu posten
    embed, view = self.make_translation_menu()
    await channel.send(embed=embed, view=view)

# Am Ende deiner Cog-Klasse hinzufügen!
TranslationCog.reload_menu = reload_menu

async def setup(bot):
    await bot.add_cog(TranslationCog(bot))