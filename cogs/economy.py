import discord
from discord.ext import commands
from datetime import datetime, timedelta

from database import c, conn, get_user_monies, update_monies, add_daily_reward
from helpers import info_embed, error_embed

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balance", help="Check your monies balance")
    async def balance(self, ctx):
        monies = get_user_monies(ctx.author.id, ctx.guild.id)
        embed = info_embed(
            "💰 Balance",
            f"{ctx.author.mention}, you have **{monies}** monies.",
            discord.Color.gold()
        )
        embed.set_footer(text="Use !daily to claim a daily reward.")
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "top"], help="Show the top 10 richest users")
    async def leaderboard(self, ctx):
        c.execute(
            "SELECT user_id, monies FROM users WHERE guild_id=? "
            "ORDER BY monies DESC LIMIT 10",
            (str(ctx.guild.id),),
        )
        top_users = c.fetchall()

        if not top_users:
            await ctx.send(embed=error_embed("No users found on the leaderboard yet!"))
            return

        embed = discord.Embed(
            title="🏆 Monies Leaderboard",
            color=discord.Color.gold(),
        )

        description = ""
        for index, (user_id, monies) in enumerate(top_users, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"

            if index == 1:
                rank = "🥇"
            elif index == 2:
                rank = "🥈"
            elif index == 3:
                rank = "🥉"
            else:
                rank = f"#{index}"

            description += f"**{rank}** {name}: **{monies}** monies\n"

        embed.description = description
        embed.set_footer(text="Use !balance to see your own monies.")
        await ctx.send(embed=embed)

    @commands.command(name="daily", help="Claim your daily 100 monies and 10 carats")
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)

        now = datetime.now()
        c.execute(
            "SELECT monies, last_daily FROM users WHERE user_id=? AND guild_id=?",
            (user_id, guild_id),
        )
        result = c.fetchone()

        if result is not None:
            _, last_daily_str = result
            if last_daily_str:
                last_daily = datetime.strptime(last_daily_str, "%Y-%m-%d %H:%M:%S")
                time_passed = now - last_daily
                if time_passed < timedelta(hours=24):
                    time_left = timedelta(hours=24) - time_passed
                    hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    embed = info_embed(
                        "⏰ Daily Cooldown",
                        f"{ctx.author.mention}, you must wait **{hours}h {minutes}m** before claiming again.",
                        discord.Color.orange()
                    )
                    await ctx.send(embed=embed)
                    return

        new_monies, new_carats = add_daily_reward(user_id, guild_id)
        embed = info_embed(
            "🎁 Daily Reward",
            f"{ctx.author.mention}, you collected your daily reward!\n"
            f"**+100** monies · **+10** carats\n"
            f"Balance: **{new_monies}** monies · **{new_carats}** carats",
            discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))