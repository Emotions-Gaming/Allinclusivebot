import os
import json
import discord

PERSIST_PATH = "persistent_data"

def _get_path(filename):
    if os.path.isabs(filename):
        return filename
    return os.path.join(PERSIST_PATH, filename)

def load_json(filename, default):
    """Lädt eine JSON-Datei. Gibt Default zurück, falls Datei fehlt oder Fehler."""
    path = _get_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filename, data):
    """Speichert Daten in eine JSON-Datei."""
    path = _get_path(filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user):
    """True, wenn User Adminrechte hat oder Guild-Owner ist."""
    try:
        if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
            return True
        if hasattr(user, "guild") and user.id == user.guild.owner_id:
            return True
    except Exception:
        pass
    return False

def has_role(user, role_id):
    """Prüft, ob der User die gegebene Rolle hat."""
    return any(r.id == role_id for r in getattr(user, "roles", []))

def has_any_role(user, role_ids):
    """Prüft, ob der User eine der Rollen in role_ids hat."""
    uroles = set(r.id for r in getattr(user, "roles", []))
    return bool(uroles.intersection(set(role_ids)))

def mention_roles(guild, role_ids):
    """Gibt einen Ping-String für alle Rollen zurück (z. B. '@Role1 @Role2')."""
    mentions = []
    for rid in role_ids:
        role = guild.get_role(rid)
        if role:
            mentions.append(role.mention)
    return " ".join(mentions) if mentions else "@everyone"

def get_member_by_id(guild, user_id):
    """Hilfsfunktion, um ein Mitglied via ID zu bekommen (None, falls nicht gefunden)."""
    try:
        return guild.get_member(user_id)
    except Exception:
        return None

def get_role_by_name(guild, name):
    """Hilfsfunktion, um eine Rolle anhand des Namens zu finden."""
    for role in guild.roles:
        if role.name.lower() == name.lower():
            return role
    return None
