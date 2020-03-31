import logging
import os

import discord
import psycopg2

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


bot.run(DISCORD_TOKEN)
