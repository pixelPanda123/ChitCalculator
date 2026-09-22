import pytest

from src.auction_schedule import AUCTION_SCHEDULE, get_auction_result

CHIT_VALUE = 500000
DURATION_MONTHS = 25
MINIMUM_BID = 25000


def test_schedule_covers_every_month():
    assert sorted(AUCTION_SCHEDULE) == list(range(1, DURATION_MONTHS + 1))


def test_get_auction_result_returns_matching_month():
    result = get_auction_result(5)

    assert result.month == 5
    assert result.bid_amount == 143000
    assert result.dividend == 4720
    assert result.prize_money == 357000


def test_invalid_months_raise_value_error():
    for month in (0, DURATION_MONTHS + 1, -1):
        with pytest.raises(ValueError):
            get_auction_result(month)


def test_bid_and_prize_add_up_to_chit_value():
    for result in AUCTION_SCHEDULE.values():
        assert result.bid_amount + result.prize_money == CHIT_VALUE


def test_month_keys_match_result_months():
    for month, result in AUCTION_SCHEDULE.items():
        assert result.month == month


def test_dividend_follows_bid_formula():
    # Dividend = (bid - minimum bid) / members, rounded down.
    for result in AUCTION_SCHEDULE.values():
        expected = (result.bid_amount - MINIMUM_BID) // DURATION_MONTHS
        assert result.dividend == expected