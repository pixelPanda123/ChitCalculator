import pytest

from src.models import SavingsInput
from src.savings_calculator import (
    calculate_monthly_installment,
    calculate_savings,
    calculate_savings_return,
    calculate_total_dividends,
    calculate_total_gross_contribution,
    calculate_total_net_contribution,
)
from src.savings_cash_flow import (
    generate_savings_cash_flows,
)


def create_sample_savings() -> SavingsInput:
    return SavingsInput(
        chit_value=500000,
        duration_months=20,
        fixed_dividend=5000,
        maturity_payout=500000,
    )


def test_monthly_installment():
    result = calculate_monthly_installment(
        chit_value=500000,
        duration_months=20,
    )
    assert result == 25000


def test_total_gross_contribution():
    result = calculate_total_gross_contribution(
        monthly_installment=25000,
        duration_months=20,
    )
    assert result == 500000


def test_total_dividends():
    result = calculate_total_dividends(
        fixed_dividend=5000,
        duration_months=20,
    )
    assert result == 100000


def test_total_net_contribution():
    result = calculate_total_net_contribution(
        total_gross_contribution=500000,
        total_dividends=100000,
    )
    assert result == 400000


def test_complete_savings_calculation():
    savings_input = create_sample_savings()
    result = calculate_savings(savings_input)

    assert result.monthly_installment == 25000
    assert result.total_gross_contribution == 500000
    assert result.total_dividends == 100000
    assert result.total_net_contribution == 400000
    assert result.maturity_payout == 500000


def test_savings_return():
    savings_input = create_sample_savings()
    savings_calculation = calculate_savings(savings_input)

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    net_cash_flows = [cash_flow.net_cash_flow for cash_flow in cash_flows]

    monthly_irr, effective_annual_return = calculate_savings_return(
        net_cash_flows
    )

    assert monthly_irr > 0
    assert effective_annual_return > 0


def test_savings_input_rejects_zero_duration():
    with pytest.raises(ValueError):
        SavingsInput(
            chit_value=500000,
            duration_months=0,
            fixed_dividend=5000,
            maturity_payout=500000,
        )