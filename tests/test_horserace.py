import pytest
from cogs.horserace import simulate_race, build_progress_bar, format_race_progress, estimate_win_rates


def make_horses(weights=None, staminas=None, consistencies=None):
    """Return a minimal horse list for testing."""
    weights = weights or [5, 5, 5, 5]
    staminas = staminas or [5] * len(weights)
    consistencies = consistencies or [5] * len(weights)
    return [
        {
            "number": i + 1,
            "name": f"Horse {i + 1}",
            "weight": w,
            "stamina": s,
            "consistency": c,
            "bets": {},
        }
        for i, (w, s, c) in enumerate(zip(weights, staminas, consistencies))
    ]


class TestBuildProgressBar:
    def test_empty_bar_at_zero(self):
        bar = build_progress_bar(0.0, width=10)
        assert bar == "[░░░░░░░░░░]"

    def test_full_bar_at_one(self):
        bar = build_progress_bar(1.0, width=10)
        assert bar == "[██████████]"

    def test_half_bar(self):
        bar = build_progress_bar(0.5, width=10)
        assert bar == "[█████░░░░░]"

    def test_bar_length_respects_width(self):
        bar = build_progress_bar(0.5, width=20)
        inner = bar[1:-1]  # strip brackets
        assert len(inner) == 20

    def test_bar_has_brackets(self):
        bar = build_progress_bar(0.0)
        assert bar.startswith("[")
        assert bar.endswith("]")


class TestSimulateRace:
    def test_all_horses_finish(self):
        horses = make_horses()
        finish_order, _ = simulate_race(horses)
        assert len(finish_order) == len(horses)

    def test_finish_order_contains_all_horse_numbers(self):
        horses = make_horses()
        finish_order, _ = simulate_race(horses)
        assert set(finish_order) == {h["number"] for h in horses}

    def test_no_duplicate_finishers(self):
        horses = make_horses()
        finish_order, _ = simulate_race(horses)
        assert len(finish_order) == len(set(finish_order))

    def test_snapshots_at_10_percent_milestones(self):
        horses = make_horses()
        _, snapshots = simulate_race(horses)
        expected = {round(x * 0.1, 1) for x in range(1, 10)}
        assert set(snapshots.keys()) == expected

    def test_snapshot_contains_all_horses(self):
        horses = make_horses()
        _, snapshots = simulate_race(horses)
        for milestone, positions in snapshots.items():
            assert set(positions.keys()) == {h["number"] for h in horses}

    def test_positions_increase_over_time(self):
        horses = make_horses([10, 10])  # fast horses, all identical weight
        _, snapshots = simulate_race(horses)
        for horse_num in [1, 2]:
            assert snapshots[0.1][horse_num] <= snapshots[0.5][horse_num]
            assert snapshots[0.5][horse_num] <= snapshots[0.9][horse_num]

    def test_positions_capped_at_1(self):
        horses = make_horses([10, 10, 10, 10])
        _, snapshots = simulate_race(horses)
        for positions in snapshots.values():
            for pos in positions.values():
                assert pos <= 1.0

    def test_milestone_snapshots_are_accurate(self):
        """Leader position at each snapshot should be >= the milestone value."""
        horses = make_horses([5, 5, 5, 5])
        _, snapshots = simulate_race(horses)
        for milestone, positions in snapshots.items():
            leader_pos = max(positions.values())
            assert leader_pos >= milestone

    def test_heavier_horse_wins_more_often_than_lighter(self):
        """Statistical: heavy horse (weight=9) should beat light (weight=4) more than 50% of the time."""
        wins = 0
        trials = 300
        for _ in range(trials):
            horses = make_horses(weights=[9, 4])
            finish_order, _ = simulate_race(horses)
            if finish_order[0] == 1:
                wins += 1
        assert wins > trials * 0.55, f"Expected heavy horse to win >55% but got {wins}/{trials}"

    def test_high_stamina_helps_over_low_stamina(self):
        """Statistical: equal weight but high stamina should win more than low stamina."""
        wins = 0
        trials = 300
        for _ in range(trials):
            horses = make_horses(weights=[5, 5], staminas=[9, 4])
            finish_order, _ = simulate_race(horses)
            if finish_order[0] == 1:
                wins += 1
        assert wins > trials * 0.55, f"Expected high-stamina horse to win >55% but got {wins}/{trials}"


class TestEstimateWinRates:
    def test_returns_entry_for_each_horse(self):
        horses = make_horses()
        rates = estimate_win_rates(horses, trials=100)
        assert set(rates.keys()) == {h["number"] for h in horses}

    def test_win_rates_sum_to_1(self):
        horses = make_horses()
        rates = estimate_win_rates(horses, trials=200)
        assert abs(sum(rates.values()) - 1.0) < 0.01

    def test_all_rates_between_0_and_1(self):
        horses = make_horses()
        rates = estimate_win_rates(horses, trials=100)
        for rate in rates.values():
            assert 0.0 <= rate <= 1.0

    def test_stronger_horse_has_higher_win_rate(self):
        """Horse with weight=9, stamina=9 should have higher win rate than weight=4, stamina=4."""
        horses = make_horses(weights=[9, 4], staminas=[9, 4])
        rates = estimate_win_rates(horses, trials=300)
        assert rates[1] > rates[2]


class TestPayoutMath:
    """Test parimutuel payout calculations directly (mirrors logic in _run_race)."""

    def _calc_payouts(self, all_bets, winner_num):
        """
        all_bets: {user_id: (horse_num, amount)}
        Returns {user_id: payout} for winners only.
        """
        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {
            uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num
        }
        winning_total = sum(winning_bets.values())
        if winning_total == 0:
            return {}
        return {
            uid: int((amt / winning_total) * total_pool)
            for uid, amt in winning_bets.items()
        }

    def test_sole_winner_gets_entire_pool(self):
        all_bets = {"u1": (1, 100), "u2": (2, 200)}
        payouts = self._calc_payouts(all_bets, winner_num=1)
        assert payouts == {"u1": 300}

    def test_two_winners_split_pool_proportionally(self):
        all_bets = {"u1": (1, 100), "u2": (1, 300), "u3": (2, 200)}
        payouts = self._calc_payouts(all_bets, winner_num=1)
        total_pool = 600
        assert payouts["u1"] == int((100 / 400) * total_pool)  # 150
        assert payouts["u2"] == int((300 / 400) * total_pool)  # 450

    def test_payouts_sum_to_total_pool(self):
        all_bets = {"u1": (1, 50), "u2": (1, 150), "u3": (2, 100)}
        payouts = self._calc_payouts(all_bets, winner_num=1)
        # int truncation may cause off-by-one, allow 1 point variance
        assert abs(sum(payouts.values()) - 300) <= 1

    def test_no_bets_on_winner_returns_empty(self):
        all_bets = {"u1": (2, 100)}
        payouts = self._calc_payouts(all_bets, winner_num=1)
        assert payouts == {}

    def test_equal_bets_split_evenly(self):
        all_bets = {"u1": (1, 100), "u2": (1, 100), "u3": (2, 100)}
        payouts = self._calc_payouts(all_bets, winner_num=1)
        assert payouts["u1"] == payouts["u2"]

    def test_empty_pool_returns_empty(self):
        payouts = self._calc_payouts({}, winner_num=1)
        assert payouts == {}


class TestFormatRaceProgress:
    def test_contains_horse_names(self):
        horses = make_horses([5, 5])
        positions = {1: 0.5, 2: 0.25}
        output = format_race_progress(horses, positions, "Test Label")
        assert "Horse 1" in output
        assert "Horse 2" in output

    def test_contains_label(self):
        horses = make_horses([5])
        output = format_race_progress(horses, {1: 0.0}, "50% Complete")
        assert "50% Complete" in output

    def test_contains_progress_bars(self):
        horses = make_horses([5])
        output = format_race_progress(horses, {1: 0.5}, "label")
        assert "[" in output and "█" in output

    def test_missing_horse_in_positions_defaults_to_zero(self):
        horses = make_horses([5])
        # Pass empty positions dict — should not raise
        output = format_race_progress(horses, {}, "label")
        assert "0%" in output
