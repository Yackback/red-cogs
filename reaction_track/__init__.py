from .reaction_track import *


def setup(bot):
    cog = ReactionTrack(bot)
    bot.add_cog(cog)
