# MyPaisaa Chit Calculator — UI

React frontend for the ChitCalculator Python engine.

This is a presentation layer only. It contains no financial formulas: it
reads values from the Python engine over HTTP and formats them. If a
number looks wrong, the fix belongs in `src/` of the Python project, not
here.

## Layout

The UI expects to sit inside the Python project:

```
ChitCalculator/
├── src/                  # calculation engine (unchanged)
├── tests/
├── main.py               # CLI (unchanged)
├── api.py                # HTTP wrapper around the engine
└── ui/                   # this folder
    ├── src/
    │   ├── lib/api.ts    # typed calls to api.py
    │   ├── lib/format.ts # rupee and percentage formatting
    │   └── routes/index.tsx
    └── package.json
```

`api.py` and this folder are the only new pieces. The engine, the CLI and
the tests are untouched.

## Running it

Two processes: the Python API and the Vite dev server.

**1. Start the engine API** from the Python project root:

```sh
python api.py
```

It serves on `http://127.0.0.1:8000`. Check it with:

```sh
curl http://127.0.0.1:8000/api/health
```

**2. Start the UI** from this folder:

```sh
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

Requests to `/api` are proxied to the Python process, so the browser sees
one origin and no host is hardcoded in the UI. To point at a different
address, set `API_URL`:

```sh
API_URL=http://127.0.0.1:9000 npm run dev
```

If the UI shows "Calculation engine unavailable", `api.py` is not
running.

## How data flows

```
auction_schedule.py → chit_calculator.py → cash_flow.py → borrowing_cost.py
                                                        → financial_utils.py (IRR)
                                                        → loan_calculator.py
                                                        → comparison.py
                              ↓
                           api.py          (JSON, no math)
                              ↓
                        src/lib/api.ts     (typed fetch)
                              ↓
                     src/routes/index.tsx  (formatting only)
```

Moving the lifting-month slider refetches `/api/chit`; the loan and
savings inputs are debounced so typing does not fire a request per
keystroke.

## Endpoints

| Endpoint       | Returns                                                       |
| -------------- | ------------------------------------------------------------- |
| `/api/health`  | Liveness check                                                 |
| `/api/config`  | Fixed demo values (chit value, duration, defaults)             |
| `/api/chit`    | Auction, chit, borrowing cost, IRR, loan, comparison, cashflow |
| `/api/savings` | Savings calculation, return and cash flows                     |

`/api/chit` takes `month`, `loanRatePercent` and `processingFee`.
`/api/savings` takes `fixedDividend` and `maturityPayout`.

## Rates that come back as N/A

The engine does not always find a single IRR — for some lifting months
the NPV stays negative at every rate. Those fields are `null` in the JSON
and render as "N/A". The UI never substitutes an estimate.

Basic cost rate (net cost ÷ amount received) is a separate, simpler
figure that always exists. It ignores payment timing, so it is not
interchangeable with the IRR.

## Scripts

| Command           | Does                       |
| ----------------- | -------------------------- |
| `npm run dev`     | Dev server on port 5173    |
| `npm run build`   | Production build           |
| `npm run preview` | Serve the build            |
| `npm run lint`    | ESLint (Prettier enforced) |
| `npm run format`  | Apply Prettier             |

## Stack

TanStack Start (React 19, TanStack Router), TanStack Query for fetching,
Tailwind CSS v4 with shadcn/ui components, Vite.
