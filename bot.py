import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ====== ENV LOAD ======
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====== Alle Module/Extensions, die geladen werden ======
STARTUP_EXTENSIONS = [
    "persist",      # Railway Persistenz
    "utils",        # Hilfsfunktionen (muss früh geladen werden!)
    "translation",  # Übersetzungs-/Gemini-System
    "strike",       # Strike-/Admin-System
    "wiki",         # Wiki-System
    "schicht",      # Schichtübergabe
    "alarm",        # Alarm-/Claim-System
]

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user}")
    try:
        # Sync alle Commands explizit auf GUILD (Dev) und global
        guild = discord.Object(id=GUILD_ID) if GUILD_ID else None
        if guild:
            await bot.tree.sync(guild=guild)
            await bot.tree.sync()  # Optional: für globale Commands (Achtung: dauert länger!)
            print("🟢 Slash-Commands synchronisiert (Guild & global)")
        else:
            await bot.tree.sync()
            print("🟢 Slash-Commands synchronisiert (Global)")
    except Exception as e:
        print(f"❌ Fehler beim Command-Sync: {e}")

    print("Alle Extensions geladen und ready!")

async def main():
    # Extensions laden (Reihenfolge ist wichtig!)
    for ext in STARTUP_EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"🧩 Extension geladen: {ext}")
        except Exception as e:
            print(f"❌ Fehler beim Laden von {ext}: {e}")

    # Bot starten
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
