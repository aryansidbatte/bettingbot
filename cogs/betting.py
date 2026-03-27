import asyncio
import discord
from discord.ext import commands

from database import c, conn, get_user_monies, update_monies
from helpers import info_embed, error_embed, get_reply_or_cancel


def parse_instant_bet(args: str) -> tuple:
    """Parse 'description | outcome1 | outcome2 ...' into (description, [outcomes]).
    Raises ValueError with a user-facing message on invalid input.
    """
    parts = [p.strip() for p in args.split("|")]
    description = parts[0]
    outcomes = parts[1:]

    if not description:
        raise ValueError("Description can't be empty.")
    if len(outcomes) < 2:
        raise ValueError("Need at least 2 outcomes.")
    if len(outcomes) > 10:
        raise ValueError("Maximum 10 outcomes.")
    if any(o == "" for o in outcomes):
        raise ValueError("Outcome names can't be empty.")

    return description, outcomes


class Betting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="createbet", help="Create a bet: !createbet desc | o1 | o2  or just !createbet for guided setup")
    async def create_bet(self, ctx, *, args: str = ""):
        if args:
            try:
                description, option_names = parse_instant_bet(args)
            except ValueError as e:
                await ctx.send(embed=error_embed(
                    f"{e}\n\nUsage:\n• `!createbet description | outcome 1 | outcome 2`\n• Or just `!createbet` for guided setup"
                ))
                return

            c.execute(
                "INSERT INTO bets (guild_id, creator_id, description) VALUES (?, ?, ?)",
                (str(ctx.guild.id), str(ctx.author.id), description),
            )
            conn.commit()
            bet_id = c.lastrowid

            for name in option_names:
                c.execute(
                    "INSERT INTO bet_options (bet_id, name) VALUES (?, ?)",
                    (bet_id, name),
                )
            conn.commit()

            lines = [f"{idx}. {name}" for idx, name in enumerate(option_names, start=1)]

            embed = info_embed("🎲 New Bet Created!", "", discord.Color.green())
            embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Outcomes", value="\n".join(lines), inline=False)
            embed.add_field(
                name="How to Bet",
                value="Use `!bet` and follow the prompts to choose this bet and an outcome.",
                inline=False,
            )
            await ctx.send(embed=embed)
            return

        wizard_msg = await ctx.send(embed=info_embed("🎲 Create a Bet", "Starting…", discord.Color.green()))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        async def ask(prompt_embed):
            """Edit the wizard message with prompt_embed, wait for a reply. Returns content string or None."""
            await wizard_msg.edit(content=None, embed=prompt_embed)
            try:
                msg = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await wizard_msg.edit(
                    embed=error_embed("Timed out. Please run the command again.")
                )
                return None
            if msg.content.strip().lower() == "cancel":
                await wizard_msg.edit(
                    embed=info_embed("❌ Cancelled", "Bet creation cancelled.", discord.Color.orange())
                )
                return None
            return msg.content.strip()

        description = await ask(info_embed(
            "🎲 Create a Bet",
            "📝 What is the bet **description**?\nExample: `Who will win the game?`",
            discord.Color.green(),
        ))
        if description is None:
            return

        count_str = await ask(info_embed(
            "🎲 Create a Bet",
            "🔢 How many **outcomes** does this bet have? (minimum 2, maximum 10)",
            discord.Color.green(),
        ))
        if count_str is None:
            return

        try:
            num_outcomes = int(count_str)
        except ValueError:
            await wizard_msg.edit(embed=error_embed("Please enter a valid number (2–10)."))
            return

        if num_outcomes < 2 or num_outcomes > 10:
            await wizard_msg.edit(embed=error_embed("Number of outcomes must be between 2 and 10."))
            return

        option_names = []
        for i in range(1, num_outcomes + 1):
            name = await ask(info_embed(
                "🎲 Create a Bet",
                f"✏️ Enter name for **Outcome #{i}**:",
                discord.Color.green(),
            ))
            if name is None:
                return
            if not name:
                await wizard_msg.edit(embed=error_embed("Outcome name cannot be empty."))
                return
            option_names.append(name)

        c.execute(
            "INSERT INTO bets (guild_id, creator_id, description) VALUES (?, ?, ?)",
            (str(ctx.guild.id), str(ctx.author.id), description),
        )
        conn.commit()
        bet_id = c.lastrowid

        for name in option_names:
            c.execute(
                "INSERT INTO bet_options (bet_id, name) VALUES (?, ?)",
                (bet_id, name),
            )
        conn.commit()

        c.execute("SELECT option_id, name FROM bet_options WHERE bet_id=?", (bet_id,))
        options = c.fetchall()
        lines = [f"{idx}. {name}" for idx, (option_id, name) in enumerate(options, start=1)]

        embed = info_embed("🎲 New Bet Created!", "", discord.Color.green())
        embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Outcomes", value="\n".join(lines), inline=False)
        embed.add_field(
            name="How to Bet",
            value="Use `!bet` and follow the prompts to choose this bet and an outcome.",
            inline=False,
        )
        await wizard_msg.edit(embed=embed)

    @commands.command(name="bets", help="View all active bets and their outcomes")
    async def view_bets(self, ctx):
        c.execute(
            "SELECT bet_id, description FROM bets WHERE guild_id=? AND status='open'",
            (str(ctx.guild.id),),
        )
        bets = c.fetchall()

        if not bets:
            await ctx.send(embed=error_embed("No active bets! Use `!createbet` to make one."))
            return

        embed = discord.Embed(
            title="🎲 Active Bets",
            description="Here are all open bets and their IDs.",
            color=discord.Color.blue(),
        )

        for bet_id, desc in bets:
            c.execute(
                "SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?",
                (bet_id,),
            )
            options = c.fetchall()
            if not options:
                continue

            pools = [row[2] for row in options]
            total_pool = sum(pools) if pools else 0

            lines = []
            for idx, (option_id, name, total_amount) in enumerate(options, start=1):
                if total_pool > 0 and total_amount > 0:
                    odds = total_pool / total_amount
                    odds_str = f"{odds:.2f}x"
                else:
                    odds_str = "1.00x"
                lines.append(
                    f"{idx}. {name} "
                    f"({total_amount} monies, Payout: {odds_str})"
                )

            embed.add_field(
                name=f"Bet #{bet_id}: {desc}",
                value="\n".join(lines),
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="bet", help="Interactively place a bet on any outcome")
    async def place_bet(self, ctx):
        c.execute(
            "SELECT bet_id, description FROM bets WHERE guild_id=? AND status='open'",
            (str(ctx.guild.id),),
        )
        bets = c.fetchall()

        if not bets:
            await ctx.send(embed=error_embed("No active bets! Use `!createbet` to make one."))
            return

        lines = [f"Bet #{bet_id}: {desc}" for bet_id, desc in bets]
        msg_id = await get_reply_or_cancel(
            self.bot,
            ctx,
            "📋 **Active Bets:**\n"
            + "\n".join(lines)
            + "\n\n📌 Reply with the **Bet ID** (number) you want to bet on."
        )
        if msg_id is None:
            return

        try:
            bet_id = int(msg_id.content.strip())
        except ValueError:
            await ctx.send(embed=error_embed("Bet ID must be a number. Run `!bet` again."))
            return

        c.execute(
            "SELECT bet_id, description, status FROM bets "
            "WHERE bet_id=? AND guild_id=?",
            (bet_id, str(ctx.guild.id)),
        )
        bet = c.fetchone()
        if not bet:
            await ctx.send(embed=error_embed(f"Bet #{bet_id} not found."))
            return

        bet_id_db, desc, status = bet
        if status != "open":
            await ctx.send(embed=error_embed(f"Bet #{bet_id_db} is not open."))
            return

        c.execute(
            "SELECT 1 FROM wagers WHERE bet_id=? AND user_id=?",
            (bet_id_db, str(ctx.author.id)),
        )
        if c.fetchone():
            await ctx.send(embed=error_embed("You already placed a wager on this bet."))
            return

        c.execute(
            "SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?",
            (bet_id_db,),
        )
        options = c.fetchall()
        if not options:
            await ctx.send(embed=error_embed("This bet has no outcomes configured."))
            return

        opt_lines = []
        for idx, (option_id, name, total_amount) in enumerate(options, start=1):
            opt_lines.append(f"{idx}. {name} — Current pool: {total_amount}")

        msg_choice = await get_reply_or_cancel(
            self.bot,
            ctx,
            f"Bet #{bet_id_db}: **{desc}**\n"
            "Reply with the **number** of the outcome you want to bet on:\n"
            + "\n".join(opt_lines)
        )
        if msg_choice is None:
            return

        try:
            choice_idx = int(msg_choice.content.strip())
        except ValueError:
            await ctx.send(embed=error_embed("You must reply with a number corresponding to an outcome."))
            return

        if not (1 <= choice_idx <= len(options)):
            await ctx.send(embed=error_embed("That choice is out of range."))
            return

        option_id, option_name, _ = options[choice_idx - 1]

        msg_amt = await get_reply_or_cancel(
            self.bot,
            ctx,
            f"💰 How many monies do you want to bet on **{option_name}**?"
        )
        if msg_amt is None:
            return

        try:
            amount = int(msg_amt.content.strip())
        except ValueError:
            await ctx.send(embed=error_embed("Bet amount must be a whole number."))
            return

        if amount <= 0:
            await ctx.send(embed=error_embed("Bet amount must be positive."))
            return

        user_monies = get_user_monies(ctx.author.id, ctx.guild.id)
        if user_monies < amount:
            await ctx.send(embed=error_embed(f"Insufficient monies! You have {user_monies} monies."))
            return

        c.execute(
            "INSERT INTO wagers (bet_id, option_id, user_id, amount) "
            "VALUES (?, ?, ?, ?)",
            (bet_id_db, option_id, str(ctx.author.id), amount),
        )
        c.execute(
            "UPDATE bet_options SET total_amount = total_amount + ? WHERE option_id=?",
            (amount, option_id),
        )

        update_monies(ctx.author.id, ctx.guild.id, user_monies - amount)
        conn.commit()

        c.execute("SELECT total_amount FROM bet_options WHERE bet_id=?", (bet_id_db,))
        pools = [row[0] for row in c.fetchall()]
        total_pool = sum(pools)

        c.execute("SELECT total_amount FROM bet_options WHERE option_id=?", (option_id,))
        this_pool = c.fetchone()[0]

        odds = total_pool / this_pool if this_pool > 0 else 1.0
        est_payout = int(amount * odds)

        embed = info_embed(
            "✅ Bet Placed",
            f"{ctx.author.mention} bet **{amount}** on **{option_name}** "
            f"for Bet #{bet_id_db}.\n"
            f"Potential payout: **{est_payout}** monies ({odds:.2f}x).",
            discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="resolve", help="Resolve a bet: !resolve <bet_id>")
    async def resolve_bet(self, ctx, bet_id: int):
        c.execute(
            "SELECT bet_id, guild_id, creator_id, description, status "
            "FROM bets WHERE bet_id=? AND guild_id=?",
            (bet_id, str(ctx.guild.id)),
        )
        bet = c.fetchone()

        if not bet:
            await ctx.send(embed=error_embed(f"Bet #{bet_id} not found."))
            return

        bet_id_db, guild_id, creator_id, desc, status = bet

        if status != "open":
            await ctx.send(embed=error_embed(f"Bet #{bet_id_db} is already closed."))
            return

        if str(ctx.author.id) != creator_id:
            await ctx.send(embed=error_embed("Only the bet creator can resolve this bet!"))
            return

        c.execute(
            "SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?",
            (bet_id_db,),
        )
        options = c.fetchall()
        if not options:
            await ctx.send(embed=error_embed("This bet has no outcomes configured."))
            return

        lines = []
        for idx, (option_id, name, total_amount) in enumerate(options, start=1):
            lines.append(f"{idx}. {name} — Pool: {total_amount}")

        msg_choice = await get_reply_or_cancel(
            self.bot,
            ctx,
            f"Resolving Bet #{bet_id_db}: **{desc}**\n"
            "Reply with the **number** of the winning outcome:\n"
            + "\n".join(lines)
        )
        if msg_choice is None:
            return

        try:
            win_idx = int(msg_choice.content.strip())
        except ValueError:
            await ctx.send(embed=error_embed("You must reply with a number corresponding to an outcome."))
            return

        if not (1 <= win_idx <= len(options)):
            await ctx.send(embed=error_embed("That choice is out of range."))
            return

        winning_option_id, winning_name, winning_total = options[win_idx - 1]

        c.execute("SELECT user_id, option_id, amount FROM wagers WHERE bet_id=?", (bet_id_db,))
        wagers = c.fetchall()

        if not wagers:
            embed = info_embed(
                "⚠️ Bet Closed",
                "No wagers were placed on this bet. Closing it with no payouts.",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            c.execute("UPDATE bets SET status='closed' WHERE bet_id=?", (bet_id_db,))
            conn.commit()
            return

        total_pool = sum(amount for _, _, amount in wagers)
        winners = [
            (user_id, amount)
            for (user_id, option_id, amount) in wagers
            if option_id == winning_option_id
        ]
        winning_total_sum = sum(amount for _, amount in winners)

        if winning_total_sum == 0:
            embed = info_embed(
                "↩️ Bets Refunded",
                f"No one bet on the winning outcome (**{winning_name}**).\nAll bets have been refunded.",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            for user_id, _, amount in wagers:
                monies = get_user_monies(user_id, ctx.guild.id)
                update_monies(user_id, ctx.guild.id, monies + amount)
        else:
            for user_id, amount in winners:
                payout = int((amount / winning_total_sum) * total_pool)
                monies = get_user_monies(user_id, ctx.guild.id)
                update_monies(user_id, ctx.guild.id, monies + payout)

            embed = info_embed(
                "✅ Bet Resolved",
                f"Bet #{bet_id_db} resolved! Winning outcome: **{winning_name}**\n"
                f"Winnings distributed to **{len(winners)}** winner(s).",
                discord.Color.green()
            )
            await ctx.send(embed=embed)

        c.execute("UPDATE bets SET status='closed' WHERE bet_id=?", (bet_id_db,))
        conn.commit()

async def setup(bot):
    await bot.add_cog(Betting(bot))