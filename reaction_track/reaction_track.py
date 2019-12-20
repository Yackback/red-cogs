#!/usr/bin/env python3.6
# Yackback 2018
# Red cog to track reactions used on a server. Can be helpful if server is
# running out of emoji spots.

import asyncio
import logging
import sys
import time

import discord

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, info, pagify
from redbot.core import Config

dflt_guild = {"total_reactions": {}}

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

    async def on_reaction_add(self, reaction, user):
        """Event: on_reaction_add."""
        if reaction.custom_emoji is False or reaction.me is True or reaction.message.author.bot is False:
            return
        if isinstance(user, discord.Member):
            settings = self.config.guild(user.Guild)
        else:
            return  # They left the server, we don't care about their reaction
        if reaction.custom_emoji:
            emoji_id = reaction.emoji
        async with settings.total_reactions as reactions:
            reactions.update({emoji_id: reactions[emoji_id] + 1})

    async def on_reaction_remove(self, reaction, user):
        """Event: on_reaction_remove."""
        if reaction.custom_emoji is False or reaction.me is True or reaction.message.author.bot is False:
            return
        if isinstance(user, discord.Member):
            settings = self.config.guild(user.Guild)
        else:
            return  # They left the server, we don't care about their reaction
        if reaction.custom_emoji:
            emoji_id = reaction.emoji
        async with settings.total_reactions as reactions:
            reactions.update({emoji_id: reactions[emoji_id] - 1})

    # Main command group
    @commands.group(name="emoji", pass_context=True)
    async def emoji_main(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @emoji_main.command(name="stats")
    async def emoji_stats(self, ctx):
        settings = self.config.guild(ctx.guild)
        fmt = ""
        for k, v in await settings.total_reactions():
            fmt += ("{}: {}\n".format(k, v))
        if fmt == "":
            await ctx.send("No reactions in database. Users need to liven up.")
        else:
            await ctx.send(info("Emoji Statistics"))
            for page in pagify(fmt):
                await ctx.send(box(page))

    @emoji_main.command(name="clear", pass_context=True)
    @checks.mod_or_permissions(manage_guild=True)
    async def emoji_clear(self, ctx):
        """Clear the emoji cache. This requires confirmation before proceeding."""
        settings = self.config.guild(ctx.guild)
        await ctx.send(
            "This is a dangerous operation: please enter Y or yes to confirm.")
        check = lambda m: m.content == "yes" or m.content == "Y" and m.channel == ctx.channel
        try:
            message = await self.bot.wait_for('message',
                                              check=check,
                                              timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Leaving emoji tracking as is.")
            return
        # Clear the emojis...with no survivors!
        await ctx.send("Deleting emoji cache... this is irreversible.")
        await settings.total_reactions.set(dict())
        self.log.info("DELETED total_reactions")


# TODO: HANDLE SERVER EMOJI REMOVAL/ADDITIONS
# TODO: AVERAGE USES PER MESSAGE REACTED
