# Space Guide Discord Bot

**Ein modularer, professioneller Discord-Bot für Community- und Teammanagement mit voller Rechtekontrolle, Persistenz, Wiki, Schichtsystem, Strike-System, Übersetzungen und Gemini AI.**

---

## Features

- **100 % Slash-Commands als Guild-Commands:**  
  Jeder sieht alle Befehle, aber Rechte werden im Bot geprüft.
- **Feingranulare Rechteverwaltung:**  
  Rechte an Commands können granular per Rolle/Person vergeben/entzogen werden.
- **Persistenz & Backups:**  
  Alle wichtigen Daten persistent und automatisch gesichert, Restore auf Knopfdruck.
- **Schichtsystem:**  
  Dienstübergaben inkl. Voice-Move, Logging, DM-Benachrichtigung, Schichtgruppen.
- **Alarm/Schicht-Claim:**  
  Lead kann Schichten vergeben oder User können sie claimen, alles mit Logging & DMs.
- **Strike-System:**  
  Formale Verwarnungen, automatische Strafen, Rollenbindung, eigene Statusmeldungen.
- **Wiki-System:**  
  In-Discord-Wiki, Editier-/Backup-/Restore-Optionen, Dropdown für Seitenwahl.
- **Translation-System (mit Google Gemini 1.5 Flash):**  
  Private Übersetzungssessions, Profilwahl, Prompterweiterung, Session-Logs.
- **Guided Setup:**  
  Kein manuelles Channel/ID-Handling, alles über /startsetup.
- **Schöne User-Experience:**  
  Blurple-Design, Embeds, Copy-Buttons, ausführliche & freundliche Fehlermeldungen.

---

## Installation

1. **Python 3.10+ installieren**
2. **Projekt klonen:**  
   `git clone`
   `cd space-guide-bot`
3. **Abhängigkeiten installieren:**  
   `pip install -r requirements.txt`
4. **.env anlegen und konfigurieren:**  
   Beispiel:

   DISCORD_TOKEN=dein-discord-bot-token  
   GUILD_ID=123456789012345678  
   GOOGLE_API_KEY=dein-gemini-api-key  

---

## Quickstart

`python bot.py`

Der Bot synchronisiert alle Slash-Commands für deine Guild, lädt alle Module und ist sofort bereit!  
Alle Commands sind für alle User sichtbar, aber Rechte werden im Code geprüft.

---

## Projektstruktur

space-guide-bot/  
├── alarm.py             (Alarm/Claim-System)  
├── bot.py               (Main-File, Bot-Startup, Cog-Loader, Logging, SlashCommand-Sync)  
├── permissions.py       (Rechteverwaltung, Rollen/Command-Permissions)  
├── persist.py           (Persistenz, Backup/Restore)  
├── schicht.py           (Schichtübergabe-System)  
├── setupbot.py          (Geführtes Setup für alle Hauptsysteme)  
├── strike.py            (Strike/Verwarnungssystem)  
├── translation.py       (Übersetzungs-/Session-System, Gemini-API)  
├── wiki.py              (Wiki-Management)  
├── utils.py             (Hilfsfunktionen: Rechte, JSON, Member, ...)  
├── requirements.txt     (Dependencies)  
├── .gitignore           (Schutz für Secrets/Daten/Cache)  
├── .env                 (NICHT tracken! Siehe .gitignore)  
└── persistent_data/     (Im Betrieb: Daten, Backups, Settings etc.)

---

## Wichtig: .gitignore

Deine `.gitignore` muss Folgendes enthalten, damit keine Secrets oder Nutzerdaten ins Repo gelangen:

.env  
persistent_data/  
railway_data_backup/  
__pycache__/  
*.pyc  
*.pyo  
.idea/  
.vscode/  
.DS_Store  
*.log

---

## Rechteverwaltung & UX

- Jeder User sieht alle Slash-Commands, aber nur Berechtigte können sie ausführen.
- Rechte werden per Command vergeben/entzogen (z.B. `/befehlpermission`).  
  Admins können mit `/refreshpermissions` alles updaten.
- Schöne Fehlermeldungen für User, falls Rechte fehlen.
- Guild-Only: Alles ist nur auf deinem Server sichtbar und sofort nach jedem Update verfügbar.

---

## Übersetzung & Gemini AI

- Für Übersetzungen wird Google Gemini 1.5 Flash genutzt.
- API-Key in `.env` hinterlegen (`GOOGLE_API_KEY=...`).
- Profile/Styles, Prompts, Logs, Sessions direkt im Bot verwaltbar.

---

## Setup & Wartung

- Nach jedem größeren Update:  
  `/refreshposts` – alle Menüs neu posten  
  `/refreshpermissions` – Rechte neu synchronisieren
- Bei Crash:  
  `/backupnow` (Backup), `/restorenow` (Restore aus letztem Backup)

---

## Lizenz & Support

Private Work-In-Progress.  
Für Support oder Verbesserungen: [Kontakt Discord oder GitHub-Issue]

---

**Viel Erfolg mit Space Guide!**  
*Modular. Sicher. Discord für Pros.*
