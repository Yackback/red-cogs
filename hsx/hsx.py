#!/usr/bin/env python3.6
# HSX cog
# Yackback 2018

import logging
import time

import bs4
import discord
from discord.ext import commands
import requests

from redbot.core import checks
from redbot.core.utils.chat_formatting import box, info, pagify
from redbot.core import Config

dflt_guild = {}

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
)

class HSX(object):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=720830880)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.hsx")
        
    def check_channel(self, ctx):
        # These commands only work in the hsx channel.
        return ctx.channel.id == 476103105512079360
    
    @commands.group(name="hsx")
    async def hsx_main(self, ctx):
        if ctx.invoked_subcommand is None:
            if self.check_channel(ctx):
                await ctx.send_help()
            
    @hsx_main.command(name="stock")
    async def hsx_stock(self, ctx, stock: str):
        if not self.check_channel(ctx):
            return
        if stock is None:
            await ctx.send_help()
            
    @hsx_main.group(name="antibody")
    @checks.mod_or_permissions(manage_guild=True)
    async def hsx_antibody(self, ctx):
        if not self.check_channel(ctx):
            return
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand,
                                                        commands.Group):
        
            url = "https://www.hsx.com/forum/forum.php?id=3"
            while await self.config.guild(ctx.guild).runAntibody():
                r = requests.get(url)
                soup = bs4.BeautifulSoup(r.content)
                topics = soup.findall("p", class_="indent0 topic")
                await ctx.send(topics)
                time.sleep(100)
                
    
    @hsx_antibody.command(name="set")
    async def hsx_antibody_set(self, ctx, toggle: int):
        """Toggle Antibody checker on and off with 0 and 1"""
        if not self.check_channel(ctx):
            return
        await self.config.guild(ctx.guild).runAntibody.set(False if toggle == 0
                                                           else True)