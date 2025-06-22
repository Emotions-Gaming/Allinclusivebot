```python
import os
import discord
from discord import app_commands, Interaction, Member, Role
from discord.ext import commands
from .utils import load_json, save_json, is_admin, has_any_role
import logging

# Guild-Konstante
GUILD_ID = int(os.getenv("GUILD_ID"))

logger = logging.getLogger(__name__)

# Dateinamen
DATA_FILE = "strike_data.json"
ROLES_FILE = "strike_roles.json"  # Rollen, die Strikes vergeben dürfen
AUTOROLE_FILE = "strike_autorole.json"  # Rolle, die bei 3 Strikes vergeben wird
LIST_CHANNEL_FILE = "strike_list_channel.json"  # Channel zum Posten der Übersicht

class StrikeCog(commands.Cog):
    """Cog für das Strike-System."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_strikes(self) -> dict[str, list]:
        return load_json(DATA_FILE, {}) or {}

    def save_strikes(self, data: dict):
        save_json(DATA_FILE, data)

    def get_roles(self) -> list[int]:
        return load_json(ROLES_FILE, []) or []

    def save_roles(self, data: list[int]):
        save_json(ROLES_FILE, data)

    def get_autorole(self) -> int | None:
        return load_json(AUTOROLE_FILE, None)

    def save_autorole(self, role_id: int | None):
        save_json(AUTOROLE_FILE, role_id)

    def get_list_channel(self) -> int | None:
        return load_json(LIST_CHANNEL_FILE, None)

    def save_list_channel(self, channel_id: int):
        save_json(LIST_CHANNEL_FILE, channel_id)

    def user_can_strike(self, member: Member) -> bool:
        return is_admin(member) or has_any_role(member, self.get_roles())

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikegive", description="Vergebe einen Strike an einen Nutzer")
    async def strikegive(self, interaction: Interaction, user: Member, grund: str):
        # Rechte prüfen
        if not self.user_can_strike(interaction.user):
            await interaction.response.send_message("Du hast keine Berechtigung, Strikes zu vergeben.", ephemeral=True)
            return
        strikes = self.get_strikes()
        uid = str(user.id)
        user_strikes = strikes.get(uid, [])
        user_strikes.append({"time": interaction.created_at.isoformat(), "grund": grund})
        strikes[uid] = user_strikes
        self.save_strikes(strikes)
        # Autorole prüfen
        autorole_id = self.get_autorole()
        if autorole_id and len(user_strikes) >= 3:
            role = interaction.guild.get_role(autorole_id)
            if role:
                await user.add_roles(role)
        await interaction.response.send_message(f"Strike vergeben an {user.mention}. Aktuell: {len(user_strikes)} Strikes.", ephemeral=True)
        await self.update_strike_list()

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikeremove", description="Entfernt einen Strike von einem Nutzer")
    async def strikeremove(self, interaction: Interaction, user: Member):
        if not self.user_can_strike(interaction.user):
            await interaction.response.send_message("Du hast keine Berechtigung, Strikes zu entfernen.", ephemeral=True)
            return
        strikes = self.get_strikes()
        uid = str(user.id)
        user_strikes = strikes.get(uid, [])
        if user_strikes:
            user_strikes.pop()
            strikes[uid] = user_strikes
            self.save_strikes(strikes)
            await interaction.response.send_message(f"Letzter Strike von {user.mention} entfernt. Aktuell: {len(user_strikes)} Strikes.", ephemeral=True)
            await self.update_strike_list()
        else:
            await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikedelete", description="Löscht alle Strikes eines Nutzers")
    async def strikedelete(self, interaction: Interaction, user: Member):
        if not self.user_can_strike(interaction.user):
            await interaction.response.send_message("Du hast keine Berechtigung.", ephemeral=True)
            return
        strikes = self.get_strikes()
        uid = str(user.id)
        if uid in strikes:
            del strikes[uid]
            self.save_strikes(strikes)
            await interaction.response.send_message(f"Alle Strikes von {user.mention} wurden gelöscht.", ephemeral=True)
            await self.update_strike_list()
        else:
            await interaction.response.send_message(f"{user.mention} hat keine Strikes.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikeview", description="Zeigt deine aktuellen Strikes an")
    async def strikeview(self, interaction: Interaction):
        strikes = self.get_strikes().get(str(interaction.user.id), [])
        count = len(strikes)
        await interaction.response.send_message(f"Du hast aktuell {count} Strikes.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikelist", description="Lege den Channel für die Strike-Übersicht fest")
    async def strikelist(self, interaction: Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können den List-Channel setzen.", ephemeral=True)
            return
        self.save_list_channel(channel.id)
        await interaction.response.send_message(f"Strike-List-Channel gesetzt auf {channel.mention}.", ephemeral=True)
        await self.update_strike_list()

    async def update_strike_list(self):
        channel_id = self.get_list_channel()
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        strikes = self.get_strikes()
        embed = discord.Embed(title="Aktuelle Strikes")
        for uid, entries in strikes.items():
            user = channel.guild.get_member(int(uid))
            embed.add_field(name=user.mention if user else uid, value=f"{len(entries)} Strikes", inline=False)
        async for msg in channel.history(limit=50):
            if msg.author == self.bot.user:
                await msg.delete()
        await channel.send(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikemaininfo", description="Zeigt das Strike-Hauptinfo-Embed")
    async def strikemaininfo(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins dürfen das Info-Embed posten.", ephemeral=True)
            return
        embed = discord.Embed(title="🛑 Strike System", description="Nutze `/strikegive`, `/strikeremove`, `/strikedelete` für die Verwaltung.")
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikerole", description="Fügt eine Rolle hinzu, die Strikes vergeben darf")
    async def strikerole(self, interaction: Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können Rollen hinzufügen.", ephemeral=True)
            return
        roles = self.get_roles()
        if role.id in roles:
            await interaction.response.send_message("Rolle ist bereits berechtigt.", ephemeral=True)
            return
        roles.append(role.id)
        self.save_roles(roles)
        await interaction.response.send_message(f"Rolle {role.mention} darf nun Strikes vergeben.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikerole_remove", description="Entfernt eine Strike-Berechtigungs-Rolle")
    async def strikerole_remove(self, interaction: Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können Rollen entfernen.", ephemeral=True)
            return
        roles = self.get_roles()
        if role.id not in roles:
            await interaction.response.send_message("Rolle war nicht berechtigt.", ephemeral=True)
            return
        roles.remove(role.id)
        self.save_roles(roles)
        await interaction.response.send_message(f"Rolle {role.mention} kann nun keine Strikes mehr vergeben.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikeaddrole", description="Setzt die Rolle, die bei 3 Strikes vergeben wird")
    async def strikeaddrole(self, interaction: Interaction, role: Role):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können die Autorole setzen.", ephemeral=True)
            return
        self.save_autorole(role.id)
        await interaction.response.send_message(f"Autorole bei 3 Strikes gesetzt auf {role.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="strikeaddrole_remove", description="Entfernt die automatische Rolle bei 3 Strikes")
    async def strikeaddrole_remove(self, interaction: Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("Nur Admins können die Autorole entfernen.", ephemeral=True)
            return
        self.save_autorole(None)
        await interaction.response.send_message("Automatische Rolle bei 3 Strikes entfernt.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = StrikeCog(bot)
    bot.add_cog(cog)
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
```