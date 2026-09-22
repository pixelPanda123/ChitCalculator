from dataclasses import dataclass

from src.models import ChitInput, ChitCalculation
from src.cash_flow import generate_cash_flows


@dataclass
class BorrowingCostResult:
    """Financial cost of using the chit as a source of funds."""

    amount_received: float
    total_installments: float
    total_dividends: float
    net_contribution: float
    net_cost: float
    # Simple cost percentage: net cost / amount received.
    # This is not an interest rate and does not replace IRR,
    # because it ignores when each payment happens.
    basic_cost_rate: float


def calculate_borrowing_cost(
    chit_input: ChitInput,
    chit_calculation: ChitCalculation,
) -> BorrowingCostResult:
    """
    Calculate the total economic cost of obtaining funds
    through the chit.

    The calculation uses the complete chit timeline:
    - Full monthly installments are paid throughout the tenure.
    - Monthly dividends are received according to the auction schedule.
    - Prize money is received in the selected lifting month.

    Basic cost rate = net cost / amount received. A negative value
    means the subscriber gets back more than they pay in overall.
    """

    cash_flows = generate_cash_flows(
        chit_input,
        chit_calculation,
    )

    total_installments = sum(
        cash_flow.gross_installment
        for cash_flow in cash_flows
    )

    total_dividends = sum(
        cash_flow.dividend
        for cash_flow in cash_flows
    )

    net_contribution = (
        total_installments
        - total_dividends
    )

    amount_received = chit_calculation.prize_amount

    net_cost = (
        net_contribution
        - amount_received
    )

    basic_cost_rate = (
        net_cost
        / amount_received
    )

    return BorrowingCostResult(
        amount_received=amount_received,
        total_installments=total_installments,
        total_dividends=total_dividends,
        net_contribution=net_contribution,
        net_cost=net_cost,
        basic_cost_rate=basic_cost_rate,
    )