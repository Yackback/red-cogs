#!/usr/bin/env python3.6
# Yackback 2018
# Discord bot to watch for Anthony changes.

import asyncio
from datetime import datetime, time
import logging
import sys

import bs4
import discord
from discord.ext import commands
import pandas as pd
import requests
import tabulate

from redbot.core import checks
from redbot.core.utils.chat_formatting import box, info, warning, escape, pagify
from redbot.core import Config

deadline_url = "https://deadline.com/2018/07/tom-cruise-mission-impossible-fallout-opening-weekend-1202434739/"
deadline_author = "Anthony D'Alessandro"
filename_ = "/home/yack/.local/share/Red-DiscordBot/logs/cogs/deadline.txt"
file_handler = logging.FileHandler(filename=filename_)
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=handlers
)
dflt_guild = {"URL"                 : deadline_url,
              "wait_time"           : 60,
              "updated_time"        : "",
              "update_check_counter": 0,
              "auto_short_wait_time": 60,
              "auto_long_wait_time" : 21600,
              "check_enabled"       : False,
              "auto_wait_time"      : False,
              "auto_wait_time_days" : [3,4,5,6],
              "auto_wait_time_hours": [[19,20,21,22],
                                       [15,16,22,23],
                                       [0,1,2,9,10],
                                       [9,10]
                                       ],
              "role_to_ping"        : "Deadline Alerts",
              "updates_until_done"  : []}

class Deadline(object):
    """Deadline Updates"""

    def __init__(self, bot, url=deadline_url, wait_time=60):
        self.bot = bot
        # Identifier is deadline to decimal (binary is really long)
        self.config = Config.get_conf(self, identifier=10010197100108105110101)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.deadline")

    async def get_chart(self, ctx):
        settings = self.config.guild(ctx.guild)
        list_to_keep = ["title", "fri", "sat", "sun", "3-day",
                        "3-day (-%)", "rank", "film", "title"]
        most_recent_chart = pd.read_html(await settings.URL(),
                                         attrs={"class":"cc-table-container"})
        # Quick preliminary thing to get rid of all the unnamed stuff
        most_recent_chart = most_recent_chart[0].iloc[3:18,1:12]
        cols = [c.lower() for c in most_recent_chart.columns
                if c.lower() in list_to_keep]
        most_recent_chart = most_recent_chart[cols]
        # If fri sat and sun are in the chart, only keep the total... no one
        # cares about the splits
        if "fri" in cols and "sat" in cols and "sun" in cols:
            most_recent_chart.drop(["fri", "sat", "sun"], axis=1, inplace=True)
        most_recent_chart.to_csv("/home/yack/chart.txt", sep=";")
        return box(tabulate.tabulate(most_recent_chart,
                                     headers=most_recent_chart.columns,
                                     showindex="never"))



    async def handle_update(self, ctx, soup: bs4.BeautifulSoup):
        """Handle the update and format the embed.
        Also checks for a chart, and returns done based on that"""
        # TODO ADD EXCEPTION FOR FRIDAY NIGHT
        done = False
        author_name = deadline_author
        author_url = "https://deadline.com/author/adalessandro/"
        author_image = "https://pmcdeadline2.files.wordpress.com/2014/06/anthony-dalessandro.png?w=200&h=200&crop=1"
        settings = self.config.guild(ctx.guild)
        deadline_URL = await settings.URL()
        deadline_title = soup.find("h1", attrs={"class": "post-title"}).text
        self.log.info("TITLE: {}".format(deadline_title))
        description = ("[{0}]({1})"
                       .format(deadline_title,deadline_URL))
        footer = ("Make sure to subscribe to alerts in the #react-for-roles "
                  "channel so you can get notified as soon as possible!")
        chart = ""
        first_part_of_article = (soup.find("div",
                                 attrs={"class": "post-content"})
                                 .find("p").find("strong").text.lower())
        send_chart = False
        if "with chart" in first_part_of_article:
            chart = await self.get_chart(ctx)
        elif "chart coming" and not "with chart":
            chart += info("REFRESH FOR CHART")
        else:
            chart += warning("NO MENTION OF CHART")

        embed = discord.Embed(color=(discord.Color.from_rgb(255,255,255)))
        embed.set_author(name=author_name, url=author_url,
                         icon_url=author_image)
        embed.set_footer(text=footer)
        embed.add_field(name="Update", value=description)
        embed.add_field(name="Chart", value=chart, inline=False)
        return (embed, done)

    @commands.command(name="deadline")
    @checks.mod_or_permissions(manage_guild=True)
    async def deadlineUpdater(self, ctx):
        """Deadline updater, checking every <wait_time> to <URL> if
        <check_enabled> is True. Does Anthony have industry estimates?
        Or has he made up his own? Find out as soon you can!"""
        settings = self.config.guild(ctx.guild)
        await settings.check_enabled.set(True)
        count = await settings.update_check_counter()
        await settings.update_check_counter.set(count + 1)
        # This double definition of count is needed
        count = await settings.update_check_counter()
        if count > 1:
            await ctx.send("Too many deadline updaters running. (max: 1)")
            await ctx.send("Killing this thread...the other will continue")
            self.log.warning("DUPLICATE UPDATER KILLED")
            await settings.update_check_counter.set(count - 1)
            return None
        await ctx.send("Writing my update now...EXCLUSIVE estimates coming.")
        enabled = await settings.check_enabled()
        while enabled:
            r = requests.get(await settings.URL())
            if r.status_code == 200:
                soup = bs4.BeautifulSoup(r.content, "lxml")
            else:
                await self.log.warning("Unable to get Deadline page: {0}".format(self.config["URL"]))
            time_= soup.find('time', class_ = 'date-published')
            time_ = time_.text
            if await settings.updated_time() == "":
                await settings.updated_time.set(time_)
            if await settings.updated_time() != time_ or True:
                for role in ctx.message.guild.roles:
                    if role.name == await settings.role_to_ping():
                        role_ = role
                embed, done = await self.handle_update(ctx, soup)
                try:
                    await ctx.send(role_.mention)
                    msg = await ctx.send(embed=embed) # save the msg to edit
                except discord.HTTPException:
                    await ctx.send("I need the `Embed links` permission to send this")
                    raise
                await settings.updated_time.set(time_)
                self.log.info("ANTHONY UPDATED, MESSAGE SENT")
            else:
                self.log.info("NO UPDATE")
            fmt = "Waiting {0} seconds to try again"
            self.log.info(fmt.format(await settings.wait_time()))
            """
            TODO:
            # If auto wait time is on
            if settings["auto_wait_time"]:
                now = dt.today()
                if now.dayOfWeek() in settings["auto_wait_time_days"]:
                    if now.hour in settings["auto_wait_time_hours"]:
                        await asyncio.sleep(settings["auto_wait_time_seconds"])
            # Fix this a bit - maybe wait until the hour in the set comes up?
            # i.e. walk through 2d array hour by hour waiting for the
            # hour/every minute on the hour?
                if now.dayOfWeek() in settings["auto_wait_time_days"]\
                        and now.hour in settings["auto_wait_time_hours"]:
                        await asyncio.sleep(settings["wait_time"])
            """
            await asyncio.sleep(await settings.wait_time())
            enabled = await settings.check_enabled()

        await ctx.send("Exiting gracefully.")
        self.log.info("UPDATER ENDED BY USER REQUEST")
        await settings.update_check_counter.set(count - 1)
        return 0

    @commands.group(name="deadlineset", no_pm=True)
    @checks.mod_or_permissions(manage_guild=True)
    async def deadlineConf(self, ctx):
        """Print the current settings"""
        settings_dict = await self.config.guild(ctx.guild).all()
        if ctx.invoked_subcommand is None:
            msg = box("Checking for Update: {check_enabled}\n"
                      "Deadline URL: {URL}\n"
                      "Wait time between checks: {wait_time}\n"
                      "".format(**settings_dict))
            msg += "\nSee {}help deadlineset to edit the settings"\
                .format(ctx.prefix)
            await ctx.send(msg)

    @deadlineConf.command(name="wait_time")
    async def configWaitTime(self, ctx, time: int):
        """Define a new pause period between Anthony's saves and proofreads.
        (How long between update checks to the URL.)
        WARNING: this will be deprecated when I implement auto checking by
        time of day."""
        try:
            await self.config.guild(ctx.guild).wait_time.set(time)
        except TypeError:
            self.send_cmd_help()
            return None
        self.log.info("For guild {0}, wait_time = {1}".format(ctx.guild.id,
                                                              time))

    @deadlineConf.command(pass_context=True, name="url")
    async def configURL(self, ctx, url: str):
        """Define a new deadline link for the bot to check for updates."""
        if ("http://" in url or "https://" in url) and "deadline" in url:
            await self.config.guild(ctx.guild).URL.set(url)
            self.log.info("url = {0}".format(url))
        else:
            await ctx.send("Are you sure that's a deadline url?")
            self.log.warning("INVALID URL {0}".format(url))

    @deadlineConf.command(pass_context=True, name="check")
    async def configCheckToggle(self, ctx, check_: int):
        """If check_ is 1, Anthony will write.
        If check_ is 0, Anthony will still write, the bot just won't report.
        (Toggle whether or not to check for updates.)
        """
        if check_ == 1:
            await self.config.guild(ctx.guild).check_enabled.set(True)
            await ctx.send("Enabled checking for deadline updates.")
            self.log.info("check_enabled = True")
        elif check_ == 0:
            await self.config.guild(ctx.guild).check_enabled.set(False)
            await ctx.send("Disabled checking for deadline updates.")
            self.log.info("check_enabled = False")
        else:
            await ctx.send("Please enter 1 or 0 to change settings.")
        else:
            await ctx.send("Please enter 1 or 0 to change settings.")
            self.log.info("check_enabled INVALID NUMBER")
