import os
import json
import discord

# -------------------- #
# 1. Pfad für Daten (persistent_data/)
# -------------------- #
DATA_DIR = "persistent_data"

def get_data_path(filename):
    """Gibt den vollständigen Pfad zu einer JSON-Datei im persistent_data-Ordner zurück."""
    return os.path.join(DATA_DIR, filename)

# -------------------- #
# 2. JSON-Dateien sicher laden/speichern
# -------------------- #
def load_json(filename, default=None):
    path = get_data_path(filename)
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(filename, data):
    path = get_data_path(filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fehler beim Speichern von {filename}: {e}")

# -------------------- #
# 3. Rechteprüfungen für User
# -------------------- #
def is_admin(user: discord.abc.User):
    # Discord.py: guild_permissions nur bei Member!
    return getattr(user, "guild_permissions", None) and user.guild_permissions.administrator

def has_role(user, role_id):
    """True, wenn User eine bestimmte Rolle besitzt (by ID)."""
    return any(getattr(r, "id", None) == role_id for r in getattr(user, "roles", []))

def has_any_role(user, role_ids):
    """True, wenn User mindestens eine Rolle aus role_ids besitzt."""
    user_roles = {getattr(r, "id", None) for r in getattr(user, "roles", [])}
    return bool(user_roles.intersection(set(role_ids)))

# -------------------- #
# 4. Optional: Helper für User-Mentions, etc.
# -------------------- #
def mention(user_or_id):
    """Gibt eine Discord-Mention für einen User oder eine ID zurück."""
    if isinstance(user_or_id, int):
        return f"<@{user_or_id}>"
    elif hasattr(user_or_id, "mention"):
        return user_or_id.mention
    else:
        return str(user_or_id)

# Weitere Hilfsfunktionen je nach Bedarf ergänzen...
