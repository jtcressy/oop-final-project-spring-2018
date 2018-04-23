import discord
import logging
from pymongo.errors import DuplicateKeyError
from discord.ext import commands
from djbot import logger_setup, get_dbclient


class DJ:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)
        self.dbclient = get_dbclient()
        self.db = self.dbclient.get_database()

    @commands.group(name="kubectl", pass_context=True)
    async def discjockey(self, ctx):
        """Disc Jockey commands"""
        if ctx.invoked_subcommand is None:
            "do kubectl help"



def setup(bot):
    bot.add_cog(DJ(bot))
