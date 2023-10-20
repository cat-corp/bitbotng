import os
import sys
from dotenv import load_dotenv
import discord
from cogs.monitoring import Monitoring
from cogs.birthdays import Birthdays
import logging


load_dotenv()

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def main():
    intents = intents = discord.Intents.default()
    intents.members = True

    bot = discord.Bot(intents=intents)

    bot.add_cog(Monitoring(bot, logger))
    bot.add_cog(Birthdays(bot, logger))

    @bot.event
    async def on_ready():
        await bot.change_presence(activity=discord.Game("memories on repeat 💾"), status=discord.Status.idle)
        logger.info(f"{bot.user} is ready and online!")

    @bot.slash_command(name="boop", description="boop bitbot")
    async def hello(ctx):
        await ctx.respond("boop :3")

    bot.run(os.getenv("TOKEN"))

if __name__ == "__main__":
    main()
