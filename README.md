# Space Guide Discord Bot

Ein multifunktionaler Discord-Bot für Community- und Teammanagement.  
**Features:** Übersetzung, Strike-System, Schichtübergaben, Alarmschicht-System, Wiki und mehr.

---

## Features im Überblick

- **Übersetzungs-Bot:** KI-gestützte Übersetzungen (Google Gemini/GPT), private Sessions, anpassbare Profile
- **Strike-System:** Strikes mit Begründung, automatischer Rollenvergabe, Admin-Dashboard, Übersicht & Verwaltung
- **Schichtübergabe:** Rollengestützte Übergaben inkl. Voice- und Logsupport, Rechteverwaltung für Befehle
- **Alarmschicht-System:** Flexible Alarmanfragen mit Rollen, Claim-Funktion & Log, benutzerdefinierte Alarmrollen
- **Wiki-System:** Speichert Channels als Wiki, Bearbeiten/Löschen, DM-Backup, Restore-Funktion
- **Komplette Rechte-/Befehlsverwaltung:** Slash-Command-Rechte, globale/individuelle Permission-Tools
- **Railway/Cloud-ready:** Volle Datensicherung über Volume, alles bleibt nach Updates erhalten

---

## **Setup**

### 1. Environment Variables

Lege folgende Variablen im Railway-Dashboard (_Deployments → Variables_) an:

```env
DISCORD_TOKEN=dein_discord_bot_token
GOOGLE_API_KEY=dein_gemini_google_api_key
GUILD_ID=deine_guild_id  # Als Zahl! Beispiel: 1249813174731931740
Alternativ für lokalen Betrieb:
.env-Datei mit denselben Werten (wird automatisch geladen, niemals committen!)

2. Persistent Data/Backup-Ordner
WICHTIG:
Alle wichtigen Daten liegen in /persistent_data/
Lege IMMER ein Railway Volume (z.B. /app/persistent_data) an, sonst gehen bei jedem Deploy/Update ALLE Daten verloren!

Nie löschen oder überschreiben!
Enthält:

Alle JSON-Konfigurationen (Strikes, Wiki, Schicht, Alarm etc.)

Backups & Logdateien

3. Start & Deploy
Lokaler Start:

bash
Kopieren
Bearbeiten
pip install -r requirements.txt
python bot.py
Railway Deployment:

Füge das Projekt zu Railway hinzu

Lege das Volume /persistent_data (Pfad: /app/persistent_data) an

Setze die Environment Variables

Starte mit python bot.py

Dateiübersicht
/persistent_data/

profiles.json – Übersetzungs-Profile

strike_data.json – Alle Strikes

strike_roles.json, strike_autorole.json – Rollenmanagement für Strikes

schicht_config.json, schicht_rights.json – Schichtübergabe-Konfig & Rechte

alarm_config.json, alarm_log.json – Alarmschicht-System

wiki_pages.json, wiki_backup.json – Wiki/Backup

commands_permissions.json – Custom Slash-Command-Permissions

...weitere Config-/Logdateien, siehe Codestruktur

/requirements.txt – Alle benötigten Python-Pakete

/bot.py – Hauptbot (alle Systeme integriert)

README.md – Diese Anleitung

Wichtige Befehle & Hinweise
Slash-Command-Rechte:
Nutze /refreshCommands & /refreshPermissions um Befehle neu zu laden und Berechtigungen festzulegen
(Erstmal alle Commands aktualisieren, dann für jeden Command erlaubte Rollen setzen – der Bot führt durch das Menü!)

Alarmschicht/Strike/Schicht/Bot-Daten gehen NIE verloren, solange /persistent_data erhalten bleibt.

Nach jedem Update/Restart:

Alle Daten und Einstellungen bleiben erhalten, wenn Volume verwendet wird

Bei Problemen: Rechte oder Befehle mit /refreshCommands und /refreshPermissions zurücksetzen

Security & Tipps
.env-Datei niemals committen (immer in .gitignore)

Keine JSON-Dateien manuell verändern, außer du weißt genau was du tust

Bei größeren Änderungen/Bugfixes:

Mache vorher ein Backup von /persistent_data/

Die persistent_data-Dateien dienen als Single Source of Truth – alles wird dort abgelegt!

Troubleshooting
Doppelte Slash-Commands?
/refreshCommands ausführen, ggf. /refreshPermissions danach

Berechtigungen funktionieren nicht?
Mit /refreshPermissions neue Rollen/Berechtigungen festlegen

Weitere Hilfe, Bugs oder Feature Requests?
Melde dich bei Martin Schulze oder im Discord.