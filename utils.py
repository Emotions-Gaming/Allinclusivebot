import os
import json
import tempfile
import re
from datetime import datetime
import logging
import discord
from discord import Member, Guild

# Pfad zum Verzeichnis für persistente Daten
tmp = os.getenv("PERSISTENT_PATH", "persistent_data")
PERSISTENT_PATH = tmp if tmp.endswith(os.sep) else tmp + os.sep

# Logging konfigurieren
logger = logging.getLogger(__name__)

# --- Directory sicherstellen ---
if not os.path.isdir(PERSISTENT_PATH):
    os.makedirs(PERSISTENT_PATH, exist_ok=True)

# --- JSON-Helper ---

def load_json(filename: str, fallback=None):
    """
    Lädt eine JSON-Datei aus dem PERSISTENT_PATH.
    Gibt fallback zurück, falls Datei fehlt oder fehlerhaft ist.
    """
    path = os.path.join(PERSISTENT_PATH, filename)
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden von json '{filename}': {e}")
        return fallback


def save_json(filename: str, data):
    """
    Speichert ein Python-Objekt als JSON-Datei atomar im PERSISTENT_PATH.
    """
    path = os.path.join(PERSISTENT_PATH, filename)
    dirpath = os.path.dirname(path)
    os.makedirs(dirpath, exist_ok=True)
    # Atomare Speicherung über tempfile
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, dir=dirpath, encoding='utf-8') as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            tempname = tf.name
        os.replace(tempname, path)
    except Exception as e:
        logger.error(f"Fehler beim Speichern von json '{filename}': {e}")
        raise

# --- Rechte-Checks ---

def is_admin(member: Member) -> bool:
    """
    Prüft, ob ein Member Administrator-Rechte im Guild hat.
    """
    try:
        return member.guild_permissions.administrator
    except Exception:
        return False


def has_role(member: Member, role_id: int) -> bool:
    """
    Prüft, ob der Member eine bestimmte Rolle besitzt.
    """
    return any(role.id == role_id for role in member.roles)


def has_any_role(member: Member, role_ids: list[int]) -> bool:
    """
    Prüft, ob der Member eine der Rollen in role_ids besitzt.
    """
    return any(role.id in role_ids for role in member.roles)

# --- Member-Funktionen ---

def get_member_by_id(guild: Guild, user_id: int) -> Member | None:
    """
    Liefert das Member-Objekt für eine gegebene User-ID, oder None.
    """
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        return guild.fetch_member(user_id)
    except Exception:
        return None


def mention_roles(guild: Guild, role_ids: list[int]) -> str:
    """
    Gibt eine durch Leerzeichen getrennte String-Liste von Role-Mentions zurück.
    Rollen, die nicht mehr existieren, werden gefiltert.
    """
    mentions = []
    for rid in role_ids:
        role = guild.get_role(rid)
        if role:
            mentions.append(role.mention)
    return ' '.join(mentions)

# --- Sonstige Utilitys ---

def parse_mention(mention: str) -> int | None:
    """
    Extrahiert eine ID aus einem Discord-Mention-String wie <@123456789> oder <@&987654321>.
    """
    match = re.match(r'<@&?(\d+)>', mention)
    if match:
        return int(match.group(1))
    return None


def to_display_time(dt: datetime) -> str:
    """
    Formatiert einen datetime in einen lesbaren Zeit-String.
    """
    if not isinstance(dt, datetime):
        return str(dt)
    return dt.strftime('%Y-%m-%d %H:%M:%S')
