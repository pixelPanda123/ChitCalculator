import pytest

from src.loan_calculator import (
    calculate_emi,
    calculate_loan,
    calculate_monthly_interest_rate,
)
from src.models import LoanInput


def test_monthly_interest_rate():
    monthly_rate = calculate_monthly_interest_rate(0.12)
    assert monthly_rate == pytest.approx(0.01)


def test_calculate_emi():
    emi = calculate_emi(
        principal=100000,
        monthly_interest_rate=0.01,
        tenure_months=12,
    )
    assert emi == pytest.approx(
        8884.88,
        abs=0.01,
    )


def test_calculate_complete_loan():
    loan_input = LoanInput(
        principal=100000,
        annual_interest_rate=0.12,
        tenure_months=12,
        processing_fee=1000,
    )
    result = calculate_loan(loan_input)

    assert result.monthly_emi == pytest.approx(
        8884.88,
        abs=0.01,
    )

    assert result.total_repayment == pytest.approx(
        106618.55,
        abs=0.01,
    )

    assert result.total_interest == pytest.approx(
        6618.55,
        abs=0.01,
    )

    assert result.processing_fee == 1000

    assert result.total_loan_cost == pytest.approx(
        7618.55,
        abs=0.01,
    )


def test_zero_interest_loan():
    loan_input = LoanInput(
        principal=120000,
        annual_interest_rate=0,
        tenure_months=12,
        processing_fee=0,
    )
    result = calculate_loan(loan_input)

    assert result.monthly_emi == 10000
    assert result.total_repayment == 120000
    assert result.total_interest == 0
    assert result.total_loan_cost == 0