import calendar
import datetime
import logging
import os
import difflib
import tempfile

from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional

import discord
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import psycopg2
from py_mini_racer import py_mini_racer

from dateutil.parser import parse as parse_date
from discord.ext import commands

from data.furniture import furniture_info
from data.critters import fish_info, bug_info

DATABASE_URL = os.environ["DATABASE_URL"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

# the code makes the followingn assumptions about DAYS_PER_WEEK:
# - "Monday AM" is hardcoded
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
BASE_PRICE_DAY = DAYS_PER_WEEK[0]

logging.basicConfig(level=logging.WARNING)
bot = commands.Bot(command_prefix=["/turnip ", "/t ", "."])
conn = psycopg2.connect(DATABASE_URL, sslmode="require")


class MarketPatterns(Enum):
    random = "random"
    all_decrease = "all_decrease"
    small_bump = "small_bump"
    big_bump = "big_bump"


@bot.command(brief="pong")
async def ping(ctx):
    await ctx.send("pong")


# @bot.command()
async def advice(ctx):
    await ctx.send("TODO")


@bot.command()
async def remove_me(ctx):
    """Remove all data about your prices"""
    user_id = str(ctx.author.id)
    c.execute(
        """
        DELETE FROM user_servers
        WHERE
            user_id = %s
        """,
        (user_id,),
    )
    c.execute(
        """
        DELETE FROM prices
        WHERE
            user_id = %s
        """,
        (user_id,),
    )
    conn.commit()
    c.close()
    await ctx.message.add_reaction("🗑")


# TODO: Remove/update price
@bot.command(
    aliases=["add"],
    usage='<date> <"am", "pm"> <price>',
    brief="Add price data. ex: /t add 4/1/2020 am 100",
    help="""Add your turnip price for a day and time (AM or PM).
    The date should not have any spaces in it.

    ex: /t add 4/1/2020 am 100""",
)
async def add_price(ctx, day: str, time_of_day: str, price: str):
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
    if db_add_price(user_id, day, new_time_of_day, price):
        await ctx.message.add_reaction("👍")
    else:
        await ctx.send("Sorry, you've already added price information for this day.")


@bot.command(
    aliases=["show", "sg", "graph"],
    usage='[date] ["me"]',
    brief="Show graph of turnip prices for this week",
    help="""Show graph of turnip prices for a week.
    If date is specified, show graph for that week.
    If "me" is provided as an argument, show graph for just the caller (and not the whole server).

    ex:
    - /t sg
        (show graph for this week for everyone in server)
    - /t sg 4/1/2020
        (show graph for week of 4/1/2020 for everyone in server)
    - /t sg me
        (show graph for this week for just the caller)
    - /t sg 4/1/2020 me
        (show graph for week of 4/1/2020 for just the caller)
    """,
)
async def show_graph(ctx, *args):
    try:
        day = datetime.date.today()
        user_only = False
        if len(args) == 1:
            try:
                day = parse_date(args[0], fuzzy=True).date()
            except:
                user_only = args[0] == "me"
        elif len(args) == 2:
            day = parse_date(args[0], fuzzy=True).date()
            user_only = args[1] == "me"

        start_day, end_day = get_week_start_end(day)

        df = get_turnip_data(ctx, start_day, end_day, user_only)
        if df is None:
            await ctx.send("Sorry, there's no data for these parameters!")

        fig = build_graph(ctx, df)

        with tempfile.NamedTemporaryFile(suffix=".png") as tf:
            fig.savefig(tf.name, bbox_inches="tight", dpi=150)
            plt.close(fig)
            await ctx.send(
                f"Showing plot for week of {start_day}",
                file=discord.File(tf.name, tf.name),
            )
    except Exception as e:
        await ctx.send(str(e))


def get_turnip_data(ctx, start_day, end_day, user_only=False):
    """
    Params match that of show_graph
    """
    user_id = str(ctx.author.id)
    server_id = str(ctx.guild.id)
    db_add_user_server(user_id, server_id)

    c = conn.cursor()

    if user_only:
        c.execute(
            """
            SELECT
            user_id,
            day,
            day_of_week,
            time_of_day,
            price
            FROM
                prices
            WHERE
                user_id = %s AND
                day >= %s AND
                day < %s
            ORDER BY
                day, time_of_day
            """,
            (user_id, start_day, end_day),
        )
    else:
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
    rows = c.fetchall()
    if len(rows) == 0:
        return None

    df = pd.DataFrame(
        rows, columns=["user_id", "day", "day_of_week", "time_of_day", "price",],
    )
    c.close()
    return df


def get_week_start_end(day: datetime.date) -> (datetime.date, datetime.date):
    if day.weekday() == 6:
        day = day - datetime.timedelta(days=-7)

    start_day = beginning_of_week(day)
    end_day = start_day + datetime.timedelta(days=7)
    return start_day, end_day


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
) -> bool:
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
        return False

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
    return True


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


def analyze_prices(ctx, df: pd.DataFrame):
    # format columns
    user_name_map = get_user_id_display_name_map(ctx, df)
    df["User"] = df["user_id"].map(user_name_map)
    df["Timepoint"] = df["day_of_week"] + " " + df["time_of_day"]

    # calculate perent of base
    def get_percent_of_base(row, base_prices):
        if row["User"] in base_prices and row["Timepoint"] != BASE_PRICE_DAY:
            return row["price"] / base_prices[row["User"]] * 100
        else:
            return None

    base_prices = {
        row["User"]: row["price"]
        for _, row in df[df["Timepoint"] == BASE_PRICE_DAY].iterrows()
    }
    df["percent_of_base"] = df.apply(
        lambda row: get_percent_of_base(row, base_prices), axis=1
    )

    # calculate and merge in most likely pattern per user
    # this calculates possible patterns using all data present, not incrementally per half day. thus, for a given user, the "pattern" column has the same value in every row
    patterns_data = {
        "User": [],
        "probability": [],
        "pattern": [],
    }
    for user, group in df.groupby("User"):
        probability, pattern = get_most_likely_pattern(
            pd.Series(data=group["price"].tolist(), index=group["Timepoint"])
        )
        patterns_data["User"].append(user)
        patterns_data["probability"].append(probability)
        patterns_data["pattern"].append(pattern)

    patterns_df = pd.DataFrame(patterns_data)
    df = pd.merge(df, patterns_df, how="left", on="User")
    return df


def build_graph(ctx, df: pd.DataFrame):
    # ctx isn't used, but needs to be passed

    df = analyze_prices(ctx, df)
    fig, ax = plt.subplots()

    # label points with price percentage relative to base
    for _, row in df.iterrows():
        if row["Timepoint"] == BASE_PRICE_DAY:
            # annotate base price
            ax.annotate(
                row["price"], xy=(DAYS_PER_WEEK.index(row["Timepoint"]), row["price"]),
            )
        elif not np.isnan(row["percent_of_base"]):
            # annotate precentage of base price
            ax.annotate(
                "{:.0f}%".format(row["percent_of_base"]),
                xy=(DAYS_PER_WEEK.index(row["Timepoint"]), row["price"]),
            )

    # include the pattern in the legend if it is known
    def format_legend(row):
        if row["probability"] > 0.5:
            return f"{row['User']} ({row['pattern']}, {row['probability'].value})"
        return row["User"]

    df["legend"] = df.apply(format_legend, axis=1)

    # pivot to plot
    df2 = df.pivot(index="Timepoint", columns="legend", values="price")
    df2 = df2.reindex(DAYS_PER_WEEK)

    df2.plot(
        ax=ax, style="o-", xlim=(0, 14),
    )
    ax.set_xticks(list(range(14)))
    ax.set_xticklabels(df2.index, rotation=60, ha="right")

    plt.legend(loc=2, prop={"size": 6})

    plt.tight_layout()

    return fig


def get_most_likely_pattern(
    user_prices: pd.Series, previous_pattern=None
) -> (float, str):
    """
    :user_prices: series where index is day of week, value is price
    :previous_pattern: not yet implemented
    """
    # improvement: cache these lines
    with open("turnipprophet/predict.js") as f:
        prophet_js_code = f.read()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(prophet_js_code)

    # format a prices array for how the js code wants it
    # pad holes for unreported days
    days = pd.Series(index=DAYS_PER_WEEK, name="days")
    user_prices.name = "prices"
    df = pd.merge(
        days.to_frame(), user_prices, how="left", right_index=True, left_index=True
    )
    assert list(df.index) == DAYS_PER_WEEK

    prices = df["prices"].tolist()
    # js code wants the initial price specified twice (i.e. Sunday PM filled in by the Sunday AM price)
    prices[1] = prices[0]
    js_formatted = [str(int(x)) if x and not np.isnan(x) else "null" for x in prices]

    ctx.eval(f'let predictor = new Predictor([{", ".join(js_formatted)}], false, null)')
    data = ctx.eval("predictor.analyze_possibilities()")

    # for the time being while not yet implemented, for simplicity remove the first element. this is the projection range across all possible patterns
    data = data[1:]

    # the returned array has a lot of information, unclear how to interpret
    # just seeing if we can pick out some things, and throwing out all the other information

    pattern_probabilities = [
        (x["category_total_probability"], x["pattern_description"])
        for x in data
        if "category_total_probability" in x and "pattern_description" in x
    ]

    if len(pattern_probabilities) == 0:
        return None, None

    # return probability, pattern
    most_likely = sorted(pattern_probabilities)[0]
    return most_likely


@bot.command(
    usage="<hot item>", brief="Show crafting and price information for hot items."
)
async def hot(ctx, *args):
    fuzzy_furniture_name = " ".join(args)
    message = get_furniture_message(fuzzy_furniture_name)

    await ctx.send(message)


def get_furniture_message(fuzzy_furniture_name: str):
    furniture_name = get_best_match_item(fuzzy_furniture_name, furniture_info)

    if not furniture_name:
        message = f"No match found for {fuzzy_furniture_name}"
    else:
        message = furniture_name.title()

        if furniture_info[furniture_name]["materials"]:
            message = message + " " + get_furniture_materials(furniture_name)
        else:
            message = message + " (no craft info)"

        if furniture_info[furniture_name]["sell"]:
            price_string = furniture_info[furniture_name]["sell"]
            if "each" in price_string:
                assert " (each)" in price_string
                double = str(int(price_string.replace(" (each)", "")) * 2) + " (each)"
            else:
                double = int(price_string) * 2
            message = message + f", sells for {price_string} x 2 = {double} bells"
        else:
            message = message + ", no price info"

    return message


def get_best_match_item(fuzzy_item_name: str, item_info: Dict[str, Dict[str, Any]]):
    matches = [
        (difflib.SequenceMatcher(None, fuzzy_item_name, name).ratio(), name)
        for name in item_info.keys()
    ]
    match_ratio, best_match_item = sorted(matches, reverse=True)[0]

    if match_ratio < 0.5:
        return None
    else:
        return best_match_item


def get_furniture_materials(furniture_name: str):
    """
    recursive method
    """
    materials = []
    for material in furniture_info[furniture_name]["materials"]:
        material_string = material["number"] + " " + material["name"]
        if material["name"] in furniture_info:
            material_string = (
                material_string + " " + get_furniture_materials(material["name"])
            )
        else:
            pass  # base case

        materials.append(material_string)

    return "(" + ", ".join(materials) + ")"


@bot.command(usage="<fish>", brief="Show price for fish.")
async def fish(ctx, *args):
    fuzzy_fish_name = " ".join(args)
    message = get_critter_message(fuzzy_fish_name, fish_info)
    await ctx.send(message)


@bot.command(usage="<bug>", brief="Show price for bug.")
async def bug(ctx, *args):
    fuzzy_bug_name = " ".join(args)
    message = get_critter_message(fuzzy_bug_name, bug_info)
    await ctx.send(message)


def get_critter_message(
    fuzzy_critter_name: str, critter_info: Dict[str, Dict[str, Any]]
) -> str:
    critter_name = get_best_match_item(fuzzy_critter_name, critter_info)

    if critter_name is None:
        message = f"No match found for {fuzzy_critter_name}"
    else:
        price = critter_info[critter_name]["price"]
        message = f"{critter_name} sells for {price} bells"
    return message


@bot.command(aliases=["pattern"], brief="List turnip price patterns.")
async def patterns(ctx, *args):
    message = """Large spike: 85-90% decreasing 3-5%, for 1-7 half days. Sell on 3rd increase for 200-600%.
    Small spike: 40-90% decreasing 3-5%, for 0-7 half days. Two halves 90-150%, then increases 140-highest (max 200%), then to the highest.
    Decreasing: 85-90% decreasing 3-5%
    Random: flips between 90-140% (initially 0-6 half days), and 60-80% decreasing 4-10%
    """
    await ctx.send(message)


bot.run(DISCORD_TOKEN)
