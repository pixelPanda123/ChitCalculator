from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.comparison import (
    calculate_chit_summary,
    compare_chit_and_loan,
)
from src.borrowing_cost import calculate_borrowing_cost
from src.financial_utils import (
    annualize_monthly_rate,
    calculate_monthly_irr,
)
from src.loan_calculator import calculate_loan
from src.models import ChitInput, LoanInput, SavingsInput
from src.savings_calculator import (
    calculate_savings,
    calculate_savings_return,
)
from src.savings_cash_flow import (
    generate_savings_cash_flows,
)


NO_IRR_MESSAGE = "N/A (no single IRR exists for these cash flows)"


def format_rate(rate: float | None) -> str:
    """Format a rate as a percentage, or explain why it is missing."""

    if rate is None:
        return NO_IRR_MESSAGE

    return f"{rate:.4%}"


def main():
    # -------------------------
    # Chit Input
    # -------------------------
    chit_input = ChitInput(
        chit_value=500000,
        duration_months=25,
        month_of_lifting=15,
    )

    # -------------------------
    # Chit Calculation
    # -------------------------
    chit_result = calculate_chit(chit_input)
    borrowing_cost = calculate_borrowing_cost(
        chit_input,
        chit_result,
    )
    # -------------------------
    # Cash Flow Generation
    # -------------------------
    cash_flows = generate_cash_flows(
        chit_input,
        chit_result,
    )

    net_cash_flows = [
        cash_flow.net_cash_flow
        for cash_flow in cash_flows
    ]

    # -------------------------
    # Effective Rate
    # -------------------------

    try:
        monthly_irr = calculate_monthly_irr(net_cash_flows)
        annual_rate = annualize_monthly_rate(monthly_irr)
    except ValueError:
        monthly_irr = None
        annual_rate = None

    # -------------------------
    # Personal Loan
    # -------------------------
    loan_input = LoanInput(
        principal=chit_result.prize_amount,
        annual_interest_rate=0.12,
        tenure_months=chit_input.duration_months,
        processing_fee=1000,
    )

    loan_result = calculate_loan(loan_input)

    # -------------------------
    # Chit Summary
    # -------------------------
    chit_summary = calculate_chit_summary(
        chit_calculation=chit_result,
        cash_flows=cash_flows,
        effective_annual_rate=annual_rate,
    )

    # -------------------------
    # Comparison
    # -------------------------
    comparison = compare_chit_and_loan(
        chit_summary=chit_summary,
        loan_input=loan_input,
        loan_calculation=loan_result,
    )

    # ==================================================
    # DISPLAY RESULTS
    # ==================================================

    print("\nCHIT CALCULATION")
    print("----------------")
    print(
        f"Monthly Installment: "
        f"₹{chit_result.monthly_installment:,.2f}"
    )
    print(
        f"Bid Amount: "
        f"₹{chit_result.bid_amount:,.2f}"
    )
    print(
        f"Commission: "
        f"₹{chit_result.commission_amount:,.2f}"
    )
    print(
        f"Prize Amount: "
        f"₹{chit_result.prize_amount:,.2f}"
    )
    print(
        f"Net Installment: "
        f"₹{chit_result.net_installment:,.2f}"
    )

    # -------------------------
    # Chit Borrowing cost
    # -------------------------
    print("\nCHIT BORROWING COST")
    print("-------------------")
    print(
        f"Amount Received: "
        f"₹{borrowing_cost.amount_received:,.2f}"
    )
    print(
        f"Total Installments: "
        f"₹{borrowing_cost.total_installments:,.2f}"
    )
    print(
        f"Total Dividends: "
        f"₹{borrowing_cost.total_dividends:,.2f}"
    )
    print(
        f"Net Contribution: "
        f"₹{borrowing_cost.net_contribution:,.2f}"
    )
    print(
        f"Net Cost: "
        f"₹{borrowing_cost.net_cost:,.2f}"
    )
    print(
        f"Basic Cost Rate: "
        f"{borrowing_cost.basic_cost_rate:.2%}"
    )
    # -------------------------
    # Chit Effective Rate
    # -------------------------
    print("\nCHIT EFFECTIVE RATE")
    print("-------------------")
    print(f"Monthly IRR: {format_rate(monthly_irr)}")
    print(f"Effective Annual Rate: {format_rate(annual_rate)}")

    # -------------------------
    # Chit Summary
    # -------------------------
    print("\nCHIT SUMMARY")
    print("------------")
    print(
        "Total Gross Installments: "
        f"₹{comparison.chit_summary.total_gross_installments:,.2f}"
    )
    print(
        "Total Dividends: "
        f"₹{comparison.chit_summary.total_dividends:,.2f}"
    )
    print(
        "Total Net Contribution: "
        f"₹{comparison.chit_summary.total_net_contribution:,.2f}"
    )

    # -------------------------
    # Personal Loan
    # -------------------------
    print("\nPERSONAL LOAN")
    print("-------------")
    print(
        f"Loan Principal: "
        f"₹{comparison.loan_principal:,.2f}"
    )
    print(
        f"Loan Nominal Annual Rate: "
        f"{comparison.loan_annual_rate:.4%}"
    )
    print(
        f"Loan Effective Annual Rate: "
        f"{comparison.loan_effective_annual_rate:.4%}"
    )
    print(
        f"Monthly EMI: "
        f"₹{comparison.loan_monthly_emi:,.2f}"
    )
    print(
        f"Total Interest: "
        f"₹{comparison.loan_total_interest:,.2f}"
    )
    print(
        f"Processing Fee: "
        f"₹{comparison.loan_processing_fee:,.2f}"
    )
    print(
        f"Total Loan Cost: "
        f"₹{comparison.loan_total_cost:,.2f}"
    )

    # -------------------------
    # Rate Comparison
    # -------------------------
    print("\nRATE COMPARISON")
    print("---------------")
    print(
        "Chit Effective Annual Rate: "
        f"{format_rate(comparison.chit_summary.effective_annual_rate)}"
    )
    print(
        "Personal Loan Effective Annual Rate: "
        f"{comparison.loan_effective_annual_rate:.4%}"
    )
    print(
        f"Rate Difference: "
        f"{format_rate(comparison.rate_difference)}"
    )

    # -------------------------
    # Savings Input & Calculation
    # -------------------------
    savings_input = SavingsInput(
        chit_value=500000,
        duration_months=20,
        fixed_dividend=5000,
        maturity_payout=500000,
    )

    savings_calculation = calculate_savings(
        savings_input
    )

    savings_cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    savings_net_cash_flows = [
        cash_flow.net_cash_flow
        for cash_flow in savings_cash_flows
    ]

    try:
        (
            savings_monthly_irr,
            savings_effective_annual_return,
        ) = calculate_savings_return(
            savings_net_cash_flows
        )
    except ValueError:
        savings_monthly_irr = None
        savings_effective_annual_return = None

    # -------------------------
    # Savings Output
    # -------------------------
    print("\nSAVINGS CHIT SCHEME")
    print("-------------------")
    print(
        f"Monthly Installment: "
        f"₹{savings_calculation.monthly_installment:,.2f}"
    )
    print(
        f"Total Gross Contribution: "
        f"₹{savings_calculation.total_gross_contribution:,.2f}"
    )
    print(
        f"Total Dividends Received: "
        f"₹{savings_calculation.total_dividends:,.2f}"
    )
    print(
        f"Total Net Contribution: "
        f"₹{savings_calculation.total_net_contribution:,.2f}"
    )
    print(
        f"Maturity Payout: "
        f"₹{savings_calculation.maturity_payout:,.2f}"
    )
    print(
        f"Savings Monthly IRR: "
        f"{format_rate(savings_monthly_irr)}"
    )
    print(
        f"Savings Effective Annual Return: "
        f"{format_rate(savings_effective_annual_return)}"
    )


if __name__ == "__main__":
    main()