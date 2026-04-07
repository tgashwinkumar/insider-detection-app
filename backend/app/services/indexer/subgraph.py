"""
The Graph subgraph indexer for Polymarket OrderFilled events.
Uses cursor-based pagination (id_gt) to avoid skip-based issues.

Subgraphs used:
  - Order Filled Events (EZCTgSzLPuBSqQcuR3ifeiKHKBnpjHSNbYpty8Mnjm9D)
    Entity: orderFilleds, negRiskCtfExchangeOrderFilleds
  - Orderbook (7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY)
    Entity: MarketData — used to resolve conditionId → token IDs
"""
import asyncio
import logging
from typing import AsyncIterator, Optional
import httpx

from app.config import settings
from app.utils.constants import POLYMARKET_SUBGRAPH_ID

logger = logging.getLogger(__name__)

# Orderbook subgraph has MarketData entity — maps conditionId → YES/NO token IDs
ORDERBOOK_SUBGRAPH_ID = "7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY"

# Buyers: maker offers collateral (USDC), receives outcome token as takerAssetId
ORDERFILLED_QUERY_TAKER = """
query fetchEventsTaker($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  orderFilleds(
    first: $first,
    where: { id_gt: $lastId, takerAssetId_in: $assetIds },
    orderBy: id,
    orderDirection: asc
  ) {
    id
    orderHash
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
    blockTimestamp
    transactionHash
    blockNumber
  }
}
"""

# Sellers: maker offers outcome token as makerAssetId, receives collateral
ORDERFILLED_QUERY_MAKER = """
query fetchEventsMaker($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  orderFilleds(
    first: $first,
    where: { id_gt: $lastId, makerAssetId_in: $assetIds },
    orderBy: id,
    orderDirection: asc
  ) {
    id
    orderHash
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
    blockTimestamp
    transactionHash
    blockNumber
  }
}
"""

# NegRisk buyers
NEG_RISK_ORDERFILLED_QUERY_TAKER = """
query fetchNegRiskEventsTaker($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  negRiskCtfExchangeOrderFilleds(
    first: $first,
    where: { id_gt: $lastId, takerAssetId_in: $assetIds },
    orderBy: id,
    orderDirection: asc
  ) {
    id
    orderHash
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
    blockTimestamp
    transactionHash
    blockNumber
  }
}
"""

# NegRisk sellers
NEG_RISK_ORDERFILLED_QUERY_MAKER = """
query fetchNegRiskEventsMaker($lastId: String!, $assetIds: [String!]!, $first: Int!) {
  negRiskCtfExchangeOrderFilleds(
    first: $first,
    where: { id_gt: $lastId, makerAssetId_in: $assetIds },
    orderBy: id,
    orderDirection: asc
  ) {
    id
    orderHash
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
    blockTimestamp
    transactionHash
    blockNumber
  }
}
"""

# Keep old names as aliases so nothing else breaks
ORDERFILLED_QUERY = ORDERFILLED_QUERY_TAKER
NEG_RISK_ORDERFILLED_QUERY = NEG_RISK_ORDERFILLED_QUERY_TAKER

# Query the Orderbook subgraph for MarketData (token IDs per condition)
MARKET_DATA_QUERY = """
query getMarketTokenIds($conditionId: String!) {
  marketDatas(
    first: 10,
    where: { condition: $conditionId }
    orderBy: outcomeIndex
    orderDirection: asc
  ) {
    id
    condition
    outcomeIndex
  }
}
"""


class SubgraphIndexer:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_url(self, subgraph_id: Optional[str] = None) -> str:
        sid = subgraph_id or POLYMARKET_SUBGRAPH_ID
        key = settings.THEGRAPH_API_KEY
        if key:
            return f"https://gateway.thegraph.com/api/{key}/subgraphs/id/{sid}"
        return f"https://api.thegraph.com/subgraphs/id/{sid}"

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Return a live httpx.AsyncClient bound to the current event loop.

        httpx clients are tied to the event loop they were created in.
        Celery workers each spin up a fresh asyncio.run() loop per task,
        so a module-level singleton client created in one loop is broken
        in the next.  We track which loop owns the client and rebuild it
        whenever the loop changes (or if the client is closed).
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._client is None
            or self._client.is_closed
            or self._client_loop is not current_loop
        ):
            if self._client and not self._client.is_closed:
                await self._client.aclose()
            self._client = httpx.AsyncClient(timeout=30.0)
            self._client_loop = current_loop

        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _query(
        self,
        query: str,
        variables: dict,
        subgraph_id: Optional[str] = None,
    ) -> Optional[dict]:
        try:
            client = await self._get_client()
            r = await client.post(
                self._get_url(subgraph_id),
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            if "errors" in data and data["errors"]:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
            return data.get("data")
        except httpx.TimeoutException:
            logger.warning("Subgraph timeout")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Subgraph HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.exception(f"Subgraph error: {e}")
            return None

    async def resolve_token_ids_from_subgraph(
        self, condition_id: str
    ) -> dict[str, str]:
        """
        Query the Orderbook subgraph's MarketData entity to get YES/NO token IDs.

        Returns {"yes": token_id, "no": token_id, "all": [token_id, ...]}
        Returns {} if not found.

        MarketData.outcomeIndex: 0 = YES token, 1 = NO token.
        """
        # Try both with and without 0x prefix, lowercase
        condition_variants = [
            condition_id.lower(),
            condition_id.lower().lstrip("0x"),
        ]
        if not condition_id.startswith("0x"):
            condition_variants.insert(0, "0x" + condition_id.lower())

        for cid in condition_variants:
            data = await self._query(
                MARKET_DATA_QUERY,
                {"conditionId": cid},
                subgraph_id=ORDERBOOK_SUBGRAPH_ID,
            )
            if not data:
                continue

            market_datas = data.get("marketDatas") or []
            if not market_datas:
                continue

            result: dict[str, str] = {}
            all_ids: list[str] = []
            for md in market_datas:
                token_id = str(md.get("id", ""))
                outcome_idx = md.get("outcomeIndex")
                all_ids.append(token_id)
                if outcome_idx == 0 or outcome_idx == "0":
                    result["yes"] = token_id
                elif outcome_idx == 1 or outcome_idx == "1":
                    result["no"] = token_id

            if all_ids:
                result["all"] = all_ids
                logger.info(
                    f"Resolved token IDs for {condition_id}: "
                    f"YES={result.get('yes')}, NO={result.get('no')}"
                )
                return result

        logger.warning(f"Could not resolve token IDs for {condition_id} from subgraph")
        return {}

    async def fetch_order_filled_events(
        self,
        asset_ids: list[str],
        last_id: str = "",
        batch_size: int = 1000,
    ) -> list[dict]:
        """
        Single page fetch of OrderFilled events — both exchange types, both directions.

        Runs 4 queries in parallel:
          - orderFilleds           with takerAssetId_in  (standard buyers)
          - orderFilleds           with makerAssetId_in  (standard sellers)
          - negRiskCtfExchange...  with takerAssetId_in  (negRisk buyers)
          - negRiskCtfExchange...  with makerAssetId_in  (negRisk sellers)

        Deduplicates by transactionHash so no trade is counted twice.
        """
        vars_ = {"lastId": last_id, "assetIds": asset_ids, "first": batch_size}

        query_names = ["std_taker", "std_maker", "neg_taker", "neg_maker"]
        results = await asyncio.gather(
            self._query(ORDERFILLED_QUERY_TAKER,            vars_),
            self._query(ORDERFILLED_QUERY_MAKER,            vars_),
            self._query(NEG_RISK_ORDERFILLED_QUERY_TAKER,   vars_),
            self._query(NEG_RISK_ORDERFILLED_QUERY_MAKER,   vars_),
            return_exceptions=True,
        )

        # Log every query failure explicitly so errors are visible in logs.
        # Collect failure messages so callers can surface them in job state.
        failed_queries: list[str] = []
        for name, result in zip(query_names, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Subgraph query '{name}' failed: "
                    f"{type(result).__name__}: {result}"
                )
                failed_queries.append(f"{name}: {type(result).__name__}: {str(result)[:150]}")

        # If every query failed, raise so the caller can mark the job FAILED
        # instead of DONE with tradesIndexed=0 (which looks like an empty market).
        if len(failed_queries) == len(query_names):
            raise RuntimeError(
                f"All {len(query_names)} subgraph queries failed: {failed_queries}"
            )

        taker_data, maker_data, neg_taker_data, neg_maker_data = results

        raw: list[dict] = []
        if isinstance(taker_data, dict):
            raw += taker_data.get("orderFilleds") or []
        if isinstance(maker_data, dict):
            raw += maker_data.get("orderFilleds") or []
        if isinstance(neg_taker_data, dict):
            raw += neg_taker_data.get("negRiskCtfExchangeOrderFilleds") or []
        if isinstance(neg_maker_data, dict):
            raw += neg_maker_data.get("negRiskCtfExchangeOrderFilleds") or []

        # Deduplicate by transactionHash — keeps first occurrence
        seen: set[str] = set()
        events: list[dict] = []
        for e in sorted(raw, key=lambda x: x.get("id", "")):
            tx = e.get("transactionHash", e.get("id", ""))
            if tx not in seen:
                seen.add(tx)
                events.append(e)

        return events

    async def fetch_all_events(
        self,
        asset_ids: list[str],
        batch_size: int = 1000,
        from_cursor: str = "",
    ) -> AsyncIterator[list[dict]]:
        """
        Cursor-paginate until no more results. Yields each batch.
        Pass from_cursor to resume a partial ingestion.
        """
        last_id = from_cursor
        while True:
            batch = await self.fetch_order_filled_events(
                asset_ids=asset_ids,
                last_id=last_id,
                batch_size=batch_size,
            )
            if not batch:
                break
            yield batch
            last_id = batch[-1]["id"]
            if len(batch) < batch_size:
                break
            await asyncio.sleep(0.1)  # be a good API citizen


subgraph_indexer = SubgraphIndexer()
