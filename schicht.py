import os
import discord
from discord.ext import commands
from discord import app_commands, TextChannel, Role, Embed, Member
from utils import is_admin, load_json, save_json, mention_roles
from permissions import has_permission_for
from discord import Interaction


GUILD_ID = int(os.environ.get("GUILD_ID"))
SCHICHT_CONFIG = "persistent_data/schicht_config.json"

def _load_config():
    return load_json(SCHICHT_CONFIG, {
        "lead_role_ids": [],
        "user_role_ids": [],
        "log_channel_id": None,
        "main_channel_id": None,
        "main_message_id": None,
        "panel_info": ""
    })

def _save_config(cfg):
    save_json(SCHICHT_CONFIG, cfg)

def is_lead_or_admin(user):
    cfg = _load_config()
    return is_admin(user) or any(r.id in cfg["lead_role_ids"] for r in getattr(user, "roles", []))

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def reload_menu(self):
        cfg = _load_config()
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
            title="👮‍♂️ Schicht-Panel",
            description=(
                f"{cfg.get('panel_info', 'Mit dem Button kannst du eine Schichtanfrage oder -übergabe starten.')}\n\n"
                "**Direkt Schichtübergabe:**\n"
                "```/schichtuebergabe [@Nutzer]```\n"
                "_Kopieren, Nutzer auswählen, abschicken!_\n\n"
                "➜ Schichtübergabe wird automatisch geloggt."
            ),
            color=0x0984e3
        )
        view = SchichtPanelView(self)
        msg = await channel.send(embed=embed, view=view)
        cfg["main_message_id"] = msg.id
        _save_config(cfg)

    @app_commands.command(
        name="schichtmain",
        description="Postet/zurücksetzt das Schicht-Hauptpanel"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtmain")
    async def schichtmain(self, interaction: discord.Interaction):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_config()
        cfg["main_channel_id"] = interaction.channel.id
        _save_config(cfg)
        await self.reload_menu()
        await interaction.response.send_message("✅ Schicht-Panel gepostet!", ephemeral=True)

    @app_commands.command(
        name="schichtlead_add",
        description="Fügt eine Rolle als Schicht-Lead hinzu"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtlead_add")
    async def schichtlead_add(self, interaction: discord.Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins.", ephemeral=True)
            return
        cfg = _load_config()
        leads = set(cfg["lead_role_ids"])
        leads.add(role.id)
        cfg["lead_role_ids"] = list(leads)
        _save_config(cfg)
        await interaction.response.send_message(f"✅ {role.mention} ist jetzt Schicht-Lead.", ephemeral=True)
        await self.reload_menu()

    @app_commands.command(
        name="schichtlead_remove",
        description="Entfernt eine Rolle als Schicht-Lead"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtlead_remove")
    async def schichtlead_remove(self, interaction: discord.Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Admins.", ephemeral=True)
            return
        cfg = _load_config()
        if role.id in cfg["lead_role_ids"]:
            cfg["lead_role_ids"].remove(role.id)
            _save_config(cfg)
            await interaction.response.send_message(f"✅ {role.mention} ist kein Lead mehr.", ephemeral=True)
            await self.reload_menu()
        else:
            await interaction.response.send_message("ℹ️ Diese Rolle war kein Lead.", ephemeral=True)

    @app_commands.command(
        name="schichtlog",
        description="Setzt Log-Channel für Schichtübergaben"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtlog")
    async def schichtlog(self, interaction: discord.Interaction, channel: TextChannel):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_config()
        cfg["log_channel_id"] = channel.id
        _save_config(cfg)
        await interaction.response.send_message(f"✅ Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(
        name="schichtpanelinfo",
        description="Setzt Infotext für das Schicht-Panel"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtpanelinfo")
    async def schichtpanelinfo(self, interaction: discord.Interaction, text: str):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return
        cfg = _load_config()
        cfg["panel_info"] = text
        _save_config(cfg)
        await self.reload_menu()
        await interaction.response.send_message("✅ Panel-Info aktualisiert.", ephemeral=True)

    @app_commands.command(
        name="schichtuebergabe",
        description="Übergibt eine Schicht an einen Nutzer"
    )
    @app_commands.guilds(GUILD_ID)
    @has_permission_for("schichtuebergabe")
    async def schichtuebergabe(self, interaction: discord.Interaction, user: Member):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return

        class ÜbergabeModal(discord.ui.Modal, title="Schichtübergabe"):
            info = discord.ui.TextInput(label="Wichtige Hinweise (optional)", required=False, max_length=300)

            async def on_submit(self, modal_interaction: discord.Interaction):
                cfg = _load_config()
                guild = interaction.guild or self.bot.get_guild(GUILD_ID)
                log_channel = guild.get_channel(cfg.get("log_channel_id"))
                embed = Embed(
                    title="👮‍♂️ Schichtübergabe",
                    description=(
                        f"**Übergeber:** {interaction.user.mention}\n"
                        f"**Neuer Nutzer:** {user.mention}\n"
                        f"{'**Hinweise:** ' + self.info.value if self.info.value else ''}"
                    ),
                    color=0x00b894
                )
                if log_channel:
                    await log_channel.send(embed=embed)
                try:
                    await user.send(
                        f"👮‍♂️ **Dir wurde eine Schicht übergeben!**\n"
                        f"Übergeber: {interaction.user.mention}\n"
                        f"{'Hinweise: ' + self.info.value if self.info.value else ''}"
                    )
                except Exception:
                    pass
                await modal_interaction.response.send_message("✅ Schichtübergabe abgeschlossen!", ephemeral=True)

        await interaction.response.send_modal(ÜbergabeModal())

class SchichtPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Schichtübergabe starten", style=discord.ButtonStyle.green, custom_id="schicht_uebergabe")
    async def start_uebergabe(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_lead_or_admin(interaction.user):
            await interaction.response.send_message("❌ Nur Lead/Admin!", ephemeral=True)
            return
        await interaction.response.send_message(
            "Nutze den Befehl `/schichtuebergabe [@Nutzer]` um gezielt zu übergeben!", ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
