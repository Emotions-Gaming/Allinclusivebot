# utils.py

import discord
import json
import os
import aiofiles
import asyncio
from datetime import datetime, timezone

# ========== Rechte-Prüfungen ==========

def is_admin(member: discord.Member) -> bool:
    """Checkt, ob ein Member Adminrechte hat."""
    if hasattr(member, "guild_permissions"):
        return member.guild_permissions.administrator
    return False

def has_role(member: discord.Member, role_id: int) -> bool:
    """Checkt, ob ein Member eine bestimmte Rolle besitzt."""
    return any(role.id == role_id for role in getattr(member, "roles", []))

def has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    """Checkt, ob ein Member mindestens eine Rolle aus der Liste besitzt."""
    return any(role.id in role_ids for role in getattr(member, "roles", []))


# ========== Member-/Rollen-Helfer ==========

def get_member_by_id(guild: discord.Guild, user_id: int) -> discord.Member | None:
    """Holt das Member-Objekt per User-ID (oder None)."""
    return guild.get_member(user_id)

def mention_roles(guild: discord.Guild, role_ids: list[int]) -> str:
    """Gibt eine @-Mention-Liste aller gültigen Rollen zurück (für Embeds, Pings, etc.)."""
    mentions = []
    for rid in role_ids:
        role = guild.get_role(rid)
        if role:
            mentions.append(role.mention)
    return " ".join(mentions) if mentions else "*(keine Rollen gefunden)*"


# ========== JSON-Handling (async) ==========

async def load_json(path: str, fallback=None):
    """Lädt eine JSON-Datei asynchron. Bei Fehler gibt es fallback zurück."""
    if not os.path.exists(path):
        return fallback if fallback is not None else {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except Exception:
        return fallback if fallback is not None else {}

async def save_json(path: str, data):
    """Speichert Daten als JSON asynchron & atomar."""
    tmp_path = path + ".tmp"
    try:
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        await aiofiles.os.replace(tmp_path, path)
    except Exception as e:
        print(f"[utils.save_json] Fehler beim Speichern von {path}: {e}")


# ========== Atomic File Copy (z.B. für Backups) ==========

async def atomic_copy(src: str, dst: str):
    """Kopiert eine Datei atomar (async, für Backups)."""
    try:
        async with aiofiles.open(src, "rb") as fsrc:
            data = await fsrc.read()
        async with aiofiles.open(dst, "wb") as fdst:
            await fdst.write(data)
    except Exception as e:
        print(f"[utils.atomic_copy] Fehler beim Kopieren {src} -> {dst}: {e}")

# ========== Sonstige Utilities ==========

def parse_mention(s: str) -> int | None:
    """
    Extrahiert eine ID aus <@123>, <@!123>, <@&123>.
    Gibt int-ID oder None zurück.
    """
    import re
    match = re.search(r"<@!?(\d+)>", s) or re.search(r"<@&(\d+)>", s)
    return int(match.group(1)) if match else None

def to_display_time(dt) -> str:
    """Wandelt UTC/ISO oder UNIX-Timestamp in schöne Uhrzeit um."""
    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(dt, tz=timezone.utc)
    elif isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M Uhr")
    return str(dt)


# ========== Schöne Discord-Nachrichten (UX) ==========

async def send_ephemeral(interaction: discord.Interaction, text: str, emoji: str = None, color: discord.Color = None, **kwargs):
    """
    Schickt eine schöne ephemeral Embed-Nachricht.
    Optional: Emoji & Farbe (default=Blau).
    """
    color = color or discord.Color.blurple()
    if emoji:
        title = f"{emoji} {text}"
    else:
        title = text
    embed = discord.Embed(description=title, color=color)
    await interaction.response.send_message(embed=embed, ephemeral=True, **kwargs)


async def send_permission_denied(interaction: discord.Interaction):
    """Einheitliche Meldung bei fehlender Berechtigung (immer hübsch & ephemeral)."""
    await send_ephemeral(
        interaction,
        text="Du bist nicht berechtigt, diesen Befehl zu nutzen.",
        emoji="🚫",
        color=discord.Color.red()
    )

async def send_success(interaction: discord.Interaction, text: str = "Aktion erfolgreich!"):
    """Erfolgsmeldung, immer hübsch."""
    await send_ephemeral(
        interaction,
        text=text,
        emoji="✅",
        color=discord.Color.green()
    )

async def send_error(interaction: discord.Interaction, text: str = "Es ist ein Fehler aufgetreten."):
    """Fehlermeldung (rot)."""
    await send_ephemeral(
        interaction,
        text=text,
        emoji="❌",
        color=discord.Color.red()
    )

# ========== Optional: Erweiterbare UX-Tools (Future-Proof) ==========

def pretty_role_list(guild: discord.Guild, ids: list[int]) -> str:
    """Gibt alle Rollen als Zeile aus (für Logs oder Embeds)."""
    return ", ".join(r.mention for r in [guild.get_role(i) for i in ids] if r) or "*Keine*"

def pretty_user(user: discord.User | discord.Member) -> str:
    """Gibt einen schön formatierten Username mit Mention zurück."""
    return f"{user.mention} (`{user.name}#{user.discriminator}`)"

# Hier kannst du beliebig weitere kleine Tools nachziehen.

# ========== END OF FILE ==========
