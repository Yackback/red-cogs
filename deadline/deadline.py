#!/usr/bin/env python3.6
# Yackback 2018
# Discord bot to watch for Anthony changes.

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
import bs4
import discord
from discord.ext import commands
import pandas as pd
import requests
import tabulate

from redbot.core import checks
from redbot.core.utils.chat_formatting import box, info, warning
from redbot.core import Config

dflt_guild = {"edit_mode": False,
              "footer": ("Make sure to subscribe to alerts in the "
                         "#react-for-roles channel so you can get notified "
                         "when we release more breaking news."),
              "last_updated_content": "",
              "last_updated_text": "",
              "last_updated_time": "",
              "deadline_url": None}


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
        most_recent_chart = most_recent_chart[0].iloc[3:18, 1:12]
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
        if ctx.invoked_subcommand is None:
            self.send_help_cmd()

    @deadline_main.group("set", no_pm=True)
    async def deadline_set(self, ctx):
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
            self.send_cmd_help()

    async def deadline_update(self, ctx):
        """Check for an update. This is based on whatever URL was specified
        by [p]deadline_begin."""
        settings = self.config.guild(ctx.guild)
        deadline_url = await settings.deadline_url()
        r = requests.get(deadline_url)
        if r.status_code == 200:
            soup = bs4.BeautifulSoup(r.content, "lxml")
        else:
            fmt = "Unable to get Deadline page: {}"
            self.log.warning(fmt.format(deadline_url))
        time_ = soup.find("time", class_="date-published")
        time_ = time_.text
        await settings.last_updated_time.set(time_)
        content_ = soup.find("div", class_="post-content").find("p")
        if await settings.last_updated_content() == "":
            await settings.last_updated_content.set(content_)
        if await settings.last_updated_text() == "":
            await settings.last_updated_text.set(content_.text)
        elif await settings.last_updated_text() != content_.text:
            # I only pass content_ here for optimization, since we could
            # just get it from soup. At least I think it's probably better.
            await self.handle_update(ctx, content_, soup)
            # After we've run the update once, now we set it into edit mode.
            # Remember the scheduler will reset edit mode to False at the start
            # of each interval.
            await settings.edit_mode.set(True)
        else:
            self.log.info("No update.")

        return content_  # I guess it needs something to be returned (not None)

    async def handle_update(self, ctx, content_, soup):
        settings = self.config.guild(ctx.guild)
        # Find this stuff automatically I guess.
        author_byline = soup.find("span", class_="byline").find("a",
                                                                class_="name")
        author_name = author_byline.text
        author_link = author_byline.href

        # Yeah screw getting this automatically.
        author_image = "https://pmcdeadline2.files.wordpress.com/2014/06/anthony-dalessandro.png"
        deadline_url = await settings.url()
        deadline_title = soup.find("h1", class_="post-title").text
        footer = await settings.footer()

        # Chart time
        chart = ""

        # Deal with the chart. :)
        # If in edit mode, make sure to edit the previous post above
        # and make the chart? Maybe include a config option on whether to
        # edit or not.
        chart_string = (soup.find("div",
                                  attrs={"class": "post-content"})
                                  .find("p").find("strong").text.lower())
        send_chart = False
        if "with chart" in chart_string:
            chart = await self.get_chart(ctx)
        if "chart coming" in chart_string:
            chart += info("CHART COMING")
        elif "refresh for chart" in self.get_chart(ctx):
            chart += info("REFRESH FOR CHART")
        else:
            chart += warning("NO DISCERNABLE MENTION OF CHART")

        embed = discord.Embed(color=(discord.Color.from_rgb(255,255,255)))
        embed.set_author(name=author_name, url=author_link,
                         icon_url=author_image)
        embed.set_footer(text=footer)
        embed.add_field(name="Update", value=deadline_title)
        embed.add_field(name="Chart", value=chart, inline=False)
        return embed

    @deadline_main.command(name="begin", pass_context=True)
    async def deadline_begin(self, ctx, url : str, friday_morning: bool = False):
        """Begin the scheduled deadline update check. Does not check for thursday
        night updates no matter what.
        :param: url: the deadline article URL
        :param: friday_morning: whether to check for a Fri morning update. To be
        used after a Thurs preview. Dflt False."""

        # Quickly set the deadline URL if it is one
        if ("https://" in url or "http://" in url) and "deadline" in url:
            await self.config.guild(ctx.guild).deadline_url.set(url)
        else:
            await ctx.send(("Are you sure that's a deadline URL?"
                        "Please input a deadline.com url."))
            return -1

        # Make the scheduler
        scheduler = AsyncIOScheduler()

        # Reset edit mode.
        def reset_edit_mode(self, ctx):
            self.config.guild(ctx.guild).edit_mode.set(False)

        # Quickly set up the Friday morning check if needed
        if friday_morning:
            friday_morning_trigger = CronTrigger(day_of_week="fri", hour="10-11",
                                                minute="*")

            scheduler.add_job(self.deadline_update, friday_morning_trigger)
            reset_edit_mode_trigger_fri_morn = OrTrigger([CronTrigger(day_of_week="fri",
                                                                    hour="10")])
            reset_edit_mode_fri_morn = scheduler.add_job(reset_edit_mode(self,ctx),
                                                        reset_edit_mode_trigger_fri_morn)

        # Trigger Warning ...sorry
        # Set when the triggers go.
        friday_afternoon_trigger = CronTrigger(day_of_week="fri", hour="14-17",
                                               minute="*")
        friday_night_trigger = OrTrigger([CronTrigger(day_of_week="fri",
                                                      hour="22-23",
                                                      minute="*/2"),
                                          CronTrigger(day_of_week="sat",
                                                      hour="0-2",
                                                      minute="*"),
                                          CronTrigger(day_of_week="sat",
                                                      hour="3",
                                                      minute="*/2")])

        saturday_morning_trigger = OrTrigger([CronTrigger(day_of_week="sat",
                                                          hour="8",
                                                          minute="*/2"),
                                              CronTrigger(day_of_week="sat",
                                                          hour="9-11",
                                                          minute="*")])

        saturday_night_trigger = OrTrigger([CronTrigger(day_of_week="sat",
                                                        hour="22-23",
                                                        minute="*"),
                                            CronTrigger(day_of_week="sun",
                                                        hour="0-1",
                                                        minute="*/2")])

        sunday_morning_trigger = OrTrigger([CronTrigger(day_of_week="sun",
                                                        hour="8",
                                                        minute="*/2"),
                                            CronTrigger(day_of_week="sun",
                                                        hour="9-11",
                                                        minute="*")])

        """
        reset_edit_mode_trigger = OrTrigger([CronTrigger(day_of_week="fri",
                                                         hour="14,22"),
                                            CronTrigger(day_of_week="sat",
                                                        hour="8,22"),
                                            CronTrigger(day_of_week="sun",
                                                        hour="8")])
        """

        # scheduler.add_job(await self.config.guild(ctx.guild).edit_mode\
        #    .set(False),
        #                 reset_edit_mode_trigger)

        # Weekends on, time to go to work.
        friday_afternoon = scheduler.add_job(await self.deadline_update(ctx),
                                             friday_afternoon_trigger)

        friday_night = scheduler.add_job(await self.deadline_update(ctx),
                                         friday_night_trigger)

        saturday_morning = scheduler.add_job(await self.deadline_update(ctx),
                                             saturday_morning_trigger)

        saturday_night = scheduler.add_job(await self.deadline_update(ctx),
                                           saturday_night_trigger)

        sunday_morning = scheduler.add_job(await self.deadline_update(ctx),
                                           sunday_morning_trigger)

        # And... start!
        scheduler.start()

    @deadline_main.command(name="stop")
    async def deadline_stop(self, ctx, force: str = ""):
        if force == "force":
            force = True
        else:
            force = False
