from src.models import SavingsInput
from src.savings_calculator import calculate_savings
from src.savings_cash_flow import generate_savings_cash_flows


def create_sample_savings() -> SavingsInput:
    return SavingsInput(
        chit_value=500000,
        duration_months=20,
        fixed_dividend=5000,
        maturity_payout=500000,
    )


def test_number_of_cash_flows():
    savings_input = create_sample_savings()

    savings_calculation = calculate_savings(
        savings_input
    )

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    assert len(cash_flows) == 20


def test_first_month_cash_flow():
    savings_input = create_sample_savings()

    savings_calculation = calculate_savings(
        savings_input
    )

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    first_month = cash_flows[0]

    assert first_month.month == 1
    assert first_month.gross_installment == 25000
    assert first_month.dividend == 5000
    assert first_month.maturity_payout == 0
    assert first_month.net_cash_flow == -20000


def test_middle_month_cash_flow():
    savings_input = create_sample_savings()

    savings_calculation = calculate_savings(
        savings_input
    )

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    middle_month = cash_flows[9]

    assert middle_month.month == 10
    assert middle_month.gross_installment == 25000
    assert middle_month.dividend == 5000
    assert middle_month.maturity_payout == 0
    assert middle_month.net_cash_flow == -20000


def test_final_month_cash_flow():
    savings_input = create_sample_savings()

    savings_calculation = calculate_savings(
        savings_input
    )

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    final_month = cash_flows[-1]

    assert final_month.month == 20
    assert final_month.gross_installment == 25000
    assert final_month.dividend == 5000
    assert final_month.maturity_payout == 500000
    assert final_month.net_cash_flow == 480000


def test_only_final_month_receives_maturity():
    savings_input = create_sample_savings()

    savings_calculation = calculate_savings(
        savings_input
    )

    cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    for cash_flow in cash_flows[:-1]:
        assert cash_flow.maturity_payout == 0

    assert cash_flows[-1].maturity_payout == 500000