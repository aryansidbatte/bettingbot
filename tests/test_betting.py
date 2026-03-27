import pytest
from cogs.betting import parse_instant_bet


class TestParseInstantBet:
    def test_valid_two_outcomes(self):
        desc, outcomes = parse_instant_bet("Who wins? | Team A | Team B")
        assert desc == "Who wins?"
        assert outcomes == ["Team A", "Team B"]

    def test_valid_three_outcomes(self):
        desc, outcomes = parse_instant_bet("Best fruit? | Apple | Banana | Cherry")
        assert desc == "Best fruit?"
        assert outcomes == ["Apple", "Banana", "Cherry"]

    def test_strips_whitespace(self):
        desc, outcomes = parse_instant_bet("  Foo?  |  Bar  |  Baz  ")
        assert desc == "Foo?"
        assert outcomes == ["Bar", "Baz"]

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="Description can't be empty"):
            parse_instant_bet(" | A | B")

    def test_one_outcome_raises(self):
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            parse_instant_bet("Foo? | Only one")

    def test_eleven_outcomes_raises(self):
        outcomes = " | ".join(f"O{i}" for i in range(11))
        with pytest.raises(ValueError, match="Maximum 10 outcomes"):
            parse_instant_bet(f"Foo? | {outcomes}")

    def test_empty_outcome_name_raises(self):
        with pytest.raises(ValueError, match="Outcome names can't be empty"):
            parse_instant_bet("Foo? | A | ")

    def test_no_pipe_raises(self):
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            parse_instant_bet("Just a description")
