import discord
import logging
from pymongo.errors import DuplicateKeyError
import pymongo
from discord.ext import commands
from djbot import logger_setup, get_dbclient


class DiscJockey:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)
        self.dbclient = get_dbclient()
        self.db = self.dbclient.get_database()

        # populate these variables at command invocation
        self.music_queue: pymongo.collection.Collection = None
        self.saved_music: pymongo.collection.Collection = None
        self.voice_client: discord.VoiceClient = None

    @commands.group(name="dj", pass_context=True)
    async def discjockey(self, ctx):
        """Disc Jockey commands"""
        self.music_queue = self.db.get_collection(f"{ctx.message.server.id}-music_queue")
        self.saved_music = self.db.get_collection(f"{ctx.message.server.id}-saved_music")
        if ctx.invoked_subcommand is None:
            "do kubectl help"

    @discjockey.command(pass_context=True)
    async def save(self, ctx, name, url, desc=""):
        """Save a song to the music collection"""

def setup(bot):
    bot.add_cog(DiscJockey(bot))
