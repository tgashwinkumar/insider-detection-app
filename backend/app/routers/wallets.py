import logging
from fastapi import APIRouter, HTTPException

from app.models.wallet import Wallet
from app.models.trade import Trade
from app.models.insider_score import InsiderScore
from app.utils.constants import KNOWN_WALLETS
from app.services.wallet_service import wallet_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/wallets/{address}/score")
async def get_wallet_score(address: str):
    address = address.lower().strip()

    # Ensure wallet is enriched
    wallet = await wallet_service.enrich_wallet(address)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Load all scored trades for this wallet
    scores = await InsiderScore.find(
        InsiderScore.wallet_address == address
    ).sort("-composite_score").to_list()

    trades = await Trade.find(Trade.maker == address).to_list()

    # Compute average factors across all scored trades
    if scores:
        avg_factors = {
            "entryTiming": sum(s.factor_entry_timing for s in scores) / len(scores),
            "marketCount": sum(s.factor_market_count for s in scores) / len(scores),
            "tradeSize": sum(s.factor_trade_size for s in scores) / len(scores),
            "walletAge": sum(s.factor_wallet_age for s in scores) / len(scores),
            "concentration": sum(s.factor_concentration for s in scores) / len(scores),
        }
        best_score = scores[0].composite_score
        classification = scores[0].classification
    else:
        avg_factors = {
            "entryTiming": 0.0,
            "marketCount": 0.0,
            "tradeSize": 0.0,
            "walletAge": 0.0,
            "concentration": 0.0,
        }
        best_score = wallet.latest_insider_score
        classification = wallet.classification

    # Build trade responses
    score_map = {s.trade_id: s for s in scores}
    trade_list = []
    for trade in trades:
        s = score_map.get(trade.transaction_hash)
        tr = {
            "id": trade.transaction_hash,
            "wallet": trade.maker,
            "walletLabel": KNOWN_WALLETS.get(address),
            "timestamp": trade.timestamp * 1000,
            "sizeUsdc": trade.amount_usdc,
            "direction": trade.direction,
            "classification": s.classification if s else "clean",
            "insiderScore": s.composite_score if s else 0.0,
            "factors": {
                "entryTiming": s.factor_entry_timing if s else 0.0,
                "marketCount": s.factor_market_count if s else 0.0,
                "tradeSize": s.factor_trade_size if s else 0.0,
                "walletAge": s.factor_wallet_age if s else 0.0,
                "concentration": s.factor_concentration if s else 0.0,
            },
            "walletCreatedAt": wallet.first_deposit_timestamp * 1000 if wallet.first_deposit_timestamp else None,
            "firstTradeAt": min(t.timestamp for t in trades) * 1000 if trades else None,
        }
        trade_list.append(tr)

    trade_list.sort(key=lambda t: t["timestamp"], reverse=True)

    # Wallet age days: computed from first deposit to now, or from first trade
    wallet_age_days = wallet.wallet_age_days
    if wallet_age_days is None and wallet.first_deposit_timestamp and trades:
        latest_trade_ts = max(t.timestamp for t in trades)
        wallet_age_days = (latest_trade_ts - wallet.first_deposit_timestamp) / 86400

    return {
        "address": address,
        "walletLabel": KNOWN_WALLETS.get(address),
        "insiderScore": best_score,
        "classification": classification,
        "walletCreatedAt": wallet.first_deposit_timestamp * 1000 if wallet.first_deposit_timestamp else None,
        "firstTradeAt": min(t.timestamp for t in trades) * 1000 if trades else None,
        "walletAgeDays": round(wallet_age_days, 2) if wallet_age_days is not None else None,
        "totalTrades": wallet.total_trades,
        "totalVolumeUsdc": wallet.total_volume_usdc,
        "marketsTraded": wallet.markets_traded,
        "avgTradeSizeUsdc": wallet.average_trade_size_usdc,
        "factors": avg_factors,
        "trades": trade_list,
    }
