# permissions.py

import json
import os
from discord import app_commands, Interaction

PERMISSIONS_PATH = "persistent_data/commands_permissions.json"

def load_permissions():
    """Lädt das Rollen-Permissions-Mapping aus JSON (oder gibt {} zurück)."""
    try:
        with open(PERMISSIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_permissions(data):
    """Speichert das Mapping als JSON."""
    os.makedirs(os.path.dirname(PERMISSIONS_PATH), exist_ok=True)
    with open(PERMISSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def has_permission_for(command_name):
    """
    Universal-Permission-Check für Slash-Commands.
    Erlaubt Command nur, wenn:
      - User Admin ist ODER
      - User eine der erlaubten Rollen für den Command hat (laut JSON)
    Usage in jedem System:
        @has_permission_for("strikegive")
        async def strikegive(...): ...
    """
    async def predicate(interaction: Interaction):
        # Immer: Admins dürfen alles
        if interaction.user.guild_permissions.administrator:
            return True
        perms = load_permissions()
        allowed_roles = perms.get(command_name, [])
        if not allowed_roles:
            # Keine erlaubten Rollen: Niemand außer Admin darf den Command
            return False
        user_role_ids = [role.id for role in getattr(interaction.user, "roles", [])]
        return any(role_id in user_role_ids for role_id in allowed_roles)
    return app_commands.check(predicate)

