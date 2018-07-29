#!/usr/bin/env python3.6
# Yackback 2018
# Discord bot to watch for Anthony changes.

import asyncio
from datetime import datetime as dt
import logging
import sys

import bs4
from discord.ext import commands
import requests

from redbot.core import checks
from redbot.core.utils.chat_formatting import box
from redbot.core import Config

deadline_url = "https://deadline.com/2018/07/tom-cruise-mission-impossible-fallout-opening-weekend-1202434739/"
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
              "role_to_ping"        : "Deadline Alerts"}

class Deadline(object):
    """Deadline Updates"""

    def __init__(self, bot, url=deadline_url, wait_time=60):
        self.bot = bot
        # Identifier is deadline to decimal (binary is really long)
        self.config = Config.get_conf(self, identifier=10010197100108105110101)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.deadline")

    @commands.command(name="deadline")
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
                await ctx.send("WARNING: Unable to get Deadline page.")
                await self.log.warning("Unable to get Deadline page: {0}".format(self.config["URL"]))
            time_= soup.find('time', class_ = 'date-published')
            time_ = time_.text
            if await settings.updated_time() == "":
                await settings.updated_time.set(time_)
            if await settings.updated_time() != time_:
                fmt = "{role.mention}, I have published an update. Read: {url}"
                for role in ctx.message.guild.roles:
                    if role.name == await settings.role_to_ping():
                        role_ = role
                await ctx.send(fmt.format(role=role_,
                                   url=await settings.URL()))
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
        self.log.info("DUPLICATE UPDATER ENDED BY USER REQUEST")
        await settings.update_check_counter.set(count - 1)
        return 0

    @commands.group(name="deadlineconf", no_pm=True)
    @checks.mod_or_permissions(manage_guild=True)
    async def deadlineConf(self, ctx):
        """Print the current settings"""
        settings_dict = await self.config.guild(ctx.guild).all()
        if ctx.invoked_subcommand is None:
            msg = box("check_enabled: {check_enabled}\n"
                      "URL: {URL}\n"
                      "wait_time: {wait_time}\n"
                      "".format(**settings_dict))
            msg += "\nSee {}help deadlineconf to edit the settings"\
                .format(ctx.prefix)
            await ctx.send(msg)

    @deadlineConf.command(name="wait_time")
    async def configWaitTime(self, ctx, time: int):
        """Define a new pause period between Anthony's saves and proofreads.
        (How long between update checks to the URL.)"""
        try:
            await self.config.guild(ctx.guild).wait_time.set(time)
        except TypeError:
            self.send_cmd_help()
            return None
        self.log.info("For guild {0}, wait_time = {1}".format(ctx.guild.id,
                                                              time))

    @deadlineConf.command(pass_context=True, name="url")
    async def configURL(self, ctx, url: str):
        """Define a new deadline link for Anthony to post to."""
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
        Caveat emptor: this will not disable the sleep function between update
        checks done by [p]deadline. It will however cause [p]deadline to quit
        when the sleep is done. This is to prevent the bad stuff that can occur
        if it is force killed."""
        if check_ == 1:
            await self.config.guild(ctx.guild).check_enabled.set(True)
            self.log.info("check_enabled = True")
        elif check_ == 0:
            await self.config.guild(ctx.guild).check_enabled.set(False)
            self.log.info("check_enabled = False")
        else:
            await ctx.send("Please enter 1 or 0 to change settings.")
            self.log.info("check_enabled INVALID NUMBER")
