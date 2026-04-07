# SENTINEL Backend Development Blueprint
## Complete Implementation Roadmap for Insider Trading Detection System

**Project:** Insider Trading Detection Platform (Fireplace)
**Architecture Version:** 2.0 (Revised)
**Status:** Ready for Implementation
**Timeline:** 2-Day Sprint
**Created:** April 2026

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Knowledge Base Integration](#knowledge-base-integration)
3. [Frontend Integration Requirements](#frontend-integration-requirements)
4. [System Architecture Overview](#system-architecture-overview)
5. [Database Schema & Models](#database-schema--models)
6. [Services & Utilities](#services--utilities)
7. [Core Scoring Engine](#core-scoring-engine)
8. [API Endpoints Reference](#api-endpoints-reference)
9. [Implementation Checklist (Day 1)](#implementation-checklist-day-1)
10. [Implementation Checklist (Day 2)](#implementation-checklist-day-2)
11. [Testing & Validation](#testing--validation)
12. [Deployment & Configuration](#deployment--configuration)

---

## 📌 Executive Summary

**SENTINEL** is a real-time insider trading detection system for Polymarket prediction markets. The backend:

- **Indexes historical trades** via The Graph Network (GraphQL subgraph)
- **Listens to live trades** via Polygon WebSocket (OrderFilled events)
- **Enriches wallet profiles** via Etherscan v2 API (deposit history)
- **Scores each trade** against 6 insider detection factors
- **Exposes REST + WebSocket APIs** for the React frontend

**Key Technologies:**
- FastAPI (async HTTP framework)
- MongoDB + Beanie ORM (database)
- Celery + Redis (background jobs & pub/sub)
- Web3.py (Polygon RPC integration)
- The Graph & Etherscan v2 APIs (external data sources)

**Deployment Model:** Docker Compose (local) → Railway (production)

---

## 🔗 Knowledge Base Integration

### Knowledge Sources Referenced

| Document | Purpose | Key Content |
|----------|---------|-------------|
| `FLARE_BACKEND_ARCHITECTURE_v2_REVISED.md` | System architecture, data flow, services | Services layout, configuration, development checklist |
| `backend/CLAUDE.md` | Tech stack, design patterns, guidelines | Framework choices, async patterns, naming conventions |
| `backend/docs/API_KNOWLEDGE_BASE.md` | External API reference | Etherscan v2, The Graph, Polygon RPC, Polymarket Gamma |
| `DOUBTS.md` | Design decisions & clarifications | Global vs. user-intent search, scoring weights, data retention |

### Integrated Architecture Decisions

1. **Global + User-Intent Hybrid Mode** (from DOUBTS.md)
   - Support both background indexing (global) AND targeted queries (user-driven)
   - User searches for market → system fetches + scores on-demand
   - Background job periodically syncs all recent trades

2. **Etherscan v2 Migration** (from API Knowledge Base)
   - PolygonScan deprecated → using Etherscan v2 with chainid=137 parameter
   - Free API key, 5 req/sec rate limit sufficient for Celery jobs

3. **The Graph (Hosted Service)** (from API Knowledge Base)
   - No API key required, publicly available
   - `https://api.thegraph.com/subgraphs/name/polymarket/polymarket`
   - Cursor-based pagination for large datasets

4. **6-Factor Scoring** (from Architecture v2)
   - Entry Timing | Traded Few Markets | Minimum Size | Wallet Age | Concentration | Manipulability
   - Equal weighting baseline → calibration via grid search

5. **Data Retention Policy** (from DOUBTS.md)
   - Store first USDC.e deposit per wallet (not all deposits)
   - Retain all trades (no limit)
   - Markets metadata updated periodically

---

## 🎨 Frontend Integration Requirements

### Frontend Stack (from package.json)
- **Framework:** React 18.2 + React Router v6
- **Styling:** Tailwind CSS 3.4 + PostCSS + Autoprefixer
- **Charts:** Recharts 2.10 (for volume, score distribution)
- **Tables:** @tanstack/react-table 8.11 (for trade lists, wallet details)
- **Build Tool:** Vite 5.0

### Frontend Expectations for Backend API

The backend must support these user journeys:

#### **Journey 1: Market Search & Analysis**
```
User Action: Search for market (by name/slug)
  ↓
Frontend calls: GET /api/markets/search?q={query}
  ↓
Backend returns: List of markets with metadata
  ↓
User clicks market
  ↓
Frontend calls: GET /api/markets/{condition_id}/trades
  ↓
Backend returns: All trades for that market + insider scores
  ↓
Frontend displays: Table of trades, scored alerts, visualizations
```

**Backend Components Needed:**
- Market search endpoint
- Trade retrieval with scoring results
- Cache layer for performance

---

#### **Journey 2: Wallet Profiling**
```
User Action: Enter wallet address
  ↓
Frontend calls: GET /api/wallets/{address}
  ↓
Backend returns: Wallet profile (trades, deposit age, insider score)
  ↓
Frontend displays: Wallet history, risk score, trading patterns
```

**Backend Components Needed:**
- Wallet enrichment service
- Historical trade aggregation
- Score calculation

---

#### **Journey 3: Real-Time Alerts**
```
Live event on Polygon
  ↓
Backend listener catches OrderFilled event
  ↓
Backend scores in real-time
  ↓
Backend publishes to WebSocket
  ↓
Frontend receives: Alert card + updates dashboard
```

**Backend Components Needed:**
- WebSocket listener (Polygon RPC)
- Real-time scoring (Celery task)
- Redis pub/sub for alert distribution
- WebSocket manager (FastAPI)

---

### API Response Format Expectations

All responses must be JSON with consistent structure:

```json
{
  "status": "success|error",
  "data": { /* response data */ },
  "meta": {
    "timestamp": "2026-04-07T12:34:56Z",
    "request_id": "uuid"
  },
  "error": null  // or { "code": "...", "message": "..." }
}
```

### Frontend Components That Will Consume Data

Based on frontend structure (from file listing):
- **pages/**: Dashboard, MarketDetail, WalletDetail, AlertsPage
- **components/**: TradeTable, WalletCard, ScoreIndicator, MarketSearch
- **hooks/**: useMarketData, useWalletProfile, useWebSocket (will need backend support)
- **services/**: API client (will call backend endpoints)

**Key Data Models Frontend Expects:**

```typescript
// Market
{
  condition_id: string
  slug: string
  question: string
  resolution_date: timestamp
  liquidity: number
  outcomes: string[]
}

// Trade
{
  id: string
  market_id: string
  maker: string
  taker: string
  timestamp: timestamp
  amount_usdc: number
  insider_score: number
  verdict: "insider" | "suspicious" | "normal"
  factors: { /* 6 factor scores */ }
}

// Wallet
{
  address: string
  first_deposit_timestamp: timestamp
  deposit_amount_usdc: number
  wallet_age_days: number
  total_trades: number
  insider_score: number
  markets_traded: number
  average_trade_size: number
}

// Alert
{
  id: string
  wallet: string
  market_id: string
  trade_id: string
  score: number
  verdict: string
  timestamp: timestamp
  factors_fired: string[]
}
```

---

## 🏗️ System Architecture Overview

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│  │ The Graph       │  │  Etherscan v2    │  │ Polygon    │  │
│  │ (Historical)    │  │  (Wallet Age)    │  │ RPC WS     │  │
│  │                 │  │                  │  │ (Live)     │  │
│  └────────┬────────┘  └────────┬─────────┘  └─────┬──────┘  │
│           │                    │                  │          │
└───────────┼────────────────────┼──────────────────┼──────────┘
            │                    │                  │
            ▼                    ▼                  ▼
    ┌──────────────────────────────────────────────────────┐
    │          INDEXER SERVICES (Celery Tasks)             │
    ├──────────────────────────────────────────────────────┤
    │  • subgraph.py (GraphQL → Historical trades)         │
    │  • live_listener.py (WebSocket → Live trades)        │
    │  • deposit_indexer.py (Etherscan → Wallet history)   │
    │  • backfill_orchestrator.py (Coordinates pipeline)   │
    └─────────────────────┬────────────────────────────────┘
                          │
                          ▼
    ┌──────────────────────────────────────────────────────┐
    │            MONGODB DATA STORAGE (Beanie)             │
    ├──────────────────────────────────────────────────────┤
    │  Collections:                                        │
    │  • trades (OrderFilled events)                      │
    │  • wallets (enriched profiles)                      │
    │  • deposits (first USDC.e transfer)                 │
    │  • markets (metadata)                               │
    │  • insider_scores (6-factor results)                │
    └──────────────┬──────────────────┬────────────────────┘
                   │                  │
        ┌──────────┘                  └──────────────┐
        ▼                                            ▼
    ┌──────────────────────────┐        ┌────────────────────────┐
    │   SCORING ENGINE         │        │  CACHE LAYER (Redis)   │
    ├──────────────────────────┤        ├────────────────────────┤
    │  • factors.py (6 signals)│        │  • Rate limit tracking │
    │  • engine.py (composite) │        │  • Result cache        │
    │  • weights.py (tuning)   │        │  • Session storage     │
    │  • calibrate.py (grid)   │        │  • Pub/sub alerts      │
    └──────────────┬───────────┘        └────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────────────┐
    │            FASTAPI REST + WebSocket                  │
    ├──────────────────────────────────────────────────────┤
    │  Routes:                                             │
    │  • GET  /api/markets/search (market search)          │
    │  • GET  /api/markets/{id}/trades (trade list)        │
    │  • GET  /api/wallets/{address} (wallet profile)      │
    │  • GET  /api/alerts (alert history)                  │
    │  • WS   /ws/alerts (real-time stream)                │
    └──────────────┬──────────────────────────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │ React Client │
            └──────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|-----------------|
| **Indexers** | Fetch data from external sources, normalize, store in MongoDB |
| **MongoDB** | Single source of truth for all indexed data |
| **Redis** | Caching, rate limit tracking, pub/sub for real-time alerts |
| **Scoring Engine** | Analyze trades, calculate 6-factor scores, produce verdicts |
| **FastAPI** | Expose REST endpoints, WebSocket connections, request validation |

---

## 💾 Database Schema & Models

### Beanie Models (ORM)

```python
# app/models/trade.py
class Trade(Document):
    """OrderFilled event from Polymarket"""
    transaction_hash: str  # Unique identifier
    block_number: int
    timestamp: int  # Unix timestamp

    # Order details
    maker: str  # Address (lowercase)
    taker: str  # Address (lowercase)
    maker_asset_id: str  # Token ID
    taker_asset_id: str  # Token ID
    maker_amount_filled: Decimal  # Wei
    taker_amount_filled: Decimal  # Wei
    fee: Decimal  # Wei

    # Metadata
    source: str  # "historical" | "live"
    indexed_at: datetime

    class Settings:
        name = "trades"
        indexes = [
            ("timestamp", -1),
            ("maker", 1),
            ("taker", 1),
            ("taker_asset_id", 1),
            (("maker", "taker"), 1),
        ]

# app/models/wallet.py
class Wallet(Document):
    """Enriched wallet profile"""
    address: str  # Unique, lowercase

    # Deposit history
    first_deposit_timestamp: int  # Unix timestamp
    first_deposit_amount_usdc: Decimal
    wallet_age_days: float

    # Trading metrics
    total_trades: int
    total_volume_usdc: Decimal
    average_trade_size_usdc: Decimal
    markets_traded: int

    # Risk scores
    latest_insider_score: float  # 0.0-1.0
    risk_level: str  # "insider" | "suspicious" | "normal"

    # Metadata
    last_updated: datetime
    first_seen: datetime

    class Settings:
        name = "wallets"
        indexes = [
            ("address", 1),
            ("latest_insider_score", -1),
            ("risk_level", 1),
        ]

# app/models/deposit.py
class Deposit(Document):
    """First USDC.e deposit per wallet"""
    wallet_address: str  # Unique
    transaction_hash: str
    block_number: int
    timestamp: int  # Unix timestamp
    amount_usdc: Decimal

    class Settings:
        name = "deposits"
        indexes = [("wallet_address", 1)]

# app/models/market.py
class Market(Document):
    """Polymarket metadata"""
    condition_id: str  # Unique identifier
    slug: str
    question: str
    resolution_date: int  # Unix timestamp
    creator: str

    # Current state
    liquidity_usdc: Decimal
    outcomes: list[str]
    resolved: bool
    resolution: str | None  # "yes" | "no" | "no-contest"

    # Metadata
    created_at: datetime
    last_updated: datetime

    class Settings:
        name = "markets"
        indexes = [
            ("condition_id", 1),
            ("slug", 1),
            ("resolution_date", 1),
        ]

# app/models/insider_score.py
class InsiderScore(Document):
    """Scoring result for a trade"""
    trade_id: str  # Reference to Trade document
    wallet_address: str
    condition_id: str

    # 6-Factor Scores (0.0-1.0)
    factor_1_entry_timing: float  # Early entry advantage
    factor_2_few_markets: float   # Focused trading
    factor_3_size: float           # Significant position
    factor_4_wallet_age: float     # Recent wallet creation
    factor_5_concentration: float  # Portfolio concentration
    factor_6_manipulability: float # Market liquidity/size

    # Composite result
    composite_score: float  # Weighted average
    verdict: str  # "insider" | "suspicious" | "normal"
    weights_applied: dict  # { "factor_1": 0.15, ... }

    # Metadata
    calculated_at: datetime
    model_version: str  # "2.0"

    class Settings:
        name = "insider_scores"
        indexes = [
            ("trade_id", 1),
            ("wallet_address", 1),
            ("condition_id", 1),
            ("composite_score", -1),
            ("verdict", 1),
        ]

# app/models/alert.py
class Alert(Document):
    """High-score alert for frontend"""
    trade_id: str
    wallet_address: str
    condition_id: str
    insider_score_id: str

    # Alert metadata
    score: float
    verdict: str
    triggered_at: datetime
    severity: str  # "critical" | "high" | "medium"

    # Factors that contributed
    factors_fired: list[str]  # ["entry_timing", "few_markets", ...]

    class Settings:
        name = "alerts"
        indexes = [
            ("triggered_at", -1),
            ("verdict", 1),
            ("severity", 1),
        ]
```

---

## 🔧 Services & Utilities

### Service Layer (`services/`)

```python
# services/indexer/subgraph.py
"""Historical indexer via The Graph GraphQL"""
class SubgraphIndexer:
    async def fetch_orderfilledevents(
        self,
        asset_id: str,
        limit: int = 1000,
        skip: int = 0
    ) -> list[OrderFilledEvent]:
        """Query The Graph for historical trades"""

    async def fetch_all_events_paginated(
        self,
        asset_id: str,
        batch_size: int = 1000
    ) -> AsyncIterator[list[OrderFilledEvent]]:
        """Paginated fetch (cursor-based)"""

# services/indexer/live_listener.py
"""Live listener via Polygon WebSocket"""
class LiveListener:
    async def subscribe_to_orderfilledevents(self) -> None:
        """Subscribe to OrderFilled events via WebSocket"""

    async def on_event(self, event: dict) -> None:
        """Handle incoming event, publish to Celery"""

# services/indexer/deposit_indexer.py
"""Wallet deposit history via Etherscan v2"""
class DepositIndexer:
    async def fetch_first_deposit(
        self,
        wallet_address: str
    ) -> Deposit | None:
        """Get first USDC.e transfer timestamp"""

# services/market_service.py
"""Polymarket Gamma API integration"""
class MarketService:
    async def search_markets(self, query: str) -> list[Market]:
        """Search Gamma API by slug, name, or condition_id"""

    async def get_market(self, condition_id: str) -> Market:
        """Fetch single market metadata"""

    async def refresh_all_markets(self) -> None:
        """Periodic sync with Gamma API"""

# services/wallet_service.py
"""Wallet enrichment orchestration"""
class WalletService:
    async def enrich_wallet(
        self,
        wallet_address: str
    ) -> Wallet:
        """Fetch deposits, aggregate trades, calculate metrics"""
```

### Utility Layer (`utils/`)

```python
# utils/polygon_rpc.py
"""Web3.py wrapper for Polygon RPC"""
class PolygonRPC:
    def __init__(self, http_url: str, ws_url: str):
        self.http = Web3(Web3.HTTPProvider(http_url))
        self.ws = Web3(Web3.WebsocketProvider(ws_url))

    async def subscribe_to_events(
        self,
        contract_address: str,
        event_signature: str
    ) -> None:
        """Subscribe to contract events"""

# utils/etherscan.py
"""Etherscan v2 API wrapper"""
class EtherscanClient:
    def __init__(self, api_key: str, chain_id: str = "137"):
        self.api_key = api_key
        self.chain_id = chain_id

    async def get_token_transfers(
        self,
        contract_address: str,
        wallet_address: str,
        sort: str = "asc"
    ) -> list[Transfer]:
        """Fetch token transfers (USDC.e deposits)"""

# utils/constants.py
"""Smart contract constants"""
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKEN_ADDRESS = "0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3"

# Event signatures
ORDERFILLED_EVENT_SIG = "0x..."  # Keccak256("OrderFilled(...)")
```

---

## 🎯 Core Scoring Engine

### 6-Factor Insider Detection Algorithm

```python
# services/scorer/factors.py
"""Individual factor calculators"""

class FactorCalculators:
    """
    Factor 1: Entry Timing
    Score = high if trade happened shortly before resolution
    Measures: Did the wallet trade with advance knowledge?
    """
    def factor_1_entry_timing(
        self,
        trade_timestamp: int,
        resolution_timestamp: int
    ) -> float:
        days_before_resolution = (resolution_timestamp - trade_timestamp) / 86400
        if days_before_resolution < 1:
            return 1.0  # Very suspicious
        elif days_before_resolution < 7:
            return 0.7
        else:
            return 0.2

    """
    Factor 2: Few Markets Traded
    Score = high if wallet only traded 1-2 markets
    Measures: Is this a focused, targeted play?
    """
    def factor_2_few_markets(
        self,
        markets_traded: int
    ) -> float:
        if markets_traded == 1:
            return 0.9
        elif markets_traded <= 3:
            return 0.6
        else:
            return 0.1

    """
    Factor 3: Minimum Trade Size
    Score = high if trade was significant (>$5,000)
    Measures: Meaningful financial commitment
    """
    def factor_3_trade_size(
        self,
        amount_usdc: Decimal,
        wallet_avg_size: Decimal
    ) -> float:
        if amount_usdc < 5000:
            return 0.0  # Below threshold
        ratio = amount_usdc / wallet_avg_size if wallet_avg_size > 0 else 1.0
        if ratio > 2.0:
            return 0.8  # Unusually large for this wallet
        else:
            return 0.4

    """
    Factor 4: Wallet Age (NEW - Etherscan v2)
    Score = high if wallet is very new (<7 days)
    Measures: Fresh wallet = possibly alternate account
    """
    def factor_4_wallet_age(
        self,
        wallet_age_days: float,
        fresh_wallet_threshold_days: int = 7
    ) -> float:
        if wallet_age_days < fresh_wallet_threshold_days:
            return 0.9  # Very suspicious
        elif wallet_age_days < 30:
            return 0.5
        else:
            return 0.1

    """
    Factor 5: Trade Concentration
    Score = high if wallet's portfolio is concentrated on one market
    Measures: All eggs in one basket?
    """
    def factor_5_concentration(
        self,
        market_volume: Decimal,
        total_volume: Decimal
    ) -> float:
        if total_volume == 0:
            return 0.0
        ratio = market_volume / total_volume
        if ratio > 0.8:
            return 0.9  # Highly concentrated
        elif ratio > 0.5:
            return 0.6
        else:
            return 0.2

    """
    Factor 6: Market Manipulability
    Score = high if market is small/illiquid (easy to move)
    Measures: Can one trade move the market?
    """
    def factor_6_manipulability(
        self,
        market_liquidity_usdc: Decimal
    ) -> float:
        if market_liquidity_usdc < 10000:
            return 0.9  # Highly manipulable
        elif market_liquidity_usdc < 100000:
            return 0.6
        else:
            return 0.2

# services/scorer/engine.py
"""Composite scoring"""

class ScoringEngine:
    def __init__(self, weights: dict):
        self.weights = weights  # { "factor_1": 0.15, ... }

    async def score_trade(
        self,
        trade: Trade,
        wallet: Wallet,
        market: Market
    ) -> InsiderScore:
        """Calculate 6-factor score and verdict"""

        factors = FactorCalculators()

        f1 = factors.factor_1_entry_timing(
            trade.timestamp,
            market.resolution_date
        )
        f2 = factors.factor_2_few_markets(wallet.markets_traded)
        f3 = factors.factor_3_trade_size(
            trade.amount_usdc,
            wallet.average_trade_size_usdc
        )
        f4 = factors.factor_4_wallet_age(wallet.wallet_age_days)
        f5 = factors.factor_5_concentration(
            wallet.latest_trades_for_market_volume,
            wallet.total_volume_usdc
        )
        f6 = factors.factor_6_manipulability(market.liquidity_usdc)

        # Weighted composite
        composite = (
            f1 * self.weights["factor_1"] +
            f2 * self.weights["factor_2"] +
            f3 * self.weights["factor_3"] +
            f4 * self.weights["factor_4"] +
            f5 * self.weights["factor_5"] +
            f6 * self.weights["factor_6"]
        )

        # Verdict
        if composite >= 0.75:
            verdict = "insider"
        elif composite >= 0.50:
            verdict = "suspicious"
        else:
            verdict = "normal"

        return InsiderScore(
            trade_id=str(trade.id),
            wallet_address=wallet.address,
            condition_id=market.condition_id,
            factor_1_entry_timing=f1,
            factor_2_few_markets=f2,
            factor_3_size=f3,
            factor_4_wallet_age=f4,
            factor_5_concentration=f5,
            factor_6_manipulability=f6,
            composite_score=composite,
            verdict=verdict,
            weights_applied=self.weights,
        )
```

### Calibration & Weight Tuning

```python
# services/scorer/calibrate.py
"""Grid search calibration against known wallets"""

class ScoreCalibrator:
    async def grid_search(
        self,
        known_insider_wallets: list[str],
        sample_size: int = 10000
    ) -> dict:
        """
        Find optimal weights by:
        1. Testing 10,000 weight combinations
        2. Scoring trades from known insiders
        3. Selecting weights that best separate insider/normal
        """

        best_weights = None
        best_auc = 0.0

        for f1 in [0.1, 0.15, 0.2]:
            for f2 in [0.1, 0.15, 0.2]:
                for f3 in [0.05, 0.1, 0.15]:
                    for f4 in [0.15, 0.2, 0.25]:
                        for f5 in [0.2, 0.25, 0.3]:
                            f6 = 1.0 - (f1 + f2 + f3 + f4 + f5)

                            weights = {
                                "factor_1": f1,
                                "factor_2": f2,
                                "factor_3": f3,
                                "factor_4": f4,
                                "factor_5": f5,
                                "factor_6": f6,
                            }

                            # Score trades, calculate AUC
                            auc = await self._evaluate_weights(weights)

                            if auc > best_auc:
                                best_auc = auc
                                best_weights = weights

        return best_weights

# Save optimal weights to config
```

---

## 📡 API Endpoints Reference

### Market Endpoints

```python
# routers/markets.py

@router.get("/api/markets/search")
async def search_markets(
    q: str,
    limit: int = 20,
    offset: int = 0
) -> dict:
    """
    Search markets by slug, name, or condition_id

    Returns:
    {
        "status": "success",
        "data": [
            {
                "condition_id": "0x...",
                "slug": "will-spain-win-fifa-2026",
                "question": "Will Spain win the FIFA 2026 World Cup?",
                "resolution_date": 1735689600,
                "liquidity_usdc": 50000.0,
                "outcomes": ["YES", "NO"]
            }
        ]
    }
    """

@router.get("/api/markets/{condition_id}/trades")
async def get_market_trades(
    condition_id: str,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """
    Get all trades for a market with insider scores

    Returns:
    {
        "status": "success",
        "data": {
            "market": { /* market data */ },
            "trades": [
                {
                    "id": "tx_hash",
                    "maker": "0x...",
                    "taker": "0x...",
                    "timestamp": 1680000000,
                    "amount_usdc": 10000.0,
                    "insider_score": 0.82,
                    "verdict": "insider",
                    "factors": {
                        "entry_timing": 0.95,
                        "few_markets": 0.60,
                        "size": 0.70,
                        "wallet_age": 0.85,
                        "concentration": 0.80,
                        "manipulability": 0.75
                    }
                }
            ],
            "pagination": {
                "total": 1500,
                "limit": 100,
                "offset": 0
            }
        }
    }
    """
```

### Wallet Endpoints

```python
# routers/wallets.py

@router.get("/api/wallets/{address}")
async def get_wallet_profile(
    address: str
) -> dict:
    """
    Get enriched wallet profile

    Returns:
    {
        "status": "success",
        "data": {
            "address": "0x...",
            "wallet_age_days": 15.5,
            "first_deposit_timestamp": 1680000000,
            "first_deposit_amount_usdc": 5000.0,
            "total_trades": 12,
            "total_volume_usdc": 120000.0,
            "average_trade_size_usdc": 10000.0,
            "markets_traded": 3,
            "latest_insider_score": 0.72,
            "risk_level": "suspicious",
            "trades": [
                { /* trade details */ }
            ]
        }
    }
    """
```

### Alerts Endpoints

```python
# routers/alerts.py

@router.get("/api/alerts")
async def get_alerts(
    verdict: str | None = None,  # "insider", "suspicious", "normal"
    severity: str | None = None,  # "critical", "high", "medium"
    limit: int = 50,
    offset: int = 0
) -> dict:
    """
    Get alert history

    Returns:
    {
        "status": "success",
        "data": [
            {
                "id": "alert_id",
                "trade_id": "tx_hash",
                "wallet_address": "0x...",
                "condition_id": "0x...",
                "score": 0.85,
                "verdict": "insider",
                "triggered_at": "2026-04-07T12:34:56Z",
                "severity": "high",
                "factors_fired": ["entry_timing", "wallet_age", "concentration"]
            }
        ]
    }
    """

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket) -> None:
    """
    Real-time WebSocket feed of alerts

    Message format:
    {
        "type": "alert",
        "data": { /* alert object */ }
    }
    """
```

---

## ✅ Implementation Checklist (Day 1)

### Morning (4 hours): Foundation

- [ ] **Config & Initialization**
  - [ ] Create `config.py` with Pydantic BaseSettings
  - [ ] Load environment variables from `.env`
  - [ ] Create `database.py` with MongoDB Beanie client
  - [ ] Create `redis_client.py` with Redis connection pool
  - [ ] Create `constants.py` with contract addresses, ABIs, event signatures

- [ ] **Beanie Models (ORM)**
  - [ ] `models/trade.py` - Trade document + indexes
  - [ ] `models/wallet.py` - Wallet document + indexes
  - [ ] `models/deposit.py` - Deposit document + indexes
  - [ ] `models/market.py` - Market document + indexes
  - [ ] `models/insider_score.py` - InsiderScore document + indexes
  - [ ] `models/alert.py` - Alert document + indexes

- [ ] **Utility Wrappers**
  - [ ] `utils/polygon_rpc.py` - Web3.py wrapper for RPC + WebSocket
  - [ ] `utils/etherscan.py` - Etherscan v2 API client (tokentx, balance, etc.)
  - [ ] Test Etherscan connectivity (run tester.py)

### Afternoon (4 hours): Data Ingestion

- [ ] **Indexer Services**
  - [ ] `services/indexer/subgraph.py` - The Graph GraphQL queries
    - [ ] `fetch_orderfilledevents()` - Single batch
    - [ ] `fetch_all_events_paginated()` - Cursor-based pagination
    - [ ] Test with real query (verify response format)

  - [ ] `services/indexer/deposit_indexer.py` - Etherscan wallet deposits
    - [ ] `fetch_first_deposit()` - Get first USDC.e transfer
    - [ ] Handle error cases (no transfers, API rate limit)

  - [ ] `services/market_service.py` - Polymarket Gamma API
    - [ ] `search_markets()` - Gamma API search endpoint
    - [ ] `get_market()` - Single market fetch
    - [ ] Parse market metadata

  - [ ] `services/wallet_service.py` - Orchestration
    - [ ] `enrich_wallet()` - Aggregate deposits + trades + metrics

- [ ] **API Routes (Part 1)**
  - [ ] `routers/markets.py`
    - [ ] GET `/api/markets/search?q={query}`
    - [ ] GET `/api/markets/{condition_id}/trades`
  - [ ] Connect FastAPI app to routers
  - [ ] Add CORS middleware for frontend (http://localhost:3000)

### Evening (2 hours): Testing

- [ ] Run The Graph query manually, verify format
- [ ] Run Etherscan API call manually, verify format
- [ ] Start MongoDB + Redis locally
- [ ] Test market search endpoint (curl / Postman)
- [ ] Test trade listing endpoint
- [ ] Verify database inserts work

---

## ✅ Implementation Checklist (Day 2)

### Morning (4 hours): Scoring Engine

- [ ] **Scoring Implementation**
  - [ ] `services/scorer/factors.py` - All 6 factor functions
    - [ ] Factor 1: Entry Timing
    - [ ] Factor 2: Few Markets
    - [ ] Factor 3: Trade Size
    - [ ] Factor 4: Wallet Age (uses Etherscan deposits)
    - [ ] Factor 5: Concentration
    - [ ] Factor 6: Manipulability

  - [ ] `services/scorer/engine.py` - Composite scoring
    - [ ] `score_trade()` - Run all 6 factors, apply weights, return verdict

  - [ ] `services/scorer/weights.py` - Weight configuration
    - [ ] Define baseline weights (equal: 0.167 each, or research-backed)
    - [ ] Weight categories (by market condition, liquidity, etc.)

  - [ ] `services/scorer/calibrate.py` - Calibration
    - [ ] Grid search over weight combinations
    - [ ] Evaluate against known insider samples
    - [ ] Save optimal weights

- [ ] **Celery Background Tasks**
  - [ ] `app/celery_app.py` - Celery initialization
  - [ ] `tasks/enrich_wallets.py` - Async wallet enrichment
  - [ ] `tasks/score_market.py` - Score all trades in a market
  - [ ] `tasks/live_score.py` - Score new OrderFilled event in real-time
  - [ ] `tasks/refresh_markets.py` - Periodic market metadata refresh

- [ ] **API Routes (Part 2)**
  - [ ] `routers/wallets.py`
    - [ ] GET `/api/wallets/{address}`
  - [ ] `routers/alerts.py`
    - [ ] GET `/api/alerts?verdict={verdict}&severity={severity}`

### Afternoon (3 hours): Real-Time & WebSocket

- [ ] **Live Event Listener**
  - [ ] `services/indexer/live_listener.py` - WebSocket subscription
    - [ ] Subscribe to Polygon WS
    - [ ] Listen for OrderFilled events
    - [ ] Trigger Celery task on event

  - [ ] `routers/ws.py` - WebSocket manager
    - [ ] WS `/ws/alerts` endpoint
    - [ ] Redis pub/sub subscription
    - [ ] Broadcast alerts to connected clients

- [ ] **Orchestration**
  - [ ] `services/indexer/backfill.py` - Coordinate full pipeline
    - [ ] Fetch markets → trades → wallets → scores → alerts

- [ ] **API Route (Part 3)**
  - [ ] WS `/ws/alerts` - Real-time alert feed

### Evening (3 hours): Integration & Testing

- [ ] **End-to-End Testing**
  - [ ] Start Docker Compose (MongoDB, Redis, FastAPI, Celery)
  - [ ] Run tester.py to validate external APIs
  - [ ] Search for a real market (via GET /api/markets/search)
  - [ ] Fetch trades for that market (via GET /api/markets/{id}/trades)
  - [ ] Verify trades have insider scores
  - [ ] Fetch wallet profile (via GET /api/wallets/{address})
  - [ ] Subscribe to WebSocket, trigger live event, verify alert

- [ ] **Frontend Integration**
  - [ ] Verify CORS headers allow frontend requests
  - [ ] Test API endpoints from React frontend
  - [ ] Verify response format matches frontend expectations

- [ ] **Documentation**
  - [ ] Write `BACKEND_README.md` with setup + deployment steps
  - [ ] Document all endpoints in OpenAPI/Swagger
  - [ ] Create sample API requests (curl/Postman)

- [ ] **Deployment Preparation** (optional)
  - [ ] Create docker-compose.yml
  - [ ] Create Dockerfile for backend
  - [ ] Prepare Railway deployment config
  - [ ] Set environment variables for production

---

## 🧪 Testing & Validation

### Unit Tests

```python
# tests/unit/test_factors.py
def test_factor_1_entry_timing():
    calculator = FactorCalculators()

    # 1 day before resolution = score 1.0
    trade_ts = 1000000
    resolution_ts = 1000000 + (1 * 86400)
    assert calculator.factor_1_entry_timing(trade_ts, resolution_ts) == 1.0

    # 7 days before = score 0.7
    resolution_ts = 1000000 + (7 * 86400)
    assert calculator.factor_1_entry_timing(trade_ts, resolution_ts) == 0.7

# tests/unit/test_wallet_service.py
@pytest.mark.asyncio
async def test_enrich_wallet():
    service = WalletService()
    wallet = await service.enrich_wallet("0x1234...")

    assert wallet.address == "0x1234..."
    assert wallet.first_deposit_timestamp > 0
    assert wallet.total_trades >= 0

# tests/unit/test_scoring_engine.py
@pytest.mark.asyncio
async def test_score_trade():
    engine = ScoringEngine(weights={
        "factor_1": 0.15,
        "factor_2": 0.15,
        # ...
    })

    trade = Trade(...)
    wallet = Wallet(...)
    market = Market(...)

    score = await engine.score_trade(trade, wallet, market)

    assert 0.0 <= score.composite_score <= 1.0
    assert score.verdict in ["insider", "suspicious", "normal"]
```

### Integration Tests

```python
# tests/integration/test_api_markets.py
@pytest.mark.asyncio
async def test_search_markets():
    client = TestClient(app)
    response = client.get("/api/markets/search?q=spain")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) > 0

@pytest.mark.asyncio
async def test_get_market_trades():
    client = TestClient(app)
    response = client.get("/api/markets/0x123/trades")

    assert response.status_code == 200
    data = response.json()
    assert "market" in data["data"]
    assert "trades" in data["data"]
    assert all("insider_score" in t for t in data["data"]["trades"])

# tests/integration/test_websocket.py
@pytest.mark.asyncio
async def test_websocket_alerts():
    client = TestClient(app)
    with client.websocket_connect("/ws/alerts") as websocket:
        # Trigger a live event
        # Receive alert via WebSocket
        data = websocket.receive_json()
        assert data["type"] == "alert"
```

### Validation Checklist

- [ ] All 6 factors return values 0.0-1.0 ✓
- [ ] Composite score is weighted average ✓
- [ ] Verdict correctly maps scores to categories ✓
- [ ] Market search returns valid results ✓
- [ ] Trade scores are persisted in MongoDB ✓
- [ ] Wallet profiles are enriched with deposit info ✓
- [ ] WebSocket broadcasts real-time alerts ✓
- [ ] CORS headers allow frontend requests ✓
- [ ] Error responses include proper status codes ✓
- [ ] Rate limiting respects Etherscan 5 req/sec ✓

---

## ⚙️ Deployment & Configuration

### Local Development Setup

```bash
# 1. Clone repo
git clone <repo> && cd insider-trader-detection-assignment

# 2. Create .env file
cp backend/.env.example backend/.env
# Edit with your Etherscan API key

# 3. Start services
docker-compose up -d

# 4. Run tester
cd backend && python tester.py

# 5. Start indexing (optional background job)
docker-compose exec celery_worker celery -A app.tasks.celery_app worker --loglevel=info

# 6. Frontend
cd frontend && npm run dev
```

### Environment Variables (.env)

```dotenv
# ─────────────────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────────────────
APP_ENV=development
API_PORT=8000
SECRET_KEY=your_random_64_char_secret_key_here
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ─────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────
MONGODB_URL=mongodb://localhost:27017/sentinel_insider
MONGODB_DB_NAME=sentinel_insider

# ─────────────────────────────────────────────────────────
# CACHE & BROKER
# ─────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ─────────────────────────────────────────────────────────
# EXTERNAL APIs
# ─────────────────────────────────────────────────────────
# Etherscan v2 (required)
ETHERSCAN_API_KEY=your_free_api_key_here
ETHERSCAN_API_URL=https://api.etherscan.io/v2/api

# The Graph (no key required for hosted service)
POLYMARKET_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/polymarket/polymarket

# Polymarket APIs (public)
POLYMARKET_GAMMA_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_URL=https://clob.polymarket.com

# Polygon Network (public)
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGON_WS_URL=wss://polygon-bor-rpc.publicnode.com

# ─────────────────────────────────────────────────────────
# CONTRACT ADDRESSES (Polygon)
# ─────────────────────────────────────────────────────────
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
USDC_E_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
CONDITIONAL_TOKEN_ADDRESS=0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3

# ─────────────────────────────────────────────────────────
# SCORING PARAMETERS
# ─────────────────────────────────────────────────────────
MIN_TRADE_SIZE_USDC=5000
INSIDER_THRESHOLD=0.75
SUSPICIOUS_THRESHOLD=0.50
FRESH_WALLET_DAYS=7

# Default weights (equal distribution)
FACTOR_1_WEIGHT=0.167
FACTOR_2_WEIGHT=0.167
FACTOR_3_WEIGHT=0.167
FACTOR_4_WEIGHT=0.167
FACTOR_5_WEIGHT=0.166
FACTOR_6_WEIGHT=0.166
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: "3.8"

services:
  mongodb:
    image: mongo:6.0
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_DATABASE: sentinel_insider
    volumes:
      - mongodb_data:/data/db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongodb:27017/sentinel_insider
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - mongodb
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  celery_worker:
    build: ./backend
    environment:
      - MONGODB_URL=mongodb://mongodb:27017/sentinel_insider
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - mongodb
      - redis
    command: celery -A app.tasks.celery_app worker --loglevel=info

volumes:
  mongodb_data:
```

---

## 📚 Key Documents to Reference

| Document | When to Reference |
|----------|-------------------|
| `FLARE_BACKEND_ARCHITECTURE_v2_REVISED.md` | Implementation layout, service responsibilities |
| `backend/CLAUDE.md` | Design patterns, tech stack, guidelines |
| `backend/docs/API_KNOWLEDGE_BASE.md` | External API details, query examples, rate limits |
| `DOUBTS.md` | Architecture decisions, clarifications |

---

## 🚀 Success Criteria

By end of Day 2, the system should:

1. ✅ Index historical trades from The Graph
2. ✅ Listen to live OrderFilled events from Polygon
3. ✅ Fetch wallet deposit history from Etherscan v2
4. ✅ Store all data in MongoDB (trades, wallets, deposits, markets)
5. ✅ Calculate 6-factor insider scores for each trade
6. ✅ Expose REST API for market search, trade listing, wallet profiles
7. ✅ Expose WebSocket feed for real-time alerts
8. ✅ Support both targeted queries and background indexing
9. ✅ Return properly formatted JSON responses
10. ✅ Allow CORS requests from React frontend (port 3000)

---

## 📞 Quick Reference: Key Files

```
backend/
├── app/
│   ├── main.py                    # FastAPI app + routers
│   ├── config.py                  # Pydantic settings
│   ├── database.py                # MongoDB client
│   ├── redis_client.py            # Redis connection
│   ├── models/                    # Beanie documents
│   │   ├── trade.py
│   │   ├── wallet.py
│   │   ├── deposit.py
│   │   ├── market.py
│   │   ├── insider_score.py
│   │   └── alert.py
│   ├── services/                  # Business logic
│   │   ├── indexer/
│   │   │   ├── subgraph.py
│   │   │   ├── live_listener.py
│   │   │   ├── deposit_indexer.py
│   │   │   └── backfill.py
│   │   ├── scorer/
│   │   │   ├── factors.py
│   │   │   ├── engine.py
│   │   │   ├── weights.py
│   │   │   └── calibrate.py
│   │   ├── market_service.py
│   │   └── wallet_service.py
│   ├── routers/                   # API endpoints
│   │   ├── markets.py
│   │   ├── wallets.py
│   │   ├── alerts.py
│   │   └── ws.py
│   ├── tasks/                     # Celery background jobs
│   │   ├── enrich_wallets.py
│   │   ├── score_market.py
│   │   ├── live_score.py
│   │   └── refresh_markets.py
│   ├── utils/                     # Helpers
│   │   ├── polygon_rpc.py
│   │   ├── etherscan.py
│   │   └── constants.py
│   └── celery_app.py              # Celery config
├── tests/
│   ├── unit/
│   └── integration/
├── .env                           # Environment variables
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container image
└── tester.py                      # Connectivity validation

frontend/
├── src/
│   ├── pages/                     # Page components
│   ├── components/                # Reusable components
│   ├── services/                  # API client
│   ├── hooks/                     # Custom React hooks
│   └── utils/                     # Helper functions
└── package.json                   # Node dependencies
```

---

## 🎓 Learning Resources

- **FastAPI:** https://fastapi.tiangelo.com
- **Beanie ORM:** https://beanie-odm.readthedocs.io
- **Celery:** https://docs.celeryproject.io
- **Web3.py:** https://web3py.readthedocs.io
- **The Graph:** https://thegraph.com/docs
- **Etherscan v2:** https://docs.etherscan.io

---

**Document Status:** Complete & Ready for Development
**Last Updated:** April 7, 2026
**Next Step:** Begin Day 1 Morning implementation with config + models
