# SENTINEL — Insider Trader Detection on Polymarket

## What Is This Assignment About?

This project builds a pipeline to detect insider trading activity on [Polymarket](https://polymarket.com), a decentralized prediction market platform. Insider traders on prediction markets are wallets that place large, well-timed bets on specific outcomes shortly before resolution — suggesting access to non-public information.

SENTINEL ingests on-chain trade data, enriches each wallet with blockchain history, and scores every trade using a five-factor model. Trades scoring above a threshold are flagged as suspicious or insider and surfaced via a real-time alert stream.

**Pipeline:** Ingest trades → Enrich wallet profiles → Score with 5-factor model → Alert on suspicious activity

**Tech stack:** Python FastAPI + Celery (backend), MongoDB + Redis (data/queue), React 18 + Vite (frontend), Docker Compose (infra).

---

## Installation

### Prerequisites

- Docker + Docker Compose
- Python 3.11+ (for local dev)
- Node.js 18+ (for frontend local dev)

### Environment Setup

The required API keys and the enrollment variables are already provided by the user. You may not need to paste or configure your own API keys here. 

### Option 1 — Docker (Recommended & Verified)

Starts MongoDB, Redis, the FastAPI backend, and the Celery worker:

```bash
docker-compose up -d
```

Verify all external API connections are healthy:

```bash
cd backend && python tester.py
```

- API docs: http://localhost:8000/docs
- Redis UI: http://localhost:5540

### Option 2 — Local Development

**Backend:**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In a second terminal — Celery worker for background scoring jobs
celery -A app.tasks.celery_app worker --loglevel=info
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
# Runs at http://localhost:5173
```

---

## Testing the Application

Enter any of the conditions that are mentioned below in the frontend through the search bar, and then you can hit run and check if the application works or not. 

```md
# Sample Condition IDs

- us-iran-nuclear-deal-by-april-30 : 
    0xd08544f6162283dc8d0a82f16362aab837a8537379df9bbe604960eec9cd4618
- will-donald-trump-win-the-2028-republican-presidential-nomination : 
    0x895e01dbf3e6a33cd9a44ca0f8cdb5df1bd2b0b6ebed5300d28f8da7145145e4
- will-mario-vizcarra-finish-in-second-place-in-the-first-round-of-the-2026-peruvian-presidential-election : 
    0x0b17fc639ecea1086ef07ba6f6770af882fa245b94a13d7cb4ab04f87df5a09d
```
Once the stack is running, pick any condition ID from the list below and trigger ingestion via the API. The backend will fetch trades, enrich wallets, score everything, and surface any flagged trades.

```bash
# Trigger ingestion for a market
curl "http://localhost:8000/api/ingest?q={CONDITION_ID}"

# Poll ingestion status
curl "http://localhost:8000/api/ingest/{CONDITION_ID}/status"

# View scored trades for the market
curl "http://localhost:8000/api/markets/{CONDITION_ID}/trades"
```

Or paste the condition ID directly into the search bar on the frontend at http://localhost:5173.

### Sample Condition IDs

<!-- Paste condition IDs below, one per line -->

---

## Scoring Methodology

Each trade receives a composite insider likelihood score between **0.0 and 1.0**, calculated as a weighted sum of five behavioral signals:

| Factor | Weight | Why It Signals Insider Activity |
|---|---|---|
| **Entry Timing** | 30% | Insiders buy close to market resolution, not early in the market's life |
| **Wallet Age** | 25% | Wallets created days before the trade are likely purpose-built for a single insider bet |
| **Market Count** | 20% | Insiders target 1–3 specific markets; legitimate traders diversify across many |
| **Trade Size** | 15% | Insiders commit large capital decisively; small trades under $5,000 USDC are excluded |
| **Concentration** | 10% | Insiders put the majority of their portfolio into one outcome |

**Classification thresholds:**
- Score ≥ 0.90 → flagged as **insider**
- Score ≥ 0.80 → flagged as **suspicious**
- Score < 0.80 (or trade < $5,000 USDC) → **clean**

---

## APIs Used

| API | Purpose |
|---|---|
| **Polymarket Gamma API** | Market metadata — titles, resolution dates, condition IDs |
| **Polymarket CLOB** | Real-time order book and trade fills |
| **The Graph** | Historical `OrderFilled` events indexed from the Polygon chain (GraphQL subgraph) |
| **Etherscan v2 API** | Wallet token transfer history on Polygon — used to determine wallet age from first USDC.e deposit |
| **Polygon RPC (Alchemy)** | Raw blockchain data and WebSocket subscription for live trade events |

The Graph is the primary data source for historical trades because querying raw blockchain events directly would be too slow and rate-limited. Etherscan v2 is used exclusively for wallet age calculation — specifically, finding the timestamp of a wallet's first USDC.e deposit on Polygon, which is the most reliable proxy for when the wallet was "activated" for prediction market activity.
