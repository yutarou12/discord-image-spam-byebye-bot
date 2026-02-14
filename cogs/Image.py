import os
from datetime import datetime, timezone

import discord
from discord import app_commands

from libs.OriginFunction import is_image_attachment, sha256_digest, normalize_name

MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "8"))
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


class ImageCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.logger = bot.logger
        self.storage = bot.storage
    
    image_group = app_commands.Group(name="image", description="Manage images in lists")

    @image_group.command(name="add", description="Add an image to a list")
    @app_commands.describe(list_name="Target list name", image_name="Image name", image="Image file")
    async def image_add(
        self,
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

        data = await self.storage.load()
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

        await self.storage.save(data)
        await interaction.response.send_message("Image added.", ephemeral=True)


    @image_group.command(name="delete", description="Delete an image from a list")
    @app_commands.describe(list_name="Target list name", image_name="Image name")
    async def image_delete(
        self,
        interaction: discord.Interaction,
        list_name: str,
        image_name: str,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command is only for guilds.", ephemeral=True)
            return

        normalized_list_name = normalize_name(list_name)
        normalized_image_name = normalize_name(image_name)

        data = await self.storage.load()
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
        await self.storage.save(data)
        await interaction.response.send_message("Image deleted.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ImageCog(bot))