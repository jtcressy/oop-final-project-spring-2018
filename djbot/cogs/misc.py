import discord
import logging
import asyncio
from discord.ext import commands
from djbot import logger_setup


class Misc:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)

    @commands.command(hidden=True, pass_context=True)
    async def clear(self, ctx, count):
        """Clear a chat channel of X lines"""
        async with ctx.message.channel.typing():
            count = int(count)
            await ctx.message.channel.purge(limit=count)
            logging.debug(f"Cleared {count} messages from channel {ctx.message.channel} in server {ctx.message.guild}")
            outmsg = await ctx.message.channel.send(f"✅Cleared {count} messages")
        await self.del_msgs(outmsg)

    async def del_msgs(self, *args: discord.Message, delay: int=3):
        """
        Delete messages with 5 second delay
        :param args: discord.Message objects to be deleted
        :param delay: Delay in seconds (int)
        :return: None
        """
        await asyncio.sleep(
            delay
        )
        for msg in args:
            try:
                await msg.delete()
            except AttributeError:  # handle msg == None
                pass


def setup(bot: discord.ext.commands.Bot):
    bot.add_cog(Misc(bot))
