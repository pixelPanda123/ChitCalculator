from src.models import LoanCalculation, LoanInput


def calculate_monthly_interest_rate(annual_interest_rate: float) -> float:
    """Convert annual interest rate to monthly interest rate."""
    return annual_interest_rate / 12


def calculate_effective_annual_rate(monthly_interest_rate: float) -> float:
    """Convert monthly interest rate to effective annual rate."""
    return (1 + monthly_interest_rate) ** 12 - 1


def calculate_emi(
    principal: float,
    monthly_interest_rate: float,
    tenure_months: int,
) -> float:
    """Calculate EMI using the reducing-balance loan formula."""

    if monthly_interest_rate == 0:
        return principal / tenure_months

    rate_factor = (1 + monthly_interest_rate) ** tenure_months

    return (
        principal
        * monthly_interest_rate
        * rate_factor
        / (rate_factor - 1)
    )


def calculate_loan(loan_input: LoanInput) -> LoanCalculation:
    """Calculate complete loan details."""

    monthly_interest_rate = calculate_monthly_interest_rate(
        loan_input.annual_interest_rate
    )

    effective_annual_rate = calculate_effective_annual_rate(
        monthly_interest_rate
    )

    monthly_emi = calculate_emi(
        principal=loan_input.principal,
        monthly_interest_rate=monthly_interest_rate,
        tenure_months=loan_input.tenure_months,
    )

    total_repayment = monthly_emi * loan_input.tenure_months

    total_interest = total_repayment - loan_input.principal

    total_loan_cost = (
        total_interest
        + loan_input.processing_fee
    )

    return LoanCalculation(
        monthly_emi=monthly_emi,
        total_repayment=total_repayment,
        total_interest=total_interest,
        processing_fee=loan_input.processing_fee,
        total_loan_cost=total_loan_cost,
        effective_annual_rate=effective_annual_rate,
    )