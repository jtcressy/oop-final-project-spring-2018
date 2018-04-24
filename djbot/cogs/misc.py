import discord
import logging
from discord.ext import commands
from djbot import logger_setup


class Misc:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)

    @commands.command(hidden=True, pass_context=True)
    async def clear(self, ctx, count):
        """Clear a chat channel of X lines"""
        count = int(count)
        await self.bot.purge_from(ctx.message.channel, limit=count)
        logging.debug(f"Cleared {count} lines from channel {ctx.message.channel} in server {ctx.message.server}")


def setup(bot: discord.ext.commands.Bot):
    bot.add_cog(Misc(bot))
