import discord
from discord.ext import commands
from discord import app_commands
import asyncio  # Bugfix für das Verschieben!
from utils import load_json, save_json, is_admin

SCHICHT_CONFIG_FILE = "persistent_data/schicht_config.json"
SCHICHT_RIGHTS_FILE = "persistent_data/schicht_rights.json"

class Schicht(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schicht_cfg = load_json(SCHICHT_CONFIG_FILE, {
            "text_channel_id": None,
            "voice_channel_id": None,
            "log_channel_id": None,
            "rollen": []
        })
        self.schicht_rights = set(load_json(SCHICHT_RIGHTS_FILE, []))

    # ================== Schichtinfo posten =====================

    @app_commands.command(name="schichtinfo", description="Postet Hinweise zur Schichtübergabe")
    async def schichtinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👮‍♂️ Schichtübergabe – Hinweise",
            description=(
                "Mit `/schichtuebergabe [Nutzer]` kannst du die Schicht gezielt übergeben.\n"
                "**Ablauf:**\n"
                "1. Nutze den Command, während du im Voice bist\n"
                "2. Der neue Nutzer muss im Discord & Voice-Channel online sein\n"
                "3. Beide werden gemeinsam in den VoiceMaster-Kanal verschoben\n"
                "4. Ab jetzt läuft die Übergabe – ggf. relevante Infos im Chat posten!"
            ),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    # ================== Rechte für Schichtübergabe steuern =====================

    @app_commands.command(name="schichtrolerights", description="Fügt eine Rolle als berechtigt für Schichtübergabe hinzu")
    @app_commands.describe(role="Rolle, die den Befehl ausführen darf")
    async def schichtrolerights(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        self.schicht_rights.add(role.id)
        save_json(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))
        await interaction.response.send_message(f"Rolle {role.mention} ist jetzt für Schichtübergabe berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtroledeleterights", description="Entfernt eine Rolle aus der Schichtübergabe-Berechtigung")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtroledeleterights(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        if role.id in self.schicht_rights:
            self.schicht_rights.remove(role.id)
            save_json(SCHICHT_RIGHTS_FILE, list(self.schicht_rights))
            await interaction.response.send_message(f"Rolle {role.mention} entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    # ================== Schichtübergabe an Nutzer =====================

    async def schicht_user_autocomplete(self, interaction: discord.Interaction, current: str):
        rollen = set(self.schicht_cfg.get("rollen", []))
        allowed = []
        for m in interaction.guild.members:
            if m.bot:
                continue
            is_role = any(r.id in rollen for r in m.roles)
            name_match = current.lower() in m.display_name.lower() or current.lower() in m.name.lower()
            if is_role and name_match:
                allowed.append(app_commands.Choice(name=m.display_name, value=str(m.id)))
            if len(allowed) >= 20: break
        return allowed

    @app_commands.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer mit Rollen-Filter")
    @app_commands.describe(nutzer="Nutzer für Übergabe")
    @app_commands.autocomplete(nutzer=schicht_user_autocomplete)
    async def schichtuebergabe(self, interaction: discord.Interaction, nutzer: str):
        user_roles = [r.id for r in interaction.user.roles]
        if self.schicht_rights and not any(rid in self.schicht_rights for rid in user_roles) and not is_admin(interaction.user):
            return await interaction.response.send_message("Du hast keine Berechtigung für diesen Command.", ephemeral=True)

        rollen = set(self.schicht_cfg.get("rollen", []))
        guild = interaction.guild
        user = guild.get_member(int(nutzer))
        if not user:
            return await interaction.response.send_message("Nutzer nicht gefunden.", ephemeral=True)
        # Check: Hat user die richtige Rolle?
        if not any(r.id in rollen for r in user.roles):
            return await interaction.response.send_message(f"{user.display_name} hat nicht die berechtigte Rolle.", ephemeral=True)
        # Check: Fragender im Voice?
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
        # Check: Zielnutzer im Voice?
        if not user.voice or not user.voice.channel:
            try:
                await user.send(f"**{interaction.user.display_name}** möchte dir die Schicht übergeben, aber du bist nicht im Sprachkanal! Bitte geh online und join einem Channel.")
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal! Ich habe ihm eine DM geschickt.", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"{user.mention} ist nicht im Sprachkanal und konnte nicht per DM benachrichtigt werden.", ephemeral=True)
            return
        v_id = self.schicht_cfg.get("voice_channel_id")
        if not v_id:
            return await interaction.response.send_message("VoiceMaster-Eingangskanal ist nicht gesetzt!", ephemeral=True)
        voice_ch = guild.get_channel(v_id)
        try:
            await interaction.user.move_to(voice_ch)
            await interaction.response.send_message(f"Du wurdest in den VoiceMaster-Kanal verschoben. Warte kurz...", ephemeral=True)
            await asyncio.sleep(5)
            await user.move_to(interaction.user.voice.channel)
            await interaction.followup.send(f"{user.mention} wurde ebenfalls verschoben. Schichtübergabe kann starten!", ephemeral=True)
            log_id = self.schicht_cfg.get("log_channel_id")
            if log_id:
                log_ch = guild.get_channel(log_id)
                if log_ch:
                    await log_ch.send(
                        f"✅ **Schichtübergabe:** {interaction.user.mention} -> {user.mention} | Kanal: {voice_ch.mention}")
        except Exception as e:
            return await interaction.followup.send(f"Fehler beim Verschieben: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Schicht(bot))
