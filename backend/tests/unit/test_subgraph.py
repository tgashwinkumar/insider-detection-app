"""
Fetch all historical OrderFilled events for a given conditionId from The Graph subgraphs.

Steps:
  1. Resolve conditionId → token IDs via the Orderbook subgraph (MarketData entity)
  2. Paginate through all OrderFilled events (standard + negRisk, taker + maker)
     using id_gt cursor pagination until exhausted
"""
import asyncio
import httpx

# ── config ────────────────────────────────────────────────────────────────────
CONDITION_ID = "0xafc235557ace53ff0b0d2e93392314a7c3f3daab26a79050e985c11282f66df7"

THEGRAPH_API_KEY = "1e8ca4741dd5cd3726e2423ee784265a"   # set if you have a paid gateway key

ORDERFILLED_SUBGRAPH_ID    = "EZCTgSzLPuBSqQcuR3ifeiKHKBnpjHSNbYpty8Mnjm9D"
ORDERBOOK_SUBGRAPH_ID      = "7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY"

BATCH_SIZE = 1000

# ── helpers ───────────────────────────────────────────────────────────────────
def subgraph_url(subgraph_id: str) -> str:
    if THEGRAPH_API_KEY:
        return f"https://gateway.thegraph.com/api/{THEGRAPH_API_KEY}/subgraphs/id/{subgraph_id}"
    return f"https://api.thegraph.com/subgraphs/id/{subgraph_id}"


async def gql(client: httpx.AsyncClient, subgraph_id: str, query: str, variables: dict) -> dict:
    r = await client.post(
        subgraph_url(subgraph_id),
        json={"query": query, "variables": variables},
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


# ── queries ───────────────────────────────────────────────────────────────────
MARKET_DATA_QUERY = """
query($conditionId: String!) {
  marketDatas(first: 10, where: { condition: $conditionId }, orderBy: outcomeIndex, orderDirection: asc) {
    id
    condition
    outcomeIndex
  }
}
"""

ORDERFILLED_TAKER = """
query($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  orderFilleds(first: $first, where: { id_gt: $lastId, takerAssetId_in: $assetIds }, orderBy: id, orderDirection: asc) {
    id orderHash maker taker makerAssetId takerAssetId
    makerAmountFilled takerAmountFilled fee blockTimestamp transactionHash blockNumber
  }
}
"""

ORDERFILLED_MAKER = """
query($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  orderFilleds(first: $first, where: { id_gt: $lastId, makerAssetId_in: $assetIds }, orderBy: id, orderDirection: asc) {
    id orderHash maker taker makerAssetId takerAssetId
    makerAmountFilled takerAmountFilled fee blockTimestamp transactionHash blockNumber
  }
}
"""

NEG_RISK_TAKER = """
query($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  negRiskCtfExchangeOrderFilleds(first: $first, where: { id_gt: $lastId, takerAssetId_in: $assetIds }, orderBy: id, orderDirection: asc) {
    id orderHash maker taker makerAssetId takerAssetId
    makerAmountFilled takerAmountFilled fee blockTimestamp transactionHash blockNumber
  }
}
"""

NEG_RISK_MAKER = """
query($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  negRiskCtfExchangeOrderFilleds(first: $first, where: { id_gt: $lastId, makerAssetId_in: $assetIds }, orderBy: id, orderDirection: asc) {
    id orderHash maker taker makerAssetId takerAssetId
    makerAmountFilled takerAmountFilled fee blockTimestamp transactionHash blockNumber
  }
}
"""

# ── main ──────────────────────────────────────────────────────────────────────
async def main():
    async with httpx.AsyncClient() as client:

        # ── step 1: resolve conditionId → token IDs ──────────────────────────
        print(f"Resolving token IDs for conditionId: {CONDITION_ID}")

        token_ids = []
        for cid in [CONDITION_ID, CONDITION_ID.lower(), "0x" + CONDITION_ID.lstrip("0x").lower()]:
            data = await gql(client, ORDERBOOK_SUBGRAPH_ID, MARKET_DATA_QUERY, {"conditionId": cid})
            rows = data.get("marketDatas") or []
            if rows:
                token_ids = [r["id"] for r in rows]
                for r in rows:
                    label = {0: "YES", "0": "YES", 1: "NO", "1": "NO"}.get(r["outcomeIndex"], f"outcome[{r['outcomeIndex']}]")
                    print(f"  {label} token: {r['id']}")
                break

        if not token_ids:
            raise RuntimeError("Could not resolve token IDs — market may not be indexed yet.")

        # ── step 2: paginate all OrderFilled events ───────────────────────────
        print(f"\nFetching all events for {len(token_ids)} token(s)...")

        all_events: list[dict] = []
        seen_tx: set[str] = set()
        last_id = ""
        batch_num = 0

        while True:
            vars_ = {"lastId": last_id, "assetIds": token_ids, "first": BATCH_SIZE}

            std_taker, std_maker, neg_taker, neg_maker = await asyncio.gather(
                gql(client, ORDERFILLED_SUBGRAPH_ID, ORDERFILLED_TAKER, vars_),
                gql(client, ORDERFILLED_SUBGRAPH_ID, ORDERFILLED_MAKER, vars_),
                gql(client, ORDERFILLED_SUBGRAPH_ID, NEG_RISK_TAKER,    vars_),
                gql(client, ORDERFILLED_SUBGRAPH_ID, NEG_RISK_MAKER,    vars_),
            )

            batch_raw: list[dict] = (
                (std_taker.get("orderFilleds") or [])
                + (std_maker.get("orderFilleds") or [])
                + (neg_taker.get("negRiskCtfExchangeOrderFilleds") or [])
                + (neg_maker.get("negRiskCtfExchangeOrderFilleds") or [])
            )

            # deduplicate by transactionHash within this batch
            batch: list[dict] = []
            for e in sorted(batch_raw, key=lambda x: x.get("id", "")):
                tx = e.get("transactionHash") or e.get("id") or ""
                if tx not in seen_tx:
                    seen_tx.add(tx)
                    batch.append(e)

            batch_num += 1
            all_events.extend(batch)
            print(f"  batch {batch_num}: {len(batch)} new events  (total so far: {len(all_events)})")

            if not batch:
                break

            last_id = batch_raw[-1]["id"]   # advance cursor by raw last id

            # if every sub-query returned fewer than BATCH_SIZE, we're done
            counts = [
                len(std_taker.get("orderFilleds") or []),
                len(std_maker.get("orderFilleds") or []),
                len(neg_taker.get("negRiskCtfExchangeOrderFilleds") or []),
                len(neg_maker.get("negRiskCtfExchangeOrderFilleds") or []),
            ]
            if max(counts) < BATCH_SIZE:
                break

            await asyncio.sleep(0.1)

        # ── results ───────────────────────────────────────────────────────────
        print(f"\nDone. {len(all_events)} total events fetched.")
        if all_events:
            print("\nFirst event:")
            for k, v in all_events[0].items():
                print(f"  {k}: {v}")
            print("\nLast event:")
            for k, v in all_events[-1].items():
                print(f"  {k}: {v}")

        return all_events


if __name__ == "__main__":
    asyncio.run(main())
