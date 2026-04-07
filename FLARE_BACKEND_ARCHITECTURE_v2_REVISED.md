# SENTINEL — Insider Trading Detection Platform
## Backend Architecture v2.0 (Revised)

**April 2026**
**Assignment: Fireplace Insider Trading Detection**
**Status: Architecture & Implementation Plan**

---

## 1. Executive Summary

SENTINEL is a real-time insider trading detection system for Polymarket. This revised architecture incorporates deprecation of PolygonScan and migration to Etherscan v2 API for wallet deposit history. The system indexes both historical and live trades, enriches wallet profiles, and scores each trade across 6 factors to identify suspicious insider activity.

### 1.1 Key Changes from v1.0

- **PolygonScan API deprecated** — migrated to Etherscan v2 API for USDC.e deposit history
- **Goldsky subgraph removed** — using The Graph Network exclusively (identical data, simpler setup)
- **Etherscan v2 supports multiple chains** via chainid parameter (Polygon chainid=42161)
- **No API keys required for The Graph**, only for Etherscan v2 (same as old PolygonScan)

---

## 2. Tools & Services Reference

| Service | Purpose | Endpoint | API Key Required | Used In |
|---------|---------|----------|------------------|---------|
| **The Graph Network** | Historical OrderFilled trades | `https://api.thegraph.com/subgraphs/name/polymarket/polymarket` | No | Historical backfill indexer |
| **Etherscan v2 API** | First USDC.e deposit per wallet | `https://api.etherscan.io/v2/api?chainid=42161` | Yes (free) | Deposit indexer service |
| **Polymarket Gamma API** | Market metadata (questions, resolution dates) | `https://gamma-api.polymarket.com` | No | Market service, search endpoint |
| **Polymarket CLOB API** | Market order book, prices | `https://clob.polymarket.com` | No | Market data (optional) |
| **Public Polygon RPC** | Live OrderFilled event subscription | `https://polygon-rpc.com` (HTTP) + `wss://polygon-bor-rpc.publicnode.com` (WS) | No | Live listener service |

### 2.1 Why These Services?

**The Graph Network:** Pre-indexed, instantly queryable historical trades. Only practical way to retrieve thousands of past trades in seconds without scanning raw blockchain logs. Required for the "classify insider trades historically" objective.

**Etherscan v2 API:** Wallet deposit history with archive access. Etherscan v2 supports Polygon via chainid parameter (42161). Provides first USDC.e deposit timestamp and amount — critical for the "wallet age" factor (Factor 4) in the scoring engine. Free API key, 5 calls/sec rate limit sufficient for this use case.

**Polymarket Gamma & CLOB APIs:** Market discovery, metadata, and order book data. Public, no authentication. Used for search functionality and to map asset IDs to market questions.

**Public Polygon RPC:** Live event listening via WebSocket. Subscribes to new OrderFilled events and triggers real-time scoring. Public endpoint, no setup required.

### 2.2 Services NOT Used

- **Goldsky Subgraph** — Redundant. The Graph Network hosts the same Polymarket subgraph.
- **PolygonScan API** — Deprecated. Replaced by Etherscan v2 API.
- **Dune Analytics** — Optional. Not required for core assignment; useful for validation only.
- **Etherscan Mainnet** — Wrong chain. We're on Polygon, not Ethereum.

---

## 3. System Architecture

SENTINEL is built with clear separation of concerns: data sources (blockchain), storage (MongoDB), processing (Celery background jobs), and API (FastAPI). All components communicate asynchronously via Redis pub/sub for real-time alerts.

### 3.1 Data Flow Diagram (Text Description)

```
Blockchain (Polygon)
     ├─ OrderFilled events (live)
     └─ USDC.e Transfer events (historical)

     ▼

     ┌─────────────────────────────────────────┐
     │   INDEXERS (Celery Background Tasks)    │
     ├─────────────────────────────────────────┤
     │  • subgraph.py (The Graph GraphQL)      │
     │  • live_listener.py (WebSocket)         │
     │  • deposit_indexer.py (Etherscan v2)    │
     └─────────────────────────────────────────┘

     ▼

     ┌─────────────────────────────────────────┐
     │      MONGODB (Data Storage)              │
     ├─────────────────────────────────────────┤
     │  • trades (OrderFilled events)          │
     │  • wallets (enriched profile)           │
     │  • deposits (first USDC.e transfer)     │
     │  • markets (metadata)                    │
     │  • insider_scores (5+1 factor results)  │
     └─────────────────────────────────────────┘

     ▼

     ┌─────────────────────────────────────────┐
     │   SCORING ENGINE (Celery Tasks)         │
     ├─────────────────────────────────────────┤
     │  • factors.py (6 factor calculators)    │
     │  • engine.py (composite scorer)         │
     │  • weights.py (dynamic weight system)   │
     │  • calibrate.py (grid search tuning)    │
     └─────────────────────────────────────────┘

     ▼

     ┌─────────────────────────────────────────┐
     │      FASTAPI (REST + WebSocket)         │
     ├─────────────────────────────────────────┤
     │  • GET /api/markets/search               │
     │  • GET /api/markets/{id}/trades         │
     │  • GET /api/wallets/{address}           │
     │  • GET /api/alerts                      │
     │  • WS /ws/alerts (live feed)            │
     └─────────────────────────────────────────┘

     ▼

     React Frontend
```

---

## 4. Where Each Service Is Used

### 4.1 The Graph Network → `services/indexer/subgraph.py`

**When:** User searches for market "Will Spain win FIFA?" OR during historical backfill

**API Call:**
```graphql
POST https://api.thegraph.com/subgraphs/name/polymarket/polymarket
{
  "query": "{
    orderFilledEvents(
      first: 1000,
      where: { takerAssetId_in: [\"12345\", \"67890\"] },
      orderBy: timestamp,
      orderDirection: asc
    ) {
      id transactionHash blockNumber timestamp maker taker
      makerAssetId takerAssetId makerAmountFilled takerAmountFilled fee
    }
  }"
}
```

### 4.2 Etherscan v2 API → `services/indexer/deposit_indexer.py` (NEW)

**When:** Wallet enrichment phase — for every unique wallet found in trades

**API Call:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={ETHERSCAN_API_KEY}
  &chainid=42161
  &module=account
  &action=tokentx
  &contractaddress=0x2791bca1f2de4661ed88a30c99a7a9449aa84174
  &address={wallet_address}
  &page=1
  &offset=10000
  &sort=asc
```

**Response:** Array of token transfer events. Take first result (earliest timestamp) as wallet's first USDC.e deposit.

```json
{
  "blockNumber": "313439348",
  "timeStamp": "1741413668",
  "hash": "0xf0d056b8...",
  "from": "0x...",
  "to": "0x2449ecef5012f0a0e153b278ef4fcc9625bc4c78",
  "value": "100000000"
}
```

### 4.3 Polymarket Gamma API → `services/market_service.py`

**When:** User searches for market by slug OR periodic refresh of live market data

**API Call:**
```
GET https://gamma-api.polymarket.com/markets?slug=will-spain-win-fifa-2026
```

### 4.4 Public Polygon RPC WebSocket → `services/indexer/live_listener.py`

**When:** System is running (continuous)

**Connection:**
```
wss://polygon-bor-rpc.publicnode.com

Subscribe to OrderFilled events from CTF Exchange contract (0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E)
```

---

## 5. Development Checklist

### 5.1 MongoDB Models (Beanie)

| Model | File | Description |
|-------|------|-------------|
| Trade | `app/models/trade.py` | OrderFilled event data + source (historical\|live) |
| Wallet | `app/models/wallet.py` | Enriched wallet profile (age, markets, volume) |
| Deposit | `app/models/deposit.py` | First USDC.e transfer event per wallet |
| Market | `app/models/market.py` | Market metadata from Gamma API |
| InsiderScore | `app/models/insider_score.py` | 5+1 factor scores + verdict + weights used |

### 5.2 Indexer Services

| Service | File | Description |
|---------|------|-------------|
| Subgraph Indexer | `services/indexer/subgraph.py` | GraphQL queries to The Graph; paginated backfill |
| Live Listener | `services/indexer/live_listener.py` | Web3.py WebSocket subscription to OrderFilled |
| Deposit Indexer | `services/indexer/deposit_indexer.py` | Etherscan v2 API tokentx queries for wallets |
| Backfill Orchestrator | `services/indexer/backfill.py` | Coordinates subgraph → enrich → score pipeline |

### 5.3 Scoring Engine

| Component | File | Description |
|-----------|------|-------------|
| Factor Functions | `services/scorer/factors.py` | 6 independent factor calculators |
| Composite Score | `services/scorer/engine.py` | Applies weights, produces final score + verdict |
| Dynamic Weights | `services/scorer/weights.py` | Category + liquidity + proximity weight axes |
| Calibration | `services/scorer/calibrate.py` | Grid search against 7 known wallets |

### 5.4 API Routes (FastAPI)

| Route | File | Description |
|-------|------|-------------|
| Market Search | `routers/markets.py` | `GET /api/markets/search?q={slug\|url\|condition_id}` |
| Market Trades | `routers/trades.py` | `GET /api/markets/{condition_id}/trades` |
| Wallet Profile | `routers/wallets.py` | `GET /api/wallets/{address}` |
| Alerts Feed | `routers/alerts.py` | `GET /api/alerts?limit=50` |
| WebSocket | `routers/ws.py` | `WS /ws/alerts` (real-time updates) |

### 5.5 Celery Background Tasks

| Task | File | Description |
|------|------|-------------|
| Enrich Wallets | `tasks/enrich_wallets.py` | Fetch deposit history + trading stats |
| Score Market | `tasks/score_market.py` | Run 6-factor algorithm on all trades |
| Live Score | `tasks/live_score.py` | Score new OrderFilled event in real-time |
| Refresh Markets | `tasks/refresh_markets.py` | Periodic: sync live market metadata |

### 5.6 Supporting Services

| Service | File | Description |
|---------|------|-------------|
| Market Service | `services/market_service.py` | Gamma API integration |
| Wallet Service | `services/wallet_service.py` | Wallet enrichment orchestration |
| Polygon RPC | `utils/polygon_rpc.py` | Web3.py wrapper for RPC + WebSocket |
| Etherscan | `utils/etherscan.py` | Etherscan v2 API wrapper (NEW) |

---

## 6. Configuration (.env)

```dotenv
# ── APP ──────────────────────────────
APP_ENV=development
API_PORT=8000
SECRET_KEY=generate_random_64_char_string
CORS_ORIGINS=http://localhost:3000

# ── MONGODB ──────────────────────────
MONGODB_URL=mongodb://localhost:27017/sentinel_insider
MONGODB_DB_NAME=sentinel_insider

# ── REDIS ────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── THE GRAPH (no key required) ──────
POLYMARKET_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/polymarket/polymarket

# ── ETHERSCAN v2 (requires free key) ─
ETHERSCAN_API_KEY=your_free_key_from_etherscan.io
ETHERSCAN_API_URL=https://api.etherscan.io/v2/api

# ── POLYMARKET ───────────────────────
POLYMARKET_GAMMA_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_URL=https://clob.polymarket.com

# ── POLYGON RPC (public) ─────────────
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGON_WS_URL=wss://polygon-bor-rpc.publicnode.com

# ── CONTRACTS ────────────────────────
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
USDC_E_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174

# ── SCORING THRESHOLDS ──────────────
MIN_TRADE_SIZE_USDC=5000
INSIDER_THRESHOLD=0.75
SUSPICIOUS_THRESHOLD=0.50
FRESH_WALLET_DAYS=7
```

### 6.1 API Key Setup

**Only ONE signup required:** Etherscan v2 (formerly PolygonScan). Sign up at **etherscan.io**, select Polygon network, create a free API key. All other services (The Graph, Polymarket APIs, public RPC) require zero authentication.

---

## 7. Implementation Plan (2 Days)

### Day 1 — Data Foundation

**Morning Session (4 hours):**
- `config.py`, `database.py`, `redis_client.py`
- All 5 Beanie models (trade, wallet, market, deposit, insider_score)
- `constants.py` with addresses, ABIs, event signatures
- `polygon_rpc.py` Web3.py wrapper
- `etherscan.py` Etherscan v2 API wrapper **(NEW)**

**Afternoon Session (4 hours):**
- `subgraph.py` historical indexer with pagination
- `deposit_indexer.py` using Etherscan v2 **(NEW)**
- `market_service.py` Gamma API integration
- `wallet_service.py` enrichment orchestration
- Wire up markets & trades routers

**Evening Session (2 hours):**
- Query The Graph, verify it returns trades
- Call Etherscan v2, verify deposit data
- Test market search endpoint

### Day 2 — Scoring & Real-time

**Morning Session (4 hours):**
- `factors.py` all 6 factor functions
- `weights.py` category + liquidity + proximity axes
- `engine.py` composite scorer
- `calibrate.py` grid search (10,000 combinations per category)
- `wallets` & `alerts` routers

**Afternoon Session (3 hours):**
- `live_listener.py` WebSocket subscriber
- `live_score.py` Celery task
- `ws.py` WebSocket manager + Redis pub/sub
- Wire frontend WebSocket hook
- Connect frontend to real API

**Evening Session (3 hours):**
- Docker Compose end-to-end test
- Railway deployment (or keep local)
- Backend README with setup instructions
- **Deferred:** Architecture diagram (last-minute)

---

## 8. Assignment Requirements Mapping

| Assignment Requirement | Implemented By | Status |
|------------------------|--------------| --------|
| Classify trades historically | `subgraph.py` → trade model → scoring engine | ✓ |
| Classify trades in real time | `live_listener.py` + Celery tasks | ✓ |
| System architecture | This document + docker-compose.yml | ✓ |
| Index historical trades via OrderFilled | `subgraph.py` (The Graph GraphQL) | ✓ |
| Index live trades via OrderFilled | `live_listener.py` (Polygon WebSocket) | ✓ |
| Index first USDC.e deposit per wallet | `deposit_indexer.py` (Etherscan v2 API) | ✓ **NEW** |
| Store trades in database | `trades` MongoDB collection | ✓ |
| Store wallet + deposit data | `wallets` + `deposits` collections | ✓ |
| Insider detection algorithm | `factors.py` + `engine.py` | ✓ |
| Optimal weights with justification | `calibrate.py` (grid search) + `weights_report.json` | ✓ |
| Entry timing factor | `factors.py` Factor 1 | ✓ |
| Traded few markets factor | `factors.py` Factor 2 | ✓ |
| Minimum size factor | `factors.py` Factor 3 | ✓ |
| Wallet age factor | `factors.py` Factor 4 (uses Etherscan deposits) | ✓ **NEW** |
| Trade concentration factor | `factors.py` Factor 5 | ✓ |
| Market manipulability factor | `factors.py` Factor 6 | ✓ |
| Reference: The Graph Subgraph | Used for historical backfill | ✓ |
| Reference: Sample tx verification | Manual test Day 1 evening | [ ] |
| Reference: Trading.sol OrderFilled | Event signature in `constants.py` | ✓ |
| Reference: USDC.e contract | Address in `constants.py` | ✓ |

---

## 9. Key Changes from v1.0

### 9.1 Etherscan v2 API Migration

PolygonScan's own documentation deprecated their API and directed users to use Etherscan v2 instead. Etherscan v2 supports Polygon via chainid parameter (42161). The query syntax remains identical to old PolygonScan API — same `tokentx` module, same response format.

**Impact:** No code logic change. Only endpoint URL and chainid parameter updated.

### 9.2 Goldsky Removal

Goldsky and The Graph both host the exact same Polymarket subgraph. Choosing The Graph eliminates complexity: no extra API key setup, no extra vendor, no redundancy.

**Impact:** Simpler onboarding, fewer API credentials, same data quality.

---

## 10. Next Steps

1. **Obtain free Etherscan API key** (5 minutes at etherscan.io)
2. **Clone repo and fill backend/.env** with endpoints
3. **Run tester.py** to verify all external APIs
4. **Start Docker Compose** (mongodb, redis, backend, celery)
5. **Begin implementation** following the 2-day timeline

---

**Document complete. Ready for implementation.**
