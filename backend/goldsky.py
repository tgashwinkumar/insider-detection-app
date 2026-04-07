import httpx
from typing import List, Dict, Any
import os

POLYMARKET_GAMMA_URL = os.getenv("POLYMARKET_GAMMA_URL")
POLYMARKET_SUBGRAPH_URL = os.getenv("POLYMARKET_SUBGRAPH_URL")
POLYMARKET_SUBGRAPH_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"

async def get_market_trades_by_slug(slug: str) -> Dict[str, Any]:
    """
    Given a market slug, fetch all historical trades for that market.
    
    Returns:
    {
        "market": {...market metadata...},
        "trades": [
            {
                "tx_hash": "0x...",
                "maker": "0x...",
                "taker": "0x...",
                "maker_amount": 1000,
                "taker_amount": 500,
                "timestamp": "2026-01-15T14:23:00Z",
                ...
            },
            ...
        ]
    }
    """
    
    # STEP 1: Get market metadata including conditionId from Gamma API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{POLYMARKET_GAMMA_URL}/markets",
            params={"slug": slug},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("markets") or len(data["markets"]) == 0:
            raise ValueError(f"Market with slug '{slug}' not found")
        
        market = data["markets"][0]
        condition_id = market["conditionId"]
        token_ids = market.get("tokenIds", [])
        
        market_info = {
            "condition_id": condition_id,
            "slug": market["slug"],
            "question": market["question"],
            "status": market.get("status", "unknown"),
            "resolution_date": market.get("resolutionDate"),
            "token_ids": token_ids,
            "outcomes": market.get("outcomes", []),
            "total_volume": market.get("volume", 0)
        }
    
    # STEP 2: Query Goldsky Subgraph for all OrderFilled events for these token IDs
    # We need to paginate because the subgraph caps at 1000 results per query
    
    all_trades = []
    skip = 0
    page_size = 1000
    
    async with httpx.AsyncClient() as client:
        while True:
            graphql_query = {
                "query": """
                    query GetOrderFilled($tokenIds: [String!]!, $skip: Int!) {
                        orderFilledEvents(
                            where: {
                                takerAssetId_in: $tokenIds
                            }
                            skip: $skip
                            first: 1000
                            orderBy: timestamp
                            orderDirection: asc
                        ) {
                            id
                            transactionHash
                            blockNumber
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
                """,
                "variables": {
                    "tokenIds": token_ids,
                    "skip": skip
                }
            }
            
            response = await client.post(
                POLYMARKET_SUBGRAPH_URL,
                json=graphql_query,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                raise ValueError(f"Subgraph error: {data['errors']}")
            
            events = data.get("data", {}).get("orderFilledEvents", [])
            
            if not events:
                break  # No more pages
            
            # Normalize the trade data
            for event in events:
                trade = {
                    "tx_hash": event["transactionHash"],
                    "block_number": int(event["blockNumber"]),
                    "timestamp": int(event["timestamp"]),
                    "maker": event["maker"].lower(),
                    "taker": event["taker"].lower(),
                    "maker_asset_id": event["makerAssetId"],
                    "taker_asset_id": event["takerAssetId"],
                    "maker_amount": float(event["makerAmountFilled"]),
                    "taker_amount": float(event["takerAmountFilled"]),
                    "fee": float(event["fee"]),
                    "condition_id": condition_id
                }
                all_trades.append(trade)
            
            skip += page_size
            
            # If we got less than a full page, we're done
            if len(events) < page_size:
                break
    
    return {
        "market": market_info,
        "trades": all_trades,
        "total_trades": len(all_trades)
    }


# Usage example:
if __name__ == "__main__":
    import asyncio
    
    result = asyncio.run(
        get_market_trades_by_slug("us-iran-nuclear-deal-by-april-30")
    )
    
    print(f"Market: {result['market']['question']}")
    print(f"Total trades: {result['total_trades']}")
    print(f"First trade: {result['trades'][0] if result['trades'] else 'No trades'}")