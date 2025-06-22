import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# ENV-Variablen laden
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

class CommandCleaner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="deletecommands", description="Löscht alle Slash-Commands des Bots auf diesem Server")
    async def deletecommands(self, interaction: discord.Interaction):
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        await interaction.response.send_message("Alle Slash-Commands für diesen Server gelöscht!", ephemeral=True)
        print("Alle Slash-Commands wurden gelöscht.")

async def setup(bot):
    await bot.add_cog(CommandCleaner(bot))

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    guild = discord.Object(id=GUILD_ID)
    try:
        await bot.tree.sync(guild=guild)
        print(f"Commands (re)synced für Guild-ID {GUILD_ID}")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")

async def main():
    await bot.load_extension(__name__)
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
