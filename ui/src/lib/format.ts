/**
 * Display formatting only. No calculations live here.
 */

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Format an amount with Indian digit grouping, e.g. ₹4,20,000.00. */
export function formatInr(value: number): string {
  return inrFormatter.format(value);
}

/**
 * Format a rate the engine returned as a decimal fraction.
 *
 * null means the engine could not produce the rate, which happens when
 * no single IRR exists. Those show as "N/A" rather than a guess.
 */
export function formatRate(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) {
    return "N/A";
  }

  return `${(value * 100).toFixed(decimals)}%`;
}
