import sqlite3
import os
from datetime import datetime

_db_dir = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(_db_dir, exist_ok=True)
_db_path = os.path.join(_db_dir, "betting.db")
conn = sqlite3.connect(_db_path)
c = conn.cursor()


def setup_db():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id    TEXT NOT NULL,
        guild_id   TEXT NOT NULL,
        monies     INTEGER NOT NULL DEFAULT 1000,
        carats     INTEGER NOT NULL DEFAULT 0,
        last_daily TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        bet_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id    TEXT,
        creator_id  TEXT,
        description TEXT,
        status      TEXT DEFAULT 'open'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bet_options (
        option_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id       INTEGER,
        name         TEXT,
        total_amount INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS wagers (
        wager_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id    INTEGER,
        option_id INTEGER,
        user_id   TEXT,
        amount    INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS race_config (
        guild_id   TEXT PRIMARY KEY,
        channel_id TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS race_notifications (
        user_id  TEXT NOT NULL,
        guild_id TEXT NOT NULL,
        PRIMARY KEY (user_id, guild_id)
    )
    """)
    conn.commit()


def get_user_monies(user_id, guild_id):
    c.execute(
        "SELECT monies FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    if result is None:
        c.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            (str(user_id), str(guild_id), 1000, 0, None),
        )
        conn.commit()
        return 1000
    return result[0]


def update_monies(user_id, guild_id, monies):
    c.execute(
        "UPDATE users SET monies=? WHERE user_id=? AND guild_id=?",
        (monies, str(user_id), str(guild_id)),
    )
    conn.commit()


def get_user_carats(user_id, guild_id):
    c.execute(
        "SELECT carats FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    return result[0] if result else 0


def update_carats(user_id, guild_id, carats):
    c.execute(
        "UPDATE users SET carats=? WHERE user_id=? AND guild_id=?",
        (carats, str(user_id), str(guild_id)),
    )
    conn.commit()


def add_daily_reward(user_id, guild_id, monies=100, carats=10):
    """Write the daily reward. Returns (new_monies, new_carats).
    Cooldown checking is the caller's responsibility.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT monies, carats FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    row = c.fetchone()
    if row is None:
        new_monies = 1000 + monies
        new_carats = carats
        c.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            (str(user_id), str(guild_id), new_monies, new_carats, now),
        )
    else:
        new_monies = row[0] + monies
        new_carats = row[1] + carats
        c.execute(
            "UPDATE users SET monies=?, carats=?, last_daily=? WHERE user_id=? AND guild_id=?",
            (new_monies, new_carats, now, str(user_id), str(guild_id)),
        )
    conn.commit()
    return new_monies, new_carats


def get_race_channel(guild_id):
    c.execute(
        "SELECT channel_id FROM race_config WHERE guild_id=?", (str(guild_id),)
    )
    row = c.fetchone()
    return row[0] if row else None


def set_race_channel(guild_id, channel_id):
    c.execute(
        "INSERT INTO race_config (guild_id, channel_id) VALUES (?,?) "
        "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
        (str(guild_id), str(channel_id)),
    )
    conn.commit()


def get_all_race_configs():
    c.execute("SELECT guild_id, channel_id FROM race_config")
    return c.fetchall()


def is_enrolled(user_id, guild_id):
    c.execute(
        "SELECT 1 FROM race_notifications WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    return c.fetchone() is not None


def toggle_enrollment(user_id, guild_id):
    if is_enrolled(user_id, guild_id):
        c.execute(
            "DELETE FROM race_notifications WHERE user_id=? AND guild_id=?",
            (str(user_id), str(guild_id)),
        )
        conn.commit()
        return False
    else:
        c.execute(
            "INSERT INTO race_notifications (user_id, guild_id) VALUES (?,?)",
            (str(user_id), str(guild_id)),
        )
        conn.commit()
        return True


def get_enrolled_users(guild_id):
    c.execute(
        "SELECT user_id FROM race_notifications WHERE guild_id=?", (str(guild_id),)
    )
    return [row[0] for row in c.fetchall()]
