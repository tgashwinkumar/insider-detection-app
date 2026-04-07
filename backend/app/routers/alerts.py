import logging
from typing import Optional
from fastapi import APIRouter, Query

from app.models.insider_score import InsiderScore
from app.models.trade import Trade
from app.models.market import Market
from app.utils.constants import KNOWN_WALLETS

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/alerts")
async def get_alerts(
    classification: Optional[str] = Query(None, description="insider | suspicious"),
    limit: int = Query(50, description="Max results"),
):
    # Query flagged scores
    query_filter = {"classification": {"$ne": "clean"}}
    if classification:
        query_filter = {"classification": classification}

    scores = (
        await InsiderScore.find(query_filter)
        .sort("-composite_score")
        .limit(limit)
        .to_list()
    )

    alerts = []
    for score in scores:
        trade = await Trade.find_one(Trade.transaction_hash == score.trade_id)
        if not trade:
            continue

        market = await Market.find_one(Market.condition_id == score.condition_id)
        wallet_label = KNOWN_WALLETS.get(score.wallet_address.lower())

        alert = {
            "id": trade.transaction_hash,
            "wallet": trade.maker,
            "walletLabel": wallet_label,
            "timestamp": trade.timestamp * 1000,
            "sizeUsdc": trade.amount_usdc,
            "direction": trade.direction,
            "classification": score.classification,
            "insiderScore": score.composite_score,
            "factors": {
                "entryTiming": score.factor_entry_timing,
                "marketCount": score.factor_market_count,
                "tradeSize": score.factor_trade_size,
                "walletAge": score.factor_wallet_age,
                "concentration": score.factor_concentration,
            },
            "walletCreatedAt": None,
            "firstTradeAt": None,
            "market": None,
        }

        if market:
            alert["market"] = {
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

        # Enrich wallet timestamps
        from app.models.wallet import Wallet
        wallet = await Wallet.find_one(Wallet.address == score.wallet_address)
        if wallet and wallet.first_deposit_timestamp:
            alert["walletCreatedAt"] = wallet.first_deposit_timestamp * 1000

        alert["firstTradeAt"] = trade.timestamp * 1000

        alerts.append(alert)

    return alerts
