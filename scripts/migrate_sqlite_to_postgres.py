"""
One-time migration: copy all data from SQLite (Pi) to RDS Postgres.
Run from your laptop with the SQLite file copied from the Pi.

Usage:
    SQLITE_PATH=/path/to/betting.db DATABASE_URL=postgresql://bettingbot:PASSWORD@RDS_ENDPOINT/bettingbot python scripts/migrate_sqlite_to_postgres.py
"""
import os
import sqlite3
import psycopg2

SQLITE_PATH = os.environ.get("SQLITE_PATH", "data/betting.db")
DATABASE_URL = os.environ["DATABASE_URL"]

sqlite_conn = sqlite3.connect(SQLITE_PATH)
pg_conn = psycopg2.connect(DATABASE_URL)
pg = pg_conn.cursor()

print(f"Connecting to SQLite: {SQLITE_PATH}")
print(f"Connecting to Postgres: {DATABASE_URL[:30]}...")

# Users
rows = sqlite_conn.execute(
    "SELECT user_id, guild_id, monies, carats, vc_minutes, last_daily FROM users"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, guild_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} users")

# Bets
rows = sqlite_conn.execute(
    "SELECT bet_id, guild_id, creator_id, description, status FROM bets"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO bets (bet_id, guild_id, creator_id, description, status)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (bet_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} bets")

# Bet options
rows = sqlite_conn.execute(
    "SELECT option_id, bet_id, name, total_amount FROM bet_options"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO bet_options (option_id, bet_id, name, total_amount)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (option_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} bet options")

# Wagers
rows = sqlite_conn.execute(
    "SELECT wager_id, bet_id, option_id, user_id, amount FROM wagers"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO wagers (wager_id, bet_id, option_id, user_id, amount)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (wager_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} wagers")

# Race config
rows = sqlite_conn.execute(
    "SELECT guild_id, channel_id FROM race_config"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO race_config (guild_id, channel_id)
        VALUES (%s, %s)
        ON CONFLICT (guild_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} race configs")

# Race notifications
rows = sqlite_conn.execute(
    "SELECT user_id, guild_id FROM race_notifications"
).fetchall()
for row in rows:
    pg.execute("""
        INSERT INTO race_notifications (user_id, guild_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, guild_id) DO NOTHING
    """, row)
print(f"Migrated {len(rows)} race notification enrollments")

# Reset SERIAL sequences so new inserts don't conflict with migrated IDs
pg.execute("SELECT setval('bets_bet_id_seq', COALESCE((SELECT MAX(bet_id) FROM bets), 1))")
pg.execute("SELECT setval('bet_options_option_id_seq', COALESCE((SELECT MAX(option_id) FROM bet_options), 1))")
pg.execute("SELECT setval('wagers_wager_id_seq', COALESCE((SELECT MAX(wager_id) FROM wagers), 1))")

pg_conn.commit()
print("Migration complete. All sequences reset.")

sqlite_conn.close()
pg_conn.close()
