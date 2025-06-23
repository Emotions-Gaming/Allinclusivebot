import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Pong zurück!")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("🏓 Pong!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TestCog(bot))

# In bot.py nur diese Extension laden und schauen, ob /ping erscheint!
