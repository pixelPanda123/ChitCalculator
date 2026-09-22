def validate_cash_flows(cash_flows: list[float]) -> None:
    """Validate that cash flows can be used for IRR calculation."""

    if len(cash_flows) < 2:
        raise ValueError(
            "At least two cash flows are required to calculate IRR."
        )

    has_positive = any(
        cash_flow > 0
        for cash_flow in cash_flows
    )

    has_negative = any(
        cash_flow < 0
        for cash_flow in cash_flows
    )

    if not has_positive or not has_negative:
        raise ValueError(
            "Cash flows must contain both positive and negative values."
        )


def calculate_npv(
    cash_flows: list[float],
    rate: float,
) -> float:
    """Calculate NPV for equally spaced monthly cash flows."""

    if rate <= -1:
        return float("inf")

    return sum(
        cash_flow / (1 + rate) ** period
        for period, cash_flow in enumerate(cash_flows)
    )


def find_irr_roots(
    cash_flows: list[float],
    min_rate: float = -0.9999,
    max_rate: float = 10.0,
    steps: int = 10000,
    tolerance: float = 1e-10,
) -> list[float]:
    """
    Find all IRR roots within the specified rate range.

    The search scans the rate range for NPV sign changes and
    then uses bisection to find each root.
    """

    step = (max_rate - min_rate) / steps

    roots = []

    previous_rate = min_rate
    previous_npv = calculate_npv(
        cash_flows,
        previous_rate,
    )

    for i in range(1, steps + 1):
        current_rate = min_rate + i * step

        current_npv = calculate_npv(
            cash_flows,
            current_rate,
        )

        if abs(previous_npv) < tolerance:
            roots.append(previous_rate)

        elif previous_npv * current_npv < 0:
            lower_rate = previous_rate
            upper_rate = current_rate

            lower_npv = previous_npv
            midpoint_rate = (lower_rate + upper_rate) / 2

            for _ in range(200):
                midpoint_rate = (
                    lower_rate + upper_rate
                ) / 2

                midpoint_npv = calculate_npv(
                    cash_flows,
                    midpoint_rate,
                )

                if abs(midpoint_npv) < tolerance:
                    break

                if lower_npv * midpoint_npv < 0:
                    upper_rate = midpoint_rate
                else:
                    lower_rate = midpoint_rate
                    lower_npv = midpoint_npv

            roots.append(midpoint_rate)

        previous_rate = current_rate
        previous_npv = current_npv

    # Remove duplicate roots caused by scan boundaries.
    unique_roots = []

    for root in roots:
        if not any(
            abs(root - existing_root) < 1e-7
            for existing_root in unique_roots
        ):
            unique_roots.append(root)

    return unique_roots


def calculate_monthly_irr(cash_flows: list[float]) -> float:
    """
    Calculate the monthly IRR.

    If multiple mathematical IRRs exist, the lowest
    non-negative IRR is returned.

    Raises ValueError when no IRR exists. This is a real
    outcome for chits, not just bad input: when payments
    happen both before and after the prize month, the NPV
    can stay below zero at every rate.
    """

    validate_cash_flows(cash_flows)

    roots = find_irr_roots(cash_flows)

    if not roots:
        raise ValueError(
            "Unable to calculate IRR for the provided cash flows."
        )

    positive_roots = [
        root
        for root in roots
        if root >= 0
    ]

    if positive_roots:
        return min(positive_roots)

    return max(roots)


def annualize_monthly_rate(monthly_rate: float) -> float:
    """Convert a monthly effective rate to an effective annual rate."""

    return (1 + monthly_rate) ** 12 - 1


def calculate_effective_annual_rate(
    cash_flows: list[float],
) -> float:
    """Calculate monthly IRR and convert it to an effective annual rate."""

    monthly_irr = calculate_monthly_irr(cash_flows)

    return annualize_monthly_rate(monthly_irr)