import logging
import os
import difflib

import discord
import psycopg2

from discord.ext import commands

from data.furniture import furniture_info

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
async def hot(ctx, fuzzy_furniture_name: str):
    message = get_furniture_message(fuzzy_furniture_name)

    await ctx.send(message)


def get_furniture_message(fuzzy_furniture_name: str):
    furniture_name = get_best_match_furniture(fuzzy_furniture_name)

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


def get_best_match_furniture(fuzzy_furniture_name: str):
    matches = [
        (difflib.SequenceMatcher(None, fuzzy_furniture_name, name).ratio(), name)
        for name in furniture_info.keys()
    ]
    match_ratio, best_match_furniture = sorted(matches, reverse=True)[0]

    if match_ratio < 0.5:
        return None
    else:
        return best_match_furniture


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


bot.run(DISCORD_TOKEN)
