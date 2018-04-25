import asyncio
import datetime
import string
import urllib.parse

import discord
import discord.utils
import pymongo
import tabulate
import youtube_dl
from discord.ext import commands

from djbot import logger_setup, get_dbclient

EMOJIS = {
    "success": "✅",
    "fail": "🛑"
}




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


#
# Command checks and errors
#
# Check decorator to see if the user is in the voice channel that the bot is in
# also pass if there is no voice channel
def is_in_voice_channel():
    def predicate(ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client is not None:
            if not ctx.message.author.voice.channel.id == voice_client.channel.id:
                raise NotInVoiceChannel(f"{EMOJIS['fail']}You cant use this command outside of the voice channel!")
        else:
            raise VoiceNotConnected(f"{EMOJIS['fail']}Not connected to a voice channel!")
        return True

    return commands.check(predicate)


def is_admin_or_mod():
    def predicate(ctx):
        msg = ctx.message
        ch = msg.channel
        names = ["Admin", "Admins", "Moderator", "Moderators"]
        if not any(discord.utils.get(msg.author.roles, name=name) for name in names):
            raise NotAnAdmin(f"{EMOJIS['fail']}You are not permitted to run this command!")
        return True

    return commands.check(predicate)


class VoiceNotConnected(commands.CheckFailure):
    pass

class NotInVoiceChannel(commands.CheckFailure):
    pass


class NotAnAdmin(commands.CheckFailure):
    pass


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
        """Disc Jockey commands"""
        self.music_queue = self.db.get_collection(f"{ctx.message.guild.id}-music_queue")
        self.saved_music = self.db.get_collection(f"{ctx.message.guild.id}-saved_music")
        if ctx.invoked_subcommand is None:
            async with ctx.message.channel.typing():
                queue = self.music_queue.find(sort=[('createdOn', 1)])
                headers = ["Name", "Description", "Length", "Playing", "Played"]
                rows = []
                self.logger.debug(f"Current music queue for {ctx.message.guild.name}:")
                for job in queue:
                    playing = job['startTime'] is not None and job['endTime'] is None
                    played = job['startTime'] is not None and job['endTime'] is not None
                    self.logger.debug(job['payload']['name'])
                    self.logger.debug(job['payload']['metadata'].keys())
                    rows.append(
                        [
                            job['payload']['name'],
                            job['payload']['desc'],
                            str(datetime.timedelta(seconds=int(job['payload']['metadata']['duration']))),
                            playing,
                            played
                        ]

                    )
                output = tabulate.tabulate(rows, headers)
                await ctx.message.channel.send(f"Current queue of music:\n```{output}```")

    async def __error(self, ctx, error):
        self.logger.debug(f"Got error {type(error)}: {error}")
        if any([isinstance(error, NotInVoiceChannel), isinstance(error, NotAnAdmin),
                isinstance(error, commands.BadArgument)]):
            outmsg = await ctx.send(error)
            await self.del_msgs(
                ctx.message,
                outmsg,
                delay=5
            )
        if isinstance(error, VoiceNotConnected):
            await self.del_msgs(
                ctx.message,
                await ctx.send(f"{EMOJIS['fail']}Summon me to a voice channel first with {ctx.prefix}dj summon"),
                delay=5
            )

    @discjockey.command()
    async def save(self, ctx, name, url, desc=""):
        """
        Save a song to the music collection
        :param name: Name of the song
        :param url: URL that points to playable media
        :param desc: Optional: Describe the song
        """
        outmsg = None
        async with ctx.message.channel.typing():
            ytdl_result = ytdl.extract_info(url, download=False)
            entry = {
                'name': name,
                'url': url,
                'desc': ''.join(filter(lambda x: x in set(string.printable),
                                       ytdl_result['title'][:30])).strip() if desc is None else desc,
                'createdby': ctx.message.author.id,
                'datecreated': datetime.datetime.now(),
                'metadata': ytdl_result
            }
            if self.saved_music.find_one({'name': entry.get('name')}):
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}That song is already saved.")
            elif bool(urllib.parse.urlparse(url).scheme):  # make sure url is a parsable url
                self.saved_music.insert_one(entry)
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Saved {name} to the music collection.")
        self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_admin_or_mod()
    async def delete(self, ctx, name):
        """
        Delete a song from the music collection
        :param name: Name of song in music collection
        """
        async with ctx.message.channel.typing():
            ""
        # TODO

    @discjockey.command()
    async def info(self, ctx, name):
        """
        Get details about a song in the music collection
        :param name: Name of song in music collection
        """
        async with ctx.message.channel.typing():
            ""
        # TODO: Tabulate the output to make it pretty

    @discjockey.command()
    async def list(self, ctx):
        """List available songs in the music collection"""
        async with ctx.message.channel.typing():
            ""
        # TODO

    @discjockey.command()
    async def summon(self, ctx):
        """Connect me to your voice channel"""
        if ctx.message.author.voice:
            vc = await ctx.message.author.voice.channel.connect()
            if vc:
                await self.del_msgs(
                    ctx.message,
                    await ctx.send(
                        f"{EMOJIS['success']}Hi there! Play some music with `{ctx.prefix}dj play <name_or_url>` or `{ctx.prefix}dj enq <name_or_url>`")
                )
        else:
            raise NotInVoiceChannel(f"{EMOJIS['fail']}You need to join a voice channel first!")

    @discjockey.command()
    @is_in_voice_channel()
    async def play(self, ctx, name_or_url=None):
        """
        Play or enqueue a song by name or url
        :param name_or_url: Optional, name of song or url
        """
        outmsg = None
        async with ctx.message.channel.typing():
            if name_or_url:
                self.enq(ctx, name_or_url)  # "play" is a wrapper for "enq" if you pass it a name or url to play
            # finally, if there is no music playing call self.next() to play the queue
            vc: discord.VoiceClient = ctx.message.guild.voice_client
            if vc is None or not vc.is_connected() or not vc.is_playing():
                self.next(ctx)
            if vc.is_paused():
                vc.resume()
                outmsg = await ctx.send(f"{EMOJIS['success']}Resumed playback.")
            else:  # In this case, there is already a player, so we say we cant find that music to enqueue
                outmsg = await ctx.message.channel.send(
                    f"{EMOJIS['fail']}Either that peice of music doesnt exist or the url is invalid")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def enq(self, ctx, name_or_url):
        """
        Add a song to the music queue
        :param name_or_url: Name of song in music collection or a direct playable URL
        """
        outmsg = None
        async with ctx.message.channel.typing():
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
                    vc = ctx.message.guild.voice_client
                    if vc is None or not vc.is_connected() or not vc.is_playing():
                        self.next(ctx)
                    outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Submitted to queue.")
            elif bool(urllib.parse.urlparse(name_or_url).scheme):  # else, check if name is a URL
                # enqueue the url without saving it in the database
                ytdl_result = ytdl.extract_info(name_or_url, download=False)
                payload = {
                    'name': ''.join(
                        filter(lambda x: x in set(string.ascii_letters), ytdl_result['title'][:15].lower())).strip(),
                    'url': name_or_url,
                    'desc': ''.join(filter(lambda x: x in set(string.printable), ytdl_result['title'][:30])).strip(),
                    'createdby': self.bot.user.id,
                    'datecreated': datetime.datetime.now(),
                    'metadata': ytdl_result
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
                    vc = ctx.message.guild.voice_client
                    if vc is None or not vc.is_connected() or not vc.is_playing():
                        self.next(ctx)
                    outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Submitted to queue.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}Could not queue {name_or_url}.")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def deq(self, ctx, name):
        """
        Remove a song from the music queue
        :param name: Name of song to dequeue
        """
        outmsg = None
        async with ctx.message.channel.typing():
            deleted = self.music_queue.delete_one({'payload.name': name})
            found = self.music_queue.find_one({'payload.name': name})
            if not found:
                self.logger.debug(f"Deleted {name} from queue")
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Removed {name} from queue.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}Could not remove {name} from queue.")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def skip(self, ctx):  # FUTURE: vote skip functionality instead of outright skip, admin could override vote
        """Skip the current playing song"""
        outmsg = None
        async with ctx.message.channel.typing():
            # TODO: Stop the current player and closeout the current job then call self.next()
            vc = ctx.message.guild.voice_client
            if vc is not None:
                vc.stop()
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Skipped current song.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}No music playing to skip.")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def stop(self, ctx):
        """Stop a bot from playing. Clears queue"""
        outmsg = None
        async with ctx.message.channel.typing():
            vc = ctx.message.guild.voice_client
            self.music_queue.delete_many({})
            if vc is not None:
                vc.stop()
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Stopped all music and cleared the queue.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}No music playing. Queue cleared.")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def pause(self, ctx):
        outmsg = None
        async with ctx.message.channel.typing():
            vc = ctx.message.guild.voice_client
            if vc is not None and vc.is_playing():
                vc.pause()
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Music paused.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}No music playing.")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    @discjockey.command()
    @is_in_voice_channel()
    async def resume(self, ctx):
        outmsg = None
        async with ctx.message.channel.typing():
            vc = ctx.message.guild.voice_client
            if vc is not None and not vc.is_playing():
                vc.resume()
                outmsg = await ctx.message.channel.send(f"{EMOJIS['success']}Music resumed.")
            else:
                outmsg = await ctx.message.channel.send(f"{EMOJIS['fail']}No music to resume")
        await self.del_msgs(
            ctx.message,
            outmsg
        )

    def next(self, ctx):  # this function is to be used as a callback in a discord StreamPlayer, see ytdl() below.
        """Play the next music in the queue"""
        voice_client = ctx.message.guild.voice_client
        if voice_client is None:
            voice_client = asyncio.run_coroutine_threadsafe(ctx.message.author.voice.channel.connect(),
                                                            loop=self.bot.loop)
        job = self.music_queue.find_one_and_update(
            # Get the oldest job that has not been started yet and set its startTime to mark it as started
            {'startTime': None},
            {'$set': {'startTime': datetime.datetime.now()}},
            sort=[('createdOn', 1)]
        )
        if job is None:
            asyncio.run_coroutine_threadsafe(ctx.message.channel.send(f"{EMOJIS['fail']}No music in the queue!"),
                                             loop=self.bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(
                self.ytdl(ctx, job['payload']['url'], after=self.next, job=job, vc=voice_client), loop=self.bot.loop)

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

        def _after(e):  # this function is called when the player finishes
            # update the job with an endtime to mark it as done
            music_queue.update_one({'_id': job['_id']}, {'$set': {'endTime': datetime.datetime.now()}})
            if after is not None:
                after(ctx)  # call the callback function we were passed and give it the context
            if e:
                asyncio.run_coroutine_threadsafe(ctx.message.channel.send(f"{EMOJIS['fail']}Error playing audio: {e}"),
                                                 loop=self.bot.loop)
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            vc.play(player, after=_after)
        except discord.errors.ClientException as e:
            await ctx.message.channel.send(EMOJIS['fail'] + str(e))

    async def del_msgs(self, *args: discord.Message, delay: int = 3):
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


def setup(bot):
    bot.add_cog(DiscJockey(bot))
