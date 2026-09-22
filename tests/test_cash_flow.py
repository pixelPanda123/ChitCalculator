from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.models import ChitInput


def create_sample_chit(
    month_of_lifting: int = 5,
) -> ChitInput:
    return ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=month_of_lifting,
    )


def test_cash_flow_count():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    assert len(cash_flows) == 25


def test_cash_flow_before_lifting():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    month_1 = cash_flows[0]

    assert month_1.month == 1
    assert month_1.gross_installment == 20000
    assert month_1.dividend == 5000
    assert month_1.prize_received == 0
    assert month_1.net_cash_flow == -15000


def test_cash_flow_on_lifting_month():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    month_5 = cash_flows[4]

    assert month_5.month == 5
    assert month_5.gross_installment == 20000
    assert month_5.dividend == 4720
    assert month_5.prize_received == 357000
    assert month_5.net_cash_flow == 341720


def test_cash_flow_after_lifting():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    month_6 = cash_flows[5]

    assert month_6.month == 6
    assert month_6.gross_installment == 20000
    assert month_6.dividend == 4439
    assert month_6.prize_received == 0
    assert month_6.net_cash_flow == -15561


def test_cash_flow_uses_month_specific_dividend():
    chit_input = create_sample_chit()
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    month_8 = cash_flows[7]
    month_15 = cash_flows[14]
    month_25 = cash_flows[24]

    assert month_8.dividend == 3880
    assert month_15.dividend == 2200
    assert month_25.dividend == 0


def test_no_dividend_after_lifting_when_disabled():
    chit_input = ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=5,
        post_lift_dividend=False,
    )
    chit_calculation = calculate_chit(chit_input)

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    assert cash_flows[4].dividend == 4720
    assert cash_flows[5].dividend == 0
    assert cash_flows[5].net_cash_flow == -20000