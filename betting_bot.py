# betting_bot.py
import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot with command prefix
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

# Database setup
conn = sqlite3.connect('betting.db')
c = conn.cursor()

# Create tables
# Database setup
conn = sqlite3.connect('betting.db')
c = conn.cursor()

# Users table (same idea as before)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT,
    guild_id TEXT,
    points INTEGER,
    last_daily TEXT,
    PRIMARY KEY (user_id, guild_id)
)
''')

# Bets: one per bet, no hardcoded options
c.execute('''
CREATE TABLE IF NOT EXISTS bets (
    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT,
    creator_id TEXT,
    description TEXT,
    status TEXT DEFAULT 'open'
)
''')

# Bet options: one row per outcome
c.execute('''
CREATE TABLE IF NOT EXISTS bet_options (
    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_id INTEGER,
    name TEXT,
    total_amount INTEGER DEFAULT 0
)
''')

# Wagers: link user to a specific option in a bet
c.execute('''
CREATE TABLE IF NOT EXISTS wagers (
    wager_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_id INTEGER,
    option_id INTEGER,
    user_id TEXT,
    amount INTEGER
)
''')

conn.commit()


# Helper functions
def get_user_points(user_id, guild_id):
    c.execute('SELECT points FROM users WHERE user_id=? AND guild_id=?', 
              (str(user_id), str(guild_id)))
    result = c.fetchone()
    if result is None:
        # Give new users starting points
        # We now need 4 values: user_id, guild_id, points, last_daily (which is None for new users)
        c.execute('INSERT INTO users (user_id, guild_id, points, last_daily) VALUES (?, ?, ?, ?)', 
                  (str(user_id), str(guild_id), 1000, None))
        conn.commit()
        return 1000
    return result[0]

def update_points(user_id, guild_id, points):
    c.execute('UPDATE users SET points=? WHERE user_id=? AND guild_id=?',
              (points, str(user_id), str(guild_id)))
    conn.commit()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

# Command: Check points balance
@bot.command(name='balance', help='Check your points balance')
async def balance(ctx):
    points = get_user_points(ctx.author.id, ctx.guild.id)

    embed = discord.Embed(
        title="💰 Balance",
        description=f"{ctx.author.mention} you have **{points}** points.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Use !daily to claim a daily reward.")
    await ctx.send(embed=embed)

# Command: Create a bet
@bot.command(name='createbet', help='Interactively create a bet with multiple outcomes')
async def create_bet(ctx):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # Description
    await ctx.send("📝 What is the bet **description**?\nExample: `Who will win the game?`")
    try:
        msg_desc = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run `!createbet` again.")
        return
    description = msg_desc.content.strip()

    # Number of outcomes
    await ctx.send("🔢 How many **outcomes** does this bet have? (minimum 2, maximum 10)")
    try:
        msg_count = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run `!createbet` again.")
        return

    try:
        num_outcomes = int(msg_count.content.strip())
    except ValueError:
        await ctx.send("Please enter a valid number (2–10).")
        return

    if num_outcomes < 2 or num_outcomes > 10:
        await ctx.send("Number of outcomes must be between 2 and 10.")
        return

    # Collect outcome names
    option_names = []
    for i in range(1, num_outcomes + 1):
        await ctx.send(f"✏️ Enter name for **Outcome #{i}**:")
        try:
            msg_opt = await bot.wait_for("message", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Timed out. Run `!createbet` again.")
            return
        name = msg_opt.content.strip()
        if not name:
            await ctx.send("Outcome name cannot be empty.")
            return
        option_names.append(name)

    # Insert bet
    c.execute(
        'INSERT INTO bets (guild_id, creator_id, description) VALUES (?, ?, ?)',
        (str(ctx.guild.id), str(ctx.author.id), description)
    )
    conn.commit()
    bet_id = c.lastrowid

    # Insert options
    option_rows = []
    for name in option_names:
        c.execute(
            'INSERT INTO bet_options (bet_id, name) VALUES (?, ?)',
            (bet_id, name)
        )
        option_rows.append((name,))
    conn.commit()

    # Fetch options with IDs for display
    c.execute('SELECT option_id, name FROM bet_options WHERE bet_id=?', (bet_id,))
    options = c.fetchall()

    # Build embed
    embed = discord.Embed(title="🎲 New Bet Created!", color=discord.Color.green())
    embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
    embed.add_field(name="Description", value=description, inline=False)

    lines = []
    for idx, (option_id, name) in enumerate(options, start=1):
        lines.append(f"{idx}. {name} (Option ID: `{option_id}`)")
    embed.add_field(
        name="Outcomes",
        value="\n".join(lines),
        inline=False
    )
    embed.add_field(
        name="How to Bet",
        value="Use `!bet` and follow the prompts to choose this bet and an outcome.",
        inline=False
    )

    await ctx.send(embed=embed)


# Command: Place a bet
@bot.command(name='bet', help='Interactively place a bet on any outcome')
async def place_bet(ctx):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # Show active bets first
    c.execute(
        'SELECT bet_id, description FROM bets WHERE guild_id=? AND status="open"',
        (str(ctx.guild.id),)
    )
    bets = c.fetchall()

    if not bets:
        await ctx.send('No active bets! Use `!createbet` to make one.')
        return

    lines = []
    for bet_id, desc in bets:
        lines.append(f"Bet #{bet_id}: {desc}")
    await ctx.send(
        "📋 **Active Bets:**\n"
        + "\n".join(lines)
        + "\n\n📌 Reply with the **Bet ID** (number) you want to bet on."
    )

    # Ask bet ID
    try:
        msg_id = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run `!bet` again.")
        return

    try:
        bet_id = int(msg_id.content.strip())
    except ValueError:
        await ctx.send("Bet ID must be a number. Run `!bet` again.")
        return

    # Fetch bet
    c.execute(
        'SELECT bet_id, description, status FROM bets WHERE bet_id=? AND guild_id=?',
        (bet_id, str(ctx.guild.id))
    )
    bet = c.fetchone()
    if not bet:
        await ctx.send(f'Bet #{bet_id} not found.')
        return

    bet_id_db, desc, status = bet
    if status != 'open':
        await ctx.send(f'Bet #{bet_id_db} is not open.')
        return

    # Fetch options for this bet
    c.execute('SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?', (bet_id_db,))
    options = c.fetchall()
    if not options:
        await ctx.send('This bet has no outcomes configured. Something went wrong.')
        return

    # Show options with indexes
    lines = []
    for idx, (option_id, name, total_amount) in enumerate(options, start=1):
        lines.append(f"{idx}. {name} — Current pool: {total_amount}")
    await ctx.send(
        f"Bet #{bet_id_db}: **{desc}**\n"
        "Reply with the **number** of the outcome you want to bet on:\n"
        + "\n".join(lines)
    )

    # Ask which index
    try:
        msg_choice = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run `!bet` again.")
        return

    try:
        choice_idx = int(msg_choice.content.strip())
    except ValueError:
        await ctx.send("You must reply with a number corresponding to an outcome.")
        return

    if not (1 <= choice_idx <= len(options)):
        await ctx.send("That choice is out of range.")
        return

    option_id, option_name, _ = options[choice_idx - 1]

    # Ask amount
    await ctx.send(f"💰 How many points do you want to bet on **{option_name}**?")
    try:
        msg_amt = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run `!bet` again.")
        return

    try:
        amount = int(msg_amt.content.strip())
    except ValueError:
        await ctx.send("Bet amount must be a whole number.")
        return

    if amount <= 0:
        await ctx.send("Bet amount must be positive.")
        return

    # Check user balance
    user_points = get_user_points(ctx.author.id, ctx.guild.id)
    if user_points < amount:
        await ctx.send(f'Insufficient points! You have {user_points} points.')
        return

    # Check they haven't already bet on this bet
    c.execute(
        'SELECT 1 FROM wagers WHERE bet_id=? AND user_id=?',
        (bet_id_db, str(ctx.author.id))
    )
    if c.fetchone():
        await ctx.send('You already placed a wager on this bet.')
        return

    # Insert wager
    c.execute(
        'INSERT INTO wagers (bet_id, option_id, user_id, amount) VALUES (?, ?, ?, ?)',
        (bet_id_db, option_id, str(ctx.author.id), amount)
    )

    # Update option pool
    c.execute(
        'UPDATE bet_options SET total_amount = total_amount + ? WHERE option_id=?',
        (amount, option_id)
    )

    # Deduct points
    update_points(ctx.author.id, ctx.guild.id, user_points - amount)
    conn.commit()

    # Compute live odds for this outcome
    c.execute('SELECT total_amount FROM bet_options WHERE bet_id=?', (bet_id_db,))
    pools = [row[0] for row in c.fetchall()]
    total_pool = sum(pools)

    c.execute('SELECT total_amount FROM bet_options WHERE option_id=?', (option_id,))
    this_pool = c.fetchone()[0]

    odds = total_pool / this_pool if this_pool > 0 else 1.0
    est_payout = int(amount * odds)

    embed = discord.Embed(
        title="✅ Bet Placed",
        description=(
            f"{ctx.author.mention} bet **{amount}** on **{option_name}** "
            f"for Bet #{bet_id_db}.\n"
            f"Potential payout: **{est_payout}** points ({odds:.2f}x)."
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)



# Command: View active bets
@bot.command(name='bets', help='View all active bets and their outcomes')
async def view_bets(ctx):
    # Get all open bets for this guild
    c.execute(
        'SELECT bet_id, description FROM bets WHERE guild_id=? AND status="open"',
        (str(ctx.guild.id),)
    )
    bets = c.fetchall()

    if not bets:
        await ctx.send('No active bets!')
        return

    embed = discord.Embed(
        title="🎲 Active Bets",
        description="Here are all open bets and their IDs.",
        color=discord.Color.blue()
    )

    for bet_id, desc in bets:
        # Fetch options for each bet
        c.execute(
            'SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?',
            (bet_id,)
        )
        options = c.fetchall()

        if not options:
            continue

        # Compute total pool and per-option odds
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
                f"(Option ID: `{option_id}`, Pool: {total_amount}, Payout: {odds_str})"
            )

        embed.add_field(
            name=f"Bet #{bet_id}: {desc}",
            value="\n".join(lines),
            inline=False
        )

    await ctx.send(embed=embed)


# Command: Resolve a bet (only creator can do this)
@bot.command(name='resolve', help='Resolve a bet: !resolve <bet_id>')
async def resolve_bet(ctx, bet_id: int):
    # Fetch bet
    c.execute(
        'SELECT bet_id, guild_id, creator_id, description, status FROM bets WHERE bet_id=? AND guild_id=?',
        (bet_id, str(ctx.guild.id))
    )
    bet = c.fetchone()

    if not bet:
        await ctx.send(f'Bet #{bet_id} not found.')
        return

    bet_id_db, guild_id, creator_id, desc, status = bet

    if status != 'open':
        await ctx.send(f'Bet #{bet_id_db} is already closed.')
        return

    # Only creator can resolve (for now)
    if str(ctx.author.id) != creator_id:
        await ctx.send('Only the bet creator can resolve this bet!')
        return

    # Fetch options
    c.execute('SELECT option_id, name, total_amount FROM bet_options WHERE bet_id=?', (bet_id_db,))
    options = c.fetchall()
    if not options:
        await ctx.send('This bet has no outcomes configured.')
        return

    # Show options with pools
    lines = []
    for idx, (option_id, name, total_amount) in enumerate(options, start=1):
        lines.append(f"{idx}. {name} — Pool: {total_amount}")
    await ctx.send(
        f"Resolving Bet #{bet_id_db}: **{desc}**\n"
        "Reply with the **number** of the winning outcome:\n"
        + "\n".join(lines)
    )

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # Ask which outcome won
    try:
        msg_choice = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out. Run the resolve command again when ready.")
        return

    try:
        win_idx = int(msg_choice.content.strip())
    except ValueError:
        await ctx.send("You must reply with a number corresponding to an outcome.")
        return

    if not (1 <= win_idx <= len(options)):
        await ctx.send("That choice is out of range.")
        return

    winning_option_id, winning_name, winning_total = options[win_idx - 1]

    # Get all wagers for this bet
    c.execute('SELECT user_id, option_id, amount FROM wagers WHERE bet_id=?', (bet_id_db,))
    wagers = c.fetchall()

    if not wagers:
        await ctx.send("No wagers were placed on this bet. Closing it with no payouts.")
        c.execute('UPDATE bets SET status="closed" WHERE bet_id=?', (bet_id_db,))
        conn.commit()
        return

    # Compute total pool and winners
    total_pool = sum(amount for _, _, amount in wagers)
    winners = [(user_id, amount) for (user_id, option_id, amount) in wagers if option_id == winning_option_id]
    winning_total_sum = sum(amount for _, amount in winners)

    if winning_total_sum == 0:
        # No one bet on the winning outcome -> refund everyone
        await ctx.send(
            f'No one bet on the winning outcome (**{winning_name}**). '
            'All bets have been refunded.'
        )
        for user_id, _, amount in wagers:
            points = get_user_points(user_id, ctx.guild.id)
            update_points(user_id, ctx.guild.id, points + amount)
    else:
        # Pay out winners proportionally from the whole pool
        for user_id, amount in winners:
            payout = int((amount / winning_total_sum) * total_pool)
            points = get_user_points(user_id, ctx.guild.id)
            update_points(user_id, ctx.guild.id, points + payout)

        await ctx.send(
            f'✅ Bet #{bet_id_db} resolved! Winning outcome: **{winning_name}**\n'
            f'Winnings distributed to {len(winners)} winner(s).'
        )

    # Close bet
    c.execute('UPDATE bets SET status="closed" WHERE bet_id=?', (bet_id_db,))
    conn.commit()


@bot.command(name='leaderboard', aliases=['lb', 'top'], help='Show the top 10 richest users')
async def leaderboard(ctx):
    # Get top 10 users by points
    c.execute('SELECT user_id, points FROM users WHERE guild_id=? ORDER BY points DESC LIMIT 10', (str(ctx.guild.id),))
    top_users = c.fetchall()
    
    if not top_users:
        await ctx.send('No users found on the leaderboard yet!')
        return
    
    # Create the Embed
    embed = discord.Embed(title="🏆 Points Leaderboard", color=discord.Color.gold())
    
    description = ""
    for index, (user_id, points) in enumerate(top_users, 1):
        # Try to get the user's name; if not found, use their ID
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        
        # Add a medal emoji for top 3
        if index == 1:
            rank = "🥇"
        elif index == 2:
            rank = "🥈"
        elif index == 3:
            rank = "🥉"
        else:
            rank = f"#{index}"
            
        description += f"**{rank}** {name}: **{points}** points\n"
        
    embed.description = description
    embed.set_footer(text="Use !balance to see your own points.")
    await ctx.send(embed=embed)

@bot.command(name='daily', help='Claim your daily 100 points')
async def daily(ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    now = datetime.now()
    c.execute('SELECT points, last_daily FROM users WHERE user_id=? AND guild_id=?', (user_id, guild_id))
    result = c.fetchone()

    if result is None:
        c.execute(
            'INSERT INTO users (user_id, guild_id, points, last_daily) VALUES (?, ?, ?, ?)',
            (user_id, guild_id, 1100, now.strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"{ctx.author.mention}, welcome! You collected your first daily **100** points.\n"
                        f"New balance: **1100** points.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return

    points, last_daily_str = result

    if last_daily_str:
        last_daily = datetime.strptime(last_daily_str, '%Y-%m-%d %H:%M:%S')
        time_passed = now - last_daily

        if time_passed < timedelta(hours=24):
            time_left = timedelta(hours=24) - time_passed
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)

            embed = discord.Embed(
                title="⏰ Daily Cooldown",
                description=f"{ctx.author.mention}, you must wait **{hours}h {minutes}m** before claiming again.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

    new_points = points + 100
    c.execute(
        'UPDATE users SET points=?, last_daily=? WHERE user_id=? AND guild_id=?',
        (new_points, now.strftime('%Y-%m-%d %H:%M:%S'), user_id, guild_id)
    )
    conn.commit()

    embed = discord.Embed(
        title="🎁 Daily Reward",
        description=f"{ctx.author.mention}, you collected your daily **100** points.\n"
                    f"New balance: **{new_points}** points.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

bot.run(TOKEN)
