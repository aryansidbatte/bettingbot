import discord
from discord.ext import commands
from datetime import datetime, timedelta

from database import c, conn, _PH, get_user_monies, update_monies, add_daily_reward, get_user_carats
from helpers import info_embed, error_embed

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balance", help="Check your monies and carats balance")
    async def balance(self, ctx):
        monies = get_user_monies(ctx.author.id, ctx.guild.id)
        carats = get_user_carats(ctx.author.id, ctx.guild.id)
        embed = info_embed(
            "💰 Balance",
            f"{ctx.author.mention}\n**{monies}** monies · **{carats}** carats",
            discord.Color.gold()
        )
        embed.set_footer(text="Use !daily to claim a daily reward.")
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "top"], help="Show the top 10 users by monies")
    async def leaderboard(self, ctx):
        c.execute(
            f"SELECT user_id, monies FROM users WHERE guild_id={_PH} "
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
            rank = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"#{index}"
            description += f"**{rank}** {name}: **{monies}** monies\n"

        embed.description = description
        embed.set_footer(text="Use !balance to see your own balance.")
        await ctx.send(embed=embed)

    @commands.command(name="caratboard", aliases=["cb"], help="Show the top 10 users by carats")
    async def caratboard(self, ctx):
        c.execute(
            f"SELECT user_id, carats FROM users WHERE guild_id={_PH} "
            "ORDER BY carats DESC LIMIT 10",
            (str(ctx.guild.id),),
        )
        top_users = c.fetchall()

        if not top_users:
            await ctx.send(embed=error_embed("No users found on the caratboard yet!"))
            return

        embed = discord.Embed(
            title="💎 Carats Leaderboard",
            color=discord.Color.purple(),
        )

        description = ""
        for index, (user_id, carats) in enumerate(top_users, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            rank = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"#{index}"
            description += f"**{rank}** {name}: **{carats}** carats\n"

        embed.description = description
        embed.set_footer(text="Use !balance to see your own balance.")
        await ctx.send(embed=embed)

    @commands.command(name="daily", help="Claim your daily 100 monies and 10 carats")
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)

        now = datetime.now()
        c.execute(
            f"SELECT monies, last_daily FROM users WHERE user_id={_PH} AND guild_id={_PH}",
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

    @commands.command(name="forcedaily", help="(Admin) Give all server members their daily reward without resetting timers")
    @commands.has_permissions(manage_guild=True)
    async def force_daily(self, ctx):
        c.execute(
            f"UPDATE users SET monies=monies+100, carats=carats+10 WHERE guild_id={_PH}",
            (str(ctx.guild.id),),
        )
        conn.commit()
        count = c.rowcount
        await ctx.send(embed=info_embed(
            "🎁 Force Daily",
            f"Gave **+100 monies** and **+10 carats** to **{count}** user(s).\nCooldown timers were not affected.",
            discord.Color.green()
        ))

async def setup(bot):
    await bot.add_cog(Economy(bot))