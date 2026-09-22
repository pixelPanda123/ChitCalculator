import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ChevronDown, Info, Landmark, PiggyBank, Sparkles } from "lucide-react";
import { useState, type CSSProperties } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { fetchChit, fetchConfig, fetchSavings, type ApiConfig } from "@/lib/api";
import { formatInr, formatRate } from "@/lib/format";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MyPaisaa Chit Calculator" },
      {
        name: "description",
        content:
          "Understand your chit borrowing cost, expected returns, and personal loan comparison.",
      },
      { property: "og:title", content: "MyPaisaa Chit Calculator" },
      {
        property: "og:description",
        content: "A clear calculator for chit borrowing costs, returns, and loan comparisons.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Metric({
  label,
  value,
  featured = false,
}: {
  label: string;
  value: string;
  featured?: boolean;
}) {
  return (
    <div className={featured ? "metric metric-featured" : "metric"}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  copy,
}: {
  eyebrow: string;
  title: string;
  copy?: string;
}) {
  return (
    <header className="section-heading">
      <p>{eyebrow}</p>
      <h2>{title}</h2>
      {copy ? <span>{copy}</span> : null}
    </header>
  );
}

/** Shown while the engine is being contacted for the first time. */
function LoadingScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <p className="text-sm text-muted-foreground">Loading calculator…</p>
    </main>
  );
}

/**
 * Shown when the engine cannot be reached. The most common cause is that
 * api.py is not running, so the message says exactly how to start it.
 */
function EngineDownScreen({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold text-foreground">Calculation engine unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        <p className="mt-4 text-sm text-muted-foreground">
          Start it from the project root with{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">python api.py</code>,
          then try again.
        </p>
        <button
          onClick={onRetry}
          className="mt-6 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Try again
        </button>
      </div>
    </main>
  );
}

function Index() {
  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
    staleTime: Infinity,
    retry: false,
  });

  if (configQuery.isPending) {
    return <LoadingScreen />;
  }

  if (configQuery.isError) {
    return (
      <EngineDownScreen
        message={configQuery.error.message}
        onRetry={() => void configQuery.refetch()}
      />
    );
  }

  return <Calculator config={configQuery.data} />;
}

function Calculator({ config }: { config: ApiConfig }) {
  const [liftingMonth, setLiftingMonth] = useState(config.defaultLiftingMonth);
  const [loanRate, setLoanRate] = useState(config.defaultLoanRatePercent);
  const [processingFee, setProcessingFee] = useState(config.defaultProcessingFee);
  const [savingsDividend, setSavingsDividend] = useState(config.savings.defaultFixedDividend);
  const [maturityPayout, setMaturityPayout] = useState(config.savings.defaultMaturityPayout);
  const [timelineOpen, setTimelineOpen] = useState(false);

  // Typed fields settle before hitting the engine; the slider does not,
  // so dragging stays responsive.
  const debouncedLoanRate = useDebouncedValue(loanRate);
  const debouncedProcessingFee = useDebouncedValue(processingFee);
  const debouncedDividend = useDebouncedValue(savingsDividend);
  const debouncedPayout = useDebouncedValue(maturityPayout);

  const chitQuery = useQuery({
    queryKey: ["chit", liftingMonth, debouncedLoanRate, debouncedProcessingFee],
    queryFn: () => fetchChit(liftingMonth, debouncedLoanRate, debouncedProcessingFee),
    placeholderData: keepPreviousData,
    retry: false,
  });

  const savingsQuery = useQuery({
    queryKey: ["savings", debouncedDividend, debouncedPayout],
    queryFn: () => fetchSavings(debouncedDividend, debouncedPayout),
    placeholderData: keepPreviousData,
    retry: false,
  });

  const result = chitQuery.data;
  const savings = savingsQuery.data;

  // Every value below is read straight from the engine's response.
  const placeholder = "—";
  const money = (value: number | undefined) =>
    value === undefined ? placeholder : formatInr(value);
  const rate = (value: number | null | undefined, decimals = 2) =>
    value === undefined ? placeholder : formatRate(value, decimals);

  const hasIrr = result?.rates.monthlyIrr !== null && result?.rates.monthlyIrr !== undefined;

  // Drives the orange track fill in styles.css. 0 at the first month, 1 at the last.
  const sliderProgress =
    config.durationMonths > 1 ? (liftingMonth - 1) / (config.durationMonths - 1) : 0;

  return (
    <TooltipProvider>
      <main className="min-h-screen bg-background text-foreground">
        <nav className="topbar">
          <div className="page-shell topbar-inner">
            <a href="#top" className="brand" aria-label="MyPaisaa home">
              <span className="brand-mark">
                <span />
              </span>
              <span>
                <strong>my</strong>Paisaa
              </span>
            </a>
            <span className="topbar-label">Chit Calculator</span>
          </div>
        </nav>

        <section id="top" className="hero-band">
          <div className="page-shell hero-layout">
            <div>
              <p className="eyebrow">Plan with clarity</p>
              <h1>
                MyPaisaa Chit <span>Calculator</span>
              </h1>
              <p className="hero-copy">
                Understand your chit borrowing cost, expected returns, and personal loan comparison.
              </p>
            </div>
            <div className="hero-visual" aria-hidden="true">
              <div className="hero-line" />
              <span>
                <PiggyBank />
              </span>
              <span>
                <Landmark />
              </span>
              <span>
                <Sparkles />
              </span>
            </div>
          </div>
        </section>

        <div className="page-shell page-content">
          {chitQuery.isError ? (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive"
            >
              {chitQuery.error.message}
            </p>
          ) : null}

          <section className="calculator-grid">
            <div className="input-stack">
              <div className="panel input-panel">
                <SectionHeading
                  eyebrow="Chit inputs"
                  title="Your chit plan"
                  copy="Value and duration are fixed for this demo."
                />
                <div className="fixed-inputs">
                  <Metric label="Chit Value" value={formatInr(config.chitValue)} />
                  <Metric label="Duration" value={`${config.durationMonths} months`} />
                </div>
                <div className="slider-block">
                  <div className="slider-heading">
                    <label htmlFor="lifting-month">Month of Lifting</label>
                    <strong>Month {liftingMonth}</strong>
                  </div>
                  <input
                    id="lifting-month"
                    type="range"
                    min={1}
                    max={config.durationMonths}
                    value={liftingMonth}
                    onChange={(event) => setLiftingMonth(Number(event.target.value))}
                    style={{ "--slider-progress": sliderProgress } as CSSProperties}
                  />
                  <div className="slider-scale">
                    <span>Month 1</span>
                    <span>Month {config.durationMonths}</span>
                  </div>
                  <p>Move the slider to update every calculation below.</p>
                </div>
              </div>

              <div className="panel loan-input-panel">
                <SectionHeading eyebrow="Comparison baseline" title="Personal loan inputs" />
                <label>
                  Personal Loan Annual Interest Rate (%)
                  <Input
                    type="number"
                    min="0"
                    step="0.25"
                    value={loanRate}
                    onChange={(event) => setLoanRate(Number(event.target.value))}
                  />
                </label>
                <label>
                  Processing Fee (₹)
                  <Input
                    type="number"
                    min="0"
                    step="500"
                    value={processingFee}
                    onChange={(event) => setProcessingFee(Number(event.target.value))}
                  />
                </label>
                <p>
                  Principal uses the month {liftingMonth} prize amount over {config.durationMonths}{" "}
                  months.
                </p>
              </div>
            </div>

            <div className="results-stack">
              <section className="selected-auction">
                <div className="auction-month">
                  <span>Selected Auction</span>
                  <strong>{liftingMonth}</strong>
                  <small>Month</small>
                </div>
                <div className="auction-metrics">
                  <Metric label="Bid Amount" value={money(result?.auction.bidAmount)} />
                  <Metric label="Dividend" value={money(result?.auction.dividend)} />
                  <Metric label="Prize Money" value={money(result?.auction.prizeMoney)} featured />
                </div>
              </section>

              <section className="panel">
                <SectionHeading eyebrow="Calculation" title="Chit calculation" />
                <div className="metric-grid five">
                  <Metric
                    label="Monthly Installment"
                    value={money(result?.chit.monthlyInstallment)}
                  />
                  <Metric label="Bid Amount" value={money(result?.chit.bidAmount)} />
                  <Metric label="Dividend" value={money(result?.chit.dividend)} />
                  <Metric label="Prize Amount" value={money(result?.chit.prizeAmount)} featured />
                  <Metric label="Net Installment" value={money(result?.chit.netInstallment)} />
                </div>
              </section>
            </div>
          </section>

          <section className="section-band borrowing-section">
            <SectionHeading
              eyebrow="Cost breakdown"
              title="Borrowing Cost"
              copy="See the full contribution and cost picture for your selected auction."
            />
            <div className="metric-grid borrowing-grid">
              <Metric label="Amount Received" value={money(result?.borrowing.amountReceived)} />
              <Metric
                label="Total Installments"
                value={money(result?.borrowing.totalInstallments)}
              />
              <Metric label="Total Dividends" value={money(result?.borrowing.totalDividends)} />
              <Metric label="Net Contribution" value={money(result?.borrowing.netContribution)} />
              <Metric label="Net Cost" value={money(result?.borrowing.netCost)} featured />
              <div className="metric metric-featured">
                <p className="metric-label tooltip-label">
                  Basic Cost Rate
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button aria-label="About basic cost rate">
                        <Info />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Basic cost rate is net cost divided by amount received. It does not account
                      for the timing of payments.
                    </TooltipContent>
                  </Tooltip>
                </p>
                <p className="metric-value">{rate(result?.borrowing.basicCostRate)}</p>
              </div>
            </div>
          </section>

          <section className="section-band comparison-section">
            <SectionHeading
              eyebrow="Side-by-side"
              title="Personal Loan Comparison"
              copy="The same amount and tenure, shown clearly across both options."
            />
            <div className="comparison-grid">
              <article className="comparison-card chit-card">
                <div className="comparison-title">
                  <span className="comparison-icon">
                    <span />
                  </span>
                  <div>
                    <small>Option 01</small>
                    <h3>MyPaisaa Chit</h3>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt>Amount Received</dt>
                    <dd>{money(result?.borrowing.amountReceived)}</dd>
                  </div>
                  <div>
                    <dt>Net Cost</dt>
                    <dd>{money(result?.borrowing.netCost)}</dd>
                  </div>
                  <div>
                    <dt>Basic Cost Rate</dt>
                    <dd>{rate(result?.borrowing.basicCostRate)}</dd>
                  </div>
                  <div>
                    <dt>Effective Annual Rate</dt>
                    <dd>{rate(result?.comparison.chitEffectiveAnnualRate)}</dd>
                  </div>
                </dl>
              </article>
              <div className="versus">VS</div>
              <article className="comparison-card loan-card">
                <div className="comparison-title">
                  <Landmark />
                  <div>
                    <small>Option 02</small>
                    <h3>Personal Loan</h3>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt>Loan Principal</dt>
                    <dd>{money(result?.loan.principal)}</dd>
                  </div>
                  <div>
                    <dt>Loan Nominal Annual Rate</dt>
                    <dd>{rate(result?.loan.nominalAnnualRate)}</dd>
                  </div>
                  <div>
                    <dt>Loan Effective Annual Rate</dt>
                    <dd>{rate(result?.loan.effectiveAnnualRate)}</dd>
                  </div>
                  <div>
                    <dt>Monthly EMI</dt>
                    <dd>{money(result?.loan.monthlyEmi)}</dd>
                  </div>
                  <div>
                    <dt>Total Interest</dt>
                    <dd>{money(result?.loan.totalInterest)}</dd>
                  </div>
                  <div>
                    <dt>Processing Fee</dt>
                    <dd>{money(result?.loan.processingFee)}</dd>
                  </div>
                  <div className="total-row">
                    <dt>Total Loan Cost</dt>
                    <dd>{money(result?.loan.totalLoanCost)}</dd>
                  </div>
                </dl>
              </article>
            </div>
          </section>

          <section className="section-band rate-section">
            <SectionHeading eyebrow="Time-adjusted view" title="Chit Effective Rate" />
            <div className="rate-layout">
              <div className="rate-primary">
                <Metric label="Monthly IRR" value={rate(result?.rates.monthlyIrr, 4)} />
                <Metric label="Effective Annual Rate" value={rate(result?.rates.annualRate)} />
              </div>
              {result && !hasIrr ? (
                <div className="rate-note">
                  <Info />
                  <div>
                    <strong>No single IRR exists for this cash-flow stream.</strong>
                    <p>
                      The calculator keeps unavailable engine results clearly marked rather than
                      estimating a value.
                    </p>
                  </div>
                </div>
              ) : null}
              <div className="rate-compare">
                <Metric
                  label="Chit Effective Annual Rate"
                  value={rate(result?.comparison.chitEffectiveAnnualRate)}
                />
                <Metric
                  label="Personal Loan Effective Annual Rate"
                  value={rate(result?.comparison.loanEffectiveAnnualRate)}
                />
                <Metric label="Rate Difference" value={rate(result?.comparison.rateDifference)} />
              </div>
            </div>
          </section>

          <Collapsible
            open={timelineOpen}
            onOpenChange={setTimelineOpen}
            className="timeline-section"
          >
            <CollapsibleTrigger asChild>
              {/* A plain button, not the shadcn Button: that component's utility
                  classes would override .timeline-trigger's layout. */}
              <button type="button" className="timeline-trigger">
                <span>
                  <small>{config.durationMonths}-month schedule</small>
                  <strong>Cash Flow Timeline</strong>
                  <em>Month {liftingMonth} is highlighted.</em>
                </span>
                <ChevronDown className={timelineOpen ? "rotate-180" : ""} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Month</th>
                      <th>Gross Installment</th>
                      <th>Dividend</th>
                      <th>Prize Received</th>
                      <th>Net Cash Flow</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result?.cashFlows ?? []).map((row) => (
                      <tr
                        key={row.month}
                        className={row.month === liftingMonth ? "selected-row" : ""}
                      >
                        <td>
                          <span>{row.month}</span>
                        </td>
                        <td>{formatInr(row.grossInstallment)}</td>
                        <td>{formatInr(row.dividend)}</td>
                        <td>{formatInr(row.prizeReceived)}</td>
                        <td>{formatInr(row.netCashFlow)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <section className="savings-section">
            <div className="savings-intro">
              <span>
                <PiggyBank />
              </span>
              <p>Separate calculation</p>
              <h2>Savings Chit Scheme</h2>
              <p>
                A distinct {config.savings.durationMonths}-month savings view, independent of the
                borrowing analysis above.
              </p>
              <div className="savings-fixed">
                <strong>{formatInr(config.savings.chitValue)}</strong>
                <span>{config.savings.durationMonths} months</span>
              </div>
            </div>
            <div className="savings-content">
              {savingsQuery.isError ? (
                <p role="alert" className="text-sm text-destructive">
                  {savingsQuery.error.message}
                </p>
              ) : null}
              <div className="savings-inputs">
                <label>
                  Fixed Monthly Dividend (₹)
                  <Input
                    type="number"
                    min="0"
                    step="500"
                    value={savingsDividend}
                    onChange={(event) => setSavingsDividend(Number(event.target.value))}
                  />
                </label>
                <label>
                  Maturity Payout (₹)
                  <Input
                    type="number"
                    min="0"
                    step="10000"
                    value={maturityPayout}
                    onChange={(event) => setMaturityPayout(Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="metric-grid savings-grid">
                <Metric
                  label="Monthly Installment"
                  value={money(savings?.savings.monthlyInstallment)}
                />
                <Metric
                  label="Total Gross Contribution"
                  value={money(savings?.savings.totalGrossContribution)}
                />
                <Metric
                  label="Total Dividends Received"
                  value={money(savings?.savings.totalDividends)}
                />
                <Metric
                  label="Total Net Contribution"
                  value={money(savings?.savings.totalNetContribution)}
                />
                <Metric
                  label="Maturity Payout"
                  value={money(savings?.savings.maturityPayout)}
                  featured
                />
                <Metric label="Savings Monthly IRR" value={rate(savings?.rates.monthlyIrr, 4)} />
                <Metric
                  label="Savings Effective Annual Return"
                  value={rate(savings?.rates.annualReturn)}
                />
              </div>
            </div>
          </section>
        </div>
      </main>
    </TooltipProvider>
  );
}