import pytest

from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.comparison import (
    calculate_chit_summary,
    calculate_rate_difference,
    compare_chit_and_loan,
)
from src.loan_calculator import calculate_loan
from src.models import ChitInput, LoanInput


def create_sample_chit(
    month_of_lifting: int = 5,
    post_lift_dividend: bool = True,
) -> ChitInput:
    return ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=month_of_lifting,
        post_lift_dividend=post_lift_dividend,
    )


def test_chit_summary_with_post_lift_dividend():
    chit_input = create_sample_chit(post_lift_dividend=True)
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    chit_summary = calculate_chit_summary(
        chit_calculation=chit_calculation,
        cash_flows=cash_flows,
        effective_annual_rate=0.15,
    )

    assert chit_summary.prize_amount == 357000
    assert chit_summary.total_gross_installments == 500000

    expected_total_dividends = sum(
        cash_flow.dividend
        for cash_flow in cash_flows
    )

    assert chit_summary.total_dividends == expected_total_dividends

    assert chit_summary.total_net_contribution == (
        500000 - expected_total_dividends
    )


def test_chit_summary_without_post_lift_dividend():
    chit_input = create_sample_chit(post_lift_dividend=False)
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    chit_summary = calculate_chit_summary(
        chit_calculation=chit_calculation,
        cash_flows=cash_flows,
        effective_annual_rate=0.15,
    )

    assert chit_summary.prize_amount == 357000
    assert chit_summary.total_gross_installments == 500000

    expected_total_dividends = sum(
        cash_flow.dividend
        for cash_flow in cash_flows
        if cash_flow.month <= chit_input.month_of_lifting
    )

    assert chit_summary.total_dividends == expected_total_dividends

    assert chit_summary.total_net_contribution == (
        500000 - expected_total_dividends
    )


def test_rate_difference():
    rate_difference = calculate_rate_difference(
        chit_annual_rate=0.157419,
        loan_annual_rate=0.12,
    )

    assert rate_difference == pytest.approx(0.037419)


def test_complete_comparison():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    chit_summary = calculate_chit_summary(
        chit_calculation=chit_calculation,
        cash_flows=cash_flows,
        effective_annual_rate=0.15,
    )

    loan_input = LoanInput(
        principal=chit_calculation.prize_amount,
        annual_interest_rate=0.12,
        tenure_months=25,
        processing_fee=1000,
    )

    loan_calculation = calculate_loan(loan_input)

    comparison = compare_chit_and_loan(
        chit_summary=chit_summary,
        loan_input=loan_input,
        loan_calculation=loan_calculation,
    )

    assert comparison.chit_summary.prize_amount == 357000
    assert comparison.loan_principal == 357000

    assert comparison.loan_monthly_emi == pytest.approx(
        loan_calculation.monthly_emi
    )

    assert comparison.loan_total_interest == pytest.approx(
        loan_calculation.total_interest
    )

    assert comparison.loan_processing_fee == 1000

    assert comparison.loan_total_cost == pytest.approx(
        loan_calculation.total_loan_cost
    )

    assert comparison.loan_effective_annual_rate == pytest.approx(
        loan_calculation.effective_annual_rate
    )

    assert comparison.rate_difference == pytest.approx(
        chit_summary.effective_annual_rate
        - loan_calculation.effective_annual_rate
    )