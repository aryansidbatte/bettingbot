import sqlite3
import pytest
import database


def table_exists(conn, name):
    conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


class TestSetupDb:
    def test_creates_users_table(self, in_memory_db):
        assert table_exists(in_memory_db, "users")

    def test_creates_bets_table(self, in_memory_db):
        assert table_exists(in_memory_db, "bets")

    def test_creates_bet_options_table(self, in_memory_db):
        assert table_exists(in_memory_db, "bet_options")

    def test_creates_wagers_table(self, in_memory_db):
        assert table_exists(in_memory_db, "wagers")

    def test_idempotent(self, in_memory_db):
        # Calling setup_db a second time should not raise
        database.setup_db()
        assert table_exists(in_memory_db, "users")


class TestGetUserPoints:
    def test_new_user_gets_1000_points(self, in_memory_db):
        points = database.get_user_points("user1", "guild1")
        assert points == 1000

    def test_new_user_row_is_created(self, in_memory_db):
        database.get_user_points("user1", "guild1")
        row = in_memory_db.execute(
            "SELECT points FROM users WHERE user_id='user1' AND guild_id='guild1'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1000

    def test_existing_user_returns_correct_points(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, points, last_daily) VALUES (?,?,?,?)",
            ("user2", "guild1", 500, None),
        )
        in_memory_db.commit()
        assert database.get_user_points("user2", "guild1") == 500

    def test_users_isolated_by_guild(self, in_memory_db):
        database.get_user_points("user1", "guild1")
        points_other_guild = database.get_user_points("user1", "guild2")
        assert points_other_guild == 1000  # separate row, separate starting balance

    def test_accepts_int_ids(self, in_memory_db):
        # Discord IDs are ints in practice; function should cast to str
        points = database.get_user_points(12345, 67890)
        assert points == 1000


class TestUpdatePoints:
    def test_updates_existing_user(self, in_memory_db):
        database.get_user_points("user1", "guild1")  # create row
        database.update_points("user1", "guild1", 250)
        assert database.get_user_points("user1", "guild1") == 250

    def test_update_to_zero(self, in_memory_db):
        database.get_user_points("user1", "guild1")
        database.update_points("user1", "guild1", 0)
        assert database.get_user_points("user1", "guild1") == 0

    def test_update_does_not_affect_other_guild(self, in_memory_db):
        database.get_user_points("user1", "guild1")
        database.get_user_points("user1", "guild2")
        database.update_points("user1", "guild1", 9999)
        assert database.get_user_points("user1", "guild2") == 1000
