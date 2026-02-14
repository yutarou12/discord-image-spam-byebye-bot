import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import discord
from discord import app_commands

DATA_PATH = Path(os.getenv("DATA_PATH", "data/storage.json"))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "8"))
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


def normalize_name(name: str) -> str:
    return name.strip().lower()


def is_image_attachment(attachment: discord.Attachment) -> bool:
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
    return Path(attachment.filename).suffix.lower() in ALLOWED_EXTENSIONS


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("image-spam-bot")

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
storage = Storage(DATA_PATH)


def ensure_guild_entry(data: Dict[str, Any], guild_id: str) -> Dict[str, Any]:
    if guild_id not in data["guilds"]:
        data["guilds"][guild_id] = {"registered_lists": []}
    return data["guilds"][guild_id]


@tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("pong", ephemeral=True)


list_group = app_commands.Group(name="list", description="Manage banned image lists")
image_group = app_commands.Group(name="image", description="Manage images in lists")


@list_group.command(name="create", description="Create a banned image list")
@app_commands.describe(name="List name")
async def list_create(interaction: discord.Interaction, name: str) -> None:
    if not interaction.guild:
        await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
        return

    list_name = normalize_name(name)
    if not list_name:
        await interaction.response.send_message("List name is required.", ephemeral=True)
        return

    data = await storage.load()
    if list_name in data["lists"]:
        await interaction.response.send_message("List name already exists.", ephemeral=True)
        return

    data["lists"][list_name] = {
        "owner_guild_id": str(interaction.guild.id),
        "shared": False,
        "images": {},
    }
    guild_entry = ensure_guild_entry(data, str(interaction.guild.id))
    if list_name not in guild_entry["registered_lists"]:
        guild_entry["registered_lists"].append(list_name)

    await storage.save(data)
    await interaction.response.send_message("List created and registered.", ephemeral=True)


@list_group.command(name="share", description="Share all lists from this guild")
async def list_share(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
        return

    data = await storage.load()
    shared_lists = []
    for list_name, list_data in data["lists"].items():
        if list_data["owner_guild_id"] == str(interaction.guild.id):
            list_data["shared"] = True
            shared_lists.append(list_name)

    if not shared_lists:
        await interaction.response.send_message("No lists found to share.", ephemeral=True)
        return

    await storage.save(data)
    await interaction.response.send_message(
        "Shared lists: " + ", ".join(shared_lists),
        ephemeral=True,
    )


@list_group.command(name="regist", description="Register a shared list to this guild")
@app_commands.describe(name="Shared list name")
async def list_regist(interaction: discord.Interaction, name: str) -> None:
    if not interaction.guild:
        await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
        return

    list_name = normalize_name(name)
    data = await storage.load()
    list_data = data["lists"].get(list_name)
    if not list_data:
        await interaction.response.send_message("List not found.", ephemeral=True)
        return

    if not list_data.get("shared", False):
        await interaction.response.send_message("List is not shared.", ephemeral=True)
        return

    guild_entry = ensure_guild_entry(data, str(interaction.guild.id))
    if list_name in guild_entry["registered_lists"]:
        await interaction.response.send_message("List already registered.", ephemeral=True)
        return

    guild_entry["registered_lists"].append(list_name)
    await storage.save(data)
    await interaction.response.send_message("List registered.", ephemeral=True)


@image_group.command(name="add", description="Add an image to a list")
@app_commands.describe(list_name="Target list name", image_name="Image name", image="Image file")
async def image_add(
    interaction: discord.Interaction,
    list_name: str,
    image_name: str,
    image: discord.Attachment,
) -> None:
    if not interaction.guild:
        await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
        return

    normalized_list_name = normalize_name(list_name)
    normalized_image_name = normalize_name(image_name)

    if not normalized_list_name or not normalized_image_name:
        await interaction.response.send_message("List name and image name are required.", ephemeral=True)
        return

    if not is_image_attachment(image):
        await interaction.response.send_message("Only image attachments are allowed.", ephemeral=True)
        return

    if image.size and image.size > MAX_IMAGE_SIZE_BYTES:
        await interaction.response.send_message(
            f"Image is too large (max {MAX_IMAGE_SIZE_MB}MB).",
            ephemeral=True,
        )
        return

    data = await storage.load()
    list_data = data["lists"].get(normalized_list_name)
    if not list_data:
        await interaction.response.send_message("List not found.", ephemeral=True)
        return

    if list_data["owner_guild_id"] != str(interaction.guild.id):
        await interaction.response.send_message("You can only edit your own lists.", ephemeral=True)
        return

    if normalized_image_name in list_data["images"]:
        await interaction.response.send_message("Image name already exists.", ephemeral=True)
        return

    image_bytes = await image.read()
    image_hash = sha256_digest(image_bytes)

    list_data["images"][normalized_image_name] = {
        "sha256": image_hash,
        "filename": image.filename,
        "content_type": image.content_type,
        "size": image.size,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await storage.save(data)
    await interaction.response.send_message("Image added.", ephemeral=True)


@image_group.command(name="delete", description="Delete an image from a list")
@app_commands.describe(list_name="Target list name", image_name="Image name")
async def image_delete(
    interaction: discord.Interaction,
    list_name: str,
    image_name: str,
) -> None:
    if not interaction.guild:
        await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
        return

    normalized_list_name = normalize_name(list_name)
    normalized_image_name = normalize_name(image_name)

    data = await storage.load()
    list_data = data["lists"].get(normalized_list_name)
    if not list_data:
        await interaction.response.send_message("List not found.", ephemeral=True)
        return

    if list_data["owner_guild_id"] != str(interaction.guild.id):
        await interaction.response.send_message("You can only edit your own lists.", ephemeral=True)
        return

    if normalized_image_name not in list_data["images"]:
        await interaction.response.send_message("Image name not found.", ephemeral=True)
        return

    del list_data["images"][normalized_image_name]
    await storage.save(data)
    await interaction.response.send_message("Image deleted.", ephemeral=True)


tree.add_command(list_group)
tree.add_command(image_group)


@bot.event
async def on_ready() -> None:
    await tree.sync()
    logger.info("Logged in as %s", bot.user)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or not message.guild:
        return

    if not message.attachments:
        return

    data = await storage.load()
    guild_entry = data["guilds"].get(str(message.guild.id))
    if not guild_entry:
        return

    registered_lists = guild_entry.get("registered_lists", [])
    if not registered_lists:
        return

    banned_hashes = set()
    for list_name in registered_lists:
        list_data = data["lists"].get(list_name)
        if not list_data:
            continue
        for image_data in list_data.get("images", {}).values():
            banned_hashes.add(image_data.get("sha256"))

    if not banned_hashes:
        return

    for attachment in message.attachments:
        if not is_image_attachment(attachment):
            continue
        if attachment.size and attachment.size > MAX_IMAGE_SIZE_BYTES:
            continue
        image_bytes = await attachment.read()
        image_hash = sha256_digest(image_bytes)
        if image_hash in banned_hashes:
            await message.delete()
            return


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")
    bot.run(token)
