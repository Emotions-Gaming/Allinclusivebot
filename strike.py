import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
STRIKE_DATA_PATH = os.path.join("persistent_data", "strike_data.json")
STRIKE_ROLES_PATH = os.path.join("persistent_data", "strike_roles.json")
STRIKE_AUTOROLE_PATH = os.path.join("persistent_data", "strike_autorole.json")
STRIKE_LIST_PATH = os.path.join("persistent_data", "strike_list.json")
STRIKE_LOG_PATH = os.path.join("persistent_data", "strike_log_channel.json")

class StrikeModal(discord.ui.Modal, title="Strike vergeben"):
    grund = discord.ui.TextInput(label="Grund für den Strike", style=discord.TextStyle.long, required=True)
    bild = discord.ui.TextInput(label="Bild-Link (optional)", style=discord.TextStyle.short, required=False)
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    async def on_submit(self, interaction: Interaction):
        await self._callback(interaction, self.grund.value, self.bild.value)

# ==== Buttons/Views für Strike-Liste ====
class StrikeListView(discord.ui.View):
    def __init__(self, strikes: dict, cog):
        super().__init__(timeout=None)
        self.strikes = strikes
        self.cog = cog
        for uid, entries in strikes.items():
            user_id = int(uid)
            self.add_item(StrikeDetailButton(user_id, entries))

class StrikeDetailButton(discord.ui.Button):
    def __init__(self, user_id, entries):
        label = f"Details zu {len(entries)} Strike{'s' if len(entries) != 1 else ''}"
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.user_id = user_id
        self.entries = entries

    async def callback(self, interaction: Interaction):
        user = interaction.guild.get_member(self.user_id)
        strikes = self.entries
        if not strikes:
            text = "Keine Strikes vorhanden!"
        else:
            desc = "\n\n".join([
                f"**{i+1}.** {s['grund']}\n(Bild: {s['bild'] or '-'})\nZeit: {s['zeit']}"
                for i, s in enumerate(strikes)
            ])
            text = f"**Strikes für {user.mention if user else self.user_id}:**\n\n{desc}"
        await utils.send_ephemeral(interaction, text=text, emoji="⚠️", color=discord.Color.orange())

# ==== Button für Admin-Log Details ====
class StrikeLogDetailButton(discord.ui.Button):
    def __init__(self, idx, entry):
        label = f"Details"
        super().__init__(label=label, style=discord.ButtonStyle.gray, custom_id=f"logdetail_{idx}")
        self.entry = entry

    async def callback(self, interaction: Interaction):
        e = self.entry
        text = (
            f"**Strike vergeben von:** {e['from_user']}\n"
            f"**An:** {e['to_user']}\n"
            f"**Grund:** {e['grund']}\n"
            f"**Bild:** {e['bild'] or '-'}\n"
            f"**Zeit:** {e['zeit']}"
        )
        await utils.send_ephemeral(interaction, text=text, emoji="🕵️", color=discord.Color.purple())

class StrikeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==== Helper ====
    async def get_strike_data(self):
        return await utils.load_json(STRIKE_DATA_PATH, {})

    async def save_strike_data(self, data):
        await utils.save_json(STRIKE_DATA_PATH, data)

    async def get_strike_roles(self):
        return await utils.load_json(STRIKE_ROLES_PATH, [])

    async def save_strike_roles(self, data):
        await utils.save_json(STRIKE_ROLES_PATH, data)

    async def get_strike_autorole(self):
        return await utils.load_json(STRIKE_AUTOROLE_PATH, None)

    async def save_strike_autorole(self, data):
        await utils.save_json(STRIKE_AUTOROLE_PATH, data)

    async def get_strike_list_channel(self, guild):
        cid = await utils.load_json(STRIKE_LIST_PATH, None)
        return guild.get_channel(cid) if cid else None

    async def get_strike_log_channel(self, guild):
        cid = await utils.load_json(STRIKE_LOG_PATH, None)
        return guild.get_channel(cid) if cid else None

    async def is_strike_mod(self, member: discord.Member):
        if utils.is_admin(member):
            return True
        roles = await self.get_strike_roles()
        return utils.has_any_role(member, roles)

    async def post_strike_log(self, guild):
        """Komplett aktualisieren: Kompakte Übersicht aller User mit Strikes."""
        data = await self.get_strike_data()
        ch = await self.get_strike_list_channel(guild)
        if not ch:
            return
        await ch.purge(limit=100, check=lambda m: m.author == guild.me)
        if not data:
            embed = discord.Embed(
                title="🛡️ Strikeliste",
                description="**Derzeit keine Strikes! 🎉**",
                color=discord.Color.green()
            )
            await ch.send(embed=embed)
            return

        # Kompakt + Buttons
        lines = []
        strikes_for_buttons = {}
        for uid, strikes in data.items():
            user = guild.get_member(int(uid))
            strikes_for_buttons[uid] = strikes
            lines.append(f"{user.mention if user else uid} = Strikes **{len(strikes)}**")
        embed = discord.Embed(
            title="🛡️ Strikeliste",
            description="\n".join(lines),
            color=discord.Color.red()
        )
        view = StrikeListView(strikes_for_buttons, self)
        await ch.send(embed=embed, view=view)

    async def add_strike(self, user: discord.Member, grund, bild, by_user=None):
        data = await self.get_strike_data()
        s = {
            "grund": grund,
            "bild": bild,
            "zeit": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "von": str(by_user.id) if by_user else None
        }
        data.setdefault(str(user.id), []).append(s)
        await self.save_strike_data(data)

    async def remove_last_strike(self, user: discord.Member):
        data = await self.get_strike_data()
        uid = str(user.id)
        if uid in data and data[uid]:
            data[uid].pop()
            if not data[uid]:
                del data[uid]
            await self.save_strike_data(data)

    async def delete_all_strikes(self, user: discord.Member):
        data = await self.get_strike_data()
        uid = str(user.id)
        if uid in data:
            del data[uid]
            await self.save_strike_data(data)

    async def check_autorole(self, user: discord.Member, guild):
        data = await self.get_strike_data()
        autorole = await self.get_strike_autorole()
        strikes = data.get(str(user.id), [])
        if autorole and len(strikes) == 3:
            role = guild.get_role(autorole)
            if role and role not in user.roles:
                await user.add_roles(role, reason="3 Strikes erreicht (Auto-Role)")

    # ========== Strike Log Handling ==========
    async def save_strike_log(self, guild, by_user, user, grund, bild):
        # Log-Channel holen
        log_channel = await self.get_strike_log_channel(guild)
        if not log_channel:
            return
        log_entry = {
            "from_user": by_user.mention if by_user else "-",
            "to_user": user.mention if user else "-",
            "grund": grund,
            "bild": bild,
            "zeit": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        # Button für Details (pro Log-Entry)
        view = discord.ui.View()
        view.add_item(StrikeLogDetailButton(0, log_entry))
        embed = discord.Embed(
            title="📋 Strike vergeben",
            description=(
                f"{by_user.mention if by_user else '-'} hat {user.mention if user else '-'} einen Strike gegeben!\n"
                f"**Grund:** {grund}\n"
                f"**Bild:** {bild or '-'}\n"
                f"**Zeit:** {log_entry['zeit']}"
            ),
            color=discord.Color.orange()
        )
        await log_channel.send(embed=embed, view=view)

    # ==== Slash Commands ====

    @app_commands.command(
        name="strikemaininfo",
        description="Zeigt die Info & Anleitung für das Strike-System (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikemaininfo(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        embed = discord.Embed(
            title="🛑 Strike System – Vergabe von Strikes",
            description=(
                "Vergib Strikes jetzt mit `/strikegive` direkt an einen Nutzer!\n"
                "Nach der Auswahl öffnet sich ein Fenster für Grund und Bildlink.\n"
                "**Nur Teamleads/Admins** können Strikes vergeben.\n"
                "Beim dritten Strike kann automatisch eine spezielle Rolle vergeben werden.\n"
                "Strike-Log und Übersicht findest du im konfigurierten Channel."
            ),
            color=discord.Color.red()
        )
        embed.add_field(
            name="Kopiere diesen Befehl:",
            value="```/strikegive```",
            inline=False
        )
        await interaction.channel.send(embed=embed)
        await utils.send_success(interaction, "Strike-System-Anleitung gepostet.")

    @app_commands.command(
        name="strikegive",
        description="Vergibt einen Strike an einen Nutzer (nur Teamleads/Admins/Sonderrollen)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikegive(self, interaction: Interaction, user: discord.Member):
        if not await self.is_strike_mod(interaction.user):
            return await utils.send_permission_denied(interaction)

        async def after_modal(modal_interaction, grund, bild):
            await self.add_strike(user, grund, bild, by_user=interaction.user)
            await self.check_autorole(user, interaction.guild)
            await utils.send_success(modal_interaction, f"{user.mention} hat einen Strike bekommen!")
            # DM an User (unterschiedlich je nach Anzahl!)
            try:
                data = await self.get_strike_data()
                anz = len(data.get(str(user.id), []))
                if anz == 1:
                    msg = (
                        f"**Du hast einen Strike bekommen!**\n\n"
                        f"**Grund:** {grund}\n"
                        f"**Bild:** {bild or '-'}\n\n"
                        f"Bitte melde dich bei einem **Operation Lead**!\n"
                        f"(Strikes: {anz}/3)"
                    )
                elif anz == 2:
                    msg = (
                        f"**Du hast jetzt schon deinen 2ten Strike bekommen!**\n\n"
                        f"**Grund:** {grund}\n"
                        f"**Bild:** {bild or '-'}\n\n"
                        f"Schau dir die Regeln nochmal an. Melde dich bei einem **Teamlead**, um darüber zu sprechen!\n"
                        f"(Strikes: {anz}/3)"
                    )
                elif anz == 3:
                    msg = (
                        f"**Es ist soweit... du hast deinen 3ten Strike gesammelt...**\n\n"
                        f"**Grund:** {grund}\n"
                        f"**Bild:** {bild or '-'}\n\n"
                        f"Jetzt muss leider eine Bestrafung folgen. Bitte melde dich **schnellstmöglich bei einem TeamLead**!\n"
                        f"(Strikes: {anz}/3)"
                    )
                else:
                    msg = (
                        f"**Du hast einen weiteren Strike erhalten!**\n\n"
                        f"**Grund:** {grund}\n"
                        f"**Bild:** {bild or '-'}\n\n"
                        f"Bitte kläre die Lage mit einem Teamlead."
                    )
                await user.send(msg)
            except Exception:
                pass
            # Log/Übersicht updaten
            await self.post_strike_log(interaction.guild)
            await self.save_strike_log(interaction.guild, interaction.user, user, grund, bild)

        await interaction.response.send_modal(StrikeModal(after_modal))

    @app_commands.command(
        name="strikeview",
        description="Zeigt dir privat deine aktuellen Strikes an."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikeview(self, interaction: Interaction):
        data = await self.get_strike_data()
        strikes = data.get(str(interaction.user.id), [])
        if not strikes:
            return await utils.send_ephemeral(
                interaction, text="Du hast aktuell **keine** Strikes! 🎉", emoji="✅", color=discord.Color.green()
            )
        desc = "\n\n".join([
            f"**{i+1}.** {s['grund']} (Bild: {s['bild'] or '-'})\nZeit: {s['zeit']}" for i, s in enumerate(strikes)
        ])
        await utils.send_ephemeral(
            interaction, text=f"**Deine Strikes:**\n\n{desc}", emoji="⚠️", color=discord.Color.red()
        )

    @app_commands.command(
        name="strikelist",
        description="Setzt den Channel für die Strike-Übersicht & postet alle aktiven Strikes (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikelist(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await utils.save_json(STRIKE_LIST_PATH, channel.id)
        await self.post_strike_log(interaction.guild)
        await utils.send_success(interaction, f"Strike-Übersicht wurde in {channel.mention} aktualisiert.")

    @app_commands.command(
        name="strikeremove",
        description="Entfernt den letzten Strike eines Users (nur Teamleads/Admins/Sonderrollen)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikeremove(self, interaction: Interaction, user: discord.Member):
        if not await self.is_strike_mod(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.remove_last_strike(user)
        await utils.send_success(interaction, f"Letzter Strike für {user.mention} entfernt.")
        await self.post_strike_log(interaction.guild)

    @app_commands.command(
        name="strikedelete",
        description="Setzt alle Strikes eines Users zurück (nur Teamleads/Admins/Sonderrollen)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikedelete(self, interaction: Interaction, user: discord.Member):
        if not await self.is_strike_mod(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.delete_all_strikes(user)
        await utils.send_success(interaction, f"Alle Strikes für {user.mention} entfernt.")
        await self.post_strike_log(interaction.guild)

    @app_commands.command(
        name="strikerole",
        description="Fügt eine Rolle zu den Strike-Berechtigten hinzu (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikerole(self, interaction: Interaction, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        roles = await self.get_strike_roles()
        if role.id not in roles:
            roles.append(role.id)
            await self.save_strike_roles(roles)
        await utils.send_success(interaction, f"Rolle {role.mention} darf jetzt Strikes vergeben.")

    @app_commands.command(
        name="strikerole_remove",
        description="Entfernt eine Rolle von den Strike-Berechtigten (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikerole_remove(self, interaction: Interaction, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        roles = await self.get_strike_roles()
        if role.id in roles:
            roles.remove(role.id)
            await self.save_strike_roles(roles)
        await utils.send_success(interaction, f"Rolle {role.mention} entfernt.")

    @app_commands.command(
        name="strikeaddrole",
        description="Setzt die Auto-Role bei 3 Strikes (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikeaddrole(self, interaction: Interaction, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.save_strike_autorole(role.id)
        await utils.send_success(interaction, f"Auto-Role bei 3 Strikes ist jetzt {role.mention}.")

    @app_commands.command(
        name="strikeaddrole_remove",
        description="Entfernt die Auto-Role bei 3 Strikes (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikeaddrole_remove(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await self.save_strike_autorole(None)
        await utils.send_success(interaction, f"Auto-Role bei 3 Strikes entfernt.")

    # ====== Menu-Refresh für Setupbot ======
    async def reload_menu(self, channel_id):
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="🛑 Strike System – Vergabe von Strikes",
                description=(
                    "Vergib Strikes jetzt mit `/strikegive` direkt an einen Nutzer!\n"
                    "Nach der Auswahl öffnet sich ein Fenster für Grund und Bildlink.\n"
                    "**Nur Teamleads/Admins** können Strikes vergeben.\n"
                    "Beim dritten Strike kann automatisch eine spezielle Rolle vergeben werden.\n"
                    "Strike-Log und Übersicht findest du im konfigurierten Channel."
                ),
                color=discord.Color.red()
            )
            embed.add_field(
                name="Kopiere diesen Befehl:",
                value="```/strikegive```",
                inline=False
            )
            await channel.send(embed=embed)

    @app_commands.command(
        name="strikelog",
        description="Setzt den Channel für das Strike-Log (nur Admins)."
    )
    @app_commands.guilds(GUILD_ID)
    async def strikelog(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await utils.save_json(STRIKE_LOG_PATH, channel.id)
        await utils.send_success(interaction, f"Strike-Log-Channel gesetzt: {channel.mention}")

# ==== Cog Setup ====
async def setup(bot):
    await bot.add_cog(StrikeCog(bot))
