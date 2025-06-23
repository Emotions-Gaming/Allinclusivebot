import os
import json
import logging
from typing import List, Any, Optional
from discord import Member, Guild, Role

# =========================
# 1. Rechte-Checks
# =========================

def is_admin(user: Member) -> bool:
    """
    Prüft, ob der Nutzer die Administrator-Berechtigung hat.
    """
    # user.roles: List[Role]
    return any(getattr(role.permissions, "administrator", False) for role in getattr(user, "roles", []))

def has_role(user: Member, role_id: int) -> bool:
    """
    Prüft, ob der Nutzer eine bestimmte Rolle hat.
    """
    return any(role.id == role_id for role in getattr(user, "roles", []))

def has_any_role(user: Member, role_ids: List[int]) -> bool:
    """
    Prüft, ob der Nutzer mindestens eine Rolle aus einer Liste hat.
    """
    user_role_ids = {role.id for role in getattr(user, "roles", [])}
    return any(rid in user_role_ids for rid in role_ids)

# =========================
# 2. Member- und Rollen-Helfer
# =========================

def get_member_by_id(guild: Guild, user_id: int) -> Optional[Member]:
    """
    Gibt das Member-Objekt zur User-ID zurück (oder None, wenn nicht gefunden).
    """
    return guild.get_member(user_id)

def mention_roles(guild: Guild, role_ids: List[int]) -> str:
    """
    Gibt eine formatierte @Mention-Liste für alle Rollen zurück (nur existierende Rollen).
    """
    mentions = []
    for rid in role_ids:
        role = guild.get_role(rid)
        if role:
            mentions.append(role.mention)
    return " ".join(mentions) if mentions else "Keine Rollen gesetzt"

# =========================
# 3. JSON-Helper
# =========================

def load_json(path: str, fallback: Any = None) -> Any:
    """
    Lädt eine JSON-Datei (UTF-8) und gibt deren Inhalt als Python-Objekt zurück.
    Falls Datei fehlt oder fehlerhaft, gibt fallback zurück.
    """
    if not os.path.exists(path):
        return fallback if fallback is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Fehler beim Laden von {path}: {e}")
        return fallback if fallback is not None else {}

def save_json(path: str, data: Any) -> None:
    """
    Speichert das Python-Objekt atomar als JSON an den gegebenen Pfad.
    Erst als temp-Datei, dann rename (Schutz vor korrupten Daten).
    """
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        logging.error(f"Fehler beim Speichern von {path}: {e}")

# =========================
# 4. Sonstige Utilities
# =========================

def parse_mention(s: str) -> Optional[int]:
    """
    Extrahiert eine User- oder Role-ID aus einem Mention-String.
    Beispiel: '<@1234567890>' oder '<@!1234567890>' oder '<@&1234567890>'
    """
    import re
    match = re.match(r"<@!?(\d+)>", s) or re.match(r"<@&(\d+)>", s)
    if match:
        return int(match.group(1))
    return None

def to_display_time(dt) -> str:
    """
    Wandelt einen datetime-Objekt oder ISO-String/Timestamp in ein lesbares Format um.
    """
    from datetime import datetime
    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(dt)
    elif isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)
    return dt.strftime("%d.%m.%Y, %H:%M")

def get_role_names(guild: Guild, role_ids: List[int]) -> List[str]:
    """
    Gibt die Namen der Rollen zurück (für Logging/Debug).
    """
    return [r.name for r in [guild.get_role(rid) for rid in role_ids] if r]

# =========================
# 5. Logging konfigurieren (einmal pro Bot-Prozess)
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
