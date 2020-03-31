import logging
import os

import discord
from discord.ext import commands

logging.basicConfig(level=logging.DEBUG)
bot = commands.Bot(command_prefix="/turnip ")


@bot.command()
async def ping(ctx):
    logging.log(logging.DEBUG, "sup bitch")
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


bot.run(os.environ["DISCORD_TOKEN"])
