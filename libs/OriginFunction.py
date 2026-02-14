import json
import discord
import hashlib
import asyncio

from pathlib import Path
from typing import Any, Dict

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


def normalize_name(name: str) -> str:
    return name.strip().lower()


def is_image_attachment(attachment: discord.Attachment) -> bool:
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
    return Path(attachment.filename).suffix.lower() in ALLOWED_EXTENSIONS


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_guild_entry(data: Dict[str, Any], guild_id: str) -> Dict[str, Any]:
    if guild_id not in data["guilds"]:
        data["guilds"][guild_id] = {"registered_lists": []}
    return data["guilds"][guild_id]


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = asyncio.Lock()

    async def load(self) -> Dict[str, Any]:
        async with self.lock:
            return self._load_unlocked()

    async def save(self, data: Dict[str, Any]) -> None:
        async with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file_handle:
                json.dump(data, file_handle, ensure_ascii=True, indent=2)

    def _load_unlocked(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"lists": {}, "guilds": {}}
        with self.path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)