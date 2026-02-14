import os

import discord
from discord.ext import commands

from libs.OriginFunction import is_image_attachment, sha256_digest

MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "8"))
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024


class EventCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.logger = bot.logger
        self.storage = bot.storage

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        if not message.attachments:
            return

        data = await self.storage.load()
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
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.tree.sync()
        self.logger.info("Logged in as %s", self.bot.user)