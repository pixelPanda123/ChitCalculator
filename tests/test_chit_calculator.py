from src.chit_calculator import (
    calculate_auction_values,
    calculate_chit,
    calculate_monthly_installment,
)
from src.models import ChitInput


def create_sample_chit() -> ChitInput:
    return ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=5,
    )


def test_monthly_installment():
    chit = create_sample_chit()

    result = calculate_monthly_installment(chit)

    assert result == 20000


def test_auction_values():
    chit = create_sample_chit()

    bid_amount, dividend, prize_amount = calculate_auction_values(chit)

    assert bid_amount == 143000
    assert dividend == 4720
    assert prize_amount == 357000


def test_complete_chit_calculation():
    chit = create_sample_chit()

    result = calculate_chit(chit)

    assert result.monthly_installment == 20000
    assert result.bid_amount == 143000
    assert result.commission_amount == 0.0
    assert result.prize_amount == 357000
    assert result.net_installment == 15280