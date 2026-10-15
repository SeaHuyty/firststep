# WealthPilot AI

Prototype of an AI wealth advisor: it learns a client's situation, assesses risk, proposes a portfolio
allocation, compares products, and explains the recommendation with cited, trusted sources.

> Educational prototype. Not financial advice. Product fees and minimums are illustrative.

## Layout

```
client/   Next.js (React, Tailwind): UI only
server/   FastAPI (Python): all finance logic + the AI
```

The browser only talks to the client origin. `client/next.config.ts` proxies `/api/*` to the server
(`API_URL`, default `http://127.0.0.1:8000`), so there is no CORS setup.

**Design rule:** deterministic code decides every number; the AI only explains and proposes.

- `server/app/domain/` pure logic: default allocation, hard guardrails (stock caps, minimum emergency
  fund), analysis, projections, product catalog, curated sources.
- `server/app/ai/` the LLM layer (pydantic-ai): streamed explanation with citations, and a tool-using
  advisor that can update the profile, *propose* allocation changes and product picks (always clamped by
  the guardrails, applied only when the user clicks Apply), and switch pages.
- `client/src/` the five-step UI plus the advisor side panel.

## Run

Needs Node 20+ and Python 3.11+.

```bash
# server
cd server
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # add an AI key (see below)
python -m uvicorn app.main:app --reload --port 8000

# client (another terminal)
cd client
npm install
npm run dev                   # http://localhost:3000
```

Shortcuts from the repo root: `npm run dev:server`, `npm run dev:client`, `npm run test:server`.

### AI key

Set **one** in `server/.env`:

- `GOOGLE_GENERATIVE_AI_API_KEY`: Gemini, has a free tier (https://aistudio.google.com/apikey)
- `ANTHROPIC_API_KEY`: Claude (used instead if both are set)

Without a key the app still runs: the explanation falls back to canned text and the advisor chat is
disabled (use the form). Model names can be overridden in `.env` (see `.env.example`).

## Live product data

`server/app/market/` pulls ETF data from Yahoo Finance through the free, unofficial `yfinance` library
(no key). Returns, volatility and drawdown are computed from dividend-adjusted daily prices; price,
expense ratio and yield come from Yahoo's fund summary. The snapshot is cached (30 min), warmed at server
start, and refreshed in the background; if Yahoo is down or blocks us, the UI falls back to the static
catalog figures. Savings accounts and money market funds have no listing, so they have no live figures.
The advisor sees the same numbers in its prompt and is told to quote them as given. Data may be delayed
and is not investment advice; being unofficial, the source can break without notice. Settings:
`MARKET_ENABLED`, `MARKET_TTL_SECONDS`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/catalog` | labels, buckets, products (with region), sources |
| GET | `/api/market` | live product metrics (price, fee, returns, volatility), keyed by ticker |
| POST | `/api/plan` | default allocation, limits, analysis for a profile |
| POST | `/api/allocation/validate` | check a proposed allocation against the guardrails |
| POST | `/api/projection` | what-if projection (3 scenarios) |
| POST | `/api/explain` | streamed, cited explanation of an allocation |
| POST | `/api/chat` | advisor turn: reply + actions for the UI |

## Tests

```bash
cd server && python -m pytest -q   # domain logic, API, and the advisor's tool path (scripted fake LLM)
cd client && npm run lint && npm run build
```
