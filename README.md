# Space Guide Discord Bot

## 1. Environment Variables

Lege folgende Variablen im Railway-Dashboard (_Deployments → Variables_) an:

DISCORD_TOKEN=dein_discord_bot_token
GOOGLE_API_KEY=dein_gemini_google_api_key
GUILD_ID=deine_guild_id # Als Zahl! Beispiel: 1249813174731931740


**Alternativ für lokalen Betrieb:**  
Erstelle eine `.env`-Datei mit denselben Werten im Projekt-Root (wird automatisch geladen, niemals committen!).

---

## 2. Persistent Data / Backup-Ordner

**WICHTIG:**  
Alle wichtigen Daten liegen im Ordner `/persistent_data/`  
Lege IMMER ein Railway Volume (z. B. `/app/persistent_data`) an, sonst gehen bei jedem Deploy/Update ALLE Daten verloren!

- **Nie löschen oder überschreiben!**
- Enthält:
    - Alle JSON-Konfigurationen (Strikes, Wiki, Schicht, Alarm etc.)
    - Backups & Logdateien

---

## 3. Start & Deploy

**Lokaler Start:**

# Projekt klonen oder kopieren
pip install -r requirements.txt
python bot.py

Railway Deployment:

Füge das Projekt zu Railway hinzu.

Lege die Environment Variables (siehe oben) an.

Erstelle und mounte ein Railway Volume auf /app/persistent_data

Starte/Deploye das Projekt.

## 4. Features (Kurzüberblick)
**Translation-System:**
Übersetzt Texte mit Rollen/Profil-Auswahl.

**Strike-System:**
Vergeben, Löschen, Verwalten von Strikes – inklusive Auto-Rollen-Vergabe.

**Schichtsystem:**
Schichtübergaben, Rollenverwaltung, Logging.

**Wiki-System:**
Discord-basiertes, interaktives Wiki mit Bearbeitung, Backup, Wiederherstellung.

**Alarm-Schicht-System:**
(Optional) Alarmrollen, Schichtanfragen, Log-Kanal, Claim-Funktion.

## 5. Datenstruktur
**Alle Konfigurations- und Logdateien befinden sich in /persistent_data/:**

profiles.json

schicht_config.json

schicht_rights.json

strike_data.json

strike_roles.json

strike_autorole.json

wiki_pages.json

wiki_backup.json

alarm_config.json

alarm_log.json

commands_permissions.json

u. v. m.

## 6. Hinweise
Die meisten Slash-Befehle sind nur für bestimmte Rollen/Admins verfügbar.

Um Befehlsrechte zu verwalten, verwende /refreshPermissions und /BefehlPermission [Befehl] [Role].

Das System ist so aufgebaut, dass alle Daten erhalten bleiben (Railway Volume!) – kein Datenverlust nach Deploys.

## 7. Support
**Bei Problemen oder Fragen gerne im Discord melden oder ein GitHub-Issue erstellen.**

