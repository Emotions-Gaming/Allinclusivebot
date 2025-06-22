import os
import discord
from dotenv import load_dotenv
import asyncio

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class CommandWipeClient(discord.Client):
    async def on_ready(self):
        print(f"🗑 Starte globalen Command-Wipe für Bot {self.user} ({self.user.id}) ...")
        try:
            # Nur globale (nicht Guild-spezifische) Application Commands holen
            commands = await self.application_commands()
            print(f"  → Globale Commands gefunden: {len(commands)}")
            for cmd in commands:
                print(f"    - {cmd.name}")
            # Löschen
            await self.http.bulk_upsert_global_application_commands(self.user.id, [])
            print("✅ Alle globalen Slash-Commands wurden entfernt!")
        except Exception as e:
            print(f"❌ Fehler beim Löschen: {e}")
        await self.close()

intents = discord.Intents.none()
client = CommandWipeClient(intents=intents)
asyncio.run(client.start(DISCORD_TOKEN))
