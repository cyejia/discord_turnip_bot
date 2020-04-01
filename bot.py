import calendar
import datetime
import logging
import os
import tempfile

from typing import List, Optional

import discord
import matplotlib.pyplot as plt
import pandas as pd
import psycopg2

from dateutil.parser import parse as parse_date
from discord.ext import commands

DATABASE_URL = os.environ["DATABASE_URL"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DAYS_PER_WEEK = [
    "Sunday",
    "",
    "Monday AM",
    "Monday PM",
    "Tuesday AM",
    "Tuesday PM",
    "Wednesday AM",
    "Wednesday PM",
    "Thursday AM",
    "Thursday PM",
    "Friday AM",
    "Friday PM",
    "Saturday AM",
    "Saturday PM",
]
logging.basicConfig(level=logging.DEBUG)
bot = commands.Bot(command_prefix="/turnip ")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


# TODO: Remove/update price
@bot.command()
async def add_price(ctx, day: str, time_of_day: str, price: str):
    """Add your price data. Takes in a date, "AM" or "PM", and your price. Example: /turnip add_price 4/1/2020 AM
    """
    # TODO some sort of permission granting?
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

    # TODO: better messaging
    if day.weekday == 6:
        new_time_of_day = "AM"

    user_id = str(ctx.author.id)
    db_add_price(
        str(ctx.guild.id), user_id, ctx.author.name, day, new_time_of_day, price
    )

    # TODO: Make this a reaction instead
    await ctx.message.add_reaction("👍")


@bot.command()
async def show_graph(ctx, day_str: Optional[str] = None):
    if day_str is not None:
        day = parse_date(day, fuzzy=True).date()
    else:
        day = datetime.date.today()

    if day.weekday() == 6:
        day = day - datetime.timedelta(days=-7)

    start_day = beginning_of_week(day)
    end_day = start_day + datetime.timedelta(days=7)

    c = conn.cursor()
    # TODO: include Sunday?
    c.execute(
        """
        SELECT
           server_id,
           user_id,
           user_name,
           day,
           day_of_week,
           time_of_day,
           price
        FROM
            prices
        WHERE
            server_id = %s AND
            day > %s AND
            day < %s
        ORDER BY
            day, time_of_day
    """,
        (str(ctx.guild.id), start_day, end_day),
    )
    df = pd.DataFrame(
        c.fetchall(),
        columns=[
            "server_id",
            "user_id",
            "user_name",
            "day",
            "day_of_week",
            "time_of_day",
            "price",
        ],
    )
    c.close()

    df["day_time"] = df["day_of_week"] + " " + df["time_of_day"]
    df2 = df.pivot(index="day_time", columns="user_id", values="price")
    df2 = df2.reindex(DAYS_PER_WEEK)

    fig, ax = plt.subplots()

    df.plot(ax=ax)

    # plt.legend()
    # plt.plot()
    # for user_id in df2.columns:
    #     plt.plot(df2.index, df2[user_id].values)

    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        fig.savefig(tf.name, bbox_inches="tight", dpi=150)
        plt.close(fig)
        await ctx.send("Showing plot for TODO", file=discord.File(tf.name, tf.name))


def beginning_of_week(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.isoweekday() % 7)


def db_add_price(
    server_id: str,
    user_id: str,
    user_name: Optional[str],
    day: datetime.date,
    time_of_day: str,
    price: int,
):
    c = conn.cursor()

    c.execute(
        """
        SELECT *
        FROM
            prices
        WHERE
            server_id = %s AND
            user_id = %s AND
            day = %s AND
            time_of_day = %s
        """,
        (server_id, user_id, day, time_of_day),
    )
    if c.fetchone() is not None:
        # TODO: Update price?
        c.close()
        return

    c.execute(
        """
        INSERT INTO
            prices (
                server_id,
                user_id,
                user_name,
                day,
                day_of_week,
                time_of_day,
                price
            )
        VALUES
            (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            server_id,
            user_id,
            user_name,
            day,
            calendar.day_name[day.weekday()],
            time_of_day,
            price,
        ),
    )
    conn.commit()
    c.close()


bot.run(DISCORD_TOKEN)
