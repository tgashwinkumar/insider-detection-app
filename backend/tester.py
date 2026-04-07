"""
SENTINEL — API & Service Connectivity Tester
Run manually: python backend/tester.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env from backend/.env relative to this file
env_path = Path(__file__).parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
except ImportError:
    print("[WARN] python-dotenv not installed. Reading OS environment only.")

# ── Config ────────────────────────────────────────────────────────────────────
MONGODB_URL             = os.getenv("MONGODB_URL", "mongodb://localhost:27017/sentinel_insider")
REDIS_URL               = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POLYMARKET_GAMMA_URL    = os.getenv("POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com")
POLYMARKET_SUBGRAPH_URL = os.getenv("POLYMARKET_SUBGRAPH_URL", "")
POLYGON_RPC_URL         = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
POLYGON_WS_URL          = os.getenv("POLYGON_WS_URL", "wss://polygon-bor-rpc.publicnode.com")
POLYMARKET_CLOB_URL     = os.getenv("POLYMARKET_CLOB_URL", "https://clob.polymarket.com")
ETHERSCAN_API_KEY       = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_API_URL       = os.getenv("ETHERSCAN_API_URL", "https://api.etherscan.io/v2/api")
THEGRAPH_API_KEY        = os.getenv("THEGRAPH_API_KEY", "")

# ── Result store ──────────────────────────────────────────────────────────────
results = []  # (name, status, reason, required)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def record(name, status, reason, required=True):
    results.append((name, status, reason, required))


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_mongodb():
    name = "MongoDB"
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        client.server_info()
        record(name, PASS, "Connected successfully")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


def test_redis():
    name = "Redis"
    try:
        import redis as redis_lib
        client = redis_lib.from_url(REDIS_URL)
        result = client.ping()
        if result:
            record(name, PASS, "Ping OK")
        else:
            record(name, FAIL, "Ping returned False")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


def test_gamma_api():
    name = "Polymarket Gamma API"
    try:
        import httpx
        r = httpx.get(f"{POLYMARKET_GAMMA_URL}/markets?limit=1", timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 1:
                record(name, PASS, f"200 OK — {len(data)} market returned")
            else:
                record(name, FAIL, f"200 OK but empty or unexpected format")
        else:
            record(name, FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


# def test_subgraph():
#     name = "Goldsky Subgraph (GraphQL)"
#     if not POLYMARKET_SUBGRAPH_URL:
#         record(name, SKIP, "No subgraph URL configured")
#         return
#     try:
#         import httpx
#         query = '{ orderFilledEvents(first: 1) { id } }'
#         r = httpx.post(POLYMARKET_SUBGRAPH_URL, json={"query": query}, timeout=10)
#         if r.status_code == 200:
#             data = r.json()
#             events = data.get("data", {}).get("orderFilledEvents")
#             if isinstance(events, list):
#                 record(name, PASS, "orderFilledEvents accessible")
#             else:
#                 record(name, FAIL, f"Unexpected response structure: {str(data)[:60]}")
#         elif r.status_code == 404:
#             record(name, FAIL, "Subgraph endpoint not found (404) — may be deleted or URL is invalid")
#         else:
#             record(name, FAIL, f"HTTP {r.status_code}")
#     except Exception as e:
#         record(name, FAIL, str(e)[:80])

def test_subgraph():
    name = "The Graph"
    try:
        import httpx
        
        # The Graph Network endpoint for Polymarket
        subgraph_url = f"https://gateway.thegraph.com/api/{THEGRAPH_API_KEY}/subgraphs/id/EZCTgSzLPuBSqQcuR3ifeiKHKBnpjHSNbYpty8Mnjm9D"
        
        query = '{ orderFilleds(first: 5) { id orderHash maker taker } negRiskCtfExchangeOrderFilleds(first: 5) { id orderHash maker taker } }'
        
        headers = {
            "Content-Type": "application/json",
            # "Authorization": f"Bearer {THEGRAPH_API_KEY}"
            # "Authorization": f"Bearer 1e8ca4741dd5cd3726e2423ee784265a"   
        }
        
    
        
        r = httpx.post(
            subgraph_url, 
            json={"query": query, "operationName": "Subgraphs", "variables": {}}, 
            headers=headers,
            timeout=10
        )
        
        if r.status_code == 200:
            data = r.json()
            
            # Check for GraphQL errors
            if "errors" in data and data["errors"]:
                record(name, FAIL, f"GraphQL error: {data['errors'][0].get('message', 'Unknown error')[:60]}")
                return
            
            events = data.get("data", {}).get("orderFilleds")
            record(name, PASS, f"orderFilledEvents accessible — {len(events)} events returned")
            
        elif r.status_code == 404:
            record(name, FAIL, "Subgraph endpoint not found (404) — URL may be invalid")
        else:
            record(name, FAIL, f"HTTP {r.status_code}: {r.text[:60]}")
    
    except Exception as e:
        record(name, FAIL, str(e)[:100])

def test_polygon_rpc():
    name = "Polygon Public RPC"
    try:
        import httpx
        payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}

        # Try primary RPC first
        rpc_urls = [
            POLYGON_RPC_URL,
            "https://rpc.ankr.com/polygon",  # Fallback: Ankr RPC
            "https://polygon.rpc.thirdweb.com"  # Fallback: Thirdweb RPC
        ]

        for rpc_url in rpc_urls:
            try:
                r = httpx.post(rpc_url, json=payload, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    block_hex = data.get("result", "")
                    if block_hex and block_hex.startswith("0x"):
                        block_num = int(block_hex, 16)
                        record(name, PASS, f"{rpc_url} worked: Block #{block_num:,}")
                        return
                    elif "error" not in data:
                        record(name, FAIL, f"Unexpected result: {block_hex}")
                        return
            except (httpx.TimeoutException, httpx.ConnectError):
                continue

        record(name, FAIL, "All RPC endpoints failed or disabled")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


def test_etherscan():
    name = "Etherescan API"
    if not ETHERSCAN_API_KEY :
        record(name, SKIP, "No key set. Get free key at polygonscan.com/apis")
        return
    try:
        import httpx
        # Use PolygonScan API V2 endpoint (V1 is deprecated)
        url = f"https://api.etherscan.io/v2/api?apikey={ETHERSCAN_API_KEY}&chainid=42161&module=account&action=txlist&address=0x2449ecef5012f0a0e153b278ef4fcc9625bc4c78&page=-1"

        r = httpx.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "1":
                record(name, PASS, "200 OK — API key valid")
            else:
                msg = data.get("message", "Unknown error")
                record(name, FAIL, f"API returned status!=1: {msg}")
        else:
            record(name, FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


def test_clob_api():
    name = "Polymarket CLOB API"
    try:
        import httpx
        r = httpx.get(f"https://gamma-api.polymarket.com/markets/slug/us-iran-nuclear-deal-by-april-30", timeout=10)
        if r.status_code == 200:
            # print(r.json())
            record(name, PASS, "200 OK")
        else:
            record(name, FAIL, f"HTTP {r.status_code}")
    except Exception as e:
        record(name, FAIL, str(e)[:80])


async def _ws_connect():
    import websockets
    async with websockets.connect(POLYGON_WS_URL, open_timeout=5) as ws:
        return True


def test_polygon_ws():
    name = "Polygon WebSocket"
    try:
        asyncio.run(asyncio.wait_for(_ws_connect(), timeout=5))
        record(name, PASS, "Handshake succeeded", required=False)
    except asyncio.TimeoutError:
        record(name, FAIL, "Timeout after 5s", required=False)
    except Exception as e:
        record(name, FAIL, str(e)[:80], required=False)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all():
    test_mongodb()
    test_redis()
    test_gamma_api()
    test_subgraph()
    test_polygon_rpc()
    test_etherscan()
    test_clob_api()
    test_polygon_ws()


# ── Printer ───────────────────────────────────────────────────────────────────

STATUS_COLOR = {PASS: "\033[32m", FAIL: "\033[31m", SKIP: "\033[33m"}
RESET = "\033[0m"


def print_results():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║       SENTINEL — API & SERVICE CONNECTIVITY TEST     ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    action_items = []

    for name, status, reason, required in results:
        color = STATUS_COLOR.get(status, "")
        tag = f"[{status}]"
        padded_name = name.ljust(30)
        print(f"  {color}{tag}{RESET} {padded_name} {reason}")
        if status in (FAIL, SKIP) and required:
            action_items.append((name, status, reason))
        elif status == FAIL and not required:
            action_items.append((name, status, reason))

    # Summary
    required_results = [(s, r) for _, s, _, r in results if r]
    optional_results = [(s, r) for _, s, _, r in results if not r]

    req_pass = sum(1 for s, _ in required_results if s == PASS)
    req_fail = sum(1 for s, _ in required_results if s == FAIL)
    req_skip = sum(1 for s, _ in required_results if s == SKIP)
    opt_pass = sum(1 for s, _ in optional_results if s == PASS)
    opt_fail = sum(1 for s, _ in optional_results if s == FAIL)

    print()
    print("══════════════════════════════════════════════════════")
    print(f"  REQUIRED   →  {req_pass} PASS  |  {req_fail} FAIL  |  {req_skip} SKIP")
    print(f"  OPTIONAL   →  {opt_pass} PASS  |  {opt_fail} FAIL")
    print("══════════════════════════════════════════════════════")

    all_required_ok = req_fail == 0
    if all_required_ok:
        print("  STATUS: \033[32m✅ READY TO BUILD\033[0m")
    else:
        print("  STATUS: \033[31m❌ NOT READY — fix required services above\033[0m")

    if action_items:
        print()
        print("  ACTION ITEMS:")
        for name, status, reason in action_items:
            if name == "Redis" and status == FAIL:
                print(f"  • Redis: make sure Redis is running (docker compose up redis)")
            elif name == "MongoDB" and status == FAIL:
                print(f"  • MongoDB: make sure MongoDB is running (docker compose up mongodb)")
            elif name == "PolygonScan API" and status == SKIP:
                print(f"  • PolygonScan: get your free API key at polygonscan.com/apis")
                print(f"        then add it to backend/.env → POLYGONSCAN_API_KEY=your_key")
            elif name == "PolygonScan API" and status == FAIL:
                print(f"  • PolygonScan: API key may be invalid — check polygonscan.com/apis")
            elif status == FAIL:
                print(f"  • {name}: {reason}")

    print("══════════════════════════════════════════════════════")
    print()

    return all_required_ok


if __name__ == "__main__":
    run_all()
    ok = print_results()
    sys.exit(0 if ok else 1)
