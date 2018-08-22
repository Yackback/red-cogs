#!/usr/bin/env python3.6
# HSX cog
# Yackback 2018

import asyncio
import logging
import re
import time

import bs4
import discord
from discord.ext import commands
import requests

from redbot.core import checks
from redbot.core.utils.chat_formatting import warning
from redbot.core import Config

dflt_guild = {"runPosttrack": True,
              "allowed_channel": 472606694153912332,
              "topics": list(),
              "whitelist": list()} # TODO

              # 476103105512079360 for production
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
        body = re.sub(r"\[([^]]+)\]",
                      r"\[\1\](http:\/\/www\.hsx\.com\/security\/view\/\1\)",
                      body)
        matches = re.finditer(r"\[([^]]]+)\]", body)
        tags = set(tags)
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
        # These commands only work in the hsx channel.
        return ctx.channel.id == (await self.config.guild(ctx.guild).allowed_channel())

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
        if len(topic.tags) > 0:
            embed.add_field(name="Tags", value=topic.tags)
        embed.add_field(name="Submitted on", value=topic.time_, inline=False)
        return embed

    @commands.group(name="hsx")
    async def hsx_main(self, ctx):
        if ctx.invoked_subcommand is None:
            if await self.check_channel(ctx):
                await ctx.send_help()

    @hsx_main.command(name="stock")
    async def hsx_stock(self, ctx, stock: str):
        if not await self.check_channel(ctx):
            return
        if stock is None:
            await ctx.send_help()

    @hsx_main.group(name="posttrack")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_posttrack(self, ctx, quiet=False):
        """
        Track new posts on hsx's movie forums and and post them as an embed.

        :param: quiet: whether to simply populate the database (to be used
        after a clear). Defaults to False
        """
        if not await self.check_channel(ctx):
            return
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
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
                        if not quiet:
                            self.log.debug("New post found, sending embed.")
                            embed = self.make_embed(topic_)
                            await ctx.send(embed=embed)
                if quiet:
                    return
                self.log.debug("Waiting 100 seconds before checking again.")
                await asyncio.sleep(100)

    @hsx_posttrack.command(name="set")
    async def hsx_posttrack_set(self, ctx, toggle: int):
        """Toggle Posttrack checker on and off with 0 and 1"""
        if not await self.check_channel(ctx):
            return
        await self.config.guild(ctx.guild).runPosttrack.set(False if toggle == 0
                                                           else True)

    @hsx_posttrack.command(name="clear")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_posttrack_clear(self, ctx):
        """Clear the post cache"""
        settings = self.config.guild(ctx.guild)
        await ctx.send(warning("WARNING: this is a dangerous operation."))
        await ctx.send("1/2: Are you sure you want to proceed? Please answer Y or N.")
        check = lambda m: m.content == "Y" and\
            m.channel == ctx.channel and m.author == ctx.message.author
        try:
            message = await self.bot.wait_for('message', check=check, timeout=30.0)
        except:
            await ctx.send("Timed out. Leaving post cache as is.")
            return

        await ctx.send("2/2: Would you like to quietly populate the cache with the current first page of posts? Please answer Y or N.")
        check = lambda m: m.content == "N" or m.content == "Y" and\
            m.channel == ctx.channel and m.author == ctx.message.author
        try:
            message = await self.bot.wait_for('message', check=check, timeout=30.0)
        except:
            await ctx.send("Timed out. Leaving post cache as is.")
            return

        await ctx.send("Deleting post cache... this is irreverisble.")
        await settings.topics.clear()
        await ctx.send("Deleted post cache.")

        if message.content == "Y":
            await self.hsx_posttrack(ctx, quiet=True)
            await ctx.send("Quietly repopulated post cache..."
                           "run [p]hsx posttrack to begin tracking again.")
