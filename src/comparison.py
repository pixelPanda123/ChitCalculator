from src.models import (
    ChitCalculation,
    ChitSummary,
    ComparisonResult,
    LoanCalculation,
    LoanInput,
    MonthlyCashFlow,
)


def calculate_chit_summary(
    chit_calculation: ChitCalculation,
    cash_flows: list[MonthlyCashFlow],
    effective_annual_rate: float | None,
) -> ChitSummary:
    """Create a financial summary of the chit using the generated cash flows."""

    total_gross_installments = sum(
        cash_flow.gross_installment
        for cash_flow in cash_flows
    )

    total_dividends = sum(
        cash_flow.dividend
        for cash_flow in cash_flows
    )

    total_net_contribution = (
        total_gross_installments - total_dividends
    )

    return ChitSummary(
        prize_amount=chit_calculation.prize_amount,
        effective_annual_rate=effective_annual_rate,
        total_gross_installments=total_gross_installments,
        total_dividends=total_dividends,
        total_net_contribution=total_net_contribution,
    )


def calculate_rate_difference(
    chit_annual_rate: float | None,
    loan_annual_rate: float,
) -> float | None:
    """Calculate the rate difference when both rates are available."""

    if chit_annual_rate is None:
        return None

    return chit_annual_rate - loan_annual_rate


def compare_chit_and_loan(
    chit_summary: ChitSummary,
    loan_input: LoanInput,
    loan_calculation: LoanCalculation,
) -> ComparisonResult:
    """Combine chit and personal loan results into one comparison."""

    rate_difference = calculate_rate_difference(
        chit_summary.effective_annual_rate,
        loan_calculation.effective_annual_rate,
    )

    return ComparisonResult(
        chit_summary=chit_summary,
        loan_principal=loan_input.principal,
        loan_annual_rate=loan_input.annual_interest_rate,
        loan_effective_annual_rate=loan_calculation.effective_annual_rate,
        loan_monthly_emi=loan_calculation.monthly_emi,
        loan_total_interest=loan_calculation.total_interest,
        loan_processing_fee=loan_calculation.processing_fee,
        loan_total_cost=loan_calculation.total_loan_cost,
        rate_difference=rate_difference,
    )