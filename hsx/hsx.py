#!/usr/bin/env python3.6
# HSX cog
# Yackback 2018-2019

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

dflt_guild = {
    "runPosttrack": True,
    "wait_time": 60,
    "allowed_channel": None,
    "topics": list(),
    "whitelist": list()  # TODO
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
        tags = [m.group(0)[1:-1] for m in re.finditer(r"\[([^]]+)\]", subj)]
        body = resolve_soup.find("div", attrs={"id": "post_message_body"})
        body = ' '.join([p.text.lstrip() for p in body.find_all("p")])
        # Formatting for Official Cashouts post.
        if subj == "Official Cashouts":
            # the "- Opening Weekend" messes with the line spacing
            body = body.replace("- Opening Weekend", "OW")
            body = "\n".join([cashout for cashout in body.split("-")])
            body = body.replace("(", "[").replace(")", "]")

        def makeUpper(match):
            return "[{0}](https:\/\/www\.hsx\.com\/security\/view\/{0})".format(
                match.group(1).upper())

        body = re.sub(r"\[([^]]+)\]", makeUpper, body)
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
        author_icon = resolve_soup.find("img", attrs={
            "id": "security_poster"
        }).get("src")
        author_icon = "https://www.hsx.com" + author_icon
        # He doesn't have an image.
        if author == "Antibody":
            author_icon = "https://www.hsx.com/images/logo_deco.gif"

        regex = r'(Jan?|Feb?|Mar?|Apr?|May?|Jun?|Jul?|Aug?|Sep?|Oct?|Nov?|Dec?)\s+\d{1,2},\s+\d{1,2}:\d{2}'
        time_ = re.search(regex, author_nick_string).group(0)
        return (subj, body, tags, author_nick, author, author_icon, time_)


class HSX(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=720830880)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.hsx")
        self.bot.add_listener(self.stock_finder, "on_message")

    async def check_channel(self, ctx_or_msg):
        # These commands only work in the hsx channel, so we check them.
        # First, no pms
        if type(ctx_or_msg) == discord.Message and ctx_or_msg.guild is None:
            return False
        channel_id = await self.config.guild(ctx_or_msg.guild
                                             ).allowed_channel()
        # Make sure there is an allowed channel.
        if channel_id is None and type(
                ctx_or_msg) is discord.ext.commands.Context:
            await ctx_or_msg.send(
                "Allowed channel id not set up. Please run `[p]hsx config set allowed_id <allowed_id>`."
            )
            return False
        return ctx_or_msg.channel.id == channel_id

    def make_embed(self, topic: Topic):
        embed = discord.Embed(color=(discord.Color.from_rgb(167, 200, 116)))
        # It's not a not a well formed url if it has spaces
        topic.author = topic.author.replace(" ", "%20")
        embed.set_author(name=topic.author_nick,
                         url="https://www.hsx.com/profile/index.php?uname=" +
                         topic.author,
                         icon_url=topic.author_icon)
        embed.set_footer(text="Happy trades!")
        if topic.body != "":
            if len(topic.body) < 1021:
                embed.add_field(name=topic.subject, value=topic.body)
            else:
                embed.add_field(name=topic.subject,
                                value=topic.body[:1018] + "...")
                for x in range(1, int(len(topic.body) / 1018 + 1)):
                    if x != int(len(topic.body) / 1018):
                        embed.add_field(name=topic.subject + " (cont.)",
                                        value="...{}...".format(
                                            topic.body[x * 1018:(x + 1) *
                                                       1018]))
                    else:
                        embed.add_field(name=topic.subject + " (cont.)",
                                        value="...{}".format(
                                            topic.body[x * 1018:(x + 1) *
                                                       1018]))
        else:
            embed.add_field(name=topic.subject, value="\u200b")
        # Add a field for tags in the title because you cant have links in a field name,
        # so we display title tags separately
        if len(topic.tags) > 0:
            title_tags = ""
            for tag in topic.tags:
                title_tags += "[{}](https:\/\/www\.hsx\.com\/security\/view\/{}), ".format(
                    tag, tag)
            title_tags = title_tags[:-2]  # remove the last ", "
            embed.add_field(name="Tags From Title",
                            value=title_tags,
                            inline=False)
        # Submit time
        embed.add_field(name="Submitted on", value=topic.time_, inline=False)
        return embed

    async def stock_finder(self, message):
        # this will exclude pms and stuff not in the right channel
        if not await self.check_channel(message):
            return

        matches = re.compile(r"\[([^]]+)\]").findall(message.content)
        for match in matches:
            url = "https://www.hsx.com/security/view/{}".format(match)
            r = requests.get(url)
            if r.status_code == 200:
                soup = bs4.BeautifulSoup(r.content, "lxml")
            else:
                fmt = "Connection error for stock {}."
                await message.channel.send(fmt.format(match))
                continue
            try:
                title = soup.find("div",
                                  class_="security_data").find("h1").text
                summary = soup.find("div", class_="security_summary")
                priceline = summary.find("p", class_="value").text
                price = priceline[0:priceline.find(".") + 3]
                delist = "Delist" in summary.find("p", class_="labels").text
            except AttributeError:
                fmt = "Stock {} not found."
                await message.channel.send(fmt.format(match))
                continue
            icon_url = soup.find("img", id="security_poster").get("src")
            if "http" not in icon_url:
                icon_url = "https://www.hsx.com" + icon_url
            # Get the change from the priceline
            change = priceline[len(price):]
            if not delist:
                # the span's class is either up or down, so get it then titlecase
                up_or_down = summary.find(
                    "p", class_="value").find("span").get("class")[0]
                if up_or_down != "no_change":
                    up_or_down = up_or_down[0].upper() + up_or_down[1:]
                    # format the string
                    change = "{0} ({1} {2})".format(
                        change.split(" ")[0], up_or_down,
                        change.split(" ")[1][1:-1])
                elif "Pre-IPO" in soup.find("div",
                                            class_="data_column").prettify():
                    try:
                        shares = soup.find(
                            "a",
                            href="/trade/index.php?symbol={}".format(
                                match)).text
                    except AttributeError:
                        shares = "unknown shares"
                    change = "Pre-IPO, {} will be sold at starting price.".format(
                        shares)
                elif "IPO Info:" in soup.prettify():
                    try:
                        shares = soup.find(
                            "a",
                            href="/trade/index.php?symbol={}".format(
                                match)).text
                    except:
                        shares = "unknown shares"
                    change = "IPO, {} left.".format(shares)
                else:
                    change = "No change today."
            else:
                change = "Delisted"
            """ Find the type of stock to get the KaiGee url and the max shares"""
            kaigee_base = "[{1}](https://www.kaigee.com/{0}/{1})"
            if soup.find(
                    "div",
                    class_="inner_columns").find("h4").text == "Distributor":
                kaigee = kaigee_base.format("MST", match)
                max_minus_one = "99999"
            elif soup.find("div", class_="inner_columns").find(
                    "h4"
            ).text == "Filmography" or "NominOptionsSM" in soup.prettify():
                kaigee = kaigee_base.format("SBO", match)
                max_minus_one = "19999"
            elif "." in match:
                kaigee = "None, derivative."
                max_minus_one = "19999"
            elif "Fund Manager:" in soup.find("div",
                                              class_="data_column").prettify():
                kaigee = kaigee_base.format("FND", match)
                max_minus_one = "19999"
            elif "TVStocks" in soup.prettify():
                kaigee = "None, TVStock."
                max_minus_one = "19999"
            else:
                kaigee = "Unknown."
                max_minus_one = "99999"
            base_trade_text = "[{1} {2}](https://www.hsx.com/trade/?symbol={0}&shares={2}&action=place-order&tradeType={1})"
            quickbuy_text = base_trade_text.format(match, "buy", "max")
            quickshort_text = base_trade_text.format(match, "short", "max")
            almost_max_buy = base_trade_text.format(match, "buy",
                                                    max_minus_one)
            almost_max_short = base_trade_text.format(match, "short",
                                                      max_minus_one)
            embed = discord.Embed(
                color=(discord.Color.from_rgb(167, 200, 116)))
            embed.set_footer(text="Happy trades!")
            embed.set_author(name=title, url=url, icon_url=icon_url)
            embed.add_field(name=match, value=price)
            embed.add_field(name="Change Today", value=change)
            embed.add_field(name="Kaigee Link", value=kaigee, inline=False)
            embed.add_field(name="Buy max", value=quickbuy_text)
            embed.add_field(name="Short max", value=quickshort_text)
            embed.add_field(name="Buy " + max_minus_one, value=almost_max_buy)
            embed.add_field(name="Short " + max_minus_one,
                            value=almost_max_short)
            await message.guild.me.edit(nick="HSX")
            try:
                await message.channel.send(embed=embed)
            except discord.errors.HTTPException:
                pass
            await message.guild.me.edit(nick=None)

    @commands.group(name="hsx")
    async def hsx_main(self, ctx):
        """The HSX cog. Useless outside of the allowed channel id (#hsx)."""
        if ctx.invoked_subcommand is None:
            return None

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
        if ctx.invoked_subcommand is None or isinstance(
                ctx.invoked_subcommand, commands.Group):
            await ctx.send_help()

    @hsx_config.group(name="set")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_set(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(
                ctx.invoked_subcommand, commands.Group):
            await ctx.send_help()

    @hsx_config.group(name="get")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_config_get(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(
                ctx.invoked_subcommand, commands.Group):
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
            await ctx.send(
                "allowed_id not set up. Please run `[p]hsx config set allowed_id <allowed_id>`."
            )

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
        channel = self.bot.get_channel(await
                                       self.config.guild(ctx.guild
                                                         ).allowed_channel())
        if channel is None:
            await ctx.send(
                "Allowed channel id not set up. Please run `[p]hsx config set allowed_id <allowed_id>`."
            )
            return
        await ctx.send("Starting in channel {}".format(channel.mention))
        url = "https://www.hsx.com/forum/forum.php?id=3"
        await self.config.guild(ctx.guild).runPosttrack.set(True)
        self.log.info("Starting posttrack to check for new posts...")
        while await self.config.guild(ctx.guild).runPosttrack():
            try:
                r = requests.get(url)
            except requests.exceptions.ConnectionError:
                continue
            self.log.debug("Checked for new posts...")
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
                async with self.config.guild(
                        ctx.guild).topics() as current_topics:
                    if topic_uniq not in current_topics:
                        current_topics.append(topic_uniq)
                if len(await self.config.guild(ctx.guild
                                               ).topics()) != current_len:
                    # Now, when making the embed we do the full class again
                    rm_str = "** This post has been removed by the forum moderator! **"
                    if not quiet and topic_.subject != rm_str:
                        self.log.debug("New post found, sending embed.")
                        embed = self.make_embed(topic_)
                        await ctx.guild.me.edit(nick="HSX")
                        await channel.send(embed=embed)
                        await ctx.guild.me.edit(nick=None)
            if quiet:  # Quiet mode exits after population.
                await ctx.send(
                    "Populated post cache in quiet mode, now exiting. "
                    "Please run again to turn on sending messages.")
                return
            wait_time = await self.config.guild(ctx.guild).wait_time()
            self.log.info(
                "Waiting {} seconds before checking again.".format(wait_time))
            await asyncio.sleep(wait_time)

    @hsx_posttrack.command(name="set")
    async def hsx_posttrack_set(self, ctx, toggle: int):
        """Toggle Posttrack checker on and off with 0 and 1"""
        if not await self.check_channel(ctx):
            return
        await self.config.guild(
            ctx.guild).runPosttrack.set(False if toggle == 0 else True)

    @checks.mod_or_permissions(manage_guild=True)
    @hsx_posttrack.command(name="clear")
    async def hsx_posttrack_clear(self, ctx):
        """clear the post cache, but ask for confirmation first"""
        if not await self.check_channel(ctx):
            return
        settings = self.config.guild(ctx.guild)
        await ctx.send(warning("WARNING: this is a dangerous operation."))
        await ctx.send(
            "Are you sure you want to proceed? Please answer Y or N.")
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
