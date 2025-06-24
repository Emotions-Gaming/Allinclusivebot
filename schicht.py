import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
import asyncio

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
SCHICHT_CONFIG_PATH = os.path.join("persistent_data", "schicht_config.json")

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===== Helper =====

    async def get_config(self):
        cfg = await utils.load_json(SCHICHT_CONFIG_PATH, {})
        if "roles" not in cfg:
            cfg["roles"] = []
        if "voice_channel_id" not in cfg:
            cfg["voice_channel_id"] = None
        if "log_channel_id" not in cfg:
            cfg["log_channel_id"] = None
        if "schicht_group_users" not in cfg:
            cfg["schicht_group_users"] = cfg.get("schicht_group", [])
        if "schicht_group_roles" not in cfg:
            cfg["schicht_group_roles"] = []
        return cfg

    async def save_config(self, config):
        await utils.save_json(SCHICHT_CONFIG_PATH, config)

    async def is_allowed(self, member: discord.Member):
        cfg = await self.get_config()
        return utils.is_admin(member) or utils.has_any_role(member, cfg.get("roles", []))

    async def is_in_group(self, member: discord.Member):
        cfg = await self.get_config()
        if member.id in cfg.get("schicht_group_users", []):
            return True
        if utils.has_any_role(member, cfg.get("schicht_group_roles", [])):
            return True
        return False

    async def get_voice_channel(self, guild):
        cfg = await self.get_config()
        if cfg.get("voice_channel_id"):
            return guild.get_channel(cfg["voice_channel_id"])
        return None

    async def get_log_channel(self, guild):
        cfg = await self.get_config()
        if cfg.get("log_channel_id"):
            return guild.get_channel(cfg["log_channel_id"])
        return None

    async def log_event(self, guild, text):
        log_channel = await self.get_log_channel(guild)
        if log_channel:
            embed = discord.Embed(description=text, color=discord.Color.blurple())
            await log_channel.send(embed=embed)

    # ===== Slash Commands =====

    @app_commands.command(
        name="schichtmain",
        description="Postet das Schichtübergabe-Panel mit Copy-Codeblock (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtmain(self, interaction: Interaction):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        embed = discord.Embed(
            title="👮‍♂️ Schichtübergabe – Hinweise",
            description=(
                "Mit `/schichtuebergabe` kannst du die Schicht gezielt übergeben.\n\n"
                "**Ablauf:**\n"
                "1. Nutze den Command, während du im Voice bist\n"
                "2. Der neue Nutzer muss in Discord & im Voice-Channel online sein (und in der Schichtgruppe!)\n"
                "3. Beide werden gemeinsam in den eingestellten Schicht-Channel gemovt\n"
                "4. Übergabe läuft – ggf. relevante Infos im Chat posten!"
            ),
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Kopiere diesen Befehl:",
            value="```/schichtuebergabe```",
            inline=False
        )
        await interaction.channel.send(embed=embed)
        await utils.send_success(interaction, "Panel gepostet!")

    @app_commands.command(
        name="schichtuebergabe",
        description="Übergibt die Schicht an einen anderen Nutzer aus der Schichtgruppe."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtuebergabe(self, interaction: Interaction, user: discord.Member):
        cfg = await self.get_config()
        initiator = interaction.user
        guild = interaction.guild

        # Rechte-Check
        if not await self.is_allowed(initiator):
            return await utils.send_permission_denied(interaction)

        # Schichtgruppen-Check
        if not await self.is_in_group(user):
            return await utils.send_error(interaction, "Dieser Nutzer ist nicht in der Schichtgruppe (weder explizit noch durch Rolle).")

        # Check: Initiator muss im Voice sein
        if not isinstance(initiator, discord.Member) or not initiator.voice or not initiator.voice.channel:
            return await utils.send_error(interaction, "Du musst dich in einem Voice-Channel befinden, um eine Schichtübergabe zu starten.")

        # Ziel-Schichtchannel
        target_voice_channel = await self.get_voice_channel(guild)
        if not target_voice_channel:
            return await utils.send_error(interaction, "Der Ziel-VoiceChannel für Schichtübergaben ist nicht gesetzt.")

        # Move Initiator
        try:
            await initiator.move_to(target_voice_channel)
        except Exception as e:
            return await utils.send_error(interaction, f"Konnte dich nicht in den Zielchannel verschieben: {e}")

        # Warten, dann Zieluser moven, falls online
        await asyncio.sleep(2)
        if user.voice and user.voice.channel:
            try:
                await user.move_to(target_voice_channel)
                await utils.send_success(interaction, f"{user.mention} wurde zu dir in den Voice-Channel verschoben!\nSchichtübergabe läuft jetzt.")
                await self.log_event(
                    guild,
                    f"Schichtübergabe: {initiator.mention} → {user.mention}"
                )
            except Exception as e:
                await utils.send_error(interaction, f"Fehler beim Verschieben: {e}")
        else:
            # Zieluser NICHT im Voice
            try:
                await user.send(f"👮‍♂️ **Schichtübergabe:** {initiator.mention} möchte mit dir eine Schichtübergabe durchführen.\nBitte komme schnellstmöglich in Discord und gehe in den Voice-Channel: **{target_voice_channel.name}**!")
                await utils.send_success(interaction, f"User nicht online/im Voice, wurde per DM benachrichtigt.")
                await self.log_event(
                    guild,
                    f"Schichtübergabe-Versuch: {initiator.mention} → {user.mention} (User offline/kein Voice, per DM erinnert)"
                )
            except Exception:
                await utils.send_error(interaction, "User konnte nicht per DM erreicht werden.")

    @app_commands.command(
        name="schichtsetrolle",
        description="Fügt eine Rolle als Schichtrolle hinzu (darf Übergaben machen)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtsetrolle(self, interaction: Interaction, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if role.id not in cfg.get("roles", []):
            cfg["roles"].append(role.id)
            await self.save_config(cfg)
        await utils.send_success(interaction, f"Rolle {role.mention} darf nun Schichtübergaben durchführen.")

    @app_commands.command(
        name="schichtremoverolle",
        description="Entfernt eine Rolle von den Schichtrollen."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtremoverolle(self, interaction: Interaction, role: discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if role.id in cfg.get("roles", []):
            cfg["roles"].remove(role.id)
            await self.save_config(cfg)
        await utils.send_success(interaction, f"Rolle {role.mention} entfernt.")

    @app_commands.command(
        name="schichtsetvoice",
        description="Setzt den Ziel-VoiceChannel für Schichtübergaben."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtsetvoice(self, interaction: Interaction, channel: discord.VoiceChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        cfg["voice_channel_id"] = channel.id
        await self.save_config(cfg)
        await utils.send_success(interaction, f"Voice-Channel für Übergaben gesetzt: {channel.mention}")

    @app_commands.command(
        name="schichtsetlog",
        description="Setzt den Log-Channel für Schichtübergaben."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtsetlog(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        cfg["log_channel_id"] = channel.id
        await self.save_config(cfg)
        await utils.send_success(interaction, f"Log-Channel gesetzt: {channel.mention}")

    @app_commands.command(
        name="schichtinfo",
        description="Zeigt die aktuelle Schicht-Konfiguration."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtinfo(self, interaction: Interaction):
        cfg = await self.get_config()
        guild = interaction.guild
        rollen = utils.pretty_role_list(guild, cfg.get("roles", []))
        group_users = ", ".join(f"<@{uid}>" for uid in cfg.get("schicht_group_users", [])) or "*Keine*"
        group_roles = utils.pretty_role_list(guild, cfg.get("schicht_group_roles", []))
        voice = guild.get_channel(cfg.get("voice_channel_id", 0))
        log = guild.get_channel(cfg.get("log_channel_id", 0))
        desc = (
            f"**Schichtrollen:** {rollen}\n"
            f"**VoiceChannel:** {voice.mention if voice else '*nicht gesetzt*'}\n"
            f"**LogChannel:** {log.mention if log else '*nicht gesetzt*'}\n"
            f"**Schichtgruppen-User:** {group_users}\n"
            f"**Schichtgruppen-Rollen:** {group_roles if group_roles else '*Keine*'}"
        )
        await utils.send_ephemeral(
            interaction,
            text=desc,
            emoji="👮‍♂️",
            color=discord.Color.teal()
        )

    # ------------- NEU: Rollen ODER User zur Schichtgruppe hinzufügen -------------
    @app_commands.command(
        name="schichtgroup",
        description="Fügt einen Nutzer ODER eine Rolle zur Schichtgruppe hinzu (nur Admin)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtgroup(self, interaction: Interaction, target: discord.Member | discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if isinstance(target, discord.Member):
            if target.id not in cfg.get("schicht_group_users", []):
                cfg["schicht_group_users"].append(target.id)
                await self.save_config(cfg)
                await utils.send_success(interaction, f"{target.mention} ist jetzt Mitglied der Schichtgruppe.")
            else:
                await utils.send_error(interaction, f"{target.mention} ist bereits Mitglied der Schichtgruppe.")
        elif isinstance(target, discord.Role):
            if target.id not in cfg.get("schicht_group_roles", []):
                cfg["schicht_group_roles"].append(target.id)
                await self.save_config(cfg)
                await utils.send_success(interaction, f"Rolle {target.mention} ist jetzt Schichtgruppe (alle mit der Rolle).")
            else:
                await utils.send_error(interaction, f"Rolle {target.mention} ist bereits Schichtgruppe.")

    @app_commands.command(
        name="schichtgroupremove",
        description="Entfernt einen Nutzer ODER eine Rolle aus der Schichtgruppe (nur Admin)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtgroupremove(self, interaction: Interaction, target: discord.Member | discord.Role):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if isinstance(target, discord.Member):
            if target.id in cfg.get("schicht_group_users", []):
                cfg["schicht_group_users"].remove(target.id)
                await self.save_config(cfg)
                await utils.send_success(interaction, f"{target.mention} wurde aus der Schichtgruppe entfernt.")
            else:
                await utils.send_error(interaction, f"{target.mention} ist nicht in der Schichtgruppe.")
        elif isinstance(target, discord.Role):
            if target.id in cfg.get("schicht_group_roles", []):
                cfg["schicht_group_roles"].remove(target.id)
                await self.save_config(cfg)
                await utils.send_success(interaction, f"Rolle {target.mention} wurde aus der Schichtgruppe entfernt.")
            else:
                await utils.send_error(interaction, f"Rolle {target.mention} ist nicht in der Schichtgruppe.")

    # ===== Menu-Refresh für SetupBot =====
    async def reload_menu(self, channel_id):
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="👮‍♂️ Schichtübergabe – Hinweise",
                description=(
                    "Mit `/schichtuebergabe` kannst du die Schicht gezielt übergeben.\n\n"
                    "**Ablauf:**\n"
                    "1. Nutze den Command, während du im Voice bist\n"
                    "2. Der neue Nutzer muss in Discord & im Voice-Channel online sein (und in der Schichtgruppe!)\n"
                    "3. Beide werden gemeinsam in den eingestellten Schicht-Channel gemovt\n"
                    "4. Übergabe läuft – ggf. relevante Infos im Chat posten!"
                ),
                color=discord.Color.teal()
            )
            embed.add_field(
                name="Kopiere diesen Befehl:",
                value="```/schichtuebergabe```",
                inline=False
            )
            await channel.send(embed=embed)

# ===== Cog Setup =====
async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
