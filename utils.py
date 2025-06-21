# utils.py
import os
import json
import discord

PERSIST_DIR = "persistent_data"

def safe_path(filename):
    """Returns the path in the persistent_data directory."""
    return os.path.join(PERSIST_DIR, filename)

def load_json(filename, default=None):
    """Lädt eine JSON-Datei oder gibt den Default-Wert zurück."""
    path = safe_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(filename, data):
    """Speichert Daten als JSON-Datei."""
    path = safe_path(filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user):
    """Prüft, ob ein User Admin ist."""
    perms = getattr(user, "guild_permissions", None)
    return perms and perms.administrator

def has_role(user, role_id):
    """Prüft, ob der User eine bestimmte Rolle hat."""
    return any(r.id == role_id for r in getattr(user, "roles", []))

def has_any_role(user, role_ids):
    """Prüft, ob der User mindestens eine der Rollen hat."""
    uroles = [r.id for r in getattr(user, "roles", [])]
    return any(r in uroles for r in role_ids)

def try_dm(user, message):
    """Versucht, einem User eine DM zu schicken (ohne zu crashen)."""
    try:
        return user.send(message)
    except Exception:
        return None

def get_log_channel(guild, filename, key="log_channel_id"):
    """Lädt die Log-Channel-ID aus einer JSON und gibt den Channel zurück."""
    cfg = load_json(filename, {})
    log_id = cfg.get(key)
    if not log_id:
        return None
    return guild.get_channel(log_id)
