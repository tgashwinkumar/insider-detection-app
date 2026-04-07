import logging
import re
from datetime import datetime
from typing import Optional
import httpx
import ast

from app.config import settings
from app.models.market import Market
from app.scorer.factors import compute_market_manipulability

logger = logging.getLogger(__name__)

POLYMARKET_URL_REGEX = re.compile(r"polymarket\.com/(event|markets?)/", re.IGNORECASE)
CONDITION_ID_REGEX = re.compile(r"^0x[0-9a-fA-F]{64}$")
TOKEN_ID_REGEX = re.compile(r"^\d{10,}$")


def detect_query_type(query: str) -> str:
    if POLYMARKET_URL_REGEX.search(query):
        return "url"
    if CONDITION_ID_REGEX.match(query):
        return "conditionId"
    if TOKEN_ID_REGEX.match(query):
        return "tokenId"
    return "text"


def _extract_slug_from_url(url: str) -> Optional[str]:
    match = re.search(r"polymarket\.com/(?:event|markets?)/([^/?#]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_url_type(url: str) -> str:
    """Return 'event' if URL path is /event/..., else 'market'."""
    if re.search(r"polymarket\.com/event/", url, re.IGNORECASE):
        return "event"
    return "market"


def _parse_resolution_date(gamma_market: dict) -> str:
    """Extract resolution date as YYYY-MM-DD string from Gamma market data."""
    end_date = gamma_market.get("endDate") or gamma_market.get("resolutionDate") or ""
    if end_date:
        # Handle various formats
        try:
            if "T" in end_date:
                return end_date.split("T")[0]
            return end_date[:10]
        except Exception:
            pass
    return ""


def _parse_resolution_timestamp(gamma_market: dict) -> Optional[int]:
    end_date = _parse_resolution_date(gamma_market)
    if end_date:
        try:
            from datetime import timezone
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass
    return None


def _gamma_to_market(gm: dict) -> dict:
    """Convert Gamma API market dict to our Market schema dict."""
    liquidity = float(gm.get("liquidity", 0) or 0)
    return {
        "condition_id": gm.get("conditionId") or gm.get("condition_id") or "",
        "slug": gm.get("slug"),
        "question": gm.get("question") or gm.get("title") or "",
        "resolution_date": _parse_resolution_date(gm),
        "resolution_timestamp": _parse_resolution_timestamp(gm),
        "creator": gm.get("creator"),
        "liquidity_usdc": liquidity,
        "volume_usdc": float(gm.get("volume") or gm.get("volumeNum", 0) or 0),
        "outcomes": gm.get("outcomes") or ["YES", "NO"],
        "resolved": bool(gm.get("closed") or gm.get("resolved")),
        "resolution": gm.get("resolution"),
        "manipulability": compute_market_manipulability(liquidity),
    }


class MarketService:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.POLYMARKET_GAMMA_URL,
                timeout=15.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: Optional[dict] = None) -> Optional[list | dict]:
        try:
            client = await self._get_client()
            r = await client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            logger.warning(f"Gamma API timeout: {path}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Gamma API HTTP {e.response.status_code}: {path}")
            return None
        except Exception as e:
            logger.exception(f"Gamma API error: {e}")
            return None

    async def search_markets(self, query: str, limit: int = 20) -> list[dict]:
        query_type = detect_query_type(query)

        if query_type == "url":
            slug = _extract_slug_from_url(query)
            if not slug:
                return []

            url_type = _extract_url_type(query)

            if url_type == "event":
                # /event/ URLs → fetch all markets belonging to the event
                markets = await self._get_event_markets(slug)
                if markets:
                    return markets[:limit]
                # Fallback: slug_contains search using the slug text
                data = await self._get(
                    "/markets",
                    params={"slug_contains": slug, "limit": limit},
                )
                return data if isinstance(data, list) else []

            else:
                # /market/ or /markets/ URLs → direct market slug lookup
                data = await self._get(f"/markets/slug/{slug}")
                if data:
                    return [data] if isinstance(data, dict) else data
                # Fallback: slug_contains
                data = await self._get(
                    "/markets",
                    params={"slug_contains": slug, "limit": limit},
                )
                return data if isinstance(data, list) else []

        elif query_type == "conditionId":
            data = await self._get("/markets", params={"condition_ids": query})
            if isinstance(data, list):
                return data
            return []

        elif query_type == "tokenId":
            data = await self._get("/markets", params={"token_id": query})
            if isinstance(data, list):
                return data
            return []

        else:  # text
            data = await self._get(
                "/markets",
                params={"slug_contains": query, "limit": limit, "active": "true"},
            )
            if isinstance(data, list):
                return data
            return []

    async def _get_event_markets(self, slug: str) -> list[dict]:
        """
        Fetch all child markets for a Polymarket event by its slug.
        Tries /events/slug/{slug} first, then /events?slug={slug}.
        Returns the markets[] array from the event, or [] if not found.
        """
        # Primary: /events/slug/{slug}
        data = await self._get(f"/events/slug/{slug}")
        if data and isinstance(data, dict):
            markets = data.get("markets") or []
            if markets:
                logger.info(
                    f"Event '{slug}' resolved to {len(markets)} markets via /events/slug/"
                )
                return markets

        # Secondary: /events?slug={slug}
        data = await self._get("/events", params={"slug": slug})
        if isinstance(data, list) and data:
            markets = data[0].get("markets") or []
            if markets:
                logger.info(
                    f"Event '{slug}' resolved to {len(markets)} markets via /events?slug="
                )
                return markets

        logger.warning(f"Could not resolve event markets for slug '{slug}'")
        return []

    async def get_market_by_condition_id(self, condition_id: str) -> Optional[dict]:
        # Check MongoDB cache first
        cached = await Market.find_one(Market.condition_id == condition_id)
        if cached:
            return cached.model_dump()

        data = await self._get("/markets", params={"condition_ids": condition_id})
        if isinstance(data, list) and data:
            return data[0]
        return None

    async def get_market_token_ids(self, condition_id: str) -> list[str]:
        """
        Return YES and NO token IDs for a market.

        Gamma API returns clobTokenIds as a JSON-encoded string, e.g.:
          '["47932698...", "60808210..."]'
        NOT as a Python list. We must json.loads() it before use.
        """
        import json as _json

        data = await self._get("/markets", params={"condition_ids": condition_id})
        if not isinstance(data, list) or not data:
            return []
        market = data[0]

        # Primary: clobTokenIds — Gamma API returns this as a JSON string, not a list
        clob_ids = market.get("clobTokenIds")
        if clob_ids:
            if isinstance(clob_ids, str):
                try:
                    clob_ids = _json.loads(clob_ids)
                except (_json.JSONDecodeError, ValueError):
                    clob_ids = None
            if isinstance(clob_ids, list) and clob_ids:
                return [str(t) for t in clob_ids if t]

        # Secondary: tokens array (CLOB API format, occasionally present)
        tokens = market.get("tokens") or []
        if tokens:
            return [str(t.get("token_id", "")) for t in tokens if t.get("token_id")]

        return []

    async def upsert_market(self, gm: dict) -> Market:
        """Upsert a Gamma market dict into MongoDB."""
        parsed = _gamma_to_market(gm)
        parsed["outcomes"] = ast.literal_eval(parsed["outcomes"])
        condition_id = parsed["condition_id"]
        if not condition_id:
            raise ValueError("Market has no condition_id")

        existing = await Market.find_one(Market.condition_id == condition_id)
        if existing:
            for k, v in parsed.items():
                if v is not None:
                    setattr(existing, k, v)
            existing.last_updated = datetime.utcnow()
            await existing.save()
            return existing
        else:
            
            m = Market(**parsed)
            await m.insert()
            return m


market_service = MarketService()
