#!/usr/bin/env python3.6
# Yackback 2018
# Discord bot to watch for Anthony changes.

import logging
import sys
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
import bs4
import discord
import pandas as pd
import requests
import tabulate

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, info, warning, pagify
from redbot.core import Config

dflt_guild = {"deadline_url": "https://deadline.com/2018/08/melissa-mccarthy-happytime-murders-crazy-rich-asians-meg-weekend-box-office-1202451694/",
              "last_updated_content": "",
              "last_updated_text": "",
              "last_updated_time": "",
              "stop_checking": False}

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
)

class Deadline(object):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=10010197100108105110101)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.deadline")

    async def get_chart(self, ctx):
        settings = self.config.guild(ctx.guild)
        list_to_keep = ["title", "fri", "sat", "sun", "3-day",
                        "3-day (-%)", "rank", "film", "title"]
        most_recent_chart = pd.read_html(await settings.URL(),
                                         attrs={"class": "cc-table-container"})
        # Quick preliminary thing to get rid of all the unnamed stuff
        try:
            most_recent_chart = most_recent_chart[0].iloc[3:18, 1:12]
        except IndexError:
            return ""
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

    @commands.group(name="deadline", no_pm=True)
    @checks.mod_or_permissions(manage_guild=True)
    async def deadline_main(self, ctx):
        """The Deadline cog provides a way to check for updates throughout the
        weekend when supplied with a deadline url. Please call
        `[p]deadline begin` for more info"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @deadline_main.group("set", no_pm=True)
    async def deadline_set(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
            await ctx.send_help()

    async def deadline_update(self, ctx):
        """Check for an update. This is based on whatever URL was specified
        by [p]deadline_begin."""
        self.log.info("Checking for update...")
        settings = self.config.guild(ctx.guild)
        deadline_url = await settings.deadline_url()
        r = requests.get(deadline_url)
        if r.status_code == 200:
            soup = bs4.BeautifulSoup(r.content, "lxml")
        else:
            fmt = "Unable to get Deadline page: {}"
            self.log.warning(fmt.format(deadline_url))
        full_text = [str(p) for p in soup.find("div", class_="post-content").find_all("p")]
        count = 0
        for i,p in enumerate(full_text):
            if "UPDATE" in p:
                count += 1
            if count == 2:
                break
        update_text = full_text[:i]
        for page in pagify("\n".join(update_text)):
            await ctx.send(page)
        sentences = [p.split(". ") for p in update_text]
        if sentences != await settings.sentences():
            await ctx.send(embed=await self.handle_update(ctx, soup))
        else:
            self.log.info("no update")

    async def handle_update(self, ctx, content_, soup):
        settings = self.config.guild(ctx.guild)
        # Find this stuff automatically I guess.
        author_byline = soup.find("span", class_="byline").find("a",
                                                                class_="name")
        author_name = author_byline.text
        author_link = author_byline.get("href")

        # Yeah screw getting this automatically.
        author_image = "https://pmcdeadline2.files.wordpress.com/2014/06/anthony-dalessandro.png"
        deadline_url = await settings.url()
        deadline_title = soup.find("h1", class_="post-title").text
        footer = await settings.footer()

        # Deal with the chart. :)
        chart_string = (soup.find("div",
                                  attrs={"class": "post-content"})
                                  .find("p").find("strong").text.lower())
        chart = ""
        if "with chart" in chart_string:
            chart = await self.get_chart(ctx)
        elif "chart coming" in chart_string:
            chart = info("CHART COMING")
        elif "refresh for chart" in chart_string:
            chart = info("REFRESH FOR CHART")
        else:
            chart = warning("NO DISCERNABLE MENTION OF CHART")

        embed = discord.Embed(color=(discord.Color.from_rgb(255,255,255)))
        embed.set_author(name=author_name, url=author_link,
                         icon_url=author_image)
        embed.set_footer(text=footer)
        embed.add_field(name="Update", value=deadline_title)
        embed.add_field(name="Chart", value=chart, inline=False)
        return embed

    @deadline_main.command(name="begin", pass_context=True)
    async def deadline_begin(self, ctx, url : str = ""):
        """Begin the scheduled deadline update check. Does not check for thursday
        night updates no matter what.
        :param: url: the deadline article URL
        :param: friday_morning: whether to check for a Fri morning update. To be
        used after a Thurs preview. Dflt False."""
        # Now check if we should stop
        if len(url) != 0:
            await self.config.guild(ctx.guild).deadline_url.set(url)
        while not await self.config.guild(ctx.guild).stop_checking():
            await self.deadline_update(ctx)
            time.sleep(5)

        await self.config.guild(ctx.guild).stop_checking.set(False)

    @deadline_set.command(name="stop")
    async def deadline_set_stop(self, ctx, force: str = ""):
        self.log.info("checking stopped by user request.")
        await self.config.guild(ctx.guild).stop_checking.set(True)
