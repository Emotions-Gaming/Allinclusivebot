# schicht.py

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
        return await utils.load_json(SCHICHT_CONFIG_PATH, {
            "roles": [],
            "voice_channel_id": None,
            "log_channel_id": None,
            "schicht_group": []
        })

    async def save_config(self, config):
        await utils.save_json(SCHICHT_CONFIG_PATH, config)

    async def is_allowed(self, member: discord.Member):
        # Prüft ob Member eine Schichtrolle hat oder Admin ist
        cfg = await self.get_config()
        return utils.is_admin(member) or utils.has_any_role(member, cfg["roles"])

    async def is_in_group(self, user_id: int):
        cfg = await self.get_config()
        return user_id in cfg.get("schicht_group", [])

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

    async def get_temp_voice_category(self, guild):
        """Kategorie des Zielkanals, falls temporäre Channels dort angelegt werden sollen"""
        channel = await self.get_voice_channel(guild)
        return channel.category if channel else None

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
                "3. Beide werden automatisch in einen temporären VoiceMaster-Kanal verschoben\n"
                "4. Übergabe läuft – ggf. relevante Infos im Chat posten!"
            ),
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Kopiere diesen Befehl:",
            value="```/schichtuebergabe (nutzer)```",
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

        # Nur Schichtgruppenmitglieder auswählbar
        if not await self.is_in_group(user.id):
            return await utils.send_error(interaction, "Dieser Nutzer ist nicht in der Schichtgruppe und kann nicht ausgewählt werden.")

        # Voice-Check: Initiator
        if not isinstance(initiator, discord.Member) or not initiator.voice or not initiator.voice.channel:
            return await utils.send_error(interaction, "Du musst dich im Voice-Channel befinden, um eine Schichtübergabe zu starten.")

        # Voice-Check: Zielnutzer
        if user.status != discord.Status.offline and user.voice and user.voice.channel:
            # Ziel-User ist online & im Voice → beide moven!
            temp_cat = await self.get_temp_voice_category(guild)
            name = f"Schichtübergabe-{initiator.name}-{user.name}"
            # Temporären VoiceChannel anlegen
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                initiator: discord.PermissionOverwrite(connect=True),
                user: discord.PermissionOverwrite(connect=True),
                guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True)
            }
            temp_voice = await guild.create_voice_channel(
                name=name,
                overwrites=overwrites,
                category=temp_cat
            )
            # Beide moven (nacheinander, damit Discord keine Fehler schmeißt)
            try:
                await initiator.move_to(temp_voice)
                await asyncio.sleep(0.3)
                await user.move_to(temp_voice)
            except Exception as e:
                await utils.send_error(interaction, f"Fehler beim Verschieben: {e}")
                await temp_voice.delete()
                return

            await utils.send_success(interaction, f"Beide Nutzer wurden in den temporären VoiceMaster verschoben!\nSchichtübergabe läuft jetzt.")
            await self.log_event(
                guild,
                f"**Schichtübergabe:** {initiator.mention} → {user.mention} | `{discord.utils.format_dt(discord.utils.utcnow(), 'f')}`"
            )
            # Optional: Channel nach Übergabe irgendwann automatisch löschen
            await asyncio.sleep(60*15)  # 15 Minuten
            try:
                await temp_voice.delete()
            except Exception:
                pass
        else:
            # Ziel-User ist nicht online/im Voice
            try:
                await user.send(f"👮‍♂️ **Schichtübergabe:** {initiator.mention} möchte mit dir eine Schichtübergabe durchführen.\nBitte komme schnellstmöglich in Discord und gehe in einen Voice-Channel!")
                await utils.send_success(interaction, f"User nicht online/im Voice, wurde per DM benachrichtigt.")
                await self.log_event(
                    guild,
                    f"**Schichtübergabe-Versuch:** {initiator.mention} → {user.mention} (User offline/kein Voice, per DM erinnert) | `{discord.utils.format_dt(discord.utils.utcnow(), 'f')}`"
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
        if role.id not in cfg["roles"]:
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
        if role.id in cfg["roles"]:
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
        group = ", ".join(f"<@{uid}>" for uid in cfg.get("schicht_group", [])) or "*Keine*"
        voice = guild.get_channel(cfg.get("voice_channel_id", 0))
        log = guild.get_channel(cfg.get("log_channel_id", 0))
        desc = (
            f"**Schichtrollen:** {rollen}\n"
            f"**VoiceChannel:** {voice.mention if voice else '*nicht gesetzt*'}\n"
            f"**LogChannel:** {log.mention if log else '*nicht gesetzt*'}\n"
            f"**Schichtgruppe:** {group}"
        )
        await utils.send_ephemeral(
            interaction,
            text=desc,
            emoji="👮‍♂️",
            color=discord.Color.teal()
        )

    @app_commands.command(
        name="schichtgroup",
        description="Fügt einen Nutzer zur Schichtgruppe hinzu (nur Admin)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtgroup(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if user.id not in cfg.get("schicht_group", []):
            cfg["schicht_group"].append(user.id)
            await self.save_config(cfg)
            await utils.send_success(interaction, f"{user.mention} ist jetzt Mitglied der Schichtgruppe.")
        else:
            await utils.send_error(interaction, f"{user.mention} ist bereits Mitglied der Schichtgruppe.")

    @app_commands.command(
        name="schichtgroupremove",
        description="Entfernt einen Nutzer aus der Schichtgruppe (nur Admin)."
    )
    @app_commands.guilds(MY_GUILD)
    async def schichtgroupremove(self, interaction: Interaction, user: discord.Member):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        cfg = await self.get_config()
        if user.id in cfg.get("schicht_group", []):
            cfg["schicht_group"].remove(user.id)
            await self.save_config(cfg)
            await utils.send_success(interaction, f"{user.mention} wurde aus der Schichtgruppe entfernt.")
        else:
            await utils.send_error(interaction, f"{user.mention} ist nicht in der Schichtgruppe.")

    # ===== Menu-Refresh für SetupBot =====
    async def reload_menu(self, channel_id):
        """Für setupbot.py: postet das Panel neu."""
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
                    "3. Beide werden automatisch in einen temporären VoiceMaster-Kanal verschoben\n"
                    "4. Übergabe läuft – ggf. relevante Infos im Chat posten!"
                ),
                color=discord.Color.teal()
            )
            embed.add_field(
                name="Kopiere diesen Befehl:",
                value="```/schichtuebergabe (nutzer)```",
                inline=False
            )
            await channel.send(embed=embed)

# ===== Cog Setup =====
async def setup(bot):
    await bot.add_cog(SchichtCog(bot))
