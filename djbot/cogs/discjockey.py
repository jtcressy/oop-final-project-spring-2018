import asyncio
import datetime
import urllib.parse

import discord
import discord.utils
import pymongo
import youtube_dl
from discord.ext import commands

from djbot import logger_setup, get_dbclient


# Check decorator to see if the user is in the voice channel that the bot is in
# also pass if there is no voice channel
def is_in_voice_channel():
    def predicate(ctx):
        voice_client = ctx.message.guild.voice_client
        return voice_client is None or ctx.message.author.voice.channel.id == voice_client.channel.id

    return commands.check(predicate)


def typing(fn):
    """Decorator to make bot send typing during command execution"""

    async def predicate(*args, **kwargs):
        async with ctx.typing():
            fn()

    return predicate


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class DiscJockey:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger_setup(self.__class__.__name__)
        self.dbclient = get_dbclient()
        self.db = self.dbclient.get_database()

        # populate these variables at command invocation
        self.music_queue: pymongo.collection.Collection = None
        self.saved_music: pymongo.collection.Collection = None

    #
    # TODO: Make command messages delete themselves *and* the user's command to avoid cluttering the chat channel
    # TODO: Ensure that we send typing to channels for each command with "async with ctx.message.channel.typing():"
    #

    @commands.group(name="dj")
    async def discjockey(self, ctx):
        import tabulate
        """Disc Jockey commands"""
        self.music_queue = self.db.get_collection(f"{ctx.message.guild.id}-music_queue")
        self.saved_music = self.db.get_collection(f"{ctx.message.guild.id}-saved_music")
        if ctx.invoked_subcommand is None:
            queue = self.music_queue.find(sort=[('createdOn', 1)])
            headers = ["Name", "Description", "Played", "Playing"]
            rows = []
            self.logger.debug(f"Current music queue for {ctx.message.guild.name}:")
            for job in queue:
                self.logger.debug(str(job))
                playing = False
                played = False
                if job['startTime'] is not None:
                    played = True
                    playing = True
                    if job['endTime'] is not None:
                        playing = False
                rows.append([job['payload']['name'], job['payload']['desc'], str(played), str(playing)])
            output = tabulate.tabulate(rows, headers)
            await ctx.message.channel.send("```" + output + "```")

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

        self.bot.delete_message(ctx.message)

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

        self.bot.delete_message(ctx.message)
        if self.saved_music.find_one({'name': name}):
            self.saved_music.delete_one({'name': name})

    @discjockey.command(pass_context=True)
    async def info(self, ctx, name):
        """
        Get details about a song in the music collection
        :param name: Name of song in music collection
        """

        self.bot.delete_message(ctx.message)
        # TODO: Tabulate the output to make it pretty

    @discjockey.command(pass_context=True)
    async def list(self, ctx):
        """List available songs in the music collection"""
        self.bot.delete_message(ctx.message)
        # TODO

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def play(self, ctx, name_or_url=None):
        """
        Play or enqueue a song by name or url, or just resume playing original queue
        :param name_or_url: Optional, name of song or url
        """
        self.bot.delete_message(ctx.message)
        if name_or_url:
            self.enq(ctx, name_or_url)  # "play" is a wrapper for "enq" if you pass it a name or url to play
        # finally, if there is no music playing call self.next() to play the queue
        vc = ctx.message.guild.voice_client
        if vc is None or not vc.is_connected() or not vc.is_playing():
            await self.next(ctx)
            #TODO: use youtube-dl to list name of video
            await self.bot.say(f"Now playing {name_or_url}")
        else:  # In this case, there is already a player, so we say we cant find that music to enqueue
            await self.bot.send_message(ctx.message.channel,
                                        "Either that peice of music doesnt exist or the url is invalid")

    @discjockey.command()
    @is_in_voice_channel()
    async def enq(self, ctx, name_or_url):
        """
        Add a song to the music queue
        :param name_or_url: Name of song in music collection or a direct playable URL
        """
        self.bot.delete_message(ctx.message)
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
            if result:
                await ctx.message.channel.send(f"Queued up {name_or_url}.")
        elif bool(urllib.parse.urlparse(name_or_url).scheme):  # else, check if name is a URL
            # enqueue the url without saving it in the database
            payload = {
                'name': "placeholder",
                'url': name_or_url,
                'desc': "",
                'createdby': self.bot.user.id,
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
            if result:
                await ctx.message.channel.send(f"Queued up {payload['name']}")

    @discjockey.command(pass_context=True)
    @is_in_voice_channel()
    async def deq(self, ctx, name):
        """
        Remove a song from the music queue
        :param name: Name of song to dequeue
        """
        # TODO: Pop a song from the music queue using self.music_queue.delete_one
        deleted = self.music_queue.delete_one({'name': name})
        if deleted:
            ctx.message.channel.send("Removed from queue.")

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
        self.bot.delete_message(ctx.message)
        self.music_queue.delete_many({})  # Removes all documents from the queue collection
        self.stop(ctx)

    async def next(self, ctx):  # this function is to be used as a callback in a discord StreamPlayer, see ytdl() below.
        """Play the next music in the queue"""
        voice_client = ctx.message.guild.voice_client
        if voice_client is None:
            voice_client = await ctx.message.author.voice.channel.connect()
        job = self.music_queue.find_one_and_update(
            # Get the oldest job that has not been started yet and set its startTime to mark it as started
            {'startTime': None},
            {'$set': {'startTime': datetime.datetime.now()}},
            sort=[('createdOn', 1)]
        )
        if job is None:
            await ctx.message.channel.send("No music in the queue!")
        else:
            await self.ytdl(ctx, job['payload']['url'], after=self.next, job=job, vc=voice_client)

    async def ytdl(self, ctx, url, after, job, vc=None):
        """
        Create a ytdl player and play music
        :param ctx: context of original command
        :param url: url pointing to music/video
        :param after: callback function to run after playback completes
        :param job: dict representing a job in a mongodb queue
        :return: None
        """
        music_queue = self.music_queue

        async def _after(e):  # this function is called when the player finishes
            # update the job with an endtime to mark it as done
            music_queue.update_one({'_id': job['_id']}, {'$set': {'endTime': datetime.datetime.now()}})
            if after is not None:
                await after(ctx)  # call the callback function we were passed and give it the context
            if e:
                ctx.send("Error playing audio: {}".format(e))
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            vc.play(player, after=_after)
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
