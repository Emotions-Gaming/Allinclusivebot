# translation.py

import os
import json
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")

DATA_DIR = "persistent_data"
PROFILES_FILE   = os.path.join(DATA_DIR, "profiles.json")
MENU_FILE       = os.path.join(DATA_DIR, "translator_menu.json")
PROMPT_FILE     = os.path.join(DATA_DIR, "translator_prompt.json")
TRANS_CAT_FILE  = os.path.join(DATA_DIR, "trans_category.json")
TRANSLATION_LOG = os.path.join(DATA_DIR, "translation_log.json")

MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.profiles = load_json(PROFILES_FILE, {"Normal": "neutraler professioneller Stil", "Flirty": "junger, koketter, aber KEINE Emojis"})
        self.menu_cfg = load_json(MENU_FILE, {})
        self.prompt_cfg = load_json(PROMPT_FILE, {})
        self.trans_cat_cfg = load_json(TRANS_CAT_FILE, {})
        self.translation_log = load_json(TRANSLATION_LOG, {})
        self.active_sessions = {}      # (user_id, profile) -> channel_id
        self.channel_info     = {}     # channel_id -> (user_id, profile, style)
        self.channel_logs     = {}     # channel_id -> [ (user, text, translation) ]
        self.menu_channel_id = self.menu_cfg.get("channel_id")
        self.menu_message_id = self.menu_cfg.get("message_id")
        self.prompt_add = self.prompt_cfg.get("addition", "")
        self.trans_cat_id = self.trans_cat_cfg.get("category_id", None)

    # --- UTILS ---
    def is_admin(self, user):
        return getattr(user, "guild_permissions", None) and user.guild_permissions.administrator

    async def call_gemini(self, prompt: str) -> str:
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

    def make_translation_menu(self):
        embed = discord.Embed(
            title="📝 Translation Support",
            description="Wähle ein Profil aus, um eine private Übersetzungs-Session zu starten:",
            color=discord.Color.teal()
        )
        view = discord.ui.View(timeout=None)
        options = [discord.SelectOption(label=nm, description=self.profiles[nm]) for nm in self.profiles]
        sel = discord.ui.Select(placeholder="Profil wählen...", options=options, max_values=1)
        async def sel_cb(inter: discord.Interaction):
            prof = inter.data["values"][0]
            await self.start_session(inter, prof)
            # Reset dropdown
            reset_embed, reset_view = self.make_translation_menu()
            await inter.message.edit(embed=reset_embed, view=reset_view)
        sel.callback = sel_cb
        view.add_item(sel)
        return embed, view

    async def update_translation_menu(self):
        if not (self.menu_channel_id and self.menu_message_id):
            return
        ch = self.bot.get_channel(self.menu_channel_id)
        if not ch:
            return
        try:
            msg = await ch.fetch_message(self.menu_message_id)
            embed, view = self.make_translation_menu()
            await msg.edit(embed=embed, view=view)
        except Exception:
            pass

    async def start_session(self, interaction: discord.Interaction, prof: str):
        user = interaction.user
        style = self.profiles[prof]
        key = (user.id, prof)
        if key in self.active_sessions:
            old = self.active_sessions[key]
            if not self.bot.get_channel(old):
                del self.active_sessions[key]
        if key in self.active_sessions:
            return await interaction.response.send_message("Du hast bereits eine aktive Session.", ephemeral=True)
        guild = interaction.guild
        cat = self.bot.get_channel(self.trans_cat_id) if self.trans_cat_id else None
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
            log_channel_id = load_json(MENU_FILE, {}).get("log_channel_id", None)
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

    # --- SLASH COMMANDS ---
    @app_commands.command(name="translatorpost", description="Postet das Übersetzungsmenü im aktuellen Kanal")
    async def translatorpost(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        embed, view = self.make_translation_menu()
        msg = await interaction.channel.send(embed=embed, view=view)
        self.menu_channel_id = interaction.channel.id
        self.menu_message_id = msg.id
        save_json(MENU_FILE, {"channel_id": self.menu_channel_id, "message_id": msg.id})
        await interaction.response.send_message("Übersetzungsmenü gepostet.", ephemeral=True)

    @app_commands.command(name="translatoraddprofile", description="Fügt ein neues Übersetzer-Profil hinzu")
    @app_commands.describe(name="Profilname", style="Stilbeschreibung")
    async def translatoraddprofile(self, interaction: discord.Interaction, name: str, style: str):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        nm = name.strip()
        if not nm or nm in self.profiles:
            return await interaction.response.send_message("Ungültiger oder existierender Name.", ephemeral=True)
        self.profiles[nm] = style
        save_json(PROFILES_FILE, self.profiles)
        await interaction.response.send_message(f"Profil **{nm}** hinzugefügt.", ephemeral=True)
        await self.update_translation_menu()

    @app_commands.command(name="translatordeleteprofile", description="Löscht ein Übersetzer-Profil")
    @app_commands.describe(name="Profilname")
    async def translatordeleteprofile(self, interaction: discord.Interaction, name: str):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if name not in self.profiles:
            return await interaction.response.send_message(f"Profil `{name}` nicht gefunden.", ephemeral=True)
        self.profiles.pop(name)
        save_json(PROFILES_FILE, self.profiles)
        await interaction.response.send_message(f"Profil **{name}** gelöscht.", ephemeral=True)
        await self.update_translation_menu()

    @app_commands.command(name="translatorsetcategorie", description="Setzt die Kategorie für Übersetzungs-Session-Channels")
    @app_commands.describe(category="Kategorie")
    async def translatorsetcategorie(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.trans_cat_id = category.id
        save_json(TRANS_CAT_FILE, {"category_id": category.id})
        await interaction.response.send_message(f"Kategorie gesetzt: {category.name}", ephemeral=True)

    @app_commands.command(name="translatorlog", description="Setzt den Log-Kanal für Übersetzungs-Session-Verläufe")
    @app_commands.describe(channel="Text-Kanal für Logs")
    async def translatorlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.menu_cfg = load_json(MENU_FILE, {})
        self.menu_cfg["log_channel_id"] = channel.id
        save_json(MENU_FILE, self.menu_cfg)
        await interaction.response.send_message(f"Log-Kanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="translatorprompt", description="Fügt eine Regel zum Haupt-Prompt hinzu")
    @app_commands.describe(text="Zusätzlicher Prompt-Text")
    async def translatorprompt(self, interaction: discord.Interaction, text: str):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        save_json(PROMPT_FILE, {"addition": text})
        await interaction.response.send_message(f"Prompt-Erweiterung gesetzt: **{text}**", ephemeral=True)

    @app_commands.command(name="translatorpromptdelete", description="Entfernt die zusätzliche Prompt-Regel")
    async def translatorpromptdelete(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        save_json(PROMPT_FILE, {"addition": ""})
        await interaction.response.send_message("Prompt-Erweiterung entfernt.", ephemeral=True)

    # --- MESSAGE EVENT (Autotranslate) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        info = self.channel_info.get(message.channel.id)
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
            translation = await asyncio.wait_for(self.call_gemini(prompt), timeout=25)
        except Exception:
            translation = "*Fehler bei Übersetzung*"

        emb = discord.Embed(description=f"```{translation}```", color=discord.Color.blue())
        emb.set_footer(text="Auto-Detected Translation")
        await message.channel.send(embed=emb)
        self.channel_logs[message.channel.id].append((message.author.display_name, txt, translation))
        # Weiter zu anderen Cogs/Commands
        await self.bot.process_commands(message)

# --- Cog-Setup ---
async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
