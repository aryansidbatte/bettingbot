import sqlite3

conn = sqlite3.connect("betting.db")
c = conn.cursor()

def setup_db():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT,
        guild_id TEXT,
        points INTEGER,
        last_daily TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        creator_id TEXT,
        description TEXT,
        status TEXT DEFAULT 'open'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bet_options (
        option_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id INTEGER,
        name TEXT,
        total_amount INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS wagers (
        wager_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id INTEGER,
        option_id INTEGER,
        user_id TEXT,
        amount INTEGER
    )
    """)
    conn.commit()

def get_user_points(user_id, guild_id):
    c.execute(
        "SELECT points FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    if result is None:
        c.execute(
            "INSERT INTO users (user_id, guild_id, points, last_daily) "
            "VALUES (?, ?, ?, ?)",
            (str(user_id), str(guild_id), 1000, None),
        )
        conn.commit()
        return 1000
    return result[0]

def update_points(user_id, guild_id, points):
    c.execute(
        "UPDATE users SET points=? WHERE user_id=? AND guild_id=?",
        (points, str(user_id), str(guild_id)),
    )
    conn.commit()
