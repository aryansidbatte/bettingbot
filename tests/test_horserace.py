import pytest
from cogs.horserace import simulate_race, build_progress_bar, format_race_progress, estimate_win_rates, _best_fraction, to_fractional_odds


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


class TestBestFraction:
    def test_evens_returns_one_one(self):
        n, d = _best_fraction(0.5)
        assert n / d == pytest.approx(1.0, abs=0.1)

    def test_heavy_favourite_returns_short_odds(self):
        # 80% win rate → very short odds (less than evens)
        n, d = _best_fraction(0.8)
        assert n / d < 1.0

    def test_longshot_returns_long_odds(self):
        # 5% win rate → long odds
        n, d = _best_fraction(0.05)
        assert n / d > 5.0

    def test_zero_win_rate_returns_100_1(self):
        assert _best_fraction(0.0) == (100, 1)

    def test_returns_tuple_of_two_ints(self):
        result = _best_fraction(0.33)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(x, int) for x in result)

    def test_fraction_is_from_standard_list(self):
        from cogs.horserace import _STANDARD_FRACTIONS
        result = _best_fraction(0.4)
        assert result in _STANDARD_FRACTIONS


class TestToFractionalOdds:
    def test_returns_string_with_dash(self):
        result = to_fractional_odds(0.5)
        assert "-" in result

    def test_format_is_n_dash_d(self):
        result = to_fractional_odds(0.33)
        parts = result.split("-")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_zero_win_rate_returns_100_1(self):
        assert to_fractional_odds(0.0) == "100-1"

    def test_consistent_with_best_fraction(self):
        n, d = _best_fraction(0.4)
        assert to_fractional_odds(0.4) == f"{n}-{d}"


class TestFixedOddsPayoutMath:
    """Test fixed-odds payout logic (mirrors _run_race after the parimutuel→fixed-odds change)."""

    def _calc_fixed_payouts(self, all_bets, winner_num, win_rate):
        """
        all_bets: {user_id: (horse_num, amount)}
        Returns {user_id: total_return} for winners only.
        total_return = stake + profit = stake * (1 + n/d)
        """
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        if not winning_bets:
            return {}
        n, d = _best_fraction(win_rate)
        multiplier = n / d
        return {uid: amt + int(amt * multiplier) for uid, amt in winning_bets.items()}

    def test_winner_gets_stake_plus_profit(self):
        # 2-1 odds: bet 100 → return 300 (100 stake + 200 profit)
        n, d = _best_fraction(0.33)  # ~2-1
        multiplier = n / d
        payouts = self._calc_fixed_payouts({"u1": (1, 100), "u2": (2, 50)}, winner_num=1, win_rate=0.33)
        assert payouts["u1"] == 100 + int(100 * multiplier)

    def test_loser_gets_nothing(self):
        payouts = self._calc_fixed_payouts({"u1": (1, 100), "u2": (2, 50)}, winner_num=1, win_rate=0.33)
        assert "u2" not in payouts

    def test_no_bets_on_winner_returns_empty(self):
        payouts = self._calc_fixed_payouts({"u1": (2, 100)}, winner_num=1, win_rate=0.5)
        assert payouts == {}

    def test_empty_bets_returns_empty(self):
        payouts = self._calc_fixed_payouts({}, winner_num=1, win_rate=0.5)
        assert payouts == {}

    def test_multiple_winners_each_paid_independently(self):
        # Both bet on winner — each gets their own fixed payout, not split
        payouts = self._calc_fixed_payouts(
            {"u1": (1, 100), "u2": (1, 200), "u3": (2, 300)},
            winner_num=1, win_rate=0.5
        )
        assert "u1" in payouts
        assert "u2" in payouts
        assert "u3" not in payouts
        # u2 bet 2x u1, so u2 payout should be 2x u1 payout
        assert payouts["u2"] == payouts["u1"] * 2

    def test_favourite_pays_less_than_longshot(self):
        bet = 100
        favourite_payout = self._calc_fixed_payouts({"u1": (1, bet)}, winner_num=1, win_rate=0.8)
        longshot_payout = self._calc_fixed_payouts({"u1": (1, bet)}, winner_num=1, win_rate=0.1)
        assert longshot_payout["u1"] > favourite_payout["u1"]

    def test_payout_always_at_least_stake(self):
        # Even at shortest odds, winner always gets their stake back
        payouts = self._calc_fixed_payouts({"u1": (1, 100)}, winner_num=1, win_rate=0.99)
        assert payouts["u1"] >= 100


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
