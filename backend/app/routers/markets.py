import logging
from typing import Optional
from fastapi import APIRouter, Query

from app.models.market import Market
from app.models.trade import Trade
from app.models.insider_score import InsiderScore
from app.services.market_service import market_service, detect_query_type
from app.utils.constants import KNOWN_WALLETS

logger = logging.getLogger(__name__)
router = APIRouter()


def _market_to_response(market: Market) -> dict:
    return {
        "conditionId": market.condition_id,
        "question": market.question,
        "resolutionDate": market.resolution_date,
        "verdict": market.verdict,
        "direction": market.direction,
        "confidence": market.confidence,
        "volume": market.volume_usdc,
        "traderCount": market.trader_count,
        "manipulability": market.manipulability,
    }


def _trade_to_response(trade: Trade, score: Optional[InsiderScore]) -> dict:
    wallet_label = KNOWN_WALLETS.get(trade.maker.lower())
    if score:
        classification = score.classification
        insider_score = score.composite_score
        factors = {
            "entryTiming": score.factor_entry_timing,
            "marketCount": score.factor_market_count,
            "tradeSize": score.factor_trade_size,
            "walletAge": score.factor_wallet_age,
            "concentration": score.factor_concentration,
        }
        factor_sources = {
            "entryTimingDeltaSeconds": score.source_entry_timing_delta_seconds,
            "previousTradesByWallet": score.source_market_count,
            "tradeSizeUsdc": score.source_trade_size_usdc,
            "walletAgeDays": score.source_wallet_age_days,
            "walletTotalVolumeUsdc": score.source_wallet_total_volume_usdc,
        }
    else:
        classification = "clean"
        insider_score = 0.0
        factors = {
            "entryTiming": 0.0,
            "marketCount": 0.0,
            "tradeSize": 0.0,
            "walletAge": 0.0,
            "concentration": 0.0,
        }
        factor_sources = {
            "entryTimingDeltaSeconds": None,
            "previousTradesByWallet": None,
            "tradeSizeUsdc": trade.amount_usdc,
            "walletAgeDays": None,
            "walletTotalVolumeUsdc": None,
        }

    return {
        "id": trade.transaction_hash,
        "wallet": trade.maker,
        "walletLabel": wallet_label,
        "timestamp": trade.timestamp * 1000,
        "sizeUsdc": trade.amount_usdc,
        "direction": trade.direction,
        "classification": classification,
        "insiderScore": insider_score,
        "factors": factors,
        "factorSources": factor_sources,
        "walletCreatedAt": None,
        "firstTradeAt": None,
    }


def _dispatch_ingest(condition_id: str) -> None:
    try:
        from app.tasks.ingest_market import ingest_market_task
        ingest_market_task.delay(condition_id)
    except Exception as e:
        logger.warning(f"Could not dispatch ingest task for {condition_id}: {e}")


def _dispatch_score(condition_id: str) -> None:
    try:
        from app.tasks.score_market import score_market_task
        score_market_task.delay(condition_id)
    except Exception as e:
        logger.warning(f"Could not dispatch score task for {condition_id}: {e}")


@router.get("/api/markets/search")
async def search_markets(
    q: str = Query(..., description="Search query"),
    limit: int = 20,
):
    if not q.strip():
        return []

    query_type = detect_query_type(q)

    # ── Specific lookup (URL / conditionId / tokenId) ─────────────────────────
    # For URL queries this may return multiple markets (event with many outcomes).
    # Upsert all of them and trigger ingestion for each.
    if query_type in ("url", "conditionId", "tokenId"):
        gamma_markets = await market_service.search_markets(q, limit=50)
        if not gamma_markets:
            return []

        result = []
        for gm in gamma_markets:
            try:
                market = await market_service.upsert_market(gm)
                _dispatch_ingest(market.condition_id)
                result.append(_market_to_response(market))
            except Exception as e:
                logger.warning(f"Failed to upsert market from event: {e}")

        return result

    # ── Text search ────────────────────────────────────────────────────────────
    # Check MongoDB cache first for fast auto-complete results
    cached_markets = await Market.find(
        {"question": {"$regex": q, "$options": "i"}}
    ).limit(limit).to_list()
    if cached_markets:
        return [_market_to_response(m) for m in cached_markets]

    # Cache miss — call Gamma API
    gamma_markets = await market_service.search_markets(q, limit=limit)
    if not gamma_markets:
        return []

    result = []
    for gm in gamma_markets[:limit]:
        try:
            market = await market_service.upsert_market(gm)
            result.append(_market_to_response(market))
        except Exception as e:
            logger.warning(f"Failed to upsert market from search: {e}")

    return result


@router.get("/api/markets/{condition_id}/trades")
async def get_market_trades(condition_id: str):
    # Look up market
    market = await Market.find_one(Market.condition_id == condition_id)
    if not market:
        gm_list = await market_service._get("/markets", params={"condition_ids": condition_id})
        if isinstance(gm_list, list) and gm_list:
            market = await market_service.upsert_market(gm_list[0])
        else:
            market = Market(
                condition_id=condition_id,
                question="Market loading...",
                resolution_date="",
            )

    # Check if trades exist
    trades = await Trade.find(Trade.condition_id == condition_id).to_list()

    if not trades:
        # Trigger ingestion via Celery (idempotent guard in ingest_market prevents duplicates)
        _dispatch_ingest(condition_id)

        # Check job status so the frontend knows what's happening
        from app.services.indexer import ingest_job
        job = await ingest_job.get_job(condition_id)

        return {
            "market": _market_to_response(market),
            "trades": [],
            "verdict": {
                "level": market.verdict,
                "direction": market.direction,
                "confidence": market.confidence,
            },
            "summary": {
                "totalTrades": 0,
                "uniqueWallets": 0,
                "flaggedCount": 0,
                "highestScore": 0.0,
            },
            "ingestion": job or {"status": "starting"},
        }

    # Load scores
    scores_list = await InsiderScore.find(
        InsiderScore.condition_id == condition_id
    ).to_list()
    score_by_trade: dict[str, InsiderScore] = {s.trade_id: s for s in scores_list}

    # If trades exist but no scores, trigger scoring
    if not scores_list:
        _dispatch_score(condition_id)

    # Build trade responses with wallet timestamps
    from app.models.wallet import Wallet
    trade_responses = []
    for trade in trades:
        score = score_by_trade.get(trade.transaction_hash)
        tr = _trade_to_response(trade, score)

        wallet = await Wallet.find_one(Wallet.address == trade.maker)
        if wallet and wallet.first_deposit_timestamp:
            tr["walletCreatedAt"] = wallet.first_deposit_timestamp * 1000
        tr["firstTradeAt"] = trade.timestamp * 1000

        trade_responses.append(tr)

    trade_responses.sort(key=lambda t: t["timestamp"], reverse=True)

    flagged = [t for t in trade_responses if t["classification"] == "insider"]
    highest = max((t["insiderScore"] for t in trade_responses), default=0.0)
    unique_wallets = len({t["wallet"] for t in trade_responses})

    if scores_list:
        max_score = max(scores_list, key=lambda s: s.composite_score)
        verdict_level = max_score.classification
        confidence = int(max_score.composite_score * 100)
        top_trade = next(
            (tr for tr in trade_responses if tr["id"] == max_score.trade_id), None
        )
        direction = top_trade["direction"] if top_trade else market.direction
    else:
        verdict_level = market.verdict
        confidence = market.confidence
        direction = market.direction

    # Include current ingestion job state for frontend polling
    from app.services.indexer import ingest_job
    job = await ingest_job.get_job(condition_id)

    return {
        "market": _market_to_response(market),
        "trades": trade_responses,
        "verdict": {
            "level": verdict_level,
            "direction": direction,
            "confidence": confidence,
        },
        "summary": {
            "totalTrades": len(trade_responses),
            "uniqueWallets": unique_wallets,
            "flaggedCount": len(flagged),
            "highestScore": highest,
        },
        "ingestion": job or {"status": "done"},
    }
