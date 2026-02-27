import discord
from discord.ext import commands

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", help="Show this help message")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="📖 Betting Bot Help",
            description="All available commands:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="!help",
            value="Show this help message.",
            inline=False
        )
        embed.add_field(
            name="!balance",
            value="Show your current points balance.",
            inline=False
        )
        embed.add_field(
            name="!daily",
            value="Claim your daily 100 points (24h cooldown).",
            inline=False
        )
        embed.add_field(
            name="!leaderboard / !lb / !top",
            value="Show the top 10 users by points in this server.",
            inline=False
        )
        embed.add_field(
            name="!createbet",
            value=(
                "Interactively create a new bet with multiple outcomes.\n"
                "You’ll be asked for description and outcome names. Type `cancel` to cancel."
            ),
            inline=False
        )
        embed.add_field(
            name="!bets",
            value="Show all active bets, IDs, outcomes, pools, and payout multipliers.",
            inline=False
        )
        embed.add_field(
            name="!bet",
            value=(
                "Interactively place a bet on an active bet.\n"
                "You’ll pick a Bet ID, an outcome, and an amount. Type `cancel` to cancel."
            ),
            inline=False
        )
        embed.add_field(
            name="!resolve <bet_id>",
            value=(
                "Resolve a bet you created. You’ll choose the winning outcome.\n"
                "If no one bet on it, all wagers are refunded."
            ),
            inline=False
        )

        embed.set_footer(text="Type 'cancel' during any interactive command to cancel it.")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Misc(bot))