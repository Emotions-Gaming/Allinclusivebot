import os
import discord
from discord.ext import commands
from discord import app_commands, Member, TextChannel, Role, Embed
from utils import is_admin, load_json, save_json, mention_roles
from permissions import has_permission_for
# WICHTIG: KEIN from discord import Interaction !!

GUILD_ID = int(os.environ.get("GUILD_ID"))
STRIKE_DATA = "persistent_data/strike_data.json"
STRIKE_ROLES = "persistent_data/strike_roles.json"
STRIKE_AUTOROLE = "persistent_data/strike_autorole.json"

def _load_strikes():
    return load_json(STRIKE_DATA, {})

def _save_strikes(data):
    save_json(STRIKE_DATA, data)

def _load_roles():
    return load_json(STRIKE_ROLES, [])

def _save_roles(data):
    save_json(STRIKE_ROLES, data)

def _load_autorole():
    return load_json(STRIKE_AUTOROLE, {"enabled": False, "count": 3, "role_id": None})

def _save_autorole(cfg):
    save_json(STRIKE_AUTOROLE, cfg)

def get_log_channel(bot):
    log_cfg = load_json("persistent_data/strike_log_channel.json", {})
    gid = int(os.environ.get("GUILD_ID"))
    return bot.get_guild(gid).get_channel(log_cfg.get("log_channel_id")) if log_cfg.get("log_channel_id") else None

def strike_count(user_id):
    data = _load_strikes()
    return len(data.get(str(user_id), []))

class StrikeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def reload_menu(self):
        cfg = load_json("persistent_data/strike_panel.json", {})
        main_channel_id = cfg.get("main_channel_id")
        if not main_channel_id:
            return
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(main_channel_id)
        if not channel:
            return
        try:
            if cfg.get("main_message_id"):
                msg = await channel.fetch_message(cfg["main_message_id"])
                await msg.delete()
        except Exception:
            pass

        embed = Embed(
            title="⚠️ Strike-Panel",
            description=(
                "Strikes dienen als Verwarnung für Regelverstöße.\n"
                "**Strike vergeben:** `/strikeadd [@User] [Grund]`\n"
                "**Strike entfernen:** `/strikeremove [@User]`\n"
                "**Alle Strikes anzeigen:** `/strikeview [@User]`\n"
                "**Autorole:** Wird automatisch bei Überschreitung vergeben (falls aktiviert)."
            ),
            color=0xe17055
        )
        data = _load_strikes()
        top = sorted([(uid, len(items)) for uid, items in data.items()], key=lambda x: x[1], reverse=True)
        if top:
            desc = "\n".join([f"<@{uid}>: {cnt} Strikes" for uid, cnt in top[:10]])
            embed.add_field(name="Top Strikes", value=desc, inline=False)
        view = StrikePanelView(self)
        msg = await channel.send(embed=embed, view=view)
        cfg["main_message_id"] = msg.id
        save_json("persistent_data/strike_panel.json", cfg)

    @app_commands.command(
        name="strikemain",
        description="Postet das Strike-Hauptpanel (nur Admin)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikemain")
    async def strikemain(self, interaction: discord.Interaction):   # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = load_json("persistent_data/strike_panel.json", {})
        cfg["main_channel_id"] = interaction.channel.id
        save_json("persistent_data/strike_panel.json", cfg)
        await self.reload_menu()
        await interaction.response.send_message("✅ Strike-Panel gepostet!", ephemeral=True)

    @app_commands.command(
        name="strikeadd",
        description="Gibt einem User einen Strike (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeadd")
    async def strikeadd(self, interaction: discord.Interaction, user: Member, grund: str):   # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
            return
        data = _load_strikes()
        data.setdefault(str(user.id), []).append({
            "by": interaction.user.id,
            "grund": grund,
            "ts": discord.utils.utcnow().isoformat()
        })
        _save_strikes(data)
        await self.check_autorole(user)
        log_channel = get_log_channel(self.bot)
        embed = Embed(
            title="⚠️ Strike vergeben",
            description=f"{user.mention} hat einen Strike erhalten.\n**Grund:** {grund}\nVergeben von: {interaction.user.mention}",
            color=0xe17055
        )
        if log_channel:
            await log_channel.send(embed=embed)
        await self.reload_menu()
        await interaction.response.send_message("✅ Strike vergeben!", ephemeral=True)

    @app_commands.command(
        name="strikeremove",
        description="Entfernt einen Strike (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeremove")
    async def strikeremove(self, interaction: discord.Interaction, user: Member):  # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
            return
        data = _load_strikes()
        if str(user.id) not in data or not data[str(user.id)]:
            await interaction.response.send_message("ℹ️ Keine Strikes vorhanden.", ephemeral=True)
            return
        data[str(user.id)].pop()
        if not data[str(user.id)]:
            del data[str(user.id)]
        _save_strikes(data)
        await self.check_autorole(user)
        log_channel = get_log_channel(self.bot)
        embed = Embed(
            title="✅ Strike entfernt",
            description=f"Ein Strike wurde von {user.mention} entfernt. Von: {interaction.user.mention}",
            color=0x00b894
        )
        if log_channel:
            await log_channel.send(embed=embed)
        await self.reload_menu()
        await interaction.response.send_message("✅ Strike entfernt!", ephemeral=True)

    @app_commands.command(
        name="strikeview",
        description="Zeigt die Strikes eines Nutzers an"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeview")
    async def strikeview(self, interaction: discord.Interaction, user: Member):  # HIER geändert!
        data = _load_strikes()
        strikes = data.get(str(user.id), [])
        if not strikes:
            await interaction.response.send_message("ℹ️ Dieser User hat keine Strikes.", ephemeral=True)
            return
        embed = Embed(
            title=f"⚠️ Strikes von {user.display_name}",
            color=0xe17055
        )
        for i, s in enumerate(reversed(strikes), 1):
            by = f"<@{s['by']}>"
            ts = s["ts"]
            embed.add_field(
                name=f"Strike {len(strikes) - i + 1}",
                value=f"Von: {by}\nGrund: {s['grund']}\nZeit: {ts}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="strikeautorole",
        description="Setzt automatische Rolle bei X Strikes (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeautorole")
    async def strikeautorole(self, interaction: discord.Interaction, count: int, role: Role):  # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
            return
        cfg = _load_autorole()
        cfg["enabled"] = True
        cfg["count"] = count
        cfg["role_id"] = role.id
        _save_autorole(cfg)
        await interaction.response.send_message(
            f"✅ Autorole wird ab {count} Strikes automatisch vergeben: {role.mention}", ephemeral=True
        )

    @app_commands.command(
        name="strikeautorole_disable",
        description="Deaktiviert automatische Strike-Rolle (nur Admins)"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("strikeautorole_disable")
    async def strikeautorole_disable(self, interaction: discord.Interaction):  # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
            return
        cfg = _load_autorole()
        cfg["enabled"] = False
        _save_autorole(cfg)
        await interaction.response.send_message("✅ Autorole deaktiviert.", ephemeral=True)

    async def check_autorole(self, user: Member):
        cfg = _load_autorole()
        if not cfg["enabled"] or not cfg["role_id"]:
            return
        guild = user.guild
        role = guild.get_role(cfg["role_id"])
        count = strike_count(user.id)
        if count >= cfg["count"]:
            if role and role not in user.roles:
                try:
                    await user.add_roles(role, reason=f"{count} Strikes erreicht")
                except Exception:
                    pass
        else:
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason=f"Strikes unter Schwelle")
                except Exception:
                    pass

class StrikePanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Strike vergeben", style=discord.ButtonStyle.red, custom_id="strike_add")
    async def add_strike(self, interaction: discord.Interaction, button: discord.ui.Button):  # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        await interaction.response.send_message(
            "Nutze `/strikeadd [@User] [Grund]` zum Strike vergeben.", ephemeral=True
        )

    @discord.ui.button(label="Strikes anzeigen", style=discord.ButtonStyle.blurple, custom_id="strike_view")
    async def view_strikes(self, interaction: discord.Interaction, button: discord.ui.Button):  # HIER geändert!
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins!", ephemeral=True)
            return
        await interaction.response.send_message(
            "Nutze `/strikeview [@User]` um Strikes anzuzeigen.", ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(StrikeCog(bot))
