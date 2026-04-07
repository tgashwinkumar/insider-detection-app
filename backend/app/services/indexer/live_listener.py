"""
Live Polygon WebSocket listener for OrderFilled events.
Uses the `websockets` library (async) instead of web3.py's blocking WebSocket.
"""
import asyncio
import json
import logging
from typing import Optional

import websockets
from web3 import Web3

from app.config import settings
from app.utils.constants import CTF_EXCHANGE_ADDRESS

logger = logging.getLogger(__name__)

# keccak256("OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
ORDERFILLED_TOPIC = Web3.keccak(
    text="OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
).hex()

_listener_task: Optional[asyncio.Task] = None


async def _subscribe_and_listen() -> None:
    """Subscribe to CTF Exchange logs and process OrderFilled events."""
    while True:
        try:
            async with websockets.connect(
                settings.POLYGON_WS_URL,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                # Subscribe to logs from CTF Exchange
                subscribe_msg = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": [
                            "logs",
                            {
                                "address": CTF_EXCHANGE_ADDRESS,
                                "topics": [ORDERFILLED_TOPIC],
                            },
                        ],
                    }
                )
                await ws.send(subscribe_msg)
                response = json.loads(await ws.recv())
                subscription_id = response.get("result")
                logger.info(f"Live listener subscribed, id={subscription_id}")

                async for message in ws:
                    try:
                        data = json.loads(message)
                        if data.get("method") == "eth_subscription":
                            log = data["params"]["result"]
                            await _process_log(log)
                    except Exception as e:
                        logger.warning(f"Error processing WS message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed, reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Live listener error: {e}, reconnecting in 10s...")
            await asyncio.sleep(10)


async def _process_log(log: dict) -> None:
    """Decode and score an OrderFilled log entry."""
    try:
        tx_hash = log.get("transactionHash", "")
        block_number = int(log.get("blockNumber", "0x0"), 16)

        # Decode topics
        topics = log.get("topics", [])
        if len(topics) < 3:
            return

        # topics[0] = event sig, topics[1] = orderHash (bytes32), topics[2] = maker, topics[3] = taker
        maker = "0x" + topics[2][-40:] if len(topics) > 2 else ""
        taker = "0x" + topics[3][-40:] if len(topics) > 3 else ""

        # Decode data (uint256 x 5: makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee)
        data_hex = log.get("data", "0x")[2:]
        if len(data_hex) >= 320:  # 5 x 64 hex chars
            chunks = [data_hex[i : i + 64] for i in range(0, 320, 64)]
            maker_asset_id = str(int(chunks[0], 16))
            taker_asset_id = str(int(chunks[1], 16))
            maker_amount = int(chunks[2], 16)
            taker_amount = int(chunks[3], 16)
            fee = int(chunks[4], 16)
        else:
            return

        amount_usdc = taker_amount / 1e6

        # Get block timestamp
        import httpx
        try:
            r = httpx.post(
                settings.POLYGON_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [hex(block_number), False],
                    "id": 1,
                },
                
                timeout=5.0,
            )
            block_data = r.json().get("result", {})
            timestamp = int(block_data.get("timestamp", "0x0"), 16)
        except Exception:
            import time
            timestamp = int(time.time())

        # Determine direction from taker_asset_id
        try:
            val = int(taker_asset_id)
            direction = "yes" if val % 2 == 0 else "no"
        except Exception:
            direction = "yes"

        trade_data = {
            "transaction_hash": tx_hash,
            "block_number": block_number,
            "timestamp": timestamp,
            "maker": maker.lower(),
            "taker": taker.lower(),
            "maker_asset_id": maker_asset_id,
            "taker_asset_id": taker_asset_id,
            "maker_amount_filled": maker_amount / 1e6,
            "taker_amount_filled": amount_usdc,
            "fee": fee / 1e6,
            "amount_usdc": amount_usdc,
            "direction": direction,
            "condition_id": "",  # Will be resolved via market lookup
            "source": "live",
        }

        # Dispatch to Celery for full processing
        try:
            from app.tasks.live_score import live_score_task
            live_score_task.apply_async(args=[trade_data])
        except Exception as e:
            logger.warning(f"Could not enqueue live_score task: {e}")

    except Exception as e:
        logger.error(f"Failed to process OrderFilled log: {e}")


def start_live_listener() -> None:
    """Start the live listener as a background asyncio task."""
    global _listener_task
    try:
        loop = asyncio.get_event_loop()
        _listener_task = loop.create_task(_subscribe_and_listen())
        logger.info("Live listener task started")
    except Exception as e:
        logger.error(f"Failed to start live listener: {e}")


def stop_live_listener() -> None:
    global _listener_task
    if _listener_task and not _listener_task.done():
        _listener_task.cancel()
        logger.info("Live listener task stopped")
