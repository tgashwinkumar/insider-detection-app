import asyncio
import logging
from typing import Optional
import httpx

from app.config import settings
from app.utils.constants import USDC_E_ADDRESS, POLYGON_CHAIN_ID

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(4)  # 4 as safety margin below 5/sec limit


class EtherscanClient:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, params: dict) -> Optional[dict]:
        base_params = {
            "apikey": settings.ETHERSCAN_API_KEY,
            "chainid": str(POLYGON_CHAIN_ID),
        }
        base_params.update(params)

        for attempt in range(3):
            async with _semaphore:
                try:
                    client = await self._get_client()
                    r = await client.get(settings.ETHERSCAN_API_URL, params=base_params)
                    r.raise_for_status()
                    data = r.json()

                    if data.get("status") == "0":
                        msg = data.get("message", "")
                        result = data.get("result", "")
                        if "rate limit" in str(result).lower() or "max rate" in str(result).lower():
                            wait = 2 ** attempt
                            logger.warning(f"Etherscan rate limit hit, waiting {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        # No results is OK
                        if "No transactions found" in str(result):
                            return data
                        logger.warning(f"Etherscan status=0: {msg} — {result}")
                        return data

                    return data

                except httpx.TimeoutException:
                    logger.warning(f"Etherscan timeout (attempt {attempt + 1})")
                    await asyncio.sleep(2 ** attempt)
                except httpx.HTTPStatusError as e:
                    logger.error(f"Etherscan HTTP {e.response.status_code}")
                    return None
                except Exception as e:
                    logger.exception(f"Etherscan unexpected error: {e}")
                    return None

        return None

    async def get_first_usdc_deposit(
        self, wallet_address: str
    ) -> tuple[Optional[int], Optional[float]]:
        """
        Fetch the earliest USDC.e transfer TO this wallet.
        Returns (unix_timestamp_seconds, amount_usdc) or (None, None).
        """
        if not settings.ETHERSCAN_API_KEY:
            logger.warning("No ETHERSCAN_API_KEY set, skipping deposit lookup")
            return None, None

        data = await self._request(
            {
                "module": "account",
                "action": "tokentx",
                "contractaddress": USDC_E_ADDRESS,
                "address": wallet_address,
                "page": "1",
                "offset": "10000",
                "sort": "asc",
            }
        )

        if not data:
            return None, None

        result = data.get("result")
        if not isinstance(result, list) or len(result) == 0:
            return None, None

        # Find first transfer TO this wallet
        wallet_lower = wallet_address.lower()
        for tx in result:
            if tx.get("to", "").lower() == wallet_lower:
                try:
                    timestamp = int(tx["timeStamp"])
                    # USDC has 6 decimals
                    amount_usdc = int(tx.get("value", "0")) / 1e6
                    return timestamp, amount_usdc
                except (KeyError, ValueError):
                    continue

        return None, None


# Singleton instance
etherscan_client = EtherscanClient()
