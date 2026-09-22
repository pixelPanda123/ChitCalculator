from src.models import SavingsCalculation, SavingsInput
from src.financial_utils import (
    calculate_monthly_irr,
    annualize_monthly_rate,
)


def calculate_monthly_installment(
    chit_value: float,
    duration_months: int,
) -> float:
    """Calculate the monthly chit installment."""
    return chit_value / duration_months


def calculate_total_gross_contribution(
    monthly_installment: float,
    duration_months: int,
) -> float:
    """Calculate total gross contributions over the full tenure."""
    return monthly_installment * duration_months


def calculate_total_dividends(
    fixed_dividend: float,
    duration_months: int,
) -> float:
    """Calculate total dividends received over the full tenure."""
    return fixed_dividend * duration_months


def calculate_total_net_contribution(
    total_gross_contribution: float,
    total_dividends: float,
) -> float:
    """Calculate total contributions after dividends."""
    return total_gross_contribution - total_dividends


def calculate_savings(
    savings_input: SavingsInput,
) -> SavingsCalculation:
    """Calculate the complete savings summary."""

    monthly_installment = calculate_monthly_installment(
        savings_input.chit_value,
        savings_input.duration_months,
    )

    total_gross_contribution = calculate_total_gross_contribution(
        monthly_installment,
        savings_input.duration_months,
    )

    total_dividends = calculate_total_dividends(
        savings_input.fixed_dividend,
        savings_input.duration_months,
    )

    total_net_contribution = calculate_total_net_contribution(
        total_gross_contribution,
        total_dividends,
    )

    return SavingsCalculation(
        monthly_installment=monthly_installment,
        total_gross_contribution=total_gross_contribution,
        total_dividends=total_dividends,
        total_net_contribution=total_net_contribution,
        maturity_payout=savings_input.maturity_payout,
    )


def calculate_savings_return(
    cash_flows: list[float],
) -> tuple[float, float]:
    """
    Calculate the monthly IRR and effective annual return
    for savings mode.
    """

    monthly_irr = calculate_monthly_irr(cash_flows)
    effective_annual_return = annualize_monthly_rate(monthly_irr)

    return (
        monthly_irr,
        effective_annual_return,
    )