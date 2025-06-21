# strike.py

import os
import json
import datetime
import discord
from discord import app_commands
from discord.ext import commands

GUILD_ID = int(os.getenv("GUILD_ID") or "0")
DATA_DIR = "persistent_data"

STRIKE_FILE         = os.path.join(DATA_DIR, "strike_data.json")
STRIKE_LIST_FILE    = os.path.join(DATA_DIR, "strike_list.json")
STRIKE_ROLES_FILE   = os.path.join(DATA_DIR, "strike_roles.json")
STRIKE_AUTOROLE_FILE = os.path.join(DATA_DIR, "strike_autorole.json")

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class StrikeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, user):
        return user.guild_permissions.administrator or getattr(user, "id", None) == getattr(getattr(user, "guild", None), "owner_id", None)

    def has_strike_role(self, user):
        strike_roles = set(load_json(STRIKE_ROLES_FILE, {}).get("role_ids", []))
        return any(r.id in strike_roles for r in getattr(user, "roles", [])) or self.is_admin(user)

    def load_strikes(self):
        return load_json(STRIKE_FILE, {})

    def save_strikes(self, data):
        save_json(STRIKE_FILE, data)

    def load_strike_roles(self):
        return set(load_json(STRIKE_ROLES_FILE, {}).get("role_ids", []))

    def save_strike_roles(self, role_ids):
        save_json(STRIKE_ROLES_FILE, {"role_ids": list(role_ids)})

    def load_strike_list_cfg(self):
        return load_json(STRIKE_LIST_FILE, {})

    def save_strike_list_cfg(self, data):
        save_json(STRIKE_LIST_FILE, data)

    def load_autorole(self):
        return load_json(STRIKE_AUTOROLE_FILE, {}).get("role_id", None)

    def save_autorole(self, role_id):
        save_json(STRIKE_AUTOROLE_FILE, {"role_id": role_id})

    async def update_strike_list(self, guild):
        strike_list_cfg = self.load_strike_list_cfg()
        ch_id = strike_list_cfg.get("channel_id")
        if not ch_id:
            return
        ch = guild.get_channel(ch_id)
        if not ch:
            return
        strikes = self.load_strikes()
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
            async def btn_cb(inter, uid=uid, uname=uname):
                strikes = self.load_strikes()
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

    # Slash-Commands

    @app_commands.command(name="strikemaininfo", description="Strike-Info für Teamleads/Mods posten")
    async def strikemaininfo(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
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

    @app_commands.command(name="strikegive", description="Vergibt einen Strike an einen User")
    @app_commands.describe(user="User der einen Strike bekommt")
    async def strikegive(self, interaction: discord.Interaction, user: discord.Member):
        if not self.has_strike_role(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
        # MODAL
        class StrikeModal(discord.ui.Modal, title="Strike vergeben"):
            reason = discord.ui.TextInput(label="Grund für Strike", style=discord.TextStyle.long, required=True, max_length=256)
            image = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False, max_length=256)
            async def on_submit(self, modal_inter: discord.Interaction):
                strikes = self.load_strikes()
                entry = {
                    "reason": self.reason.value,
                    "image": self.image.value,
                    "by": interaction.user.display_name,
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds")
                }
                strikes.setdefault(str(user.id), []).append(entry)
                self.save_strikes(strikes)
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
                    auto_role_id = self.load_autorole()
                    if auto_role_id:
                        role = interaction.guild.get_role(auto_role_id)
                        if role:
                            await user.add_roles(role, reason="Automatisch zugewiesen nach 3 Strikes.")
                try:
                    await user.send(msg)
                except Exception:
                    pass
                await modal_inter.response.send_message(f"Strike für {user.mention} vergeben und DM gesendet! (Strike-Zahl: {strike_count})", ephemeral=True)
                await self.update_strike_list(interaction.guild)
        await interaction.response.send_modal(StrikeModal())

    @app_commands.command(name="strikelist", description="Setzt den Channel für die Strike-Übersicht")
    @app_commands.describe(channel="Channel für Strikes")
    async def strikelist(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.save_strike_list_cfg({"channel_id": channel.id})
        await interaction.response.send_message(f"Strike-Übersicht wird jetzt hier gepostet: {channel.mention}", ephemeral=True)
        await self.update_strike_list(interaction.guild)

    @app_commands.command(name="strikerole", description="Fügt eine Rolle zu den Strike-Berechtigten hinzu")
    @app_commands.describe(role="Discord Rolle")
    async def strikerole(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        strike_roles = self.load_strike_roles()
        strike_roles.add(role.id)
        self.save_strike_roles(strike_roles)
        await interaction.response.send_message(f"Rolle **{role.name}** ist jetzt Strike-Berechtigt.", ephemeral=True)

    @app_commands.command(name="strikerole_remove", description="Entfernt eine Rolle von den Strike-Berechtigten")
    @app_commands.describe(role="Discord Rolle")
    async def strikerole_remove(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        strike_roles = self.load_strike_roles()
        if role.id in strike_roles:
            strike_roles.remove(role.id)
            self.save_strike_roles(strike_roles)
            await interaction.response.send_message(f"Rolle **{role.name}** ist **nicht mehr** Strike-Berechtigt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle **{role.name}** war nicht Strike-Berechtigt.", ephemeral=True)

    @app_commands.command(name="strikeaddrole", description="Setzt die automatische Rolle beim 3. Strike")
    @app_commands.describe(role="Rolle für automatisches Vergeben beim 3. Strike")
    async def strikeaddrole(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.save_autorole(role.id)
        await interaction.response.send_message(f"Die Rolle {role.mention} wird beim 3. Strike automatisch vergeben.", ephemeral=True)

    @app_commands.command(name="strikeaddrole_remove", description="Entfernt die automatische Strike-Rolle")
    async def strikeaddrole_remove(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.save_autorole(None)
        await interaction.response.send_message("Die automatische Strike-Rolle wurde entfernt.", ephemeral=True)

    @app_commands.command(name="strikedelete", description="Alle Strikes von User entfernen")
    @app_commands.describe(user="User zum Löschen")
    async def strikedelete(self, interaction: discord.Interaction, user: discord.Member):
        if not self.has_strike_role(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
        strikes = self.load_strikes()
        if str(user.id) in strikes:
            strikes.pop(str(user.id))
            self.save_strikes(strikes)
            await self.update_strike_list(interaction.guild)
            await interaction.response.send_message(f"Alle Strikes für {user.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

    @app_commands.command(name="strikeremove", description="Entfernt einen Strike")
    @app_commands.describe(user="User für Strike-Abbau")
    async def strikeremove(self, interaction: discord.Interaction, user: discord.Member):
        if not self.has_strike_role(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung!", ephemeral=True)
        strikes = self.load_strikes()
        entrys = strikes.get(str(user.id), [])
        if entrys:
            entrys.pop()
            if not entrys:
                strikes.pop(str(user.id))
            else:
                strikes[str(user.id)] = entrys
            self.save_strikes(strikes)
            await self.update_strike_list(interaction.guild)
            await interaction.response.send_message(f"Ein Strike für {user.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

    @app_commands.command(name="strikeview", description="Zeigt dir, wie viele Strikes du hast (privat)")
    async def strikeview(self, interaction: discord.Interaction):
        strikes = self.load_strikes()
        user_id = str(interaction.user.id)
        count = len(strikes.get(user_id, []))
        msg = (
            f"👮‍♂️ **Strike-Übersicht** für {interaction.user.mention}:\n\n"
            f"Du hast aktuell **{count} Strike{'s' if count!=1 else ''}**.\n"
            f"{'Wenn du mehr wissen willst, schreibe dem Bot einfach eine DM.' if count else 'Du hast aktuell keine Strikes.'}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

# --- Cog Setup ---
async def setup(bot):
    await bot.add_cog(StrikeCog(bot))
