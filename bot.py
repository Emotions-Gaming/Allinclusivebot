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
            # Hole die App-ID (=Bot-ID)
            app_info = await self.application_info()
            app_id = app_info.id

            # Hole alle globalen Commands (RAW API)
            commands = await self.http.get_global_commands(app_id)
            print(f"  → Globale Commands gefunden: {len(commands)}")
            for cmd in commands:
                print(f"    - {cmd['name']}")

            # Lösche alle globalen Commands (RAW API)
            await self.http.bulk_upsert_global_commands(app_id, [])
            print("✅ Alle globalen Slash-Commands wurden entfernt!")
        except Exception as e:
            print(f"❌ Fehler beim Löschen: {e}")
        await self.close()

intents = discord.Intents.none()
client = CommandWipeClient(intents=intents)
asyncio.run(client.start(DISCORD_TOKEN))
