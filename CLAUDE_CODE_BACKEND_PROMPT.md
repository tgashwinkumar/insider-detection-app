# Claude Code Prompt — SENTINEL Backend Implementation

> **How to use this file:**
> Open your terminal, `cd` into the `insider-trader-detection-assignment/` folder, launch
> Claude Code (`claude`), and paste everything below the horizontal rule as your first message.
> Claude Code will read the referenced files automatically.

---

## PROMPT START — PASTE EVERYTHING BELOW THIS LINE

You are building **SENTINEL**, a real-time insider trading detection backend for Polymarket prediction markets. The React frontend already exists and is wired to a set of fixed API contracts. Your job is to scaffold and implement the entire FastAPI backend so that the frontend works with zero mock data.

---

## 0. Read These Files First — Before Writing a Single Line of Code

Read all five documents completely before planning anything. They are the single source of truth.

1. `FLARE_BACKEND_ARCHITECTURE_v2_REVISED.md` — system architecture, services, data flow
2. `backend/CLAUDE.md` — tech stack, design patterns, code style guidelines
3. `backend/docs/API_KNOWLEDGE_BASE.md` — Etherscan v2 and The Graph API reference, full schemas, rate limits, query examples
4. `BACKEND_DEVELOPMENT_BLUEPRINT.md` — implementation blueprint and checklist
5. `DOUBTS.md` — resolved design decisions (global vs. targeted mode, deposit retention, hybrid architecture)

Also read these frontend files to understand the exact API contract you must satisfy:

6. `frontend/src/services/api.js` — all four fetch functions with exact URL paths
7. `frontend/src/utils/mockData.js` — exact shape of every response object
8. `frontend/src/utils/constants.js` — factor key names, risk level strings, known wallet addresses
9. `frontend/src/hooks/useWebSocket.js` — WebSocket base URL and path construction
10. `frontend/src/hooks/useTradeData.js` — how market detail data is consumed
11. `frontend/src/hooks/useMarketSearch.js` — how search results are consumed

---

## 1. Project Context

**What SENTINEL does:**
- Indexes historical Polymarket trades from The Graph (GraphQL)
- Listens to live `OrderFilled` events from Polygon via WebSocket
- Fetches each wallet's first USDC.e deposit from Etherscan v2 (Polygon chain, chainid=137)
- Runs a 5-factor insider detection algorithm on every trade
- Exposes a REST + WebSocket API consumed by the existing React frontend

**What already exists:**
- `frontend/` — complete React app (Vite + Tailwind + Recharts + React Router v6)
- `backend/requirements.txt` — all Python dependencies already pinned
- `backend/CLAUDE.md` — architecture and guidelines
- `backend/docs/API_KNOWLEDGE_BASE.md` — full external API reference

**What you must build:**
- The entire `backend/app/` directory from scratch, following the structure below

---

## 2. Folder Structure to Create

Create this exact directory and file layout inside `backend/`:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app entry, lifespan, router registration
│   ├── config.py                      # Pydantic BaseSettings, loads from .env
│   ├── database.py                    # Beanie init, MongoDB motor client
│   ├── redis_client.py                # Redis connection pool singleton
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── trade.py                   # Trade document
│   │   ├── wallet.py                  # Wallet document
│   │   ├── deposit.py                 # Deposit document
│   │   ├── market.py                  # Market document
│   │   ├── insider_score.py           # InsiderScore document
│   │   └── alert.py                   # Alert document
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── markets.py                 # GET /api/markets/search, GET /api/markets/{id}/trades
│   │   ├── wallets.py                 # GET /api/wallets/{address}/score
│   │   ├── alerts.py                  # GET /api/alerts
│   │   └── ws.py                      # WS /ws/trades
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── market_service.py          # Polymarket Gamma API wrapper
│   │   ├── wallet_service.py          # Wallet enrichment orchestration
│   │   └── indexer/
│   │       ├── __init__.py
│   │       ├── subgraph.py            # The Graph GraphQL queries
│   │       ├── deposit_indexer.py     # Etherscan v2 tokentx queries
│   │       ├── live_listener.py       # Polygon WebSocket subscriber
│   │       └── backfill.py            # Full pipeline orchestrator
│   │
│   ├── scorer/
│   │   ├── __init__.py
│   │   ├── factors.py                 # 5 factor calculator functions
│   │   ├── engine.py                  # Composite scorer, verdict logic
│   │   ├── weights.py                 # Configurable weight definitions
│   │   └── calibrate.py              # Grid-search calibration against known wallets
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py              # Celery instance with Redis broker
│   │   ├── enrich_wallets.py          # Celery task: enrich batch of wallets
│   │   ├── score_market.py            # Celery task: score all trades in a market
│   │   ├── live_score.py              # Celery task: score a single live trade
│   │   └── refresh_markets.py         # Celery periodic task: refresh market metadata
│   │
│   └── utils/
│       ├── __init__.py
│       ├── polygon_rpc.py             # Web3.py wrapper for HTTP + WebSocket RPC
│       ├── etherscan.py               # Etherscan v2 API client
│       └── constants.py              # Contract addresses, ABIs, event signatures
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_factors.py
│   │   ├── test_engine.py
│   │   └── test_wallet_service.py
│   └── integration/
│       ├── test_markets_router.py
│       ├── test_wallets_router.py
│       └── test_alerts_router.py
│
├── .env.example
├── Dockerfile
├── tester.py
└── requirements.txt                   # Already exists — do not modify
```

---

## 3. Critical: Exact API Contract

The frontend is hardwired to these endpoints. **Do not change the URL paths or response shapes.**

### 3.1 — GET /api/markets/search?q={query}

Called by `frontend/src/services/api.js → searchMarkets()` and consumed by `useMarketSearch.js`.

**Request:** `GET /api/markets/search?q=spain`

**Response — array of market objects:**
```json
[
  {
    "conditionId": "0xaabb...",
    "question": "Will Spain win the FIFA World Cup 2026?",
    "resolutionDate": "2026-07-19",
    "verdict": "insider",
    "direction": "yes",
    "confidence": 87,
    "volume": 2100000,
    "traderCount": 47,
    "manipulability": 0.89
  }
]
```

**Field rules:**
- `conditionId` — hex string, the Polymarket condition ID
- `resolutionDate` — ISO date string `"YYYY-MM-DD"` (not a timestamp)
- `verdict` — one of `"insider"` | `"suspicious"` | `"clean"` (never `"normal"`)
- `direction` — `"yes"` | `"no"` | `null` (which outcome insiders bought)
- `confidence` — integer 0–100 (percentage)
- `manipulability` — float 0.0–1.0

**Query handling:**
- Detect query type using the same logic as the frontend (`POLYMARKET_URL_REGEX`, `CONDITION_ID_REGEX`, `TOKEN_ID_REGEX` from `frontend/src/utils/constants.js`)
- If query is a Polymarket URL, extract slug and look up via Gamma API
- If query is a condition ID (0x + 64 hex chars), fetch that market directly
- If query is a plain text string, call Gamma API `/markets?slug_contains={q}` and return top matches
- Search MongoDB cache first; call Gamma API on cache miss

---

### 3.2 — GET /api/markets/{conditionId}/trades

Called by `frontend/src/services/api.js → getMarketTrades()` and consumed by `useTradeData.js`.

**Response — full market detail object:**
```json
{
  "market": {
    "conditionId": "0xaabb...",
    "question": "Will Spain win the FIFA World Cup 2026?",
    "resolutionDate": "2026-07-19",
    "verdict": "insider",
    "direction": "yes",
    "confidence": 87,
    "volume": 2100000,
    "traderCount": 47,
    "manipulability": 0.89
  },
  "trades": [
    {
      "id": "0xtxhash...",
      "wallet": "0xee50...",
      "walletLabel": "AlphaRaccoon",
      "timestamp": 1712345678000,
      "sizeUsdc": 89000,
      "direction": "yes",
      "classification": "insider",
      "insiderScore": 0.94,
      "factors": {
        "entryTiming": 0.95,
        "marketCount": 0.98,
        "tradeSize": 0.82,
        "walletAge": 0.97,
        "concentration": 0.98
      },
      "walletCreatedAt": 1711000000000,
      "firstTradeAt": 1711200000000
    }
  ],
  "verdict": {
    "level": "insider",
    "direction": "yes",
    "confidence": 87
  },
  "summary": {
    "totalTrades": 8,
    "uniqueWallets": 8,
    "flaggedCount": 3,
    "highestScore": 0.94
  }
}
```

**Field rules:**
- `timestamp`, `walletCreatedAt`, `firstTradeAt` — **milliseconds** Unix epoch (multiply by 1000 from any seconds-based source)
- `classification` — one of `"insider"` | `"suspicious"` | `"clean"` (never `"normal"`)
- `insiderScore` — float 0.0–1.0
- `factors` — exactly these five camelCase keys: `entryTiming`, `marketCount`, `tradeSize`, `walletAge`, `concentration`
- `walletLabel` — look up `wallet` address in the `KNOWN_WALLETS` dict (from constants.js) and return the label, or `null`
- `verdict.confidence` — integer 0–100 (derive from highest insider score × 100)
- `summary.flaggedCount` — trades where `classification === "insider"`

**On first call for a new conditionId:** trigger background Celery task to backfill historical trades from The Graph, enrich wallets via Etherscan, and score all trades. Return whatever is cached so far immediately (do not block the response).

---

### 3.3 — GET /api/wallets/{address}/score

Called by `frontend/src/services/api.js → getWalletScore()`.

**Note the path:** `/api/wallets/{address}/score` — NOT `/api/wallets/{address}`

**Response:**
```json
{
  "address": "0xee50...",
  "walletLabel": "AlphaRaccoon",
  "insiderScore": 0.91,
  "classification": "insider",
  "walletCreatedAt": 1711000000000,
  "firstTradeAt": 1711200000000,
  "walletAgeDays": 12.5,
  "totalTrades": 7,
  "totalVolumeUsdc": 312000,
  "marketsTraded": 2,
  "avgTradeSizeUsdc": 44571,
  "factors": {
    "entryTiming": 0.95,
    "marketCount": 0.98,
    "tradeSize": 0.82,
    "walletAge": 0.97,
    "concentration": 0.98
  },
  "trades": [ /* same trade object shape as above */ ]
}
```

---

### 3.4 — GET /api/alerts

Called by `frontend/src/services/api.js → getAlerts()` and consumed by `AlertsPage.jsx`.

**Response — array of alert objects:**
```json
[
  {
    "id": "0xtxhash...",
    "wallet": "0xee50...",
    "walletLabel": "AlphaRaccoon",
    "timestamp": 1712345678000,
    "sizeUsdc": 89000,
    "direction": "yes",
    "classification": "insider",
    "insiderScore": 0.94,
    "factors": {
      "entryTiming": 0.95,
      "marketCount": 0.98,
      "tradeSize": 0.82,
      "walletAge": 0.97,
      "concentration": 0.98
    },
    "walletCreatedAt": 1711000000000,
    "firstTradeAt": 1711200000000,
    "market": {
      "conditionId": "0xaabb...",
      "question": "Will Spain win the FIFA World Cup 2026?",
      "resolutionDate": "2026-07-19",
      "verdict": "insider",
      "direction": "yes",
      "confidence": 87,
      "volume": 2100000,
      "traderCount": 47,
      "manipulability": 0.89
    }
  }
]
```

This is the trade object with `market` nested inside. Return all trades where `classification !== "clean"`, sorted by `insiderScore` descending, default limit 50. Support `?classification=insider|suspicious` and `?limit={n}` query params.

---

### 3.5 — WebSocket: ws://localhost:8000/ws/trades

Called by `frontend/src/hooks/useWebSocket.js`. The hook constructs the URL as:
```
WS_URL + path   →   ws://localhost:8000/ws + /trades   →   ws://localhost:8000/ws/trades
```

The WebSocket manager must:
1. Accept client connections on `/ws/trades`
2. Subscribe to a Redis pub/sub channel (e.g., `"sentinel:alerts"`)
3. When a new trade is scored and classified as `"insider"` or `"suspicious"`, publish the full alert object to the channel
4. Broadcast to all connected WebSocket clients

**WebSocket message format:**
```json
{
  "type": "trade",
  "data": { /* same shape as alert object above */ }
}
```

---

## 4. Implementation Plan — Ordered Build Sequence

Build in this exact order. Each phase should be independently testable before moving on.

### Phase 1 — Foundation (build first, everything depends on this)

**Step 1.1 — `app/utils/constants.py`**
Define all smart contract constants, event signatures, and the known wallet lookup dict.

```python
# Contract addresses (Polygon PoS mainnet)
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKEN_ADDRESS = "0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3"

# Polygon network
POLYGON_CHAIN_ID = 137

# Known wallets — for label display (used by all routers)
KNOWN_WALLETS = {
    "0xee50a31c3f5a7c77824b12a941a54388a2827ed6": "AlphaRaccoon",
    "0x6baf05d193692bb208d616709e27442c910a94c5": "SBet365",
    "0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2": "ricosuave",
    "0x7f1329ade2ec162c6f8791dad99125e0dc49801c": "gj1",
    "0xc51eedc01790252d571648cb4abd8e9876de5202": "hogriddahhhh",
    "0x976685b6e867a0400085b1273309e84cd0fc627c": "fromagi",
    "0x55ea982cebff271722419595e0659ef297b48d7c": "flaccidwillie",
    "0x31a56e9e690c621ed21de08cb559e9524cdb8ed9": None,  # Maduro unnamed — no label
}

# Calibration ground truth — sourced directly from the assignment PDF
# CONFIRMED INSIDER wallets (positives for calibration):
INSIDER_CALIBRATION_WALLETS = [
    "0xee50a31c3f5a7c77824b12a941a54388a2827ed6",  # AlphaRaccoon — Google d4vd market
    "0x6baf05d193692bb208d616709e27442c910a94c5",  # SBet365 — Maduro out
    "0x31a56e9e690c621ed21de08cb559e9524cdb8ed9",  # Unnamed — Maduro out (no label)
    "0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2",  # ricosuave — Israel/Iran market
    "0x7f1329ade2ec162c6f8791dad99125e0dc49801c",  # gj1 — Trump pardon CZ
    "0x976685b6e867a0400085b1273309e84cd0fc627c",  # fromagi — MicroStrategy
    "0x55ea982cebff271722419595e0659ef297b48d7c",  # flaccidwillie — DraftKings
]

# NOT an insider — assignment PDF explicitly says "not insider just smart guy scraped"
# Use as a CLEAN/control wallet in calibration to avoid false positives
CLEAN_CALIBRATION_WALLETS = [
    "0xc51eedc01790252d571648cb4abd8e9876de5202",  # hogriddahhhh — smart trader, scraped data
]

# Reference transaction from the assignment PDF for validation
# OrderFilled sample tx on Polygon: used to verify event decoding in tester.py
SAMPLE_ORDER_FILLED_TX = "0x6599fcc58912b6ea1f3fbed5a801b28399097edfac3216fbf3cbbc9763837273"

# ERC20 Transfer event signature — used by deposit_indexer.py for USDC.e transfers
# Source: OpenZeppelin ERC20.sol#L203 (referenced in assignment PDF)
ERC20_TRANSFER_EVENT_SIG = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# = keccak256("Transfer(address,address,uint256)")

# Classification thresholds
INSIDER_THRESHOLD = 0.75
SUSPICIOUS_THRESHOLD = 0.50

# Minimum trade size to score
MIN_TRADE_SIZE_USDC = 5000.0

# Fresh wallet threshold
FRESH_WALLET_DAYS = 7
```

**Step 1.2 — `app/config.py`**
Use `pydantic_settings.BaseSettings`. Load from `.env`. Validate all required keys at startup so the app fails fast with a clear error if config is missing.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017/sentinel_insider"
    MONGODB_DB_NAME: str = "sentinel_insider"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Etherscan v2
    ETHERSCAN_API_KEY: str
    ETHERSCAN_API_URL: str = "https://api.etherscan.io/v2/api"

    # The Graph
    POLYMARKET_SUBGRAPH_URL: str = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket"

    # Polymarket APIs
    POLYMARKET_GAMMA_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_URL: str = "https://clob.polymarket.com"

    # Polygon RPC
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"
    POLYGON_WS_URL: str = "wss://polygon-bor-rpc.publicnode.com"

    # Scoring
    MIN_TRADE_SIZE_USDC: float = 5000.0
    INSIDER_THRESHOLD: float = 0.75
    SUSPICIOUS_THRESHOLD: float = 0.50
    FRESH_WALLET_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Step 1.3 — `app/database.py`**
Motor async client + Beanie init. Use `asynccontextmanager` lifespan hook in `main.py`.

**Step 1.4 — `app/redis_client.py`**
Singleton Redis connection pool. Expose `get_redis()` and `get_pubsub()` helpers.

---

### Phase 2 — Beanie Models

One file per model. Follow these rules:
- All `Document` subclasses use `class Settings` inner class with `name` (collection name) and `indexes`
- Field names must be camelCase where they map directly to frontend fields (or use Pydantic `alias`)
- All timestamps stored as `int` (Unix seconds in DB) — convert to milliseconds only in the router serialization layer

**`app/models/trade.py`**
```python
class Trade(Document):
    transaction_hash: str          # unique
    block_number: int
    timestamp: int                 # Unix seconds (stored as seconds)
    maker: str                     # lowercase hex
    taker: str                     # lowercase hex
    maker_asset_id: str
    taker_asset_id: str
    maker_amount_filled: Decimal128
    taker_amount_filled: Decimal128
    fee: Decimal128
    amount_usdc: float             # derived: taker_amount_filled / 1e6
    direction: str                 # "yes" | "no"
    condition_id: str              # FK to Market
    source: str                    # "historical" | "live"
    indexed_at: datetime

    class Settings:
        name = "trades"
        indexes = [
            [("condition_id", 1), ("timestamp", -1)],
            [("maker", 1)],
            [("taker", 1)],
            [("timestamp", -1)],
        ]
```

**`app/models/wallet.py`**
```python
class Wallet(Document):
    address: str                   # unique, lowercase
    first_deposit_timestamp: int | None    # Unix seconds from Etherscan
    first_deposit_amount_usdc: float | None
    wallet_age_days: float | None
    total_trades: int = 0
    total_volume_usdc: float = 0.0
    average_trade_size_usdc: float = 0.0
    markets_traded: int = 0
    latest_insider_score: float = 0.0
    classification: str = "clean"  # "insider" | "suspicious" | "clean"
    last_updated: datetime
    first_seen: datetime

    class Settings:
        name = "wallets"
        indexes = [
            [("address", 1)],
            [("latest_insider_score", -1)],
            [("classification", 1)],
        ]
```

**`app/models/deposit.py`**
```python
class Deposit(Document):
    wallet_address: str            # unique
    transaction_hash: str
    block_number: int
    timestamp: int                 # Unix seconds
    amount_usdc: float

    class Settings:
        name = "deposits"
        indexes = [[("wallet_address", 1)]]
```

**`app/models/market.py`**
```python
class Market(Document):
    condition_id: str              # unique
    slug: str | None
    question: str
    resolution_date: str           # "YYYY-MM-DD" string
    resolution_timestamp: int | None   # Unix seconds, derived
    creator: str | None
    liquidity_usdc: float = 0.0
    volume_usdc: float = 0.0
    outcomes: list[str] = ["YES", "NO"]
    resolved: bool = False
    resolution: str | None
    verdict: str = "clean"         # "insider" | "suspicious" | "clean"
    direction: str | None
    confidence: int = 0            # 0-100
    manipulability: float = 0.0
    trader_count: int = 0
    last_updated: datetime

    class Settings:
        name = "markets"
        indexes = [
            [("condition_id", 1)],
            [("slug", 1)],
        ]
```

**`app/models/insider_score.py`**
```python
class InsiderScore(Document):
    trade_id: str                  # transaction_hash reference
    wallet_address: str
    condition_id: str
    # 5 factor scores
    factor_entry_timing: float
    factor_market_count: float
    factor_trade_size: float
    factor_wallet_age: float
    factor_concentration: float
    # Composite
    composite_score: float         # 0.0-1.0
    classification: str            # "insider" | "suspicious" | "clean"
    weights_used: dict
    model_version: str = "2.0"
    calculated_at: datetime

    class Settings:
        name = "insider_scores"
        indexes = [
            [("trade_id", 1)],
            [("wallet_address", 1)],
            [("condition_id", 1)],
            [("composite_score", -1)],
        ]
```

**`app/models/alert.py`**
```python
class Alert(Document):
    trade_id: str
    wallet_address: str
    condition_id: str
    score: float
    classification: str
    triggered_at: datetime
    notified: bool = False

    class Settings:
        name = "alerts"
        indexes = [
            [("triggered_at", -1)],
            [("classification", 1)],
        ]
```

---

### Phase 3 — Utility Clients

**Step 3.1 — `app/utils/etherscan.py`**

Implement an async `EtherscanClient` using `httpx.AsyncClient`. Key rules:
- All requests include `chainid=137` (Polygon PoS) and `apikey`
- Respect 5 req/sec rate limit — use `asyncio.Semaphore(5)` with 1-second window
- Implement exponential backoff (1s, 2s, 4s) on `status == "0"` rate-limit errors
- Primary method: `get_first_usdc_deposit(wallet_address)` → returns `(timestamp_seconds, amount_usdc)` or `(None, None)` if no transfers found

```python
async def get_first_usdc_deposit(
    self,
    wallet_address: str
) -> tuple[int | None, float | None]:
    """
    Fetch the earliest USDC.e transfer to this wallet.
    Use action=tokentx, contractaddress=USDC_E_ADDRESS, sort=asc, offset=1.
    Returns (unix_timestamp_seconds, amount_usdc) or (None, None).
    """
```

**Step 3.2 — `app/utils/polygon_rpc.py`**

`PolygonRPC` class wrapping `web3.py`. Two providers:
- `w3_http` — `Web3(Web3.HTTPProvider(POLYGON_RPC_URL))` for one-off calls
- Async websocket handled separately in `live_listener.py` (Web3.py WebSocket is blocking; use `websockets` library directly for async event subscription)

---

### Phase 4 — Indexer Services

**Step 4.1 — `app/services/indexer/subgraph.py`**

`SubgraphIndexer` class using `httpx.AsyncClient`. Implement cursor-based pagination as recommended in `API_KNOWLEDGE_BASE.md`:

```python
async def fetch_order_filled_events(
    self,
    condition_id: str,
    last_id: str = "",
    batch_size: int = 1000,
) -> list[dict]:
    """
    Query the Orderbook subgraph for OrderFilledEvents.
    Filter by takerAssetId matching the condition's token IDs.
    Use id_gt cursor for pagination, not skip.
    Subgraph ID: 7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY
    """
    query = """
    query fetchEvents($lastId: String!, $assetIds: [String!]!, $first: Int!) {
      orderFilledEvents(
        first: $first,
        where: { id_gt: $lastId, takerAssetId_in: $assetIds },
        orderBy: id,
        orderDirection: asc
      ) {
        id
        transactionHash
        timestamp
        maker
        taker
        makerAssetId
        takerAssetId
        makerAmountFilled
        takerAmountFilled
        fee
      }
    }
    """

async def fetch_all_events(
    self,
    condition_id: str,
) -> AsyncIterator[list[dict]]:
    """Paginate until no more results. Yield each batch."""
```

Map `takerAssetId` → `conditionId` using the Gamma API. The condition ID is embedded in the market's `conditionId` field; token IDs for YES and NO outcomes are the two asset IDs you query.

**Step 4.2 — `app/services/indexer/deposit_indexer.py`**

`DepositIndexer` using the `EtherscanClient`. Process wallets in batches with semaphore to respect the 5 req/sec limit:

```python
async def index_wallets(self, wallet_addresses: list[str]) -> None:
    """
    For each wallet, if not already in Deposit collection:
    1. Call EtherscanClient.get_first_usdc_deposit()
    2. Upsert Deposit document
    3. Update Wallet.first_deposit_timestamp and wallet_age_days
    """
```

**Step 4.3 — `app/services/market_service.py`**

Gamma API integration:

```python
async def search_markets(self, query: str, query_type: str) -> list[dict]:
    """
    query_type: "url" | "conditionId" | "tokenId" | "text"
    - "url": extract slug from URL, call GET /markets?slug={slug}
    - "conditionId": call GET /markets?condition_ids={id}
    - "tokenId": call GET /markets?token_id={id}
    - "text": call GET /markets?slug_contains={query}&limit=20
    Returns raw Gamma API market dicts.
    """

async def get_market_by_condition_id(self, condition_id: str) -> dict | None:
    """Single market fetch. Check MongoDB cache first."""

async def get_market_token_ids(self, condition_id: str) -> list[str]:
    """Return the YES and NO token IDs for a market (needed for subgraph query)."""
```

**Step 4.4 — `app/services/indexer/backfill.py`**

`BackfillOrchestrator` — coordinates the full pipeline for a market:

```python
async def backfill_market(self, condition_id: str) -> None:
    """
    1. Fetch market metadata from Gamma API, upsert Market document
    2. Fetch all OrderFilled events from The Graph (cursor-paginated)
    3. Normalise and upsert each event as Trade document
    4. Extract unique wallet addresses from trades
    5. Enqueue deposit_indexer for all wallets (Celery task)
    6. After deposits are indexed, enqueue score_market task
    """
```

**Step 4.5 — `app/services/indexer/live_listener.py`**

Connect to `wss://polygon-bor-rpc.publicnode.com` using the `websockets` library (not web3.py WebSocket which is blocking). Subscribe to logs from `CTF_EXCHANGE_ADDRESS`. Decode `OrderFilled` events. On each event:
1. Upsert Trade document (source="live")
2. Dispatch `live_score` Celery task

```python
ORDERFILLED_TOPIC = Web3.keccak(
    text="OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
).hex()
```

---

### Phase 5 — Scoring Engine

This is the core of the system. Implement each factor as a pure function in `scorer/factors.py`, then combine them in `scorer/engine.py`.

**Critical user-context note:** The end users are **Polymarket traders** who want to receive a signal when a probable insider trades a market so they can trade the same market in the same direction and profit. This means:
- **Latency matters for live scoring.** In `live_listener.py`, run the scoring pipeline *synchronously before dispatching to Celery* for the initial score. The Celery task can then do a deeper re-score once wallet enrichment is complete. Do not make traders wait for a queue to drain.
- **The `direction` field is the actionable output.** Always populate `direction: "yes" | "no"` on every scored trade — this is what a trader needs to know which side to take.
- **Alert early, refine later.** If wallet enrichment data is not yet available (new wallet, Etherscan not yet called), score with `walletAge` returning `0.50` (neutral) and emit a preliminary alert. Emit a second alert once the full enrichment completes and the score updates materially.

#### 5.1 — Factor Definitions (`app/scorer/factors.py`)

All factor functions return a `float` in range `[0.0, 1.0]`. Higher = more suspicious.

---

**Factor 1 — Entry Timing (`entryTiming`)**

*Signal: Did this wallet enter the trade close to market resolution?*

Insiders know outcomes in advance. Their trades cluster in the hours/days before resolution. Normal traders spread across the market's lifetime.

```python
def factor_entry_timing(
    trade_timestamp: int,        # Unix seconds
    resolution_timestamp: int,   # Unix seconds
    market_creation_timestamp: int,  # Unix seconds
) -> float:
    """
    Normalise position within market lifetime.
    position = (trade_ts - creation_ts) / (resolution_ts - creation_ts)
    A position close to 1.0 (near resolution) is suspicious.

    Score curve:
    - position >= 0.95  → 1.0 (last 5% of market life — extreme)
    - position >= 0.90  → 0.85
    - position >= 0.80  → 0.65
    - position >= 0.70  → 0.45
    - position >= 0.50  → 0.20
    - position < 0.50   → 0.05 (early entry — neutral/opposite signal)

    Edge case: if trade_ts > resolution_ts, return 0.0 (post-resolution, irrelevant)
    Edge case: if market lifetime < 1 hour, clamp to avoid division weirdness
    """
```

---

**Factor 2 — Market Count (`marketCount`)**

*Signal: Has this wallet traded in very few markets?*

Insiders target one specific market — or a tightly related cluster (e.g., 2-3 markets about the same event or person). The PDF defines the insider as someone trading "2-3 (or 1) **related** markets". Legitimate traders diversify broadly across unrelated markets.

```python
def factor_market_count(
    markets_traded: int,          # total unique markets this wallet has ever traded
    trades_in_window: int = 1,    # trades placed within a 7-day window (for clustering detection)
) -> float:
    """
    Primary signal: raw market count. Fewer markets = more suspicious.
    markets_traded == 1  → 1.0   (single market — maximum suspicion)
    markets_traded == 2  → 0.85  (2 markets — likely related, per the PDF definition)
    markets_traded == 3  → 0.65  (3 markets — still possibly related cluster)
    markets_traded == 4  → 0.40
    markets_traded == 5  → 0.20
    markets_traded >= 6  → 0.05  (broadly diversified — clean signal)

    NOTE on "related markets": The PDF specifically says insiders trade "2-3 (or 1) related markets".
    The ideal implementation would detect whether the 2-3 markets share a topic (same event, person,
    or outcome). As a practical approximation, score wallets with 2-3 markets nearly as high as
    wallets with 1 market, since the threshold for insider-like focus is genuinely 1-3, not just 1.
    If Market.question text is available, a future enhancement could apply cosine similarity on
    market questions to detect topically related clusters and boost the score accordingly.
    For now, the stepped scoring above captures this intent sufficiently.
    """
```

---

**Factor 3 — Trade Size (`tradeSize`)**

*Signal: Is this trade significantly larger than this wallet's average, and above minimum threshold?*

Insiders commit capital decisively. They place large, confident bets — not test trades.

```python
def factor_trade_size(
    amount_usdc: float,          # this trade's size
    wallet_avg_usdc: float,      # wallet's average trade size across all markets
    min_threshold: float = 5000, # from config MIN_TRADE_SIZE_USDC
) -> float:
    """
    If amount_usdc < min_threshold: return 0.0 (below minimum — ignore)

    Size ratio = amount_usdc / max(wallet_avg_usdc, min_threshold)

    ratio >= 5.0  → 1.0   (5x average — enormous relative to history)
    ratio >= 3.0  → 0.80
    ratio >= 2.0  → 0.60
    ratio >= 1.5  → 0.40
    ratio >= 1.0  → 0.20
    ratio < 1.0   → 0.10  (smaller than usual)

    Also apply absolute size bonus:
    amount >= $100,000 → add 0.10 bonus (capped at 1.0)
    amount >= $50,000  → add 0.05 bonus
    """
```

---

**Factor 4 — Wallet Age (`walletAge`)**

*Signal: Was this wallet newly created relative to the trade date?*

Insiders often use fresh wallets to avoid pattern detection. A wallet funded days before a winning trade is a strong red flag.

```python
def factor_wallet_age(
    first_deposit_timestamp: int | None,  # Unix seconds from Etherscan
    trade_timestamp: int,                  # Unix seconds
    fresh_threshold_days: int = 7,         # from config FRESH_WALLET_DAYS
) -> float:
    """
    If first_deposit_timestamp is None: return 0.50 (unknown age — neutral)

    age_at_trade_days = (trade_timestamp - first_deposit_timestamp) / 86400

    If age_at_trade_days < 0: return 0.0 (wallet created after trade — data error)

    age_at_trade_days == 0       → 1.0  (funded same day — extreme signal)
    age_at_trade_days <= 1       → 0.95
    age_at_trade_days <= 3       → 0.85
    age_at_trade_days <= 7       → 0.70  (within fresh threshold)
    age_at_trade_days <= 14      → 0.45
    age_at_trade_days <= 30      → 0.25
    age_at_trade_days <= 90      → 0.10
    age_at_trade_days > 90       → 0.02  (established wallet — clean signal)
    """
```

---

**Factor 5 — Concentration (`concentration`)**

*Signal: Is this trade a disproportionate share of this wallet's total volume?*

An insider bets everything they have on one outcome. A normal trader allocates partial capital.

```python
def factor_concentration(
    trade_amount_usdc: float,       # this trade's size
    wallet_total_volume_usdc: float, # all trades across all markets
) -> float:
    """
    If wallet_total_volume_usdc == 0: return 0.0

    share = trade_amount_usdc / wallet_total_volume_usdc

    share >= 0.90  → 1.0   (entire portfolio on one trade)
    share >= 0.75  → 0.85
    share >= 0.60  → 0.70
    share >= 0.50  → 0.55
    share >= 0.35  → 0.35
    share >= 0.20  → 0.15
    share < 0.20   → 0.05  (diversified allocation — clean)
    """
```

---

**Note on Manipulability (Factor 6 from architecture docs):**
Manipulability is a *market-level* property, not a per-trade factor in the frontend. Compute it once per market and store it on the `Market` document. It is NOT included in `trade.factors`. Use this formula:

```python
def compute_market_manipulability(liquidity_usdc: float) -> float:
    """
    liquidity < 10,000    → 0.95 (trivially manipulable)
    liquidity < 50,000    → 0.75
    liquidity < 100,000   → 0.55
    liquidity < 500,000   → 0.35
    liquidity < 1,000,000 → 0.15
    liquidity >= 1,000,000 → 0.05
    """
```

Store this on `Market.manipulability` and include it in all market responses.

---

#### 5.2 — Composite Scorer (`app/scorer/engine.py`)

```python
class ScoringEngine:
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS

    async def score_trade(
        self,
        trade: Trade,
        wallet: Wallet,
        market: Market,
    ) -> InsiderScore:
        """
        1. Call all 5 factor functions
        2. Compute weighted composite score
        3. Apply classification threshold:
           score >= INSIDER_THRESHOLD   → "insider"
           score >= SUSPICIOUS_THRESHOLD → "suspicious"
           else                          → "clean"
        4. Save InsiderScore to MongoDB
        5. Update Wallet.latest_insider_score and Wallet.classification
        6. If classification != "clean", upsert Alert and publish to Redis channel "sentinel:alerts"
        7. Return InsiderScore
        """
```

Default weights (`app/scorer/weights.py`):
```python
DEFAULT_WEIGHTS = {
    "entryTiming":   0.30,   # Strongest signal — timing is the clearest insider tell
    "marketCount":   0.20,   # Strong — focused wallets are unusual
    "walletAge":     0.25,   # Strong — new wallets for single trade is a red flag
    "tradeSize":     0.15,   # Medium — large bets matter but can be coincidence
    "concentration": 0.10,   # Supporting — all-in bets reinforce other signals
}
# Weights sum to 1.0
```

Justify these weights in a comment: entry timing and wallet age have the strongest academic backing from insider trading literature. Market count is a uniquely strong Polymarket-specific signal.

---

#### 5.3 — Calibration (`app/scorer/calibrate.py`)

Calibrate using the ground-truth sets defined in `constants.py`. **Do not treat all known wallets as insiders** — the assignment PDF explicitly distinguishes them:

- **`INSIDER_CALIBRATION_WALLETS`** (7 wallets) — confirmed insiders, should score high
- **`CLEAN_CALIBRATION_WALLETS`** (1 wallet: hogriddahhhh) — smart trader, NOT an insider, per the PDF: *"not insider just smart guy scraped"*. Use as a negative/control example to prevent false positives.

```python
async def run_calibration() -> dict:
    """
    1. Load all trades from INSIDER_CALIBRATION_WALLETS (7 wallets) from MongoDB
    2. Load all trades from CLEAN_CALIBRATION_WALLETS (1 wallet: hogriddahhhh) from MongoDB
    3. Grid-search weight combinations (step size 0.05, constrained to sum=1.0)
    4. For each combination, score all trades from both sets
    5. Optimisation metric:
       - Maximise mean composite score for insider wallets (target: >= 0.75)
       - Minimise mean composite score for clean wallets (target: <= 0.40)
       - Use F1-style combined objective: insider_mean - clean_mean
    6. Select the weight combination with the highest objective score
    7. Write weights_report.json to the backend/ directory with this exact structure:
       {
         "model_version": "2.0",
         "generated_at": "<ISO timestamp>",
         "optimal_weights": {
           "entryTiming":   <float>,
           "marketCount":   <float>,
           "walletAge":     <float>,
           "tradeSize":     <float>,
           "concentration": <float>
         },
         "weight_justification": {
           "entryTiming":   "Strongest signal — insiders buy close to resolution",
           "walletAge":     "Fresh wallets created specifically for the trade are high-confidence insider tells",
           "marketCount":   "Insiders target 1-3 specific markets; legitimate traders diversify",
           "tradeSize":     "Insiders commit large capital; small trades below $5K are excluded",
           "concentration": "Insiders go all-in on one outcome; diversified allocations indicate normal behaviour"
         },
         "calibration_results": {
           "insider_wallets_mean_score": <float>,
           "clean_wallets_mean_score": <float>,
           "separation_delta": <float>,
           "wallets_tested": {
             "<address>": { "label": "<name>", "mean_score": <float>, "type": "insider|clean" }
           }
         },
         "thresholds": {
           "insider":    0.75,
           "suspicious": 0.50
         }
       }
    8. Return optimal_weights dict
    """
```

**Why this matters for the assignment:** The PDF requirement is *"optimal parameters and weights for each factor in the model"*. The `weights_report.json` is the deliverable that proves the weights were derived empirically, not chosen arbitrarily.

---

### Phase 6 — Celery Tasks (`app/tasks/`)

**`celery_app.py`** — Celery instance, Redis broker, beat schedule

**`enrich_wallets.py`**
```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
async def enrich_wallets_task(self, wallet_addresses: list[str]) -> None:
    """
    For each address:
    1. Upsert Wallet document (create if not exists)
    2. Run DepositIndexer.index_wallets()
    3. Aggregate trade stats from MongoDB (total_trades, total_volume, avg_size, markets_traded)
    4. Update Wallet document
    """
```

**`score_market.py`**
```python
@celery_app.task
async def score_market_task(condition_id: str) -> None:
    """
    1. Load all trades for condition_id from MongoDB
    2. Load corresponding wallets and market
    3. For each trade, call ScoringEngine.score_trade()
    4. Update Market.verdict, Market.confidence, Market.direction based on aggregate scores
    """
```

**`live_score.py`**
```python
@celery_app.task
async def live_score_task(trade_data: dict) -> None:
    """
    1. Upsert Trade from event dict
    2. Ensure wallet exists (enrich if not)
    3. Score the single trade
    4. Publish alert to Redis if flagged
    """
```

**`refresh_markets.py`**
```python
@celery_app.task
async def refresh_markets_task() -> None:
    """Periodic task (every 10 minutes). Re-fetch all active markets from Gamma API.
    Update liquidity, volume, resolved status."""
```

---

### Phase 7 — FastAPI Routers

#### `app/routers/markets.py`

```python
@router.get("/api/markets/search")
async def search_markets(q: str, limit: int = 20):
    """
    1. Detect query type (url/conditionId/tokenId/text)
    2. Check MongoDB Market collection for matching documents first
    3. On cache miss, call MarketService.search_markets()
    4. Upsert returned markets to MongoDB
    5. Serialize each market using the exact field names from Section 3.1
    6. Return array
    """

@router.get("/api/markets/{condition_id}/trades")
async def get_market_trades(condition_id: str):
    """
    1. Look up Market in MongoDB, fetch from Gamma API if not found
    2. Check if trades exist for this condition_id in MongoDB
    3. If no trades: trigger BackfillOrchestrator.backfill_market() as background task
       Return empty trades list immediately (do not await)
    4. If trades exist but no scores: trigger score_market_task
    5. JOIN trades with insider_scores on trade_id
    6. Add walletLabel from KNOWN_WALLETS lookup
    7. Convert all timestamps to milliseconds (× 1000)
    8. Compute summary stats
    9. Return full response shape from Section 3.2
    """
```

#### `app/routers/wallets.py`

```python
@router.get("/api/wallets/{address}/score")  # NOTE: /score suffix
async def get_wallet_score(address: str):
    """
    1. Normalise address to lowercase
    2. Fetch Wallet document, enrich if not found
    3. Fetch all InsiderScores for this wallet
    4. Fetch recent Trades for this wallet
    5. Compute average factors across all scored trades
    6. Return shape from Section 3.3
    """
```

#### `app/routers/alerts.py`

```python
@router.get("/api/alerts")
async def get_alerts(
    classification: str | None = None,  # "insider" | "suspicious"
    limit: int = 50,
):
    """
    1. Query InsiderScore collection where classification != "clean"
    2. Filter by classification param if provided
    3. Sort by composite_score descending
    4. For each result, join with Trade and Market documents
    5. Build alert objects with nested market field
    6. Convert timestamps to milliseconds
    7. Return array
    """
```

#### `app/routers/ws.py`

```python
class ConnectionManager:
    """Manage WebSocket connections. Broadcast to all connected clients."""

    async def broadcast(self, message: dict) -> None:
        """Send JSON message to all active connections. Remove dead connections."""

manager = ConnectionManager()

@router.websocket("/ws/trades")  # EXACTLY /ws/trades — matches frontend hook
async def websocket_trades(websocket: WebSocket):
    """
    1. Accept connection
    2. Subscribe to Redis pub/sub channel "sentinel:alerts" in background task
    3. Forward any published messages to the WebSocket client
    4. Handle disconnect — unsubscribe and remove from manager
    """
```

---

### Phase 8 — `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()          # Beanie + Motor
    await init_redis()             # Connection pool
    start_live_listener()          # Background asyncio task
    yield
    # Shutdown — close connections

app = FastAPI(
    title="SENTINEL API",
    description="Insider trading detection for Polymarket",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets_router)
app.include_router(wallets_router)
app.include_router(alerts_router)
app.include_router(ws_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 5. Coding Best Practices — Enforce These Throughout

### Python / FastAPI
- Use `async def` for every route handler and I/O function (DB, HTTP, Redis)
- Use `httpx.AsyncClient` as an async context manager or as a shared client with lifespan
- Never block the event loop with synchronous I/O
- Use `typing` annotations everywhere — no bare `dict` or `list`
- Pydantic v2 models for all request/response bodies — no raw dicts returned from routes
- Use `logging` module (not `print`) — structured log format with level, module, message
- Handle all exceptions at the router level with proper HTTP status codes:
  - 404 for missing market/wallet
  - 422 for validation errors (FastAPI handles automatically)
  - 503 when external APIs are unavailable
  - 500 for unexpected errors — log the traceback

### MongoDB / Beanie
- Always use `await` with Beanie operations
- Use `upsert` pattern for indexers: `await Trade.find_one(...).upsert(...)` to avoid duplicates
- Create all indexes in model `Settings` class — do not create indexes manually
- Use projection queries where possible to avoid loading full documents

### Celery
- Use `bind=True` and `self.retry()` with exponential backoff for all tasks that call external APIs
- Use `countdown` parameter for retry delays
- Serialise task arguments as plain JSON-serialisable dicts (no Beanie objects)
- Use `apply_async` with `countdown` to stagger wallet enrichment batches

### Etherscan v2 — Rate Limit Safety
- Implement `asyncio.Semaphore(4)` (4, not 5, as safety margin)
- Track last request time, enforce minimum 200ms between requests
- On `"Max rate limit reached"` response, wait 2 seconds and retry
- Batch wallet addresses: process in groups of 10 with 2-second pauses between groups

### The Graph — Pagination Safety
- Always use cursor-based pagination (`id_gt`), never `skip` offset
- Check `_meta.hasIndexingErrors` before processing each batch
- Set `first: 1000` (maximum per query)
- Add 100ms delay between pagination requests to be a good API citizen

### Error Handling Pattern
```python
# Use this pattern in all services
try:
    result = await external_api_call()
except httpx.TimeoutException:
    logger.warning(f"Timeout calling {service_name}: {url}")
    return None
except httpx.HTTPStatusError as e:
    logger.error(f"HTTP {e.response.status_code} from {service_name}")
    return None
except Exception as e:
    logger.exception(f"Unexpected error in {service_name}: {e}")
    return None
```

---

## 6. Environment Setup

Create `backend/.env.example` (and a real `backend/.env` for local dev):

```dotenv
# Application
APP_ENV=development
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# MongoDB (run with docker-compose)
MONGODB_URL=mongodb://localhost:27017/sentinel_insider
MONGODB_DB_NAME=sentinel_insider

# Redis (run with docker-compose)
REDIS_URL=redis://localhost:6379/0

# Etherscan v2 — get free key at https://etherscan.io/apis
# Select Polygon PoS network when creating the key
ETHERSCAN_API_KEY=your_etherscan_api_key_here
ETHERSCAN_API_URL=https://api.etherscan.io/v2/api

# The Graph — no key required for hosted service
POLYMARKET_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/polymarket/polymarket

# Polymarket APIs — no auth required
POLYMARKET_GAMMA_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_URL=https://clob.polymarket.com

# Polygon RPC — public endpoints, no auth
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGON_WS_URL=wss://polygon-bor-rpc.publicnode.com

# Contract addresses on Polygon PoS
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
USDC_E_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174

# Scoring thresholds
MIN_TRADE_SIZE_USDC=5000
INSIDER_THRESHOLD=0.75
SUSPICIOUS_THRESHOLD=0.50
FRESH_WALLET_DAYS=7
```

---

## 7. Docker Compose

Create `docker-compose.yml` at the project root:

```yaml
version: "3.9"

services:
  mongodb:
    image: mongo:6.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost/test --quiet
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    environment:
      MONGODB_URL: mongodb://mongodb:27017/sentinel_insider
      REDIS_URL: redis://redis:6379/0
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    working_dir: /app

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: ./backend/.env
    environment:
      MONGODB_URL: mongodb://mongodb:27017/sentinel_insider
      REDIS_URL: redis://redis:6379/0
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
    volumes:
      - ./backend:/app
    working_dir: /app

volumes:
  mongo_data:
```

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 8. tester.py — Connectivity Validation Script

Create `backend/tester.py` that validates all external service connections before development begins:

```python
#!/usr/bin/env python3
"""
Run this before starting development to verify all external APIs are reachable.
Usage: cd backend && python tester.py
"""
```

Test these in order:
1. MongoDB — can connect and ping
2. Redis — can connect and ping
3. Etherscan v2 — balance query for address `0x000...0` with your API key, chainid=137
4. The Graph — `orderFilledEvents(first: 1) { id }` against the Orderbook subgraph
5. Polymarket Gamma API — `GET /markets?limit=1`
6. Polygon HTTP RPC — `eth_blockNumber` JSON-RPC call
7. Polygon WebSocket — connect and get latest block number

Print clear PASS/FAIL for each. Exit with code 1 if any critical service (MongoDB, Redis, Etherscan) fails.

---

## 9. Implementation Order Summary

Build in this sequence — each step should run before starting the next:

```
1.  constants.py + config.py                   → verify .env loads
2.  database.py + redis_client.py              → verify DB connections
3.  All 5 Beanie models                        → verify collections created
4.  utils/etherscan.py                         → test one tokentx call
5.  utils/polygon_rpc.py                       → test eth_blockNumber
6.  services/market_service.py                 → test Gamma API search
7.  services/indexer/subgraph.py               → test one GraphQL query
8.  services/indexer/deposit_indexer.py        → test one wallet lookup
9.  scorer/factors.py                          → unit test all 5 factors
10. scorer/engine.py + weights.py              → score a mock trade
11. scorer/calibrate.py                        → calibrate against known wallets
12. tasks/ (all Celery tasks)                  → test with real messages
13. services/indexer/backfill.py               → backfill one real market
14. services/indexer/live_listener.py          → subscribe to live events
15. routers/markets.py                         → GET /api/markets/search
16. routers/markets.py                         → GET /api/markets/{id}/trades
17. routers/wallets.py                         → GET /api/wallets/{address}/score
18. routers/alerts.py                          → GET /api/alerts
19. routers/ws.py                              → WS /ws/trades
20. main.py                                    → full app runs end-to-end
21. docker-compose.yml + Dockerfile            → docker-compose up works
22. tester.py                                  → all 7 checks pass
```

---

## 10. Verification Checklist

Before declaring the backend complete, verify every item:

**API Contract:**
- [ ] `GET /api/markets/search?q=spain` returns an array of market objects with all required fields
- [ ] `GET /api/markets/{conditionId}/trades` returns `{ market, trades, verdict, summary }` with factors in camelCase
- [ ] `GET /api/wallets/{address}/score` (with `/score` suffix) returns wallet profile
- [ ] `GET /api/alerts` returns array of alert objects with nested `market` field
- [ ] All timestamps in responses are in **milliseconds** (13-digit Unix epoch)
- [ ] All `classification` fields use `"insider" | "suspicious" | "clean"` (never `"normal"`)
- [ ] Factor keys are exactly: `entryTiming`, `marketCount`, `tradeSize`, `walletAge`, `concentration`

**WebSocket:**
- [ ] Frontend can connect to `ws://localhost:8000/ws/trades`
- [ ] Messages have shape `{ "type": "trade", "data": { /* alert object */ } }`
- [ ] Auto-reconnect works (disconnect and reconnect the client)

**Scoring Engine:**
- [ ] All 5 factor functions return values strictly in [0.0, 1.0]
- [ ] Composite score is correct weighted sum
- [ ] Calibration uses 7 INSIDER wallets and 1 CLEAN wallet (hogriddahhhh) as negative control
- [ ] `weights_report.json` is written to `backend/` and contains: `optimal_weights`, `weight_justification`, `calibration_results` (scores per wallet), and `thresholds`
- [ ] Mean score for insider calibration wallets is >= 0.75 with optimal weights
- [ ] Mean score for hogriddahhhh (clean wallet) is <= 0.40 with optimal weights
- [ ] Every scored trade has `direction: "yes" | "no"` populated — never null or missing
- [ ] Live alerts are emitted before Celery enrichment completes (preliminary alert), not after

**Integration:**
- [ ] CORS allows requests from `http://localhost:5173` and `http://localhost:3000`
- [ ] Frontend `HomePage` shows real market cards (not mock data)
- [ ] Frontend `MarketDetailPage` shows real trade table with scores
- [ ] Frontend `AlertsPage` shows real flagged trades
- [ ] No errors in browser console related to CORS, 404, or response shape mismatches

---

## PROMPT END