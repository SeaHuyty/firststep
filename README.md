# WealthPilot AI

Prototype of an AI wealth advisor: it learns a client's situation, assesses risk, proposes a portfolio
allocation, compares products, and explains the recommendation with cited, trusted sources.

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
  `stocks.py` screens individual stocks from the S&P 500 (`server/app/data/sp500.csv`) on live price
  history for the client's risk level, at most two per sector. Individual stocks are capped at 20% of
  the stocks bucket (a satellite next to the ETFs). The shortlist is suggested by default, like the ETFs, and the client can remove or add any; the advisor is told to propose only from it.
- `server/app/ai/` the LLM layer (pydantic-ai): streamed explanation with citations, and a tool-using
  advisor that can update the profile, *propose* allocation changes and product picks (always clamped by
  the guardrails, applied only when the user clicks Apply), and switch pages.
- `client/src/` the three-step UI (info, analysis, one combined plan page) plus the advisor chat card.

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

## Tests

```bash
cd server && python -m pytest -q   # domain logic, API, and the advisor's tool path (scripted fake LLM)
cd client && npm run lint && npm run build
```
