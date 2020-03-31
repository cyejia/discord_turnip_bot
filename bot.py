import logging
import os
import difflib

import discord
import psycopg2

from discord.ext import commands

from data.furniture import furniture_prices

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
    await ctx.send(f"Adding {ctx.author.name}")


@bot.command()
async def add_price(ctx, time: str, price: str):
    new_time = time.upper()
    if new_time not in {"AM", "PM"}:
        await ctx.send("The first argument should be 'am' or 'pm'")
        return

    try:
        price = int(price)
    except ValueError as e:
        await ctx.send("The second argument must be a whole number")
        return

    await ctx.send(f"Ok! Adding {new_time} price for {ctx.author.name} as {price}")


@bot.command()
async def show_graph(ctx, time: str, price: str):
    await ctx.send("Not implemented :(")


@bot.command()
async def hot(ctx, furniture_name: str):
    best_match_furniture, price = get_furniture_price(furniture_name)

    if not best_match_furniture:
        message = f"No match found for {furniture_name}"
    else:
        if price:
            message = f"{best_match_furniture}, sells for {price} x 2 = {price * 2}"
        else:
            message = f"No price found for {best_match_furniture}"

        await ctx.send(message)


def get_furniture_price(furniture_name: str):
    """
    Returns (best_match_furniture_name, price)
    """

    def bells_to_int(price):
        return int(price.replace(" Bells", "").replace(",", ""))

    matches = [
        (difflib.SequenceMatcher(None, furniture_name, name).ratio(), name)
        for name in furniture_prices.keys()
    ]
    match_ratio, best_match_furniture = sorted(matches, reverse=True)[0]

    if match_ratio < 0.5:
        return None, None
    else:
        price_string = furniture_prices[best_match_furniture]

        if price_string == "" or price_string == "*":
            return best_match_furniture, None
        else:
            price = bells_to_int(price_string)
            return best_match_furniture, price


bot.run(DISCORD_TOKEN)
