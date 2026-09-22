"""
Streamlit UI for the MyPaisaa chit calculator.

This file is a presentation layer only. Every financial value shown on
the page comes from the existing calculation engine in ``src/``. No
formulas are implemented here.

Run with:
    streamlit run app.py
"""

import pandas as pd
import streamlit as st

from src.auction_schedule import AUCTION_SCHEDULE, get_auction_result
from src.borrowing_cost import calculate_borrowing_cost
from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.comparison import calculate_chit_summary, compare_chit_and_loan
from src.financial_utils import annualize_monthly_rate, calculate_monthly_irr
from src.loan_calculator import calculate_loan
from src.models import ChitInput, LoanInput, SavingsInput
from src.savings_calculator import calculate_savings, calculate_savings_return
from src.savings_cash_flow import generate_savings_cash_flows


# ----------------------------------------------------------------------
# Demo configuration (same values used by main.py and the demo brief)
# ----------------------------------------------------------------------
# Chit value and duration are fixed for the demo. Duration is read from
# the auction schedule so the slider always matches the available data.
CHIT_VALUE = 500_000
DURATION_MONTHS = len(AUCTION_SCHEDULE)
DEFAULT_LIFTING_MONTH = 15

DEFAULT_LOAN_RATE_PERCENT = 12.0
DEFAULT_PROCESSING_FEE = 1_000

SAVINGS_CHIT_VALUE = 500_000
SAVINGS_DURATION_MONTHS = 20
DEFAULT_SAVINGS_FIXED_DIVIDEND = 5_000
DEFAULT_SAVINGS_MATURITY_PAYOUT = 500_000

NOT_AVAILABLE = "N/A"

PAGE_CSS = """
<style>
    [data-testid="stMainBlockContainer"], .block-container {
        max-width: 1200px;
        padding-top: 2.5rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-variant-numeric: tabular-nums;
    }
    .st-key-selected-auction {
        background-color: #F2F6FA;
        border-left: 4px solid #1F5F8B;
    }
</style>
"""

LIFTING_ROW_STYLE = "background-color: #E6EEF6"


# ----------------------------------------------------------------------
# Formatting helpers (display only)
# ----------------------------------------------------------------------
def format_inr(amount: float) -> str:
    """Format an amount with Indian digit grouping, e.g. ₹5,00,000.00."""

    amount = round(amount, 2)
    sign = "-" if amount < 0 else ""
    rupees, paise = f"{abs(amount):.2f}".split(".")

    if len(rupees) > 3:
        head, tail = rupees[:-3], rupees[-3:]
        groups = []

        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]

        if head:
            groups.insert(0, head)

        rupees = ",".join(groups + [tail])

    return f"{sign}₹{rupees}.{paise}"


def format_rate(rate: float | None, decimals: int = 2) -> str:
    """Format a rate as a percentage, or N/A when the engine returned none."""

    if rate is None:
        return NOT_AVAILABLE

    return f"{rate:.{decimals}%}"


def show_metrics(items: list[tuple[str, str]], per_row: int = 4) -> None:
    """Render label/value pairs as bordered metric cards."""

    for start in range(0, len(items), per_row):
        columns = st.columns(per_row)

        for column, (label, value) in zip(columns, items[start:start + per_row]):
            with column:
                with st.container(border=True):
                    st.metric(label, value)


# ----------------------------------------------------------------------
# Engine calls
# ----------------------------------------------------------------------
def calculate_chit_irr(net_cash_flows: list[float]) -> tuple[float | None, float | None]:
    """
    Get the monthly IRR and effective annual rate from the engine.

    Mirrors main.py: when the engine raises ValueError (no IRR exists),
    both values are None and the UI shows N/A.
    """

    try:
        monthly_irr = calculate_monthly_irr(net_cash_flows)
    except ValueError:
        return None, None

    return monthly_irr, annualize_monthly_rate(monthly_irr)


def build_cash_flow_table(cash_flows, lifting_month: int):
    """Build the month-by-month table from the engine's cash flows."""

    money_columns = [
        "Gross Installment",
        "Dividend",
        "Prize Received",
        "Net Cash Flow",
    ]

    table = pd.DataFrame(
        [
            {
                "Month": cash_flow.month,
                "Gross Installment": cash_flow.gross_installment,
                "Dividend": cash_flow.dividend,
                "Prize Received": cash_flow.prize_received,
                "Net Cash Flow": cash_flow.net_cash_flow,
            }
            for cash_flow in cash_flows
        ]
    )

    def highlight_lifting_month(row):
        style = LIFTING_ROW_STYLE if row["Month"] == lifting_month else ""
        return [style] * len(row)

    return (
        table.style
        .format({column: format_inr for column in money_columns})
        .apply(highlight_lifting_month, axis=1)
    )


# ----------------------------------------------------------------------
# Page sections
# ----------------------------------------------------------------------
def render_chit_inputs() -> int:
    """Show the fixed chit details and return the selected lifting month."""

    st.subheader("Chit Inputs")

    show_metrics(
        [
            ("Chit Value", format_inr(CHIT_VALUE)),
            ("Duration", f"{DURATION_MONTHS} months"),
        ],
        per_row=2,
    )
    st.caption("Chit value and duration are fixed for this demo.")

    month_of_lifting = st.slider(
        "Month of Lifting",
        min_value=1,
        max_value=DURATION_MONTHS,
        value=DEFAULT_LIFTING_MONTH,
        step=1,
        format="Month %d",
    )

    return int(month_of_lifting)


def render_selected_auction(auction) -> None:
    st.subheader("Selected Auction Details")

    with st.container(border=True, key="selected-auction"):
        st.markdown(f"**Auction month {auction.month}**")
        st.caption(
            "These values are read from the auction schedule for the "
            "selected lifting month. They are not entered manually."
        )

        month_column, bid_column, dividend_column, prize_column = st.columns(4)
        month_column.metric("Auction Number / Month", str(auction.month))
        bid_column.metric("Bid Amount", format_inr(auction.bid_amount))
        dividend_column.metric("Dividend", format_inr(auction.dividend))
        prize_column.metric("Prize Money", format_inr(auction.prize_money))


def render_chit_calculation(chit_result, auction) -> None:
    st.subheader("Chit Calculation")

    show_metrics(
        [
            ("Monthly Installment", format_inr(chit_result.monthly_installment)),
            ("Bid Amount", format_inr(chit_result.bid_amount)),
            ("Dividend", format_inr(auction.dividend)),
            ("Prize Amount", format_inr(chit_result.prize_amount)),
            ("Net Installment", format_inr(chit_result.net_installment)),
        ],
        per_row=5,
    )


def render_borrowing_cost(borrowing_cost) -> None:
    st.subheader("Borrowing Cost")

    show_metrics(
        [
            ("Amount Received", format_inr(borrowing_cost.amount_received)),
            ("Total Installments", format_inr(borrowing_cost.total_installments)),
            ("Total Dividends", format_inr(borrowing_cost.total_dividends)),
            ("Net Contribution", format_inr(borrowing_cost.net_contribution)),
            ("Net Cost", format_inr(borrowing_cost.net_cost)),
            ("Basic Cost Rate", format_rate(borrowing_cost.basic_cost_rate)),
        ],
        per_row=3,
    )
    st.caption(
        "Basic cost rate is net cost divided by amount received. "
        "It ignores payment timing, so it is not the same as the "
        "effective rate (IRR) shown below."
    )


def render_loan_inputs(month_of_lifting: int, duration_months: int) -> tuple[float, int]:
    st.subheader("Personal Loan Comparison")

    rate_column, fee_column = st.columns(2)

    with rate_column:
        annual_rate_percent = st.number_input(
            "Personal Loan Annual Interest Rate (%)",
            min_value=0.0,
            value=DEFAULT_LOAN_RATE_PERCENT,
            step=0.25,
            format="%.2f",
        )

    with fee_column:
        processing_fee = st.number_input(
            "Processing Fee (₹)",
            min_value=0,
            value=DEFAULT_PROCESSING_FEE,
            step=500,
        )

    st.caption(
        f"Loan principal is the month {month_of_lifting} prize amount. "
        f"Loan tenure matches the chit duration ({duration_months} months)."
    )

    return annual_rate_percent, int(processing_fee)


def render_loan_results(comparison) -> None:
    show_metrics(
        [
            ("Loan Principal", format_inr(comparison.loan_principal)),
            ("Loan Nominal Annual Rate", format_rate(comparison.loan_annual_rate)),
            (
                "Loan Effective Annual Rate",
                format_rate(comparison.loan_effective_annual_rate),
            ),
            ("Monthly EMI", format_inr(comparison.loan_monthly_emi)),
            ("Total Interest", format_inr(comparison.loan_total_interest)),
            ("Processing Fee", format_inr(comparison.loan_processing_fee)),
            ("Total Loan Cost", format_inr(comparison.loan_total_cost)),
        ],
        per_row=4,
    )


def render_effective_rate(monthly_irr, annual_rate, comparison) -> None:
    st.subheader("Chit Effective Rate")

    show_metrics(
        [
            ("Monthly IRR", format_rate(monthly_irr, decimals=4)),
            ("Effective Annual Rate", format_rate(annual_rate)),
        ],
        per_row=2,
    )

    if monthly_irr is None:
        st.info(
            "No single IRR exists for this chit's cash flows, "
            "so the rate is shown as N/A."
        )

    st.markdown("**Rate comparison**")

    show_metrics(
        [
            (
                "Chit Effective Annual Rate",
                format_rate(comparison.chit_summary.effective_annual_rate),
            ),
            (
                "Personal Loan Effective Annual Rate",
                format_rate(comparison.loan_effective_annual_rate),
            ),
            ("Rate Difference", format_rate(comparison.rate_difference)),
        ],
        per_row=3,
    )


def render_cash_flow_table(cash_flows, month_of_lifting: int) -> None:
    st.subheader("Cash Flow Table")
    st.caption(
        "Month-by-month timeline generated from the auction schedule. "
        f"The lifting month (month {month_of_lifting}) is highlighted."
    )

    row_height = 35
    st.dataframe(
        build_cash_flow_table(cash_flows, month_of_lifting),
        hide_index=True,
        height=row_height * (len(cash_flows) + 1) + 3,
    )


def render_savings_section() -> None:
    st.divider()
    st.subheader("Savings Chit Scheme")
    st.caption("A separate calculation, independent of the borrowing analysis above.")

    show_metrics(
        [
            ("Savings Chit Value", format_inr(SAVINGS_CHIT_VALUE)),
            ("Savings Duration", f"{SAVINGS_DURATION_MONTHS} months"),
        ],
        per_row=2,
    )

    dividend_column, payout_column = st.columns(2)

    with dividend_column:
        fixed_dividend = st.number_input(
            "Fixed Monthly Dividend (₹)",
            min_value=0,
            value=DEFAULT_SAVINGS_FIXED_DIVIDEND,
            step=500,
        )

    with payout_column:
        maturity_payout = st.number_input(
            "Maturity Payout (₹)",
            min_value=0,
            value=DEFAULT_SAVINGS_MATURITY_PAYOUT,
            step=10_000,
        )

    try:
        savings_input = SavingsInput(
            chit_value=SAVINGS_CHIT_VALUE,
            duration_months=SAVINGS_DURATION_MONTHS,
            fixed_dividend=fixed_dividend,
            maturity_payout=maturity_payout,
        )
    except ValueError as error:
        st.error(f"Check the savings inputs: {error}")
        return

    savings_calculation = calculate_savings(savings_input)

    savings_cash_flows = generate_savings_cash_flows(
        savings_input,
        savings_calculation,
    )

    savings_net_cash_flows = [
        cash_flow.net_cash_flow
        for cash_flow in savings_cash_flows
    ]

    try:
        savings_monthly_irr, savings_annual_return = calculate_savings_return(
            savings_net_cash_flows
        )
    except ValueError:
        savings_monthly_irr, savings_annual_return = None, None

    show_metrics(
        [
            ("Monthly Installment", format_inr(savings_calculation.monthly_installment)),
            (
                "Total Gross Contribution",
                format_inr(savings_calculation.total_gross_contribution),
            ),
            (
                "Total Dividends Received",
                format_inr(savings_calculation.total_dividends),
            ),
            (
                "Total Net Contribution",
                format_inr(savings_calculation.total_net_contribution),
            ),
            ("Maturity Payout", format_inr(savings_calculation.maturity_payout)),
            ("Savings Monthly IRR", format_rate(savings_monthly_irr, decimals=4)),
            (
                "Savings Effective Annual Return",
                format_rate(savings_annual_return),
            ),
        ],
        per_row=4,
    )

    if savings_monthly_irr is None:
        st.info(
            "No single IRR exists for these savings cash flows, "
            "so the return is shown as N/A."
        )


# ----------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="MyPaisaa Chit Calculator",
        page_icon="₹",
        layout="wide",
    )
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    st.title("MyPaisaa Chit Calculator")
    st.caption("Chit borrowing and savings analysis")

    month_of_lifting = render_chit_inputs()

    try:
        # Chit input -> auction values -> chit calculation
        chit_input = ChitInput(
            chit_value=CHIT_VALUE,
            duration_months=DURATION_MONTHS,
            month_of_lifting=month_of_lifting,
        )
        auction = get_auction_result(chit_input.month_of_lifting)
        chit_result = calculate_chit(chit_input)

        # Borrowing cost and cash-flow timeline
        borrowing_cost = calculate_borrowing_cost(chit_input, chit_result)
        cash_flows = generate_cash_flows(chit_input, chit_result)
    except ValueError as error:
        st.error(f"Check the chit inputs: {error}")
        st.stop()

    net_cash_flows = [cash_flow.net_cash_flow for cash_flow in cash_flows]
    monthly_irr, annual_rate = calculate_chit_irr(net_cash_flows)

    render_selected_auction(auction)
    render_chit_calculation(chit_result, auction)
    render_borrowing_cost(borrowing_cost)

    annual_rate_percent, processing_fee = render_loan_inputs(
        month_of_lifting,
        chit_input.duration_months,
    )

    # Personal loan -> chit summary -> comparison
    loan_input = LoanInput(
        principal=chit_result.prize_amount,
        annual_interest_rate=annual_rate_percent / 100,
        tenure_months=chit_input.duration_months,
        processing_fee=processing_fee,
    )
    loan_result = calculate_loan(loan_input)

    chit_summary = calculate_chit_summary(
        chit_calculation=chit_result,
        cash_flows=cash_flows,
        effective_annual_rate=annual_rate,
    )
    comparison = compare_chit_and_loan(
        chit_summary=chit_summary,
        loan_input=loan_input,
        loan_calculation=loan_result,
    )

    render_loan_results(comparison)
    render_effective_rate(monthly_irr, annual_rate, comparison)
    render_cash_flow_table(cash_flows, month_of_lifting)
    render_savings_section()


if __name__ == "__main__":
    main()