import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
# Note: We set help_command=None to disable default help, as you have a custom one.
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Initialize database tables
database.setup_db()

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")

async def main():
    async with bot:
        # Load cogs
        await bot.load_extension("cogs.economy")
        await bot.load_extension("cogs.betting")
        await bot.load_extension("cogs.misc")
        await bot.load_extension("cogs.horserace")
        await bot.load_extension("cogs.bigrace")

        # Start bot
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())