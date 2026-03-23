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



class TestSetupDbNewSchema:
    def test_users_table_has_monies_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "monies" in cols

    def test_users_table_has_carats_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "carats" in cols

    def test_users_table_has_no_points_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "points" not in cols

    def test_creates_race_config_table(self, in_memory_db):
        assert table_exists(in_memory_db, "race_config")

    def test_creates_race_notifications_table(self, in_memory_db):
        assert table_exists(in_memory_db, "race_notifications")


class TestGetUserMonies:
    def test_new_user_gets_1000_monies(self, in_memory_db):
        assert database.get_user_monies("user1", "guild1") == 1000

    def test_new_user_row_is_created(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        row = in_memory_db.execute(
            "SELECT monies FROM users WHERE user_id='user1' AND guild_id='guild1'"
        ).fetchone()
        assert row is not None and row[0] == 1000

    def test_existing_user_returns_correct_monies(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user2", "guild1", 500, 0, None),
        )
        in_memory_db.commit()
        assert database.get_user_monies("user2", "guild1") == 500

    def test_users_isolated_by_guild(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        assert database.get_user_monies("user1", "guild2") == 1000


class TestUpdateMonies:
    def test_updates_existing_user(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.update_monies("user1", "guild1", 250)
        assert database.get_user_monies("user1", "guild1") == 250

    def test_update_does_not_affect_other_guild(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.get_user_monies("user1", "guild2")
        database.update_monies("user1", "guild1", 9999)
        assert database.get_user_monies("user1", "guild2") == 1000


class TestGetUserCarats:
    def test_new_user_gets_0_carats(self, in_memory_db):
        database.get_user_monies("user1", "guild1")  # ensure row exists
        assert database.get_user_carats("user1", "guild1") == 0

    def test_returns_correct_carats(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 1000, 50, None),
        )
        in_memory_db.commit()
        assert database.get_user_carats("user1", "guild1") == 50


class TestUpdateCarats:
    def test_updates_carats(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 1000, 0, None),
        )
        in_memory_db.commit()
        database.update_carats("user1", "guild1", 25)
        assert database.get_user_carats("user1", "guild1") == 25


class TestAddDailyReward:
    def test_new_user_gets_starting_balance_plus_reward(self, in_memory_db):
        monies, carats = database.add_daily_reward("user1", "guild1")
        assert monies == 1100  # 1000 default + 100 reward
        assert carats == 10

    def test_existing_user_gets_reward_added(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 500, 5, None),
        )
        in_memory_db.commit()
        monies, carats = database.add_daily_reward("user1", "guild1")
        assert monies == 600
        assert carats == 15

    def test_sets_last_daily(self, in_memory_db):
        database.add_daily_reward("user1", "guild1")
        row = in_memory_db.execute(
            "SELECT last_daily FROM users WHERE user_id='user1' AND guild_id='guild1'"
        ).fetchone()
        assert row[0] is not None


class TestRaceConfig:
    def test_get_race_channel_returns_none_when_unset(self, in_memory_db):
        assert database.get_race_channel("guild1") is None

    def test_set_and_get_race_channel(self, in_memory_db):
        database.set_race_channel("guild1", "123456")
        assert database.get_race_channel("guild1") == "123456"

    def test_set_race_channel_overwrites(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild1", "222")
        assert database.get_race_channel("guild1") == "222"

    def test_get_all_race_configs_empty(self, in_memory_db):
        assert database.get_all_race_configs() == []

    def test_get_all_race_configs_returns_rows(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild2", "222")
        configs = database.get_all_race_configs()
        assert len(configs) == 2


class TestEnrollment:
    def test_not_enrolled_by_default(self, in_memory_db):
        assert database.is_enrolled("user1", "guild1") is False

    def test_toggle_enrolls_user(self, in_memory_db):
        result = database.toggle_enrollment("user1", "guild1")
        assert result is True
        assert database.is_enrolled("user1", "guild1") is True

    def test_toggle_unenrolls_user(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        result = database.toggle_enrollment("user1", "guild1")
        assert result is False
        assert database.is_enrolled("user1", "guild1") is False

    def test_enrollment_isolated_by_guild(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        assert database.is_enrolled("user1", "guild2") is False

    def test_get_enrolled_users(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild1")
        database.toggle_enrollment("user1", "guild2")  # different guild
        users = database.get_enrolled_users("guild1")
        assert set(users) == {"user1", "user2"}
