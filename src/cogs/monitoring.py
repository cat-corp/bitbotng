from prometheus_client import start_http_server, Gauge
from discord.ext import commands
import discord

class Monitoring(commands.Cog):
    bot: discord.Bot
    member_count_gauge: Gauge

    def __init__(self, bot):
        self.bot = bot
        self.guild_count_gauge = Gauge("discord_guild_count", "Number of guilds the bot is a member of")
        self.member_count_gauge = Gauge("discord_guild_member_count", "Number of members in a guild", ["name"])
        start_http_server(8192)
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.guild_count_gauge.set(len(self.bot.guilds))
        for guild in self.bot.guilds:
            self.member_count_gauge.labels(guild.name).set(guild.member_count)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.guild_count_gauge.inc()
        self.member_count_gauge.labels(guild.name).set(guild.member_count)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        self.guild_count_gauge.dec()
        self.member_count_gauge.remove(guild.name)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild.name
        self.member_count_gauge.labels(guild).inc()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild.name
        self.member_count_gauge.labels(guild).dec()