import logging
import os
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

from libs.OriginFunction import Storage

DATA_PATH = Path(os.getenv("DATA_PATH", "data/storage.json"))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "8"))


extensions_list = [f[:-3] for f in os.listdir("./cogs") if f.endswith(".py")]


class MyBot(commands.Bot):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def setup_hook(self):
        try:
            await bot.load_extension('jishaku')
        except discord.ext.commands.ExtensionAlreadyLoaded:
            await bot.reload_extension('jishaku')
        for ext in extensions_list:
            try:
                await bot.load_extension(f'cogs.{ext}')
            except discord.ext.commands.ExtensionAlreadyLoaded:
                await bot.reload_extension(f'cogs.{ext}')

    async def get_context(self, message, *args, **kwargs):
        return await super().get_context(message, *args, **kwargs)
    

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("image-spam-bot")

storage = Storage(DATA_PATH)

bot = MyBot(
    command_prefix=commands.when_mentioned_or('is.'),
    intents=intents,
    allowed_mentions=discord.AllowedMentions(replied_user=False, everyone=False),
    help_command=None
)

bot.logger = logger
bot.storage = storage

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")
    bot.run(token)
