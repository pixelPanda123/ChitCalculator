from src.models import ChitCalculation, ChitInput, MonthlyCashFlow
from src.auction_schedule import get_auction_result


def get_monthly_dividend(
    month: int,
    chit_input: ChitInput,
) -> float:
    """
    Return the dividend the subscriber receives in the given month.

    If post-lift dividends are disabled, no dividend is received
    after the lifting month.
    """

    if (
        not chit_input.post_lift_dividend
        and month > chit_input.month_of_lifting
    ):
        return 0.0

    auction = get_auction_result(month)

    return auction.dividend


def get_prize_received(
    month: int,
    chit_input: ChitInput,
    chit_calculation: ChitCalculation,
) -> float:
    """Return the prize amount only in the lifting month."""

    if month == chit_input.month_of_lifting:
        return chit_calculation.prize_amount

    return 0.0


def calculate_month_cash_flow(
    month: int,
    chit_input: ChitInput,
    chit_calculation: ChitCalculation,
) -> MonthlyCashFlow:
    """Calculate the complete cash flow for one month."""

    gross_installment = chit_calculation.monthly_installment

    dividend = get_monthly_dividend(month, chit_input)

    prize_received = get_prize_received(
        month,
        chit_input,
        chit_calculation,
    )

    net_cash_flow = (
        -gross_installment
        + dividend
        + prize_received
    )

    return MonthlyCashFlow(
        month=month,
        gross_installment=gross_installment,
        dividend=dividend,
        prize_received=prize_received,
        net_cash_flow=net_cash_flow,
    )


def generate_cash_flows(
    chit_input: ChitInput,
    chit_calculation: ChitCalculation,
) -> list[MonthlyCashFlow]:
    """Generate the complete month-by-month chit cash flow timeline."""

    cash_flows = []

    for month in range(1, chit_input.duration_months + 1):
        monthly_cash_flow = calculate_month_cash_flow(
            month,
            chit_input,
            chit_calculation,
        )

        cash_flows.append(monthly_cash_flow)

    return cash_flows