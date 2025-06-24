# translation.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
PROFILES_PATH = os.path.join("persistent_data", "profiles.json")
MENU_PATH = os.path.join("persistent_data", "translator_menu.json")
CATEGORY_PATH = os.path.join("persistent_data", "trans_category.json")
PROMPT_PATH = os.path.join("persistent_data", "translator_prompt.json")
TRANSLATION_LOG_PATH = os.path.join("persistent_data", "translation_log.json")

# Dummy-Übersetzung (hier später API call einbauen!)
async def translate_text(text, style, prompt):
    # Hier kannst du OpenAI/Google/andere API einbauen!
    # Prompt-Logik: Wenn deutsch, -> englisch; Wenn englisch, -> deutsch.
    # Prompt-Stil dranhängen, Zusatzregeln immer dranhängen.
    # Keine Emojis, kein KI-Talk, keine Smileys, kein Icon!
    return f"[{style}] {text[::-1]} (Simulierte Übersetzung)"  # Dummy: rückwärts als Demo.

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}  # user_id → channel_id

    # ==== Helper ====

    async def get_profiles(self):
        return await utils.load_json(PROFILES_PATH, {})

    async def save_profiles(self, data):
        await utils.save_json(PROFILES_PATH, data)

    async def get_menu_channel(self, guild):
        d = await utils.load_json(MENU_PATH, {})
        return guild.get_channel(d.get("menu_channel_id", 0)) if d.get("menu_channel_id") else None

    async def set_menu_channel(self, channel_id):
        d = await utils.load_json(MENU_PATH, {})
        d["menu_channel_id"] = channel_id
        await utils.save_json(MENU_PATH, d)

    async def get_log_channel(self, guild):
        d = await utils.load_json(MENU_PATH, {})
        return guild.get_channel(d.get("log_channel_id", 0)) if d.get("log_channel_id") else None

    async def set_log_channel(self, channel_id):
        d = await utils.load_json(MENU_PATH, {})
        d["log_channel_id"] = channel_id
        await utils.save_json(MENU_PATH, d)

    async def get_category(self, guild):
        cid = await utils.load_json(CATEGORY_PATH, None)
        return guild.get_channel(cid) if cid else None

    async def set_category(self, cid):
        await utils.save_json(CATEGORY_PATH, cid)

    async def get_prompts(self):
        return await utils.load_json(PROMPT_PATH, [])

    async def add_prompt(self, text):
        prompts = await self.get_prompts()
        prompts.append(text)
        await utils.save_json(PROMPT_PATH, prompts)

    async def remove_prompt(self, index):
        prompts = await self.get_prompts()
        if 0 <= index < len(prompts):
            prompts.pop(index)
        await utils.save_json(PROMPT_PATH, prompts)

    async def get_log(self):
        return await utils.load_json(TRANSLATION_LOG_PATH, {})

    async def save_log(self, data):
        await utils.save_json(TRANSLATION_LOG_PATH, data)

    # ==== Menu/Dynamic Views ====
    class ProfileDropdown(discord.ui.Select):
        def __init__(self, profiles, callback):
            options = [discord.SelectOption(label=name, description=stil[:80]) for name, stil in profiles.items()]
            super().__init__(placeholder="Profil wählen…", min_values=1, max_values=1, options=options)
            self._callback = callback

        async def callback(self, interaction):
            await self._callback(interaction, self.values[0])

    class EndSessionView(discord.ui.View):
        def __init__(self, send_log_cb):
            super().__init__(timeout=None)
            self.send_log_cb = send_log_cb

        @discord.ui.button(label="Session beenden & Verlauf senden", style=discord.ButtonStyle.red, emoji="🛑")
        async def end_btn(self, interaction: Interaction, button: discord.ui.Button):
            await self.send_log_cb(interaction)

    # ==== Slash Commands ====

    @app_commands.command(
        name="translatorpost",
        description="Postet das Übersetzungsmenü für User (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorpost(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        profiles = await self.get_profiles()
        if not profiles:
            return await utils.send_error(interaction, "Es gibt keine Profile. Füge erst eines mit /translatoraddprofile hinzu.")
        embed = discord.Embed(
            title="🌐 Übersetzungs-Menu",
            description="Wähle ein Profil, um eine private Übersetzungs-Session zu starten.",
            color=discord.Color.blue()
        )
        view = discord.ui.View()
        view.add_item(self.ProfileDropdown(profiles, self.start_session_callback))
        msg = await interaction.channel.send(embed=embed, view=view)
        await self.set_menu_channel(interaction.channel.id)
        await utils.send_success(interaction, "Übersetzungsmenü wurde gepostet!")

    async def start_session_callback(self, interaction: Interaction, profile_name):
        profiles = await self.get_profiles()
        stil = profiles[profile_name]
        guild = interaction.guild
        user = interaction.user

        # Kategorie holen
        cat = await self.get_category(guild)
        if not cat:
            return await utils.send_error(interaction, "Kategorie für Sessions nicht gesetzt. Bitte Admin fragen.")
        # Existierende Session löschen
        for c in cat.text_channels:
            if c.name == f"translat-{profile_name.lower()}-{user.name.lower()}":
                try:
                    await c.delete()
                except Exception:
                    pass
        # Channel erstellen
        name = f"translat-{profile_name.lower()}-{user.name.lower()}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        channel = await guild.create_text_channel(
            name=name,
            category=cat,
            overwrites=overwrites,
            topic=f"Übersetzungs-Session für {user.display_name} ({profile_name})"
        )
        self.active_sessions[user.id] = channel.id
        embed = discord.Embed(
            title=f"Session gestartet ({profile_name})",
            description="Schreibe eine Nachricht, um sie zu übersetzen.\n"
                        "Mit dem Button unten kannst du die Session beenden & den Verlauf senden lassen.",
            color=discord.Color.blue()
        )
        view = self.EndSessionView(lambda i: self.end_session(i, channel, user, profile_name))
        await channel.send(f"{user.mention}", embed=embed, view=view)
        await interaction.response.send_message(
            f"Deine Session ist bereit: {channel.mention}", ephemeral=True
        )

    async def end_session(self, interaction, channel, user, profile_name):
        # Verlauf posten und Channel löschen
        log = await self.get_log()
        userlog = log.get(str(user.id), {}).get(profile_name, [])
        log_channel = await self.get_log_channel(channel.guild)
        if log_channel and userlog:
            embed = discord.Embed(
                title=f"Übersetzungs-Session – {user.display_name} ({profile_name})",
                color=discord.Color.green(),
                description="Hier die letzten Übersetzungen dieser Session (max. 10):"
            )
            for entry in userlog[-10:]:
                embed.add_field(
                    name=entry["zeit"],
                    value=f"**Eingabe:** {entry['original']}\n**Übersetzung:** {entry['translated']}",
                    inline=False
                )
            await log_channel.send(embed=embed)
        await utils.send_ephemeral(interaction, "Session beendet & Verlauf gesendet!")
        try:
            await channel.delete()
        except Exception:
            pass

    @app_commands.command(
        name="translatoraddprofile",
        description="Fügt ein neues Übersetzerprofil hinzu (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatoraddprofile(self, interaction: Interaction, name: str, stil: str):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        profiles = await self.get_profiles()
        profiles[name] = stil
        await self.save_profiles(profiles)
        await utils.send_success(interaction, f"Profil **{name}** hinzugefügt.")

    @app_commands.command(
        name="translatordeleteprofile",
        description="Löscht ein Übersetzerprofil (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatordeleteprofile(self, interaction: Interaction, name: str):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        profiles = await self.get_profiles()
        if name not in profiles:
            return await utils.send_error(interaction, f"Profil **{name}** existiert nicht.")
        del profiles[name]
        await self.save_profiles(profiles)
        await utils.send_success(interaction, f"Profil **{name}** entfernt.")

    @app_commands.command(
        name="translatorlog",
        description="Setzt den Logchannel für Übersetzungsverläufe (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorlog(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.set_log_channel(channel.id)
        await utils.send_success(interaction, f"Logchannel für Übersetzungen gesetzt: {channel.mention}")

    @app_commands.command(
        name="translatorsetcategorie",
        description="Setzt die Kategorie für Übersetzungs-Sessions (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorsetcategorie(self, interaction: Interaction, category: discord.CategoryChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.set_category(category.id)
        await utils.send_success(interaction, f"Kategorie für Sessions gesetzt: {category.name}")

    @app_commands.command(
        name="translatorprompt",
        description="Fügt eine Zusatzregel (Prompt) hinzu (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorprompt(self, interaction: Interaction, text: str):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.add_prompt(text)
        await utils.send_success(interaction, f"Prompt hinzugefügt: {text}")

    @app_commands.command(
        name="translatorpromptdelete",
        description="Entfernt eine Zusatzregel anhand der Nummer (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorpromptdelete(self, interaction: Interaction, nummer: int):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        prompts = await self.get_prompts()
        if not prompts or not (1 <= nummer <= len(prompts)):
            return await utils.send_error(interaction, f"Ungültige Nummer. Es gibt aktuell {len(prompts)} Prompts.")
        text = prompts[nummer-1]
        await self.remove_prompt(nummer-1)
        await utils.send_success(interaction, f"Prompt entfernt: {text}")

    @app_commands.command(
        name="translatorpromptview",
        description="Zeigt alle aktiven Prompt-Regeln für Übersetzungen (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def translatorpromptview(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        prompts = await self.get_prompts()
        if not prompts:
            return await utils.send_ephemeral(
                interaction, text="Es sind aktuell **keine Zusatzregeln** hinterlegt.", emoji="ℹ️", color=discord.Color.light_grey()
            )
        desc = "\n".join([f"**{i+1}.** {p}" for i, p in enumerate(prompts)])
        embed = discord.Embed(
            title="Aktive Zusatzregeln / Prompts",
            description=desc,
            color=discord.Color.blurple()
        )
        await utils.send_ephemeral(interaction, embed=embed)

    # ==== Message Listener ====
    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if DM or not in Session
        if message.author.bot or not message.guild:
            return
        user = message.author
        if user.id not in self.active_sessions:
            return
        channel = message.guild.get_channel(self.active_sessions[user.id])
        if not channel or channel.id != message.channel.id:
            return

        # Fetch session details
        profile_name = None
        if channel.name.startswith("translat-"):
            try:
                profile_name = channel.name.split("-")[1]
            except IndexError:
                return
        if not profile_name:
            return

        profiles = await self.get_profiles()
        stil = profiles.get(profile_name)
        if not stil:
            return
        prompts = await self.get_prompts()
        prompt = " ".join(prompts)

        # Call translation (dummy)
        try:
            translated = await translate_text(message.content, stil, prompt)
        except Exception:
            translated = "*Fehler bei Übersetzung*"

        # Log this
        log = await self.get_log()
        userlog = log.setdefault(str(user.id), {}).setdefault(profile_name, [])
        userlog.append({
            "zeit": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "original": message.content,
            "translated": translated
        })
        await self.save_log(log)

        # Respond as embed
        embed = discord.Embed(
            title=f"Übersetzung ({profile_name})",
            description=f"**Original:**\n{message.content}\n\n**Übersetzung:**\n{translated}",
            color=discord.Color.green()
        )
        await channel.send(f"{user.mention}", embed=embed)

    # ===== Menu-Refresh für Setupbot =====
    async def reload_menu(self, channel_id):
        """Für setupbot.py: postet das Profil-Dropdown neu."""
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(channel_id)
        profiles = await self.get_profiles()
        if channel and profiles:
            embed = discord.Embed(
                title="🌐 Übersetzungs-Menu",
                description="Wähle ein Profil, um eine private Übersetzungs-Session zu starten.",
                color=discord.Color.blue()
            )
            view = discord.ui.View()
            view.add_item(self.ProfileDropdown(profiles, self.start_session_callback))
            await channel.send(embed=embed, view=view)

# ==== Cog Setup ====
async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
