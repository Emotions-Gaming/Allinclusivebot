import os
import json

PERSIST_PATH = "persistent_data"

def _get_path(filename):
    """Gibt absoluten Pfad für Persistenzdatei zurück."""
    if os.path.isabs(filename):
        return filename
    return os.path.join(PERSIST_PATH, filename)

def load_json(filename, default=None):
    """Lädt JSON-Datei. Gibt Default zurück, falls Datei fehlt oder fehlerhaft ist."""
    path = _get_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filename, data):
    """Speichert Dictionary als JSON (pretty)"""
    path = _get_path(filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Discord Helper (nicht zwingend alle, aber deine wichtigsten):
def is_admin(user):
    """Check: User ist Admin oder Guild-Owner."""
    try:
        if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
            return True
        if hasattr(user, "guild") and user.id == user.guild.owner_id:
            return True
    except Exception:
        pass
    return False

def has_role(user, role_id):
    """True, wenn User die Role hat."""
    return any(r.id == role_id for r in getattr(user, "roles", []))

def has_any_role(user, role_ids):
    """True, wenn User eine der Rollen hat."""
    user_roles = set(r.id for r in getattr(user, "roles", []))
    return bool(user_roles.intersection(set(role_ids)))

def mention_roles(guild, role_ids):
    """Gibt eine Mention-Liste für mehrere Rollen (Ping)."""
    mentions = []
    for rid in role_ids:
        role = guild.get_role(rid)
        if role:
            mentions.append(role.mention)
    return " ".join(mentions) if mentions else "@everyone"

def get_member_by_id(guild, user_id):
    """Gibt Member-Objekt zu user_id zurück oder None."""
    try:
        return guild.get_member(user_id)
    except Exception:
        return None

def get_role_by_name(guild, name):
    """Sucht eine Rolle nach Name (case-insensitive)."""
    for role in guild.roles:
        if role.name.lower() == name.lower():
            return role
    return None
