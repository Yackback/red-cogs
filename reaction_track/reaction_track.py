#!/usr/bin/env python3.6
# Yackback 2018
# Red cog to track reactions used on a server. Can be helpful if server is
# running out of emoji spots.

import logging
import sys
import time

import discord
from discord.ext import commands

from redbot.core import checks
from redbot.core.utils.chat_formatting import box, info, pagify
from redbot.core import Config

dflt_guild = {
    "total_reactions": {}
}

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
)

class ReactionTrack(object):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=46114101979911633)
        self.config.register_guild(**dflt_guild)
        self.log = logging.getLogger("redbot.cogs.reaction_track")
        self.bot.add_listener(self.when_raw_reaction_added, "on_raw_reaction_add")
    
    async def when_raw_reaction_added(self, payload):
        """Event: on_reaction_add."""
        settings = self.config.guild(self.bot.get_guild(payload.guild_id))
        name = payload.emoji.name # name of the emoji
        current_count = await settings.total_reactions()[name]
        await settings.total_reactions.name.set(current_count)
    
    @commands.command(name="emojistats")
    async def emojistats(self, ctx):
        settings = self.config.guild(ctx.guild)
        fmt = ""
        async for k, v in await settings.total_reactions():
            fmt += ("{}: {}\n".format(k,v))
        await ctx.send(info("Emoji Statistics"))
        for page in pagify(fmt):
            await ctx.send(box(page))