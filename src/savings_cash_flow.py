from src.models import (
    MonthlySavingsCashFlow,
    SavingsCalculation,
    SavingsInput,
)


def generate_savings_cash_flows(
    savings_input: SavingsInput,
    savings_calculation: SavingsCalculation,
) -> list[MonthlySavingsCashFlow]:
    """Generate month-by-month cash flows for savings mode."""
    cash_flows = []

    for month in range(1, savings_input.duration_months + 1):
        maturity_payout = 0.0

        if month == savings_input.duration_months:
            maturity_payout = savings_input.maturity_payout

        net_cash_flow = (
            -savings_calculation.monthly_installment
            + savings_input.fixed_dividend
            + maturity_payout
        )

        cash_flows.append(
            MonthlySavingsCashFlow(
                month=month,
                gross_installment=savings_calculation.monthly_installment,
                dividend=savings_input.fixed_dividend,
                maturity_payout=maturity_payout,
                net_cash_flow=net_cash_flow,
            )
        )

    return cash_flows