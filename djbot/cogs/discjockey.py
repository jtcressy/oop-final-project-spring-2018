import discord
import logging
from pymongo.errors import DuplicateKeyError
import pymongo
from discord.ext import commands
from djbot import logger_setup, get_dbclient
import urllib.parse
import asyncio

class DiscJockey:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)
        self.dbclient = get_dbclient()
        self.db = self.dbclient.get_database()

        # populate these variables at command invocation
        self.music_queue: pymongo.collection.Collection = None
        self.saved_music: pymongo.collection.Collection = None
        self.players = {}

    @commands.group(name="dj", pass_context=True)
    async def discjockey(self, ctx):
        """Disc Jockey commands"""
        self.music_queue = self.db.get_collection(f"{ctx.message.server.id}-music_queue")
        self.saved_music = self.db.get_collection(f"{ctx.message.server.id}-saved_music")
        if ctx.invoked_subcommand is None:
            """Send status to channel"""
            player: discord.voice_client.StreamPlayer = self.players.get(ctx.message.server.id)
            if player is not None:
                if player.is_playing():
                    voice_client = self.bot.voice_client_in(ctx.message.server)

    @discjockey.command(pass_context=True)
    async def play(self, ctx, name):
        request = self.saved_music.find_one({'name': name})  # attempt to fetch the requested music
        if request is not None:  # check if it found an entry
            # enqueue the requested music entry from database
            ""
        elif bool(urllib.parse.urlparse(name).scheme):  # else, check if name is a URL
            ""
        else:
            await self.bot.send_message(ctx.message.channel, "Either that peice of music doesnt exist or the url is invalid")

    async def next(self, ctx):
        """Play the next music in the queue"""

    async def ytdl(self, ctx, url, after=None):
        try:
            await self.bot.join_voice_channel(ctx.message.author.voice.voice_channel)
            self.players[ctx.message.server.id] = await self.bot.voice_client_in(ctx.message.server).create_ytdl_player(
                url,
                after=after
            )
            self.players[ctx.message.server.id].start()
            self.players[ctx.message.server.id].volume = 0.10
        except discord.errors.ClientException as e:
            await self.bot.send_message(ctx.message.channel, content=str(e))


def setup(bot):
    bot.add_cog(DiscJockey(bot))
