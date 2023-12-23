from discord.ext import commands
import logging
import discord
import aiosqlite
import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
from typing import Optional
import asyncio

DB_PATH = "./data/birthdays.sqlite"
TIME_ZONE = ZoneInfo("America/New_York")
BIRTHDAY_TIME = datetime.time(9, tzinfo=TIME_ZONE)


class Birthdays(commands.Cog):
    bot: discord.Bot
    log: logging.Logger
    birthday_slash: discord.SlashCommandGroup = discord.SlashCommandGroup("birthday", "Birthday commands")

    def __init__(self, bot, logger):
        self.bot = bot
        self.log = logger
    
    @commands.Cog.listener()
    async def on_ready(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    guild_id INTEGER,
                    user_id INTEGER,
                    birthday TEXT,
                    last_updated TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await cur.close()
            await db.commit()
        
        self.poll_loop_task = asyncio.create_task(self.poll_loop())
        self.log.info("Started birthday module")

        
    async def poll_loop(self):
        self.log.info("Started birthday poll loop")
        now = self.get_datetime()
        schedule_time = datetime.datetime.combine(now.date(), BIRTHDAY_TIME)
        while True:
            if now < schedule_time:
                await asyncio.sleep((schedule_time - now).total_seconds())
                try:
                    self.log.info("Polling birthdays")
                    await self.poll_birthdays()
                except Exception as e:
                    self.log.error(f"Error polling birthdays: {e}")
            now = self.get_datetime()
            schedule_time = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), BIRTHDAY_TIME, tzinfo=TIME_ZONE)
            

    def cog_unload(self):
        self.poll_loop_task.cancel()
        self.log.info("Unloaded birthday module")


    @birthday_slash.command(name="set", description="Sets your birth date to have a message sent on your birthday!", group="birthday")
    @discord.commands.guild_only()
    async def set_birthday(self, ctx: discord.ApplicationContext, date: discord.Option(str, "The date of your birthday in YYYY-MM-DD format")):
        try:
            birth_date = datetime.date.fromisoformat(date)
        except: 
            await ctx.respond("Invalid date format! Please use YYYY-MM-DD", ephemeral=True)
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                INSERT OR REPLACE INTO birthdays (guild_id, user_id, birthday, last_updated)
                VALUES (?, ?, ?, ?)""", (guild_id, user_id, birth_date, self.get_datetime()))
            await cur.close()
            await db.commit()
        await ctx.respond("Saved!", ephemeral=True)

    @birthday_slash.command(name="upcoming", description="Shows a list of upcoming birthdays in the server.")
    @discord.commands.guild_only()
    async def birthdays(self, ctx: discord.ApplicationContext, limit: Optional[int] = 10):
        if limit < 1:
            await ctx.respond("Limit must be greater than 0!", ephemeral=True)
            return

        guild_id = ctx.guild.id
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, birthday FROM birthdays WHERE guild_id = ?", [guild_id]) as cur:
                birthdays = [(user, datetime.date.fromisoformat(bday)) for user, bday in await cur.fetchall()]

        today = self.get_date()
        def format_bday(date: datetime.date):
            numdays = (date - today).days
            span = "Today!" if numdays == 0 else f"{numdays} day{'s' if numdays != 1 else ''}"
            return f"{date.strftime('%b')} {date.day} ({span})"

        sorted_bdays = [(user, self.adjust_date(today, bday)) for user, bday in birthdays]
        sorted_bdays.sort(key=lambda x: x[1])
        sorted_bdays = sorted_bdays[:limit]

        msg = "\n".join(["**Upcoming birthdays:**"] + [f"{format_bday(date)} - {ctx.guild.get_member(user).mention}" for user, date in sorted_bdays if ctx.guild.get_member(user) is not None])

        await ctx.respond(msg, ephemeral=True)

    @commands.slash_command(name="birthdaychannel", description="Sets the channel where birthday messages should be sent.")
    @discord.commands.guild_only()
    @discord.default_permissions(manage_guild=True)
    async def birthday_channel(self,
                       ctx: discord.ApplicationContext,
                       channel: discord.Option(discord.SlashCommandOptionType.channel,
                                               "The channel where birthday messages should be sent",
                                               channel_types=[discord.ChannelType.text])):
        guild_id = ctx.guild.id
        channel_id = channel.id
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                INSERT OR REPLACE INTO guilds (guild_id, channel_id)
                VALUES (?, ?)""", (guild_id, channel_id))
            await cur.close()
            await db.commit()
        await ctx.respond(f"Saved! Birthday messages will be sent to {channel.mention}.", ephemeral=True)
        
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        pass

    def adjust_date(self, now: datetime.date, bday: datetime.date):
        new_bday = bday.replace(now.year)
        if new_bday < now:
            return new_bday.replace(now.year + 1)
        else:
            return new_bday

    async def poll_birthdays(self):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT guild_id, user_id, birthday FROM birthdays") as cur:
                birthdays = await cur.fetchall()

        today = self.get_date()
        nextbirthdays = [(guild, user, self.adjust_date(today, datetime.date.fromisoformat(bday))) for guild, user, bday in birthdays]

        for guild, user, date in nextbirthdays:
            if date == today:
                try:
                    await self.send_birthday(guild, user)
                except Exception as e:
                    self.log.error(f"Error sending birthday message: {e}")
                    continue

    async def send_birthday(self, guild_id: int, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id FROM guilds WHERE guild_id = ?", [guild_id]) as cur:
                channel_id_row = await cur.fetchone()
                if channel_id_row is None:
                    self.log.error(f"Error sending birthday message: No channel set for guild {guild_id}")
                    return
                try:
                    guild = self.bot.get_guild(guild_id)
                    channel = guild.get_channel(channel_id_row[0])
                    user = guild.get_member(user_id)
                    await channel.send(f"Happy birthday, {user.mention}! :partying_face::birthday:")
                except Exception as e:
                    self.log.error(f"Error sending birthday message: {e}")
                    return
                
    def get_date(self) -> datetime.date:
        return self.get_datetime().date()

    def get_datetime(self) -> datetime.datetime:
        return datetime.datetime.now(tz=TIME_ZONE)