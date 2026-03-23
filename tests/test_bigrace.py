import pytest
import database


class TestBigRacePayouts:
    """Test the parimutuel payout math in isolation (no Discord)."""

    def _compute_payouts(self, all_bets, winner_num):
        """Mirrors _run_big_race payout logic."""
        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        winning_total = sum(winning_bets.values())
        if total_pool == 0 or winning_total == 0:
            return {}
        return {
            uid: int((amt / winning_total) * total_pool)
            for uid, amt in winning_bets.items()
        }

    def test_single_winner_gets_whole_pool(self):
        bets = {"user1": (1, 100), "user2": (2, 200)}
        payouts = self._compute_payouts(bets, winner_num=1)
        assert payouts == {"user1": 300}

    def test_two_winners_split_proportionally(self):
        bets = {"user1": (1, 100), "user2": (1, 200), "user3": (2, 300)}
        payouts = self._compute_payouts(bets, winner_num=1)
        assert payouts["user1"] == 200   # 100/300 * 600
        assert payouts["user2"] == 400   # 200/300 * 600

    def test_no_bets_returns_empty(self):
        assert self._compute_payouts({}, winner_num=1) == {}

    def test_no_winner_bets_returns_empty(self):
        bets = {"user1": (2, 100)}
        assert self._compute_payouts(bets, winner_num=1) == {}


class TestEnrollmentViaDb:
    def test_racenotify_toggle_on(self, in_memory_db):
        result = database.toggle_enrollment("user1", "guild1")
        assert result is True

    def test_racenotify_toggle_off(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        result = database.toggle_enrollment("user1", "guild1")
        assert result is False

    def test_get_enrolled_users_empty(self, in_memory_db):
        assert database.get_enrolled_users("guild1") == []

    def test_get_enrolled_users_after_enroll(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild1")
        assert set(database.get_enrolled_users("guild1")) == {"user1", "user2"}

    def test_get_enrolled_users_excludes_other_guild(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild2")
        assert database.get_enrolled_users("guild1") == ["user1"]


class TestRaceConfigViaDb:
    def test_no_config_returns_none(self, in_memory_db):
        assert database.get_race_channel("guild1") is None

    def test_set_and_retrieve_channel(self, in_memory_db):
        database.set_race_channel("guild1", "99999")
        assert database.get_race_channel("guild1") == "99999"

    def test_get_all_returns_all_guilds(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild2", "222")
        assert len(database.get_all_race_configs()) == 2
