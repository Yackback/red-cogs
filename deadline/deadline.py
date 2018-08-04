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
import schedule
import tabulate

from redbot.core import checks
from redbot.core.utils.chat_formatting import box, info, warning, escape, pagify
from redbot.core import Config

class Deadline:
  def __init__(self, bot):
    self.bot = bot
    self.config = Config.get_conf(self, identifier=10010197100108105110101)
    self.config.register_guild(**dflt_guild)
    self.log = logging.getLogger("redbot.cogs.deadline")
  
  async def get_chart(self, ctx):
    # TO BE IMPLEMENTED
    
  @commands.group(name="deadline", no_pm=True)
  @checks.mod_or_permissions(manage_guild=True)
  async def deadlineMain(self, ctx):
    if ctx.invoked_subcommand is None:
      self.send_cmd_help()
  
  @deadline.group("set", no_pm=True)
  async def deadlineSet(self, ctx):
    if ctx.invoked subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
      self.send_cmd_help()
  
  @deadline.command(name="begin"):
  async def deadlineBegin(self, ctx):
    def run_threaded(job_func):
      job_thread = threading.Thread(target=job_func)
      job_thread.start()
    schedule.every(10)