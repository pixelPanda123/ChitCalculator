from dataclasses import dataclass


@dataclass
class ChitInput:
    chit_value: float
    duration_months: int
    month_of_lifting: int
    # When False, the subscriber stops receiving dividends
    # after the month in which they lift the chit.
    post_lift_dividend: bool = True

    def __post_init__(self):
        if self.chit_value <= 0:
            raise ValueError("Chit value must be greater than 0.")

        if self.duration_months <= 0:
            raise ValueError("Duration must be greater than 0.")

        if not 1 <= self.month_of_lifting <= self.duration_months:
            raise ValueError(
                "Month of lifting must be between 1 and the duration."
            )


@dataclass
class ChitCalculation:
    """Results from the basic chit calculations."""

    monthly_installment: float
    bid_amount: float
    commission_amount: float
    prize_amount: float
    net_installment: float


@dataclass
class MonthlyCashFlow:
    """Represents the subscriber's cash flow for one month."""

    month: int
    gross_installment: float
    dividend: float
    prize_received: float
    net_cash_flow: float


@dataclass
class ChitSummary:
    """Financial summary of the chit timeline and effective return."""

    prize_amount: float
    effective_annual_rate: float | None
    total_gross_installments: float
    total_dividends: float
    total_net_contribution: float


@dataclass
class LoanInput:
    """Input values required for personal loan calculations."""

    principal: float
    annual_interest_rate: float
    tenure_months: int
    processing_fee: float = 0.0

    def __post_init__(self):
        if self.principal <= 0:
            raise ValueError("Loan principal must be greater than zero.")

        if self.annual_interest_rate < 0:
            raise ValueError("Annual interest rate cannot be negative.")

        if self.tenure_months <= 0:
            raise ValueError("Loan tenure must be greater than zero.")

        if self.processing_fee < 0:
            raise ValueError("Processing fee cannot be negative.")


@dataclass
class ComparisonResult:
    """Results from comparing a chit with a personal loan."""

    chit_summary: ChitSummary
    loan_principal: float
    loan_annual_rate: float
    loan_effective_annual_rate: float
    loan_monthly_emi: float
    loan_total_interest: float
    loan_processing_fee: float
    loan_total_cost: float
    rate_difference: float | None


@dataclass
class LoanCalculation:
    """Results from personal loan calculations."""

    monthly_emi: float
    total_repayment: float
    total_interest: float
    processing_fee: float
    total_loan_cost: float
    effective_annual_rate: float


@dataclass
class SavingsInput:
    chit_value: float
    duration_months: int
    fixed_dividend: float
    maturity_payout: float

    def __post_init__(self):
        if self.chit_value <= 0:
            raise ValueError("Chit value must be greater than 0.")

        if self.duration_months <= 0:
            raise ValueError("Duration must be greater than 0.")

        if self.fixed_dividend < 0:
            raise ValueError("Fixed dividend cannot be negative.")

        if self.maturity_payout < 0:
            raise ValueError("Maturity payout cannot be negative.")


@dataclass
class SavingsCalculation:
    monthly_installment: float
    total_gross_contribution: float
    total_dividends: float
    total_net_contribution: float
    maturity_payout: float


@dataclass
class MonthlySavingsCashFlow:
    month: int
    gross_installment: float
    dividend: float
    maturity_payout: float
    net_cash_flow: float