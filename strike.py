import discord
from discord import app_commands, Interaction
from discord.ext import commands
import os
import utils
from datetime import datetime

GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
MY_GUILD = discord.Object(id=GUILD_ID)
STRIKE_DATA_PATH = os.path.join("persistent_data", "strike_data.json")
STRIKE_LIST_CHANNEL_PATH = os.path.join("persistent_data", "strike_list_channel.json")

def format_time(ts=None):
    return datetime.now().strftime("%d.%m.%Y %H:%M") if ts is None else ts

async def get_strike_data():
    return await utils.load_json(STRIKE_DATA_PATH, {})

async def save_strike_data(data):
    await utils.save_json(STRIKE_DATA_PATH, data)

async def get_strike_list_channel_id():
    return await utils.load_json(STRIKE_LIST_CHANNEL_PATH, 0)

async def set_strike_list_channel_id(cid):
    await utils.save_json(STRIKE_LIST_CHANNEL_PATH, cid)

class StrikeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Core Strike Logic ---
    async def reload_strike_panel(self, guild):
        channel_id = await get_strike_list_channel_id()
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        strikes = await get_strike_data()
        embed = discord.Embed(
            title="⚠️ Strike-Übersicht",
            description="Alle aktiven Strikes auf dem Server.",
            color=discord.Color.red()
        )

        any_strikes = False
        for uid, strikes_list in strikes.items():
            if not strikes_list:
                continue
            member = guild.get_member(int(uid))
            name = member.mention if member else f"<@{uid}>"
            anzahl = len(strikes_list)
            embed.add_field(
                name=f"{name} ({anzahl} Strike{'s' if anzahl > 1 else ''})",
                value="• " + "\n• ".join(
                    [f"Grund: {s['grund']} ({format_time(s['zeit'])})" for s in strikes_list[-3:]]
                ),
                inline=False
            )
            any_strikes = True

        if not any_strikes:
            embed.description += "\n\n> Aktuell **keine vergebenen Strikes**!"

        await channel.purge(limit=5, check=lambda m: m.author == guild.me)
        await channel.send(embed=embed, view=StrikeListView(self))

    # --- Strike Give ---
    @app_commands.command(
        name="strikegive",
        description="Vergibt einen Strike an einen Nutzer (nur Teamleads/Admins/Sonderrollen)."
    )
    @app_commands.guilds(MY_GUILD)
    async def strikegive(self, interaction: Interaction, user: discord.Member, grund: str, bild: str = "-"):
        if not utils.is_strikeadmin(interaction.user):
            return await utils.send_permission_denied(interaction)

        strikes = await get_strike_data()
        user_id = str(user.id)
        if user_id not in strikes:
            strikes[user_id] = []

        strikes[user_id].append({
            "grund": grund,
            "bild": bild,
            "zeit": datetime.now().isoformat()
        })
        await save_strike_data(strikes)
        anzahl = len(strikes[user_id])

        # User informieren
        try:
            await user.send(
                f"Du hast einen neuen Strike erhalten!\n\nGrund: {grund}\nBild: {bild}\nAnzahl deiner Strikes: {anzahl}"
            )
        except Exception:
            pass

        await interaction.response.send_message(
            f"{user.mention} hat nun **{anzahl} Strike{'s' if anzahl != 1 else ''}**.",
            ephemeral=True
        )
        await self.reload_strike_panel(interaction.guild)

    # --- Strike Main Info ---
    @app_commands.command(
        name="strikemaininfo",
        description="Zeigt die Info & Anleitung für das Strike-System (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
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
            value="```/strikegive (nutzer)```",
            inline=False
        )
        await interaction.response.send_message(embed=embed, view=CopyStrikeCommandView(), ephemeral=True)

    # --- Strike List Channel Setup ---
    @app_commands.command(
        name="strikelist",
        description="Setzt den Channel für die Strike-Übersicht & postet alle aktiven Strikes (nur Admins)."
    )
    @app_commands.guilds(MY_GUILD)
    async def strikelist(self, interaction: Interaction, channel: discord.TextChannel):
        if not utils.is_admin(interaction.user):
            return await utils.send_permission_denied(interaction)
        await set_strike_list_channel_id(channel.id)
        await self.reload_strike_panel(interaction.guild)
        await utils.send_success(interaction, f"Strike-Übersicht wurde in {channel.mention} gepostet!")

    # --- View for details ---
    @app_commands.command(
        name="strikeview",
        description="Zeigt dir privat deine aktuellen Strikes an."
    )
    @app_commands.guilds(MY_GUILD)
    async def strikeview(self, interaction: Interaction):
        user = interaction.user
        strikes = await get_strike_data()
        user_strikes = strikes.get(str(user.id), [])
        if not user_strikes:
            return await interaction.response.send_message(
                "Du hast derzeit keine Strikes! 🎉", ephemeral=True
            )
        desc = ""
        for idx, s in enumerate(user_strikes, 1):
            desc += (
                f"**{idx}.** Grund: {s['grund']}\n"
                f"Bild: {s['bild']}\n"
                f"Zeit: {format_time(s['zeit'])}\n\n"
            )
        await interaction.response.send_message(
            f"**Deine Strikes:**\n\n{desc}", ephemeral=True
        )

    # --- Remove Strike ---
    @app_commands.command(
        name="strikeremove",
        description="Entfernt den letzten Strike eines Users (nur Teamleads/Admins/Sonderrollen)."
    )
    @app_commands.guilds(MY_GUILD)
    async def strikeremove(self, interaction: Interaction, user: discord.Member):
        if not utils.is_strikeadmin(interaction.user):
            return await utils.send_permission_denied(interaction)
        strikes = await get_strike_data()
        user_id = str(user.id)
        if user_id in strikes and strikes[user_id]:
            strikes[user_id].pop()
            await save_strike_data(strikes)
            await self.reload_strike_panel(interaction.guild)
            await utils.send_success(interaction, "Letzter Strike entfernt.")
        else:
            await utils.send_error(interaction, "User hat keine Strikes.")

# --- Custom View for Copy-Button in Info ---
class CopyStrikeCommandView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Befehl kopieren", style=discord.ButtonStyle.gray, emoji="📋")
    async def copy_cmd(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Kopiere den Befehl unten:\n```/strikegive (nutzer)```",
            ephemeral=True
        )

# --- StrikeListView: Details-Button (z. B. für Strike-Liste) ---
class StrikeListView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        # Optional: Du könntest für jeden User einen eigenen Button bauen, 
        # falls du pro User Details anzeigen willst. (Siehe unten!)

# --- Cog Setup ---
async def setup(bot):
    await bot.add_cog(StrikeCog(bot))

