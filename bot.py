import datetime
import logging
import os

import discord
import psycopg2

from dateutil.parser import parse as parse_date
from discord.ext import commands

DATABASE_URL = os.environ["DATABASE_URL"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

logging.basicConfig(level=logging.DEBUG)
bot = commands.Bot(command_prefix="/turnip ")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.command()
async def add_me(ctx):
    db_add_user(str(ctx.author.id), str(ctx.guild.id))
    await ctx.send(f"Adding {ctx.author.name} to {ctx.guild.name}'s turnip tracking'")


@bot.command()
async def add_price(ctx, day: str, time_of_day: str, price: str):
    new_time_of_day = time_of_day.upper()
    if new_time_of_day not in {"AM", "PM"}:
        await ctx.send("The first argument should be 'am', 'pm', 'AM', or 'PM'")
        return

    try:
        price = int(price)
    except ValueError as e:
        await ctx.send("The second argument must be a whole number")
        return

    try:
        day = parse_date(day, fuzzy=True).date()
    except Exception as e:
        await ctx.send(f"Sorry, could not parse {day} as a date")
        return

    user_id = str(ctx.author.id)

    if not db_user_exists(user_id):
        db_add_user(user_id, str(ctx.guild.id))

    db_add_price(user_id, day, new_time_of_day, price)

    await ctx.send(
        f"Ok! Adding {day} {new_time_of_day} price for {ctx.author.name} as {price}"
    )


@bot.command()
async def show_graph(ctx, time: str, price: str):
    await ctx.send("Not implemented :(")


def db_user_exists(user_id: str) -> bool:
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    exists = c.fetchone() is not None
    c.close()
    return exists


def db_add_user(user_id: str, server_id: str):
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))

    c.execute(
        "SELECT * FROM servers WHERE user_id = %s AND server_id = %s",
        (user_id, server_id),
    )
    if c.fetchone() is None:
        c.execute(
            "INSERT INTO servers (user_id, server_id) VALUES (%s, %s)",
            (user_id, server_id),
        )

    c.close()


def db_add_price(user_id: str, day: datetime.date, time_of_day: str, price: int):
    c = conn.cursor()
    c.execute(
        "INSERT INTO prices (user_id, day, time_of_day, price) VALUES (%s, %s, %s, %s)",
        (user_id, day, time_of_day, price),
    )
    c.close()


bot.run(DISCORD_TOKEN)
