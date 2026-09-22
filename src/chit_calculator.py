from src.models import ChitCalculation, ChitInput
from src.auction_schedule import get_auction_result


def calculate_monthly_installment(chit_input: ChitInput) -> float:
    """Calculate the gross monthly installment."""
    return chit_input.chit_value / chit_input.duration_months


def calculate_auction_values(chit_input: ChitInput):
    """Get the bid, dividend, and prize for the selected lifting month."""
    auction = get_auction_result(chit_input.month_of_lifting)

    return (
        auction.bid_amount,
        auction.dividend,
        auction.prize_money,
    )


def calculate_net_installment(
    monthly_installment: float,
    dividend: float,
) -> float:
    """Calculate the installment after applying the auction dividend."""
    return monthly_installment - dividend


def calculate_chit(chit_input: ChitInput) -> ChitCalculation:
    """Run the basic chit calculations using the selected auction month."""

    monthly_installment = calculate_monthly_installment(chit_input)

    bid_amount, dividend, prize_amount = calculate_auction_values(
        chit_input
    )

    net_installment = calculate_net_installment(
        monthly_installment,
        dividend,
    )

    return ChitCalculation(
        monthly_installment=monthly_installment,
        bid_amount=bid_amount,
        commission_amount=0.0,
        prize_amount=prize_amount,
        net_installment=net_installment,
    )