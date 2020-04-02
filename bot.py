import calendar
import datetime
import logging
import os
import tempfile

from collections import defaultdict
from typing import Dict, List, Optional

import discord
import matplotlib.pyplot as plt
import pandas as pd
import psycopg2

from dateutil.parser import parse as parse_date
from discord.ext import commands

DATABASE_URL = os.environ["DATABASE_URL"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DAYS_PER_WEEK = [
    "Sunday AM",
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
    db_add_user_server(user_id, str(ctx.guild.id))
    db_add_price(user_id, day, new_time_of_day, price)

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

    user_id = str(ctx.author.id)
    server_id = str(ctx.guild.id)
    db_add_user_server(user_id, server_id)

    c = conn.cursor()

    c.execute(
        """
        SELECT
           prices.user_id,
           day,
           day_of_week,
           time_of_day,
           price
        FROM
            prices
        JOIN
            user_servers
        ON
            prices.user_id = user_servers.user_id
        WHERE
            server_id = %s AND
            day >= %s AND
            day < %s
        ORDER BY
            day, time_of_day
    """,
        (server_id, start_day, end_day),
    )
    df = pd.DataFrame(
        c.fetchall(),
        columns=["user_id", "day", "day_of_week", "time_of_day", "price",],
    )
    c.close()

    fig = build_graph(ctx, df)

    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        fig.savefig(tf.name, bbox_inches="tight", dpi=150)
        plt.close(fig)
        await ctx.send(
            f"Showing plot for week of {start_day}", file=discord.File(tf.name, tf.name)
        )


def beginning_of_week(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.isoweekday() % 7)


def db_add_user_server(user_id: str, server_id: str):
    c = conn.cursor()

    c.execute(
        """
        SELECT *
        FROM
            user_servers
        WHERE
            user_id = %s AND
            server_id = %s
        """,
        (user_id, server_id),
    )

    row = c.fetchone()
    if row is None:
        c.execute(
            """
        INSERT INTO
            user_servers (user_id, server_id)
        VALUES
            (%s, %s)
        """,
            (user_id, server_id),
        )
        conn.commit()
    c.close()


def db_add_price(
    user_id: str, day: datetime.date, time_of_day: str, price: int,
):
    c = conn.cursor()

    c.execute(
        """
        SELECT *
        FROM
            prices
        WHERE
            user_id = %s AND
            day = %s AND
            time_of_day = %s
        """,
        (user_id, day, time_of_day),
    )
    if c.fetchone() is not None:
        # TODO: Update price?
        c.close()
        return

    c.execute(
        """
        INSERT INTO
            prices (
                user_id,
                day,
                day_of_week,
                time_of_day,
                price
            )
        VALUES
            (%s, %s, %s, %s, %s)
        """,
        (user_id, day, calendar.day_name[day.weekday()], time_of_day, price,),
    )
    conn.commit()
    c.close()


def get_user_id_display_name_map(ctx, df: pd.DataFrame) -> Dict[str, str]:
    turnip_users = pd.unique(df["user_id"])
    members = [member for member in ctx.guild.members if str(member.id) in turnip_users]

    user_id_member_map = {
        str(member.id): (member.display_name, member.name, member.discriminator)
        for member in members
    }

    display_name_counts = defaultdict(int)
    use_discriminator = False

    for user_id, (display_name, name, discriminator) in user_id_member_map.items():
        display_name_counts[display_name] = display_name_counts[display_name] + 1
        if display_name_counts[display_name] > 1:
            use_discriminator = True
            break

    return {
        user_id: f"{display_name} ({name}#{discriminator})"
        if use_discriminator
        else display_name
        for user_id, (display_name, name, discriminator) in user_id_member_map.items()
    }


def build_graph(ctx, df: pd.DataFrame):
    user_name_map = get_user_id_display_name_map(ctx, df)
    df["User"] = df["user_id"].map(user_name_map)
    df["Timepoint"] = df["day_of_week"] + " " + df["time_of_day"]

    df2 = df.pivot(index="Timepoint", columns="User", values="price")
    df2 = df2.reindex(DAYS_PER_WEEK)

    fig, ax = plt.subplots()

    df2.plot(
        ax=ax, style="o-", xlim=(0, 14),
    )
    ax.set_xticks(list(range(14)))
    ax.set_xticklabels(df2.index, rotation=60, ha="right")
    plt.legend(loc=2, prop={"size": 6})

    plt.tight_layout()

    return fig


bot.run(DISCORD_TOKEN)
