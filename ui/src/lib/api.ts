/**
 * Typed access to the Python calculation engine.
 *
 * Every number rendered by this UI comes from these responses. There are
 * no financial formulas in the frontend: api.py calls the engine in
 * src/ and returns the results, and the components only format them.
 *
 * Requests go to /api, which Vite proxies to the Python process during
 * development (see vite.config.ts).
 */

export type ApiConfig = {
  chitValue: number;
  durationMonths: number;
  defaultLiftingMonth: number;
  defaultLoanRatePercent: number;
  defaultProcessingFee: number;
  savings: {
    chitValue: number;
    durationMonths: number;
    defaultFixedDividend: number;
    defaultMaturityPayout: number;
  };
};

export type AuctionDetails = {
  month: number;
  bidAmount: number;
  dividend: number;
  prizeMoney: number;
};

export type CashFlowRow = {
  month: number;
  grossInstallment: number;
  dividend: number;
  prizeReceived: number;
  netCashFlow: number;
};

/** A rate is null when the engine found no single IRR. Render it as "N/A". */
export type ChitResponse = {
  auction: AuctionDetails;
  chit: {
    monthlyInstallment: number;
    bidAmount: number;
    dividend: number;
    commissionAmount: number;
    prizeAmount: number;
    netInstallment: number;
  };
  borrowing: {
    amountReceived: number;
    totalInstallments: number;
    totalDividends: number;
    netContribution: number;
    netCost: number;
    basicCostRate: number | null;
  };
  summary: {
    totalGrossInstallments: number;
    totalDividends: number;
    totalNetContribution: number;
  };
  rates: {
    monthlyIrr: number | null;
    annualRate: number | null;
  };
  loan: {
    principal: number;
    nominalAnnualRate: number;
    effectiveAnnualRate: number;
    monthlyEmi: number;
    totalInterest: number;
    processingFee: number;
    totalLoanCost: number;
    tenureMonths: number;
  };
  comparison: {
    chitEffectiveAnnualRate: number | null;
    loanEffectiveAnnualRate: number;
    rateDifference: number | null;
  };
  cashFlows: CashFlowRow[];
};

export type SavingsResponse = {
  input: {
    chitValue: number;
    durationMonths: number;
    fixedDividend: number;
    maturityPayout: number;
  };
  savings: {
    monthlyInstallment: number;
    totalGrossContribution: number;
    totalDividends: number;
    totalNetContribution: number;
    maturityPayout: number;
  };
  rates: {
    monthlyIrr: number | null;
    annualReturn: number | null;
  };
  cashFlows: {
    month: number;
    grossInstallment: number;
    dividend: number;
    maturityPayout: number;
    netCashFlow: number;
  }[];
};

/** Thrown when the engine rejects the inputs, carrying its message. */
export class ApiError extends Error {}

async function getJson<T>(path: string, params: Record<string, number> = {}): Promise<T> {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    query.set(key, String(value));
  }

  const suffix = query.toString();
  const response = await fetch(suffix ? `${path}?${suffix}` : path, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    // api.py reports engine validation errors as {"error": "..."}.
    const detail = await response
      .json()
      .then((body: { error?: string }) => body.error)
      .catch(() => undefined);

    throw new ApiError(detail ?? `Request failed (${response.status}).`);
  }

  return (await response.json()) as T;
}

export function fetchConfig() {
  return getJson<ApiConfig>("/api/config");
}

export function fetchChit(month: number, loanRatePercent: number, processingFee: number) {
  return getJson<ChitResponse>("/api/chit", { month, loanRatePercent, processingFee });
}

export function fetchSavings(fixedDividend: number, maturityPayout: number) {
  return getJson<SavingsResponse>("/api/savings", { fixedDividend, maturityPayout });
}
