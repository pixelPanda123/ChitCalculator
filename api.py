"""
HTTP API that exposes the ChitCalculator engine to the React UI.

This file is a transport layer only. Every financial value it returns
comes from the existing calculation engine in ``src/``. There are no
formulas here: the handlers call engine functions, read fields off the
returned dataclasses, and rename them to camelCase for JSON.

Uses only the Python standard library, so it adds no dependencies.

Run with:
    python api.py                 # serves on http://127.0.0.1:8000

Endpoints:
    GET /api/health
    GET /api/config
    GET /api/chit?month=15&loanRatePercent=12&processingFee=1000
    GET /api/savings?fixedDividend=5000&maturityPayout=500000
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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

HOST = "127.0.0.1"
PORT = 8000

# ----------------------------------------------------------------------
# Demo configuration. Chit value and duration are fixed for the demo;
# duration comes from the auction schedule so the UI slider can never
# ask for a month the engine has no data for.
# ----------------------------------------------------------------------
CHIT_VALUE = 500_000
DURATION_MONTHS = len(AUCTION_SCHEDULE)
DEFAULT_LIFTING_MONTH = 15

DEFAULT_LOAN_RATE_PERCENT = 12.0
DEFAULT_PROCESSING_FEE = 1_000

SAVINGS_CHIT_VALUE = 500_000
SAVINGS_DURATION_MONTHS = 20
DEFAULT_SAVINGS_DIVIDEND = 5_000
DEFAULT_SAVINGS_MATURITY_PAYOUT = 500_000


class RequestError(Exception):
    """A bad request from the client, reported as HTTP 400."""


def safe_number(value: float | None) -> float | None:
    """
    Return a JSON-safe number.

    ``json.dumps`` would emit ``Infinity`` or ``NaN`` for non-finite
    floats, which is not valid JSON and would break the UI's parser.
    Those become null instead, which the UI already renders as "N/A".
    """

    if value is None:
        return None

    if not math.isfinite(value):
        return None

    return value


# ----------------------------------------------------------------------
# Query-string parsing
# ----------------------------------------------------------------------
def read_int(query: dict[str, list[str]], name: str, default: int) -> int:
    values = query.get(name)

    if not values:
        return default

    try:
        return int(float(values[0]))
    except ValueError:
        raise RequestError(f"{name} must be a number.") from None


def read_float(query: dict[str, list[str]], name: str, default: float) -> float:
    values = query.get(name)

    if not values:
        return default

    try:
        return float(values[0])
    except ValueError:
        raise RequestError(f"{name} must be a number.") from None


# ----------------------------------------------------------------------
# Engine calls
# ----------------------------------------------------------------------
def chit_rates(net_cash_flows: tuple[float, ...]):
    """
    Return the monthly IRR and effective annual rate from the engine.

    The engine raises ValueError when no single IRR exists, which is a
    real outcome for some lifting months. That becomes (None, None) so
    the UI can show "N/A" without inventing a number.
    """

    try:
        monthly_irr = calculate_monthly_irr(list(net_cash_flows))
    except ValueError:
        return None, None

    return monthly_irr, annualize_monthly_rate(monthly_irr)


@lru_cache(maxsize=512)
def build_chit_payload(
    month_of_lifting: int,
    loan_rate_percent: float,
    processing_fee: float,
) -> dict:
    """Run the full borrowing flow and shape it for the UI."""

    chit_input = ChitInput(
        chit_value=CHIT_VALUE,
        duration_months=DURATION_MONTHS,
        month_of_lifting=month_of_lifting,
    )

    auction = get_auction_result(chit_input.month_of_lifting)
    chit_calculation = calculate_chit(chit_input)
    borrowing_cost = calculate_borrowing_cost(chit_input, chit_calculation)
    cash_flows = generate_cash_flows(chit_input, chit_calculation)

    net_cash_flows = tuple(
        cash_flow.net_cash_flow
        for cash_flow in cash_flows
    )
    monthly_irr, annual_rate = chit_rates(net_cash_flows)

    loan_input = LoanInput(
        principal=chit_calculation.prize_amount,
        annual_interest_rate=loan_rate_percent / 100,
        tenure_months=chit_input.duration_months,
        processing_fee=processing_fee,
    )
    loan_calculation = calculate_loan(loan_input)

    chit_summary = calculate_chit_summary(
        chit_calculation=chit_calculation,
        cash_flows=cash_flows,
        effective_annual_rate=annual_rate,
    )
    comparison = compare_chit_and_loan(
        chit_summary=chit_summary,
        loan_input=loan_input,
        loan_calculation=loan_calculation,
    )

    return {
        "auction": {
            "month": auction.month,
            "bidAmount": auction.bid_amount,
            "dividend": auction.dividend,
            "prizeMoney": auction.prize_money,
        },
        "chit": {
            "monthlyInstallment": chit_calculation.monthly_installment,
            "bidAmount": chit_calculation.bid_amount,
            "dividend": auction.dividend,
            "commissionAmount": chit_calculation.commission_amount,
            "prizeAmount": chit_calculation.prize_amount,
            "netInstallment": chit_calculation.net_installment,
        },
        "borrowing": {
            "amountReceived": borrowing_cost.amount_received,
            "totalInstallments": borrowing_cost.total_installments,
            "totalDividends": borrowing_cost.total_dividends,
            "netContribution": borrowing_cost.net_contribution,
            "netCost": borrowing_cost.net_cost,
            "basicCostRate": safe_number(borrowing_cost.basic_cost_rate),
        },
        "summary": {
            "totalGrossInstallments": chit_summary.total_gross_installments,
            "totalDividends": chit_summary.total_dividends,
            "totalNetContribution": chit_summary.total_net_contribution,
        },
        "rates": {
            "monthlyIrr": safe_number(monthly_irr),
            "annualRate": safe_number(annual_rate),
        },
        "loan": {
            "principal": comparison.loan_principal,
            "nominalAnnualRate": comparison.loan_annual_rate,
            "effectiveAnnualRate": comparison.loan_effective_annual_rate,
            "monthlyEmi": comparison.loan_monthly_emi,
            "totalInterest": comparison.loan_total_interest,
            "processingFee": comparison.loan_processing_fee,
            "totalLoanCost": comparison.loan_total_cost,
            "tenureMonths": loan_input.tenure_months,
        },
        "comparison": {
            "chitEffectiveAnnualRate": safe_number(
                comparison.chit_summary.effective_annual_rate
            ),
            "loanEffectiveAnnualRate": comparison.loan_effective_annual_rate,
            "rateDifference": safe_number(comparison.rate_difference),
        },
        "cashFlows": [
            {
                "month": cash_flow.month,
                "grossInstallment": cash_flow.gross_installment,
                "dividend": cash_flow.dividend,
                "prizeReceived": cash_flow.prize_received,
                "netCashFlow": cash_flow.net_cash_flow,
            }
            for cash_flow in cash_flows
        ],
    }


@lru_cache(maxsize=512)
def build_savings_payload(
    fixed_dividend: float,
    maturity_payout: float,
) -> dict:
    """Run the savings flow and shape it for the UI."""

    savings_input = SavingsInput(
        chit_value=SAVINGS_CHIT_VALUE,
        duration_months=SAVINGS_DURATION_MONTHS,
        fixed_dividend=fixed_dividend,
        maturity_payout=maturity_payout,
    )

    savings_calculation = calculate_savings(savings_input)
    cash_flows = generate_savings_cash_flows(savings_input, savings_calculation)

    net_cash_flows = [
        cash_flow.net_cash_flow
        for cash_flow in cash_flows
    ]

    try:
        monthly_irr, annual_return = calculate_savings_return(net_cash_flows)
    except ValueError:
        monthly_irr, annual_return = None, None

    return {
        "input": {
            "chitValue": savings_input.chit_value,
            "durationMonths": savings_input.duration_months,
            "fixedDividend": savings_input.fixed_dividend,
            "maturityPayout": savings_input.maturity_payout,
        },
        "savings": {
            "monthlyInstallment": savings_calculation.monthly_installment,
            "totalGrossContribution": savings_calculation.total_gross_contribution,
            "totalDividends": savings_calculation.total_dividends,
            "totalNetContribution": savings_calculation.total_net_contribution,
            "maturityPayout": savings_calculation.maturity_payout,
        },
        "rates": {
            "monthlyIrr": safe_number(monthly_irr),
            "annualReturn": safe_number(annual_return),
        },
        "cashFlows": [
            {
                "month": cash_flow.month,
                "grossInstallment": cash_flow.gross_installment,
                "dividend": cash_flow.dividend,
                "maturityPayout": cash_flow.maturity_payout,
                "netCashFlow": cash_flow.net_cash_flow,
            }
            for cash_flow in cash_flows
        ],
    }


def build_config_payload() -> dict:
    """Fixed demo values, so the UI hardcodes nothing."""

    return {
        "chitValue": CHIT_VALUE,
        "durationMonths": DURATION_MONTHS,
        "defaultLiftingMonth": min(DEFAULT_LIFTING_MONTH, DURATION_MONTHS),
        "defaultLoanRatePercent": DEFAULT_LOAN_RATE_PERCENT,
        "defaultProcessingFee": DEFAULT_PROCESSING_FEE,
        "savings": {
            "chitValue": SAVINGS_CHIT_VALUE,
            "durationMonths": SAVINGS_DURATION_MONTHS,
            "defaultFixedDividend": DEFAULT_SAVINGS_DIVIDEND,
            "defaultMaturityPayout": DEFAULT_SAVINGS_MATURITY_PAYOUT,
        },
    }


# ----------------------------------------------------------------------
# Routing
# ----------------------------------------------------------------------
def route(path: str, query: dict[str, list[str]]) -> dict:
    if path == "/api/health":
        return {"status": "ok"}

    if path == "/api/config":
        return build_config_payload()

    if path == "/api/chit":
        month = read_int(query, "month", DEFAULT_LIFTING_MONTH)

        if not 1 <= month <= DURATION_MONTHS:
            raise RequestError(
                f"month must be between 1 and {DURATION_MONTHS}."
            )

        loan_rate_percent = read_float(
            query,
            "loanRatePercent",
            DEFAULT_LOAN_RATE_PERCENT,
        )
        processing_fee = read_float(
            query,
            "processingFee",
            DEFAULT_PROCESSING_FEE,
        )

        if loan_rate_percent < 0:
            raise RequestError("loanRatePercent cannot be negative.")

        if processing_fee < 0:
            raise RequestError("processingFee cannot be negative.")

        return build_chit_payload(month, loan_rate_percent, processing_fee)

    if path == "/api/savings":
        fixed_dividend = read_float(
            query,
            "fixedDividend",
            DEFAULT_SAVINGS_DIVIDEND,
        )
        maturity_payout = read_float(
            query,
            "maturityPayout",
            DEFAULT_SAVINGS_MATURITY_PAYOUT,
        )

        if fixed_dividend < 0:
            raise RequestError("fixedDividend cannot be negative.")

        if maturity_payout < 0:
            raise RequestError("maturityPayout cannot be negative.")

        return build_savings_payload(fixed_dividend, maturity_payout)

    raise KeyError(path)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "ChitCalculatorApi/1.0"
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # The UI is served by Vite on another port during development.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            self._send(200, route(parsed.path, query))
        except KeyError:
            self._send(404, {"error": f"Unknown endpoint: {parsed.path}"})
        except RequestError as error:
            self._send(400, {"error": str(error)})
        except ValueError as error:
            # Raised by the engine's own input validation.
            self._send(400, {"error": str(error)})

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # One compact line per request instead of the stdlib's default.
        print(f"[api] {self.address_string()} {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"ChitCalculator API on http://{HOST}:{PORT}")
    print("Endpoints: /api/health  /api/config  /api/chit  /api/savings")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
