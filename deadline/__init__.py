from .deadline import *


def setup(bot):
    cog = Deadline(bot)
    bot.add_cog(cog)
