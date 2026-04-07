# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SENTINEL** — Insider Trading Detection System for Polymarket

A FastAPI backend that detects suspicious insider trading activity on Polymarket prediction markets by:
1. Ingesting on-chain order data from Polymarket's CLOB and TheGraph subgraph
2. Fetching blockchain transaction history from Etherscan
3. Analyzing trading patterns (entry timing, concentration, wallet age, market coverage, trade size)
4. Scoring wallets against configurable insider likelihood thresholds
5. Running async analysis jobs via Celery workers

## Tech Stack & Key Dependencies

- **Framework**: FastAPI 0.111.0 + Uvicorn
- **Async Job Queue**: Celery 5.4.0 (Redis broker)
- **Database**: MongoDB (motor async driver, beanie ORM)
- **Caching & Broker**: Redis 5.0.4
- **Blockchain Integration**: web3.py 6.19.0, Etherscan API
- **External APIs**: Polymarket Gamma API, Goldsky GraphQL Subgraph
- **Config Management**: Pydantic 2.7.1, python-dotenv
- **WebSockets**: websockets 12.0
- **HTTP Client**: httpx 0.27.0
- **Python**: 3.11+

## Development & Setup

### Environment

Create/update `.env` in the backend directory. Critical variables:
- `MONGODB_URL` — MongoDB connection string (default: `mongodb://localhost:27017/sentinel_insider`)
- `REDIS_URL` — Redis connection string (default: `redis://localhost:6379/0`)
- `ETHERSCAN_API_KEY` — Etherscan API key (required for transaction lookups)
- `POLYMARKET_SUBGRAPH_URL` — Goldsky GraphQL subgraph endpoint
- `POLYGON_RPC_URL` — Polygon RPC for on-chain queries
- `INSIDER_THRESHOLD` / `SUSPICIOUS_THRESHOLD` — Scoring cutoffs (0.0–1.0)
- `MIN_TRADE_SIZE_USDC` — Minimum trade size for analysis filter

See `.env` (in repo) for full list and defaults.

### Running the Backend

**From the repository root:**

```bash
# Start all services (MongoDB, Redis, FastAPI, Celery worker)
docker-compose up -d

# Verify connectivity to external services
cd backend && python tester.py

# View logs
docker-compose logs -f backend
docker-compose logs -f celery_worker
```

**Local development (without Docker):**

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB and Redis separately, then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Celery worker:
celery -A app.tasks.celery_app worker --loglevel=info
```

### Testing Connectivity

Use the bundled tester to validate all external service connections:

```bash
python tester.py
```

This checks MongoDB, Redis, Polymarket Gamma API, Goldsky subgraph, Polygon RPC, and Etherscan API health.

## Architecture & Key Modules

The backend does not yet exist as an app module — it will be scaffolded with this structure:

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic settings loader from .env
│   ├── models/              # Beanie MongoDB schemas
│   ├── routers/             # API endpoint groups
│   ├── services/            # Business logic (data fetch, scoring)
│   ├── tasks/               # Celery async job definitions
│   └── utils/               # Helpers (blockchain, API clients)
├── tests/
│   ├── unit/                # Unit tests (services, utils)
│   └── integration/         # Integration tests (API endpoints)
├── Dockerfile
├── requirements.txt
└── tester.py                # Connectivity checker
```

### Key Design Patterns (To Be Implemented)

1. **Async Throughout** — Use `async def` for all I/O-bound operations (API calls, DB queries).
2. **Config Validation** — Use Pydantic to validate environment variables at startup.
3. **Separation of Concerns**:
   - `services/` — External API integration, data fetching, business logic
   - `routers/` — HTTP request handling, response serialization
   - `tasks/` — Long-running async jobs (indexing, scoring sweeps)
4. **Celery for Background Work** — Offload heavy compute (wallet scoring, bulk analysis) to worker processes.
5. **MongoDB Collections** (via Beanie):
   - `wallets` — Wallet profiles with insider scores and metadata
   - `trades` — Parsed order fill events
   - `markets` — Polymarket market definitions
   - `deposits` — USDC.e deposit timelines per wallet

## Insider Scoring Algorithm

The core scoring mechanism combines five signals into a 0.0–1.0 insider probability:

1. **Entry Timing** — Did the wallet trade before resolution, and if so, how early?
2. **Trade Concentration** — What % of the wallet's liquidity was on one market?
3. **Wallet Age** — How long before the trade was the wallet created/funded?
4. **Market Coverage** — Did this wallet trade only one market, or several?
5. **Trade Size** — What was the position size relative to the wallet's average?

Thresholds are configurable:
- `INSIDER_THRESHOLD` (e.g., 0.75) — Flag as highly suspicious
- `SUSPICIOUS_THRESHOLD` (e.g., 0.50) — Flag as moderately suspicious

## External Service Integration

### Polymarket APIs

- **Gamma API** (`https://gamma-api.polymarket.com`) — Market metadata, order history
- **CLOB** (`https://clob.polymarket.com`) — Real-time order book, trade fills
- **Goldsky Subgraph** — GraphQL for historical order fill events (indexed from The Graph)

### Blockchain Data

- **Etherscan API** (`https://api.etherscan.io/v2/api`) — Transaction history, wallet creation, contract interactions
- **Polygon RPC** — On-chain balance queries, contract calls

### Data Flow

1. **Fetch Market Orders** — Call Polymarket Gamma API or Subgraph for order fills
2. **Extract Wallets** — Parse unique trader addresses from order data
3. **Query Blockchain** — Etherscan for wallet creation time, USDC.e deposit history
4. **Score Wallets** — Run insider detection algorithm on each wallet
5. **Store Results** — Persist wallets, trades, markets to MongoDB
6. **Cache** — Use Redis for intermediate results, rate-limit tracking

## Development Guidelines

### Code Style

- **Formatting**: Run Prettier (or `black` for Python)
- **Linting**: Use ESLint/Pylint; follow PEP 8
- **Line Length**: 100 characters max
- **Indentation**: 2 spaces (or 4 for Python conventions)

### Naming Conventions

- **Files**: `kebab_case.py` (snake_case for Python)
- **Functions/Variables**: `camelCase` (or `snake_case` per Python convention)
- **Constants**: `UPPER_SNAKE_CASE`
- **Classes**: `PascalCase`
- **Database Collections**: `snake_case` (e.g., `insider_wallets`)

### API Standards

- **Endpoints**: RESTful, prefixed with `/api/v1/`
- **Request/Response**: JSON only
- **Status Codes**: Use correct HTTP status codes (200, 201, 400, 404, 500, etc.)
- **Documentation**: Docstrings for all endpoints; consider FastAPI auto-docs at `/docs`

### Testing Requirements

- Minimum 80% code coverage (unit + integration)
- Test filenames: `test_*.py` or `*_test.py`
- Use `pytest` or FastAPI's `TestClient` for endpoint testing
- Integration tests hit a real (containerized) MongoDB and Redis; do not mock external services unless testing error handling

### Important: Etherscan Migration

**PolygonScan has been replaced by Etherscan.** All blockchain data lookups (transaction history, wallet creation, contract interactions) must use the Etherscan API v2 (`https://api.etherscan.io/v2/api`). The API key is in `.env` as `ETHERSCAN_API_KEY`.

## Known Issues & Open Questions

Refer to `DOUBTS.md` in the parent directory for architectural decisions on:

- **Global vs. User-Intent Search**: Should the system ingest all trades globally or respond to user-driven queries?
- **Targeted Query Mode**: Support ad-hoc market/wallet lookups vs. continuous background indexing?
- **Scoring Weights**: Are the five insider signals equally weighted, or does a preferred weighting apply?
- **Data Retention**: Should the system store all historical deposits, or only the first-ever deposit per wallet?

## Docker & Deployment

The project uses Docker Compose for local development. All services (MongoDB, Redis, FastAPI, Celery) are defined in `docker-compose.yml` at the project root.

For production:
- Build the backend image: `docker build -t sentinel_backend ./backend`
- Push to registry and deploy via Kubernetes or orchestration tool
- Ensure environment variables are injected securely (not hardcoded in image)
- Enable health checks on all containers
- Set up monitoring/alerting on Celery worker queues and MongoDB connection pooling

## Useful Commands

| Command | Purpose |
|---------|---------|
| `docker-compose up -d` | Start all services |
| `docker-compose down` | Stop all services |
| `docker-compose logs -f backend` | Stream backend logs |
| `python tester.py` | Test external service connectivity |
| `pip install -r requirements.txt` | Install dependencies locally |
| `uvicorn app.main:app --reload` | Run FastAPI with auto-reload (dev only) |
| `celery -A app.tasks.celery_app worker --loglevel=info` | Run Celery worker locally |

## References

- **Assignment**: See `Insider Trading Detection Assignment.pdf` in project root
- **External APIs**: Polymarket docs, Etherscan API v2 docs, Goldsky docs
- **FastAPI**: https://fastapi.tiangolo.com
- **Beanie ORM**: https://beanie-odm.readthedocs.io
- **Celery**: https://docs.celeryproject.io
