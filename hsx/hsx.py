#!/usr/bin/env python3.6
# HSX cog
# Yackback 2018

import asyncio
import logging
import re
import time

import bs4
import discord
import requests

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import warning
from redbot.core import Config

dflt_guild = {"runPosttrack": True,
              "wait_time": 60,
              "allowed_channel": None,
              "topics": list(),
              "whitelist": list() # TODO
}
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
)


class Topic(object):
    def __init__(self, tag):
        """Init with a BeautifulSoup tag"""
        self.href = "https://www.hsx.com/forum/" + tag.find("a").get("href")
        # Please help me I don't know why I did it this way.
        self.subject, self.body, self.tags, self.author_nick,\
            self.author, self.author_icon, self.time_ = self.resolve()


    def resolve(self):
        # Gotta scrape em all!
        r = requests.get(self.href)
        resolve_soup = bs4.BeautifulSoup(r.content, "lxml")
        resolve_soup = resolve_soup.find("div", class_="post_message")
        subj = resolve_soup.find("p", class_="subject").text
        tags = [m.group(0)[1:-1] for m in re.finditer(r"\[([^]]+)\]",
                                                      subj)]
        body = resolve_soup.find("div", attrs={"id": "post_message_body"})
        body = ' '.join([p.text.lstrip() for p in body.find_all("p")])
        def makeUpper(match):
            return "[\[" + match.group(1).upper() + "\]](http:\/\/www\.hsx\.com\/security\/view\/" +\
                match.group(1).upper() + ")"
        body = re.sub(r"\[([^]]+)\]",
                      makeUpper,
                      body)
        author_nick_string = resolve_soup.find("p",
                                               class_="author").text.lstrip()
        author_nick_string = author_nick_string[11:]
        if author_nick_string.find("(a.k.a") != -1:
            # Take the stuff after the a.k.a
            author_nick = author_nick_string[:author_nick_string.find("(a.k")]
        else:
            author_nick = resolve_soup.find("p",
                                            class_="author").find("a").text
        author = resolve_soup.find("p", class_="author").find("a").text
        author_icon = resolve_soup.find("img", attrs={"id":"security_poster"}).get("src")
        author_icon = "https://www.hsx.com" + author_icon
        # He doesn't have an image.
        if author == "Antibody":
            author_icon = "https://www.hsx.com/images/logo_deco.gif"
        regex = r'(Jan?|Feb?|Mar?|Apr?|May?|Jun?|Jul?|Aug?|Sep?|Oct?|Nov?|Dec?)\s+\d{1,2},\s+\d{1,2}:\d{2}'
        time_ = re.search(regex, author_nick_string).group(0)
        return (subj, body, tags, author_nick, author, author_icon, time_)


class HSX(object):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=720830880)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.hsx")

    async def check_channel(self, ctx):
        # These commands only work in the hsx channel, so we check them.
        channel_id = await self.config.guild(ctx.guild).allowed_channel()
        # Make sure there is an allowed channel.
        if channel_id is None:
            await ctx.send("Allowed channel id not set up. Please run `[p]hsx config set allowed_id <allowed_id>`.")
            return False
        return ctx.channel.id == channel_id

    def make_embed(self, topic: Topic):
        embed = discord.Embed(color=(discord.Color.from_rgb(167, 200, 116)))
        embed.set_author(name=topic.author_nick,
                         url="https://www.hsx.com/profile/index.php?uname="+topic.author,
                         icon_url=topic.author_icon)
        embed.set_footer(text="Happy trades!")
        if topic.body != "":
            embed.add_field(name=topic.subject, value=topic.body)
        else:
            embed.add_field(name=topic.subject, value="\u200b")
        # Add a field for tags in the title because you cant have links in a field name,
        # so we display title tags separately
        if len(topic.tags) > 0:
            title_tags = ""
            for tag in topic.tags:
                title_tags += "[{}](https:\/\/www\.hsx\.com\/security\/view\/{}), ".format(tag, tag)
            title_tags = title_tags[:-2] # remove the last ", "
            embed.add_field(name="Tags From Title", value=title_tags, inline=False)
        # Submit time
        embed.add_field(name="Submitted on", value=topic.time_)
        return embed


    @commands.group(name="hsx")
    async def hsx_main(self, ctx):
        if ctx.invoked_subcommand is None:
            if await self.check_channel(ctx):
                await ctx.send_help()


    @checks.mod_or_permissions(manage_guild=True)
    @hsx_main.group(name="config")
    async def hsx_config(self, ctx):
        # DO NOT CHECK CHANNEL SINCE ONE OF THE SUBCOMMANDS
        # IS THE CHANNEL CHANGER
        if ctx.invoked_subcommand == None:
            return None


    @hsx_main.group(name="posttrack")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_posttrack(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
            await ctx.send_help()


    """
    # WIP
    @hsx_main.command(name="stock")
    async def hsx_stock(self, ctx=None, stock_or_msg: str = ""):
        \"""Handle printing out information about stocks.\"""
        if not await self.check_channel(ctx):
            return
        if stock is None:
            await ctx.send_help()
    """


    @hsx_config.group(name="set")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_set(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
            await ctx.send_help()
    
   
    @hsx_config.group(name="get")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_get(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
            await ctx.send_help()
    

    # begin the getters and setters for the config stuff
    # they dont check the channel id on purpose
    @hsx_config_set.command(name="allowed_id")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_set_allowed_id(self, ctx, allowed_id):
        fmt = "Variable allowed_id updated for guild id {} to {}"
        self.log.info(fmt.format(ctx.guild.id, str(allowed_id)))
        await self.config.guild(ctx.guild).allowed_channel.set(int(allowed_id))


    @hsx_config_get.command(name="allowed_id")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_get_allowed_id(self, ctx):
        id_ = await self.config.guild(ctx.guild).allowed_channel()
        if id_ is not None:
            await ctx.send(id_)
        else:
            await ctx.send("allowed_id not set up. Please run `[p]hsx config set allowed_id <allowed_id>`.")


    @hsx_config_set.command(name="wait_time")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_set_wait_time(self, ctx, wait_time):
        fmt = "Variable wait_time updated for guild id {} to {}"
        self.log.info(fmt.format(ctx.guild.id, str(wait_time)))
        await self.config.guild(ctx.guild).wait_time.set(int(wait_time))


    @hsx_config_get.command(name="wait_time")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_get_wait_time(self, ctx):
        await ctx.send(await self.config.guild(ctx.guild).wait_time())


    @hsx_posttrack.command(name="start")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_posttrack_start(self, ctx, quiet=False):
        """
        Track new posts on hsx's movie forums and and post them as an embed.

        :param: quiet: whether to simply populate the database (to be used
        after a clear). Defaults to False
        """
        if not await self.check_channel(ctx):
            return
        await ctx.send("Starting")
        url = "https://www.hsx.com/forum/forum.php?id=3"
        await self.config.guild(ctx.guild).runPosttrack.set(True)
        self.log.info("Starting posttrack to check for new posts...")
        while await self.config.guild(ctx.guild).runPosttrack():
            self.log.debug("Checking for new posts...")
            r = requests.get(url)
            soup = bs4.BeautifulSoup(r.content, "lxml")
            topics = soup.find_all("p", class_="indent0 topic")
            for topic in topics:
                # topic_ = instance of Topic class
                # topic_uniq = dict of important stuff
                # topic = the value of the loop
                current_len = len(await self.config.guild(ctx.guild).topics())
                # We only want to store the unique identifier, that way we
                # can save much more space.
                topic_ = Topic(topic)
                topic_uniq = {"subj": topic_.subject, "time": topic_.time_}
                async with self.config.guild(ctx.guild).topics() as current_topics:
                    if topic_uniq not in current_topics:
                        current_topics.append(topic_uniq)
                if len(await self.config.guild(ctx.guild).topics()) != current_len:
                    # Now, when making the embed we do the full class again
                    rm_str = "** This post has been removed by the forum moderator! **"
                    if not quiet and topic_.subject != rm_str:
                        self.log.debug("New post found, sending embed.")
                        embed = self.make_embed(topic_)
                        await ctx.send(embed=embed)
            if quiet: # Quiet mode exits after population.
                await ctx.send("Populated post cache in quiet mode, now exiting. "
                               "Please run again to turn on sending messages.")
                return
            wait_time = await self.config.guild(ctx.guild).wait_time()
            self.log.info("Waiting {} seconds before checking again.".format(wait_time))
            await asyncio.sleep(wait_time)


    @hsx_posttrack.command(name="set")
    async def hsx_posttrack_set(self, ctx, toggle: int):
        """Toggle Posttrack checker on and off with 0 and 1"""
        if not await self.check_channel(ctx):
            return
        await self.config.guild(ctx.guild).runPosttrack.set(False if toggle == 0
                                                           else True)


    @checks.mod_or_permissions(manage_guild=True)
    @hsx_posttrack.command(name="clear")
    async def hsx_posttrack_clear(self, ctx):
        """clear the post cache, but ask for confirmation first"""
        if not await self.check_channel(ctx):
            return
        settings = self.config.guild(ctx.guild)
        await ctx.send(warning("WARNING: this is a dangerous operation."))
        await ctx.send("Are you sure you want to proceed? Please answer Y or N.")
        check = lambda m: m.content == "Y" and\
            m.channel == ctx.channel and m.author == ctx.message.author
        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except:
            await ctx.send("Timed out. Leaving post cache as is.")
            return

        await ctx.send("Deleting post cache... this is irreverisble.")
        await settings.topics.clear()
        await ctx.send("Deleted post cache.")

            
    """
    # WIP
    async def on_message(self, message):
        settings = self.config.guild(ctx.guild)
        if message.guild is None:
            return
        
        if not await self.check_channel(await settings.allowed_channel):
            return

        matches = re.compile(r"\[([^]]+)\]").findall(message.content)
        for match in matches:
            await self.hsx_stock(self, stock=match[1:-1])
        

    """