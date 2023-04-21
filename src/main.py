import os
import discord
from dotenv import load_dotenv

load_dotenv()
bot = discord.Bot()

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("memories on repeat 💾"), status=discord.Status.idle)
    print(f"{bot.user} is ready and online!")

@bot.slash_command(name = "boop", description = "boop bitbot")
async def hello(ctx):
    await ctx.respond("boop :3")

bot.run(os.getenv("TOKEN"))