# betting_bot.py
import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot with command prefix
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

# Database setup
conn = sqlite3.connect('betting.db')
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id TEXT, guild_id TEXT, points INTEGER,
              PRIMARY KEY (user_id, guild_id))''')

c.execute('''CREATE TABLE IF NOT EXISTS bets
             (bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
              guild_id TEXT,
              creator_id TEXT,
              description TEXT,
              option_a TEXT,
              option_b TEXT,
              total_a INTEGER DEFAULT 0,
              total_b INTEGER DEFAULT 0,
              status TEXT DEFAULT 'open')''')

c.execute('''CREATE TABLE IF NOT EXISTS wagers
             (wager_id INTEGER PRIMARY KEY AUTOINCREMENT,
              bet_id INTEGER,
              user_id TEXT,
              option TEXT,
              amount INTEGER)''')

conn.commit()

try:
    c.execute('ALTER TABLE users ADD COLUMN last_daily TEXT')
    conn.commit()
except sqlite3.OperationalError:
    pass # Column likely already exists

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
    await ctx.send(f'{ctx.author.mention}, you have **{points}** points!')

# Command: Create a bet
@bot.command(name='createbet', help='Create a bet: !createbet "Description" "Option A" "Option B"')
async def create_bet(ctx, description: str, option_a: str, option_b: str):
    c.execute('''INSERT INTO bets (guild_id, creator_id, description, option_a, option_b)
                 VALUES (?, ?, ?, ?, ?)''',
              (str(ctx.guild.id), str(ctx.author.id), description, option_a, option_b))
    conn.commit()
    bet_id = c.lastrowid
    
    embed = discord.Embed(title="🎲 New Bet Created!", color=discord.Color.green())
    embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="Options", value=f"A: {option_a}\nB: {option_b}", inline=False)
    embed.add_field(name="How to Bet", value=f"Use `!bet {bet_id} A <amount>` or `!bet {bet_id} B <amount>`")
    
    await ctx.send(embed=embed)

# Command: Place a bet
@bot.command(name='bet', help='Place a bet: !bet <bet_id> <A or B> <amount>')
async def place_bet(ctx, bet_id: int, option: str, amount: int):
    option = option.upper()
    
    if option not in ['A', 'B']:
        await ctx.send('Please choose option A or B!')
        return
    
    if amount <= 0:
        await ctx.send('Bet amount must be positive!')
        return
    
    # Check if bet exists and is open
    c.execute('SELECT * FROM bets WHERE bet_id=? AND guild_id=? AND status="open"',
              (bet_id, str(ctx.guild.id)))
    bet = c.fetchone()
    
    if not bet:
        await ctx.send(f'Bet #{bet_id} not found or already closed!')
        return
    
    # Check user has enough points
    user_points = get_user_points(ctx.author.id, ctx.guild.id)
    if user_points < amount:
        await ctx.send(f'Insufficient points! You have {user_points} points.')
        return
    
    # Check if user already bet on this
    c.execute('SELECT * FROM wagers WHERE bet_id=? AND user_id=?',
              (bet_id, str(ctx.author.id)))
    if c.fetchone():
        await ctx.send('You already placed a wager on this bet!')
        return
    
    # Place wager
    c.execute('INSERT INTO wagers (bet_id, user_id, option, amount) VALUES (?, ?, ?, ?)',
              (bet_id, str(ctx.author.id), option, amount))
    
    # Update bet totals
    if option == 'A':
        c.execute('UPDATE bets SET total_a = total_a + ? WHERE bet_id=?', (amount, bet_id))
    else:
        c.execute('UPDATE bets SET total_b = total_b + ? WHERE bet_id=?', (amount, bet_id))
    
    # Deduct points from user
    update_points(ctx.author.id, ctx.guild.id, user_points - amount)
    conn.commit()
    
    # Calculate new odds after this bet
    c.execute('SELECT total_a, total_b FROM bets WHERE bet_id=?', (bet_id,))
    ta, tb = c.fetchone()
    total_pool = ta + tb
    
    if option == 'A':
        new_odds = total_pool / ta
    else:
        new_odds = total_pool / tb
        
    await ctx.send(f'{ctx.author.mention} placed **{amount}** on **{option}**! Potential payout: **{int(amount * new_odds)}** points ({new_odds:.2f}x)')


# Command: View active bets
@bot.command(name='bets', help='View all active bets with live odds')
async def view_bets(ctx):
    c.execute('SELECT * FROM bets WHERE guild_id=? AND status="open"', (str(ctx.guild.id),))
    bets = c.fetchall()
    
    if not bets:
        await ctx.send('No active bets!')
        return
    
    embed = discord.Embed(title="🎲 Active Bets & Live Odds", color=discord.Color.blue())
    
    for bet in bets:
        bet_id, guild_id, creator_id, desc, opt_a, opt_b, total_a, total_b, status = bet
        
        total_pool = total_a + total_b
        
        # Calculate Odds for A
        if total_a > 0:
            odds_a = total_pool / total_a
            str_odds_a = f"{odds_a:.2f}x"
        else:
            str_odds_a = "1.00x" # Default if no bets yet
            
        # Calculate Odds for B
        if total_b > 0:
            odds_b = total_pool / total_b
            str_odds_b = f"{odds_b:.2f}x"
        else:
            str_odds_b = "1.00x"

        embed.add_field(
            name=f"Bet #{bet_id}: {desc}",
            value=f"**Option A:** {opt_a}\n"
                  f"• Pool: {total_a}\n"
                  f"• Payout: **{str_odds_a}**\n\n"
                  f"**Option B:** {opt_b}\n"
                  f"• Pool: {total_b}\n"
                  f"• Payout: **{str_odds_b}**",
            inline=False
        )
    
    await ctx.send(embed=embed)


# Command: Resolve a bet (only creator can do this)
@bot.command(name='resolve', help='Resolve a bet: !resolve <bet_id> <A or B>')
async def resolve_bet(ctx, bet_id: int, winning_option: str):
    winning_option = winning_option.upper()
    
    if winning_option not in ['A', 'B']:
        await ctx.send('Please choose winning option A or B!')
        return
    
    # Get bet details
    c.execute('SELECT * FROM bets WHERE bet_id=? AND guild_id=? AND status="open"',
              (bet_id, str(ctx.guild.id)))
    bet = c.fetchone()
    
    if not bet:
        await ctx.send(f'Bet #{bet_id} not found or already closed!')
        return
    
    bet_id_db, guild_id, creator_id, desc, opt_a, opt_b, total_a, total_b, status = bet
    
    # Check if user is the creator
    if str(ctx.author.id) != creator_id:
        await ctx.send('Only the bet creator can resolve it!')
        return
    
    # Calculate payouts
    total_pool = total_a + total_b
    winners = []
    losers = []
    
    c.execute('SELECT user_id, option, amount FROM wagers WHERE bet_id=?', (bet_id,))
    wagers = c.fetchall()
    
    for user_id, option, amount in wagers:
        if option == winning_option:
            winners.append((user_id, amount))
        else:
            losers.append((user_id, amount))
    
    # Distribute winnings proportionally
    winning_total = total_a if winning_option == 'A' else total_b
    
    if winning_total == 0:
        await ctx.send('No one bet on the winning option! All bets refunded.')
        # Refund everyone
        for user_id, _, amount in wagers:
            points = get_user_points(user_id, ctx.guild.id)
            update_points(user_id, ctx.guild.id, points + amount)
    else:
        # Pay out winners proportionally
        for user_id, amount in winners:
            payout = int((amount / winning_total) * total_pool)
            points = get_user_points(user_id, ctx.guild.id)
            update_points(user_id, ctx.guild.id, points + payout)
    
    # Close the bet
    c.execute('UPDATE bets SET status="closed" WHERE bet_id=?', (bet_id,))
    conn.commit()
    
    winning_opt_name = opt_a if winning_option == 'A' else opt_b
    await ctx.send(f'✅ Bet #{bet_id} resolved! Winning option: **{winning_option}: {winning_opt_name}**\nWinnings distributed to {len(winners)} winner(s)!')

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
    await ctx.send(embed=embed)

@bot.command(name='daily', help='Claim your daily 100 points')
async def daily(ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)
    
    # 1. Get current time and user data
    now = datetime.now()
    c.execute('SELECT points, last_daily FROM users WHERE user_id=? AND guild_id=?', (user_id, guild_id))
    result = c.fetchone()
    
    if result is None:
        # New user: Create them and give them the daily bonus immediately
        c.execute('INSERT INTO users (user_id, guild_id, points, last_daily) VALUES (?, ?, ?, ?)', 
                  (user_id, guild_id, 1000 + 100, now.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        await ctx.send(f'{ctx.author.mention}, welcome! You collected your first daily reward of **100** points! Balance: 1100')
        return

    points, last_daily_str = result
    
    # 2. Check if they can claim
    if last_daily_str:
        last_daily = datetime.strptime(last_daily_str, '%Y-%m-%d %H:%M:%S')
        time_passed = now - last_daily
        
        if time_passed < timedelta(hours=24):
            # Calculate time left
            time_left = timedelta(hours=24) - time_passed
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.send(f'{ctx.author.mention}, you must wait **{hours}h {minutes}m** before claiming again!')
            return

    # 3. Give points and update time
    new_points = points + 100
    c.execute('UPDATE users SET points=?, last_daily=? WHERE user_id=? AND guild_id=?',
              (new_points, now.strftime('%Y-%m-%d %H:%M:%S'), user_id, guild_id))
    conn.commit()
    
    await ctx.send(f'💰 {ctx.author.mention}, you collected your daily **100** points! New balance: **{new_points}**')

bot.run(TOKEN)
