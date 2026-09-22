import pytest

from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.financial_utils import (
    annualize_monthly_rate,
    calculate_effective_annual_rate,
    calculate_monthly_irr,
    calculate_npv,
    validate_cash_flows,
)
from src.loan_calculator import calculate_emi
from src.models import ChitInput


def chit_net_cash_flows(month_of_lifting: int) -> list[float]:
    chit_input = ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=month_of_lifting,
    )
    chit_calculation = calculate_chit(chit_input)

    return [
        cash_flow.net_cash_flow
        for cash_flow in generate_cash_flows(chit_input, chit_calculation)
    ]


def test_validate_requires_two_cash_flows():
    with pytest.raises(ValueError):
        validate_cash_flows([-100])


def test_validate_requires_mixed_signs():
    with pytest.raises(ValueError):
        validate_cash_flows([-100, -50])

    with pytest.raises(ValueError):
        validate_cash_flows([100, 50])


def test_npv_at_zero_rate_is_sum():
    assert calculate_npv([-100, 30, 80], 0.0) == pytest.approx(10)


def test_simple_irr():
    assert calculate_monthly_irr([-100, 110]) == pytest.approx(0.10)


def test_irr_of_loan_matches_loan_rate():
    emi = calculate_emi(
        principal=100000,
        monthly_interest_rate=0.01,
        tenure_months=12,
    )
    cash_flows = [100000] + [-emi] * 12

    assert calculate_monthly_irr(cash_flows) == pytest.approx(0.01, abs=1e-8)


def test_annualize_monthly_rate():
    assert annualize_monthly_rate(0.01) == pytest.approx(0.126825, abs=1e-6)


def test_effective_annual_rate():
    assert calculate_effective_annual_rate([-100, 110]) == pytest.approx(
        1.1**12 - 1
    )


def test_multiple_irrs_returns_lowest_non_negative():
    # Lifting in month 5 produces two IRRs (about 2.65% and 75%).
    assert calculate_monthly_irr(chit_net_cash_flows(5)) == pytest.approx(
        0.0264767, abs=1e-6
    )


def test_no_irr_raises_value_error():
    # Lifting in month 15: NPV is negative at every rate, so no IRR exists.
    with pytest.raises(ValueError, match="Unable to calculate IRR"):
        calculate_monthly_irr(chit_net_cash_flows(15))