import os
import logging
import datetime
import discord
from discord.ext import commands
from discord import app_commands, Interaction, Member, Role, TextChannel, Embed
from utils import is_admin, has_any_role, load_json, save_json
from permissions import has_permission_for

GUILD_ID = int(os.environ.get("GUILD_ID"))

STRIKE_DATA = "persistent_data/strike_data.json"
STRIKE_ROLES = "persistent_data/strike_roles.json"
STRIKE_AUTOROLE = "persistent_data/strike_autorole.json"
STRIKE_LIST = "persistent_data/strike_list.json"

def _load_data():
    return load_json(STRIKE_DATA, {})

def _save_data(data):
    save_json(STRIKE_DATA, data)

def _load_roles():
    return load_json(STRIKE_ROLES, [])

def _save_roles(roles):
    save_json(STRIKE_ROLES, roles)

def _load_autorole():
    return load_json(STRIKE_AUTOROLE, None)

def _save_autorole(role_id):
    save_json(STRIKE_AUTOROLE, role_id)

def _load_list():
    return load_json(STRIKE_LIST, None)

def _save_list(channel_id):
    save_json(STRIKE_LIST, channel_id)

def is_strike_berechtigt(user):
    if is_admin(user):
        return True
    strike_roles = _load_roles()
    return has_any_role(user, strike_roles)

def get_strike_count(user_id):
    data = _load_data()
    return len(data.get(str(user_id), []))

def update_strike_list(bot):
    """Aktualisiert die Übersichtsliste aller User mit Strikes."""
    channel_id = _load_list()
    if not channel_id:
        return
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    data = _load_data()
    # Lösche alte Bot-Messages im Log-Channel
    async def clear_and_post():
        async for msg in channel.history(limit=30):
            if msg.author == bot.user and "Aktive Strikes" in (msg.embeds[0].title if msg.embeds else ""):
                try:
                    await msg.delete()
                except Exception:
                    pass
        # Jetzt neues Embed posten
        embed = Embed(
            title="🛑 Aktive Strikes",
            description="Hier siehst du alle User mit mindestens 1 aktivem Strike.",
            color=0xe74c3c
        )
        found = False
        for uid, strikes in data.items():
            if strikes:
                member = guild.get_member(int(uid))
                if member:
                    found = True
                    desc = "\n".join([
                        f"- {s['reason']} (`{s['date']}`)" + (f" [Bild]({s['image']})" if s['image'] else "")
                        for s in strikes
                    ])
                    embed.add_field(
                        name=f"{member.display_name} ({len(strikes)}x)",
                        value=desc[:1000] or "*Keine Details*",
                        inline=False
                    )
        if not found:
            embed.description = "Es sind derzeit keine Strikes vergeben."
        await channel.send(embed=embed)
    # Muss als Task aufgerufen werden, weil Cogs keine awaitbaren normalen Funktionen zulassen
    bot.loop.create_task(clear_and_post())

class StrikeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==== Slash Commands ====

    @app_commands.command(
        name="strikemaininfo",
        description="Postet eine Anleitung zur Strikevergabe"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikemaininfo")
    async def strikemaininfo(self, interaction: discord.Interaction):
        if not is_strike_berechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        embed = Embed(
            title="🛑 Strike System – Vergabe von Strikes",
            description=(
                "Mit `/strikegive` kannst du direkt einen Nutzer verwarnen.\n"
                "Nach dem Auswählen öffnet sich ein Fenster für Grund und (optional) Bild-Link.\n"
                "**Nur Teamleads/Admins/Strike-Rollen** können Strikes vergeben.\n\n"
                "```/strikegive [@Nutzer]```\n"
                "_Befehl kopieren und im Commandfeld einfügen!_\n"
                "- Jeder Nutzer kann mit `/strikeview` seine eigenen Strikes sehen (privat)."
            ),
            color=0xe74c3c
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Anleitung gepostet.", ephemeral=True)

    @app_commands.command(
        name="strikegive",
        description="Gibt einem User einen Strike (nur für berechtigte Rollen)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikegive")
    async def strikegive(self, interaction: discord.Interaction, user):
        if not is_strike_berechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung für Strikevergabe.", ephemeral=True)
            return

        # Modal für Grund/Bild-Link
        class StrikeModal(commands.ui.Modal, title="Strike vergeben"):
            reason = commands.ui.TextInput(label="Grund", style=2, min_length=5, max_length=300)
            image = commands.ui.TextInput(label="Bild-Link (optional)", required=False, max_length=200)

            async def on_submit(self, modal_interaction: discord.Interaction):
                # Speichern des Strikes
                data = _load_data()
                uid = str(user.id)
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                entry = {
                    "reason": self.reason.value,
                    "image": self.image.value.strip() if self.image.value else "",
                    "date": now,
                    "author": interaction.user.id
                }
                if uid not in data:
                    data[uid] = []
                data[uid].append(entry)
                _save_data(data)
                # DM/ephemeral Feedback an User
                strike_count = len(data[uid])
                try:
                    await user.send(
                        f"Du hast einen neuen Strike erhalten!\n"
                        f"**Grund:** {entry['reason']}\n"
                        f"{f'Bild: {entry['image']}' if entry['image'] else ''}\n"
                        f"Anzahl deiner Strikes: {strike_count}"
                    )
                except Exception:
                    pass
                await modal_interaction.response.send_message(
                    f"✅ Strike vergeben an {user.mention} (insgesamt {strike_count}).",
                    ephemeral=True
                )

                # Automatische Rolle zuweisen bei 3 Strikes
                autorole_id = _load_autorole()
                if autorole_id and strike_count == 3:
                    autorole = user.guild.get_role(autorole_id)
                    if autorole:
                        try:
                            await user.add_roles(autorole)
                        except Exception:
                            pass
                # Logging in Übersichtskanal
                update_strike_list(self.bot)

        await interaction.response.send_modal(StrikeModal())

    @app_commands.command(
        name="strikeremove",
        description="Entfernt den letzten Strike eines Users"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeremove")
    async def strikeremove(self, interaction: discord.Interaction, user):
        if not is_strike_berechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        data = _load_data()
        uid = str(user.id)
        if uid in data and data[uid]:
            removed = data[uid].pop()
            _save_data(data)
            await interaction.response.send_message(
                f"✅ Letzter Strike von {user.mention} entfernt ({removed['reason']}).", ephemeral=True
            )
            update_strike_list(self.bot)
        else:
            await interaction.response.send_message("ℹ️ Dieser User hat keine Strikes.", ephemeral=True)

    @app_commands.command(
        name="strikedelete",
        description="Entfernt alle Strikes eines Users"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikedelete")
    async def strikedelete(self, interaction: discord.Interaction, user):
        if not is_strike_berechtigt(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        data = _load_data()
        uid = str(user.id)
        if uid in data and data[uid]:
            count = len(data[uid])
            data[uid] = []
            _save_data(data)
            await interaction.response.send_message(
                f"✅ Alle ({count}) Strikes von {user.mention} entfernt.", ephemeral=True
            )
            update_strike_list(self.bot)
        else:
            await interaction.response.send_message("ℹ️ Dieser User hat keine Strikes.", ephemeral=True)

    @app_commands.command(
        name="strikeview",
        description="Zeigt dir deine eigenen Strikes (privat)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeview")
    async def strikeview(self, interaction: discord.Interaction):
        data = _load_data()
        uid = str(interaction.user.id)
        strikes = data.get(uid, [])
        if not strikes:
            msg = "Du hast aktuell **keine Strikes**. Bleib weiter so!"
        else:
            msg = f"Du hast aktuell **{len(strikes)} Strike(s)**:\n"
            for s in strikes:
                msg += f"- `{s['date']}`: {s['reason']}\n"
                if s.get("image"):
                    msg += f"  [Bild]({s['image']})\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="strikelist",
        description="Setzt den Channel für die Strike-Übersicht"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikelist")
    async def strikelist(self, interaction: discord.Interaction, channel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins dürfen das setzen.", ephemeral=True)
            return
        _save_list(channel.id)
        update_strike_list(self.bot)
        await interaction.response.send_message(f"✅ Strike-Übersicht wird jetzt in {channel.mention} gepostet.", ephemeral=True)

    @app_commands.command(
        name="strikerole",
        description="Fügt eine Rolle zu den Strike-Berechtigten hinzu"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikerole")
    async def strikerole(self, interaction: discord.Interaction, role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        roles = set(_load_roles())
        roles.add(role.id)
        _save_roles(list(roles))
        await interaction.response.send_message(f"✅ {role.mention} kann jetzt Strikes vergeben.", ephemeral=True)

    @app_commands.command(
        name="strikerole_remove",
        description="Entfernt eine Rolle aus den Strike-Berechtigten"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikerole_remove")
    async def strikerole_remove(self, interaction: discord.Interaction, role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        roles = set(_load_roles())
        if role.id in roles:
            roles.remove(role.id)
            _save_roles(list(roles))
            await interaction.response.send_message(f"✅ {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Diese Rolle war nicht berechtigt.", ephemeral=True)

    @app_commands.command(
        name="strikeaddrole",
        description="Setzt die Rolle, die bei 3 Strikes automatisch vergeben wird"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeaddrole")
    async def strikeaddrole(self, interaction: discord.Interaction, role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_autorole(role.id)
        await interaction.response.send_message(f"✅ Beim 3. Strike wird {role.mention} automatisch vergeben.", ephemeral=True)

    @app_commands.command(
        name="strikeaddrole_remove",
        description="Entfernt die Auto-Rolle für 3 Strikes"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeaddrole_remove")
    async def strikeaddrole_remove(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        _save_autorole(None)
        await interaction.response.send_message("✅ Auto-Rolle entfernt.", ephemeral=True)

# === Setup-Funktion für Extension-Loader ===

async def setup(bot):
    await bot.add_cog(StrikeCog(bot))
