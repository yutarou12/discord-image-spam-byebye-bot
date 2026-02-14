import asyncio
import json

from pathlib import Path
from typing import Any, Dict

import discord
from discord import app_commands

from libs.OriginFunction import normalize_name, ensure_guild_entry

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


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


class ListCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.logger = bot.logger
        self.storage = bot.storage

    list_group = app_commands.Group(name="list", description="Manage banned image lists")

    @list_group.command(name="create", description="Create a banned image list")
    @app_commands.describe(name="List name")
    async def list_create(self, interaction: discord.Interaction, name: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
            return

        list_name = normalize_name(name)
        if not list_name:
            await interaction.response.send_message("List name is required.", ephemeral=True)
            return

        data = await self.storage.load()
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

        await self.storage.save(data)
        await interaction.response.send_message("List created and registered.", ephemeral=True)


    @list_group.command(name="share", description="Share all lists from this guild")
    async def list_share(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
            return

        data = await self.storage.load()
        shared_lists = []
        for list_name, list_data in data["lists"].items():
            if list_data["owner_guild_id"] == str(interaction.guild.id):
                list_data["shared"] = True
                shared_lists.append(list_name)

        if not shared_lists:
            await interaction.response.send_message("No lists found to share.", ephemeral=True)
            return

        await self.storage.save(data)
        await interaction.response.send_message(
            "Shared lists: " + ", ".join(shared_lists),
            ephemeral=True,
        )


    @list_group.command(name="regist", description="Register a shared list to this guild")
    @app_commands.describe(name="Shared list name")
    async def list_regist(self, interaction: discord.Interaction, name: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
            return

        list_name = normalize_name(name)
        data = await self.storage.load()
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
        await self.storage.save(data)
        await interaction.response.send_message("List registered.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ListCog(bot))