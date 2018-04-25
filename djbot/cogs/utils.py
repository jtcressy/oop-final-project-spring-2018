import asyncio
import logging

import discord
from discord.ext import commands

from djbot import logger_setup


def is_admin_or_mod():
    def predicate(ctx):
        msg = ctx.message
        ch = msg.channel
        names = ["Admin", "Admins", "Moderator", "Moderators"]
        if not any(discord.utils.get(msg.author.roles, name=name) for name in names):
            raise NotAnAdmin(f"{EMOJIS['fail']} You are not permitted to run this command!")
        return True

    return commands.check(predicate)


class NotAnAdmin(commands.CheckFailure):
    pass


class Utils:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)

    @commands.command(hidden=True, pass_context=True)
    @is_admin_or_mod()
    async def clear(self, ctx, count):
        """Clear a chat channel of X lines"""
        async with ctx.message.channel.typing():
            count = int(count)
            await ctx.message.channel.purge(limit=count)
            logging.debug(f"Cleared {count} messages from channel {ctx.message.channel} in server {ctx.message.guild}")
            outmsg = await ctx.message.channel.send(f"✅Cleared {count} messages")
        await self.del_msgs(outmsg)

    @clear.error
    async def clear_error(self, ctx, error):
        await self.del_msgs(
            ctx.message,
            await ctx.send("🛑You are not permitted to use this command."),
            delay=5
        )

    @commands.command(name="eval")
    @commands.is_owner()
    async def _eval(self, ctx):
        code = '\n'.join(ctx.message.content.split('\n')[1:-1])
        self.logger.debug(f"evaulating code:\n{code}")
        await ctx.send(eval(code, globals(), locals()))

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
    bot.add_cog(Utils(bot))
