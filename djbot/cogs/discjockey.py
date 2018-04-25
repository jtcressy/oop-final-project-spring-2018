import datetime
import urllib.parse

import discord
import pymongo
from discord.ext import commands

from djbot import logger_setup, get_dbclient


# Check decorator to see if the user is in the voice channel that the bot is in
# also pass if there is no voice channel
def is_in_voice_channel():
    def predicate(ctx):
        voice_client = ctx.bot.voice_client_in(ctx.message.guild)
        return voice_client is None or ctx.message.author.voice.voice_channel.id == voice_client.channel.id

    return commands.check(predicate)


def typing(fn):
    """Decorator to make bot send typing during command execution"""

    async def predicate(*args, **kwargs):
        async with ctx.message.channel.typing():
            fn()

    return predicate


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

    #
    # TODO: Make command messages delete themselves *and* the user's command to avoid cluttering the chat channel
    # TODO: Ensure that we send typing to channels for each command with "async with ctx.message.channel.typing():"
    #

    @commands.group(name="dj")
    @typing
    async def discjockey(self):
        """Disc Jockey commands"""
        self.music_queue = self.db.get_collection(f"{ctx.message.server.id}-music_queue")
        self.saved_music = self.db.get_collection(f"{ctx.message.server.id}-saved_music")
        if ctx.invoked_subcommand is None:
            # Send status to channel
            # TODO: List the songs in the current music queue and the playing status
            player: discord.voice_client.StreamPlayer = self.players.get(ctx.message.server.id)
            if player is not None:
                if player.is_playing():
                    voice_client = self.bot.voice_client_in(ctx.message.server)
                    await self.bot.send_message(ctx.message.channel,
                                                f"Currently playing in #{voice_client.channel.name}")

    @discjockey.command(pass_context=True)
    async def save(self, ctx, name, url, desc=""):
        """
        Save a song to the music collection
        :param name: Name of the song
        :param url: URL that points to playable media
        :param desc: Optional: Describe the song
        """
        entry = {
            'name' : name,
            'url': url,
            'desc': desc,
            'createdby': ctx.message.author.id,
            'datecreated': datetime.datetime.now()
        }
        if self.saved_music.find_one({'name': entry.get('name')}):
            botmsg = await self.bot.say("That song is already saved.")
        elif bool(urllib.parse.urlparse(url).scheme):  # make sure url is a parsable url
            self.saved_music.insert_one(entry)
            botmsg = await self.bot.say(f"Saved {name} to the music collection.")


    @discjockey.command(pass_context=True)
    @commands.has_any_role("Admin", "Admins", "Moderator", "Moderators")
    async def delete(self, ctx, name):
        """
        Delete a song from the music collection
        :param name: Name of song in music collection
        """
        # TODO

    @discjockey.command(pass_context=True)
    async def info(self, ctx, name):
        """
        Get details about a song in the music collection
        :param name: Name of song in music collection
        """
        # TODO: Tabulate the output to make it pretty

    @discjockey.command(pass_context=True)
    async def list(self, ctx):
        """List available songs in the music collection"""
        # TODO

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def play(self, ctx, name_or_url=None):
        """
        Play or enqueue a song by name or url, or just resume playing original queue
        :param name_or_url: Optional, name of song or url
        """
        await self.bot.send_typing(ctx.message.channel)
        if name_or_url:
            self.enq(ctx, name_or_url)  # "play" is a wrapper for "enq" if you pass it a name or url to play
        # finally, if there is no music playing call self.next() to play the queue
        player: discord.voice_client.StreamPlayer = self.players[ctx.message.server.id]
        if player is None or not player.is_alive() or not player.is_done():
            await self.next(ctx)
            # TODO: Send a message stating that the player was successful
        else:  # In this case, there is already a player, so we say we cant find that music to enqueue
            await self.bot.send_message(ctx.message.channel,
                                        "Either that peice of music doesnt exist or the url is invalid")

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def enq(self, ctx, name_or_url):
        """
        Add a song to the music queue
        :param name_or_url: Name of song in music collection or a direct playable URL
        """
        request = self.saved_music.find_one({'name': name_or_url})  # attempt to fetch the requested music
        if request is not None:  # check if it found an entry
            # enqueue the requested music entry from database
            job = {
                'startTime': None,
                'endTime': None,
                'createdOn': datetime.datetime.now(),
                'priority': 1,
                'payload': request
            }
            result = self.music_queue.insert_one(job)
            # TODO: Send message that the song was queued by checking result
        elif bool(urllib.parse.urlparse(name_or_url).scheme):  # else, check if name is a URL
            # enqueue the url without saving it in the database
            payload = {
                'name': "placeholder",
                'url': name_or_url,
                'createdby': self.bot.connection.user.id,
                'datecreated': datetime.datetime.now()
            }
            job = {
                'startTime': None,
                'endTime': None,
                'createdOn': datetime.datetime.now(),
                'priority': 1,
                'payload': payload
            }
            result = self.music_queue.insert_one(job)
            # TODO: Send message that the song was queued by checking result

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def deq(self, ctx, name):
        """
        Remove a song from the music queue
        :param name: Name of song to dequeue
        """
        # TODO: Pop a song from the music queue using self.music_queue.delete_one

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def skip(self, ctx):  # FUTURE: vote skip functionality instead of outright skip, admin could override vote
        """Skip the current playing song"""
        # TODO: Stop the current player and closeout the current job then call self.next()

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    @commands.has_any_role("Admin", "Admins", "Moderator", "Moderators")
    async def stop(self, ctx):
        """Stop a bot from playing. Keeps queue intact"""
        # TODO: Stop the current player and find a way to stop the bot from fetching jobs form the queue temporarily

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    @commands.has_any_role("Admin", "Admins", "Moderator", "Moderators")
    async def clear(self, ctx):
        """Stops and clears the bot's queue"""
        self.music_queue.delete_many({})  # Removes all documents from the queue collection
        self.stop(ctx)

    async def next(self, ctx):  # this function is to be used as a callback in a discord StreamPlayer, see ytdl() below.
        """Play the next music in the queue"""
        voice_client = self.bot.voice_client_in(ctx.message.server)
        if voice_client is None:
            await self.bot.join_voice_channel(ctx.message.author.voice.voice_channel)
        job = self.music_queue.find_one_and_update(
            # Get the oldest job that has not been started yet and set its startTime to mark it as started
            {'startTime': None},
            {'$set': {'startTime': datetime.datetime.now()}},
            sort={'createdOn': 1}
        )
        await self.ytdl(ctx, job['payload']['url'], after=self.next, job=job)

    async def ytdl(self, ctx, url, after, job):
        """
        Create a ytdl player and play music
        :param ctx: context of original command
        :param url: url pointing to music/video
        :param after: callback function to run after playback completes
        :param job: dict representing a job in a mongodb queue
        :return: None
        """
        music_queue = self.music_queue

        async def _after():  # this function is called when the player finishes
            # update the job with an endtime to mark it as done
            music_queue.update_one({'_id': job['_id']}, {'$set': {'endTime': datetime.datetime.now()}})
            if after is not None:
                await after(ctx)  # call the callback function we were passed and give it the context
        try:
            self.players[ctx.message.server.id] = await self.bot.voice_client_in(ctx.message.server).create_ytdl_player(
                url,
                after=_after  # we pass the above function as a callback
            )
            self.players[ctx.message.server.id].start()
            self.players[ctx.message.server.id].volume = 0.10
        except discord.errors.ClientException as e:
            await self.bot.send_message(ctx.message.channel, content=str(e))

    @staticmethod
    async def del_msgs(*args, delay=5):
        """
        Delete messages with 5 second delay
        :param args: discord.Message objects to be deleted
        :param delay: Delay in seconds (int)
        :return: None
        """


def setup(bot):
    bot.add_cog(DiscJockey(bot))
