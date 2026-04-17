import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.trade import Trade
from app.models.wallet import Wallet
from app.models.market import Market
from app.models.insider_score import InsiderScore
from app.models.alert import Alert
from app.scorer.factors import (
    factor_entry_timing,
    factor_market_count,
    factor_trade_size,
    factor_wallet_age,
    factor_concentration,
)
from app.scorer.weights import DEFAULT_WEIGHTS
from app.utils.constants import ALERTS_CHANNEL

logger = logging.getLogger(__name__)


class ScoringEngine:
    def __init__(self, weights: Optional[dict[str, float]] = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def _classify(self, score: float, amount_usdc: float) -> str:
        # Trades under the minimum size are never flagged — too small to be meaningful.
        if amount_usdc <= settings.MIN_TRADE_SIZE_USDC:
            return "clean"
        if score >= settings.INSIDER_THRESHOLD:
            return "insider"
        if score >= settings.SUSPICIOUS_THRESHOLD:
            return "suspicious"
        return "clean"

    async def score_trade(
        self,
        trade: Trade,
        wallet: Wallet,
        market: Market,
    ) -> InsiderScore:
        # Calculate resolution timestamp from market resolution_date if not set
        resolution_ts = market.resolution_timestamp
        if not resolution_ts and market.resolution_date:
            try:
                from datetime import timezone
                dt = datetime.strptime(market.resolution_date, "%Y-%m-%d")
                resolution_ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                resolution_ts = trade.timestamp + 86400 * 30  # fallback

        # Estimate market creation timestamp (30 days before resolution if unknown)
        market_creation_ts = resolution_ts - 86400 * 30 if resolution_ts else trade.timestamp - 86400 * 30

        # Use trade timestamp for wallet age calculation
        trade_wallet = trade.maker if trade.maker != "0x0000000000000000000000000000000000000000" else trade.taker

        # Factor 1: Entry Timing
        f_entry = factor_entry_timing(
            trade_timestamp=trade.timestamp,
            resolution_timestamp=resolution_ts or (trade.timestamp + 86400 * 7),
            market_creation_timestamp=market_creation_ts,
        )

        # Factor 2: Market Count
        f_market = factor_market_count(markets_traded=wallet.markets_traded or 1)

        # Factor 3: Trade Size
        f_size = factor_trade_size(
            amount_usdc=trade.amount_usdc,
            wallet_avg_usdc=wallet.average_trade_size_usdc or trade.amount_usdc,
            min_threshold=settings.MIN_TRADE_SIZE_USDC,
        )

        # Factor 4: Wallet Age
        f_age = factor_wallet_age(
            first_deposit_timestamp=wallet.first_deposit_timestamp,
            trade_timestamp=trade.timestamp,
        )

        # Factor 5: Concentration
        f_concentration = factor_concentration(
            trade_amount_usdc=trade.amount_usdc,
            wallet_total_volume_usdc=wallet.total_volume_usdc or trade.amount_usdc,
        )

        # Raw source values for UI display
        src_entry_delta = float(
            (resolution_ts or (trade.timestamp + 86400 * 7)) - trade.timestamp
        )
        src_market_count = wallet.markets_traded or 1
        src_trade_size = trade.amount_usdc
        src_wallet_age_days = (
            float(trade.timestamp - wallet.first_deposit_timestamp) / 86400.0
            if wallet.first_deposit_timestamp else None
        )
        src_wallet_total_volume = wallet.total_volume_usdc or trade.amount_usdc

        # Composite weighted score
        w = self.weights
        composite = (
            f_entry * w.get("entryTiming", 0.30)
            + f_market * w.get("marketCount", 0.20)
            + f_size * w.get("tradeSize", 0.15)
            + f_age * w.get("walletAge", 0.25)
            + f_concentration * w.get("concentration", 0.10)
        )
        composite = max(0.0, min(1.0, composite))

        classification = self._classify(composite, trade.amount_usdc)

        # Upsert InsiderScore
        existing = await InsiderScore.find_one(InsiderScore.trade_id == trade.transaction_hash)
        if existing:
            existing.factor_entry_timing = f_entry
            existing.factor_market_count = f_market
            existing.factor_trade_size = f_size
            existing.factor_wallet_age = f_age
            existing.factor_concentration = f_concentration
            existing.source_entry_timing_delta_seconds = src_entry_delta
            existing.source_market_count = src_market_count
            existing.source_trade_size_usdc = src_trade_size
            existing.source_wallet_age_days = src_wallet_age_days
            existing.source_wallet_total_volume_usdc = src_wallet_total_volume
            existing.composite_score = composite
            existing.classification = classification
            existing.weights_used = self.weights
            existing.calculated_at = datetime.utcnow()
            await existing.save()
            score_doc = existing
        else:
            score_doc = InsiderScore(
                trade_id=trade.transaction_hash,
                wallet_address=trade.maker,
                condition_id=trade.condition_id,
                factor_entry_timing=f_entry,
                factor_market_count=f_market,
                factor_trade_size=f_size,
                factor_wallet_age=f_age,
                factor_concentration=f_concentration,
                source_entry_timing_delta_seconds=src_entry_delta,
                source_market_count=src_market_count,
                source_trade_size_usdc=src_trade_size,
                source_wallet_age_days=src_wallet_age_days,
                source_wallet_total_volume_usdc=src_wallet_total_volume,
                composite_score=composite,
                classification=classification,
                weights_used=self.weights,
            )
            await score_doc.insert()

        # Update wallet classification
        if composite > wallet.latest_insider_score:
            wallet.latest_insider_score = composite
            wallet.classification = classification
            wallet.last_updated = datetime.utcnow()
            await wallet.save()

        # Emit alert if flagged
        if classification != "clean":
            await self._emit_alert(trade, score_doc, market)

        return score_doc

    async def _emit_alert(
        self,
        trade: Trade,
        score: InsiderScore,
        market: Market,
    ) -> None:
        try:
            # Upsert alert document
            existing = await Alert.find_one(Alert.trade_id == trade.transaction_hash)
            if not existing:
                alert = Alert(
                    trade_id=trade.transaction_hash,
                    wallet_address=trade.maker,
                    condition_id=trade.condition_id,
                    score=score.composite_score,
                    classification=score.classification,
                )
                await alert.insert()

            # Publish to Redis
            try:
                from app.redis_client import get_redis
                from app.utils.constants import KNOWN_WALLETS
                import json

                wallet_label = KNOWN_WALLETS.get(trade.maker.lower())
                payload = {
                    "type": "trade",
                    "data": {
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
                        "market": {
                            "conditionId": market.condition_id,
                            "question": market.question,
                            "resolutionDate": market.resolution_date,
                            "verdict": market.verdict,
                            "direction": market.direction,
                            "confidence": market.confidence,
                            "volume": market.volume_usdc,
                            "traderCount": market.trader_count,
                            "manipulability": market.manipulability,
                        },
                    },
                }
                redis = get_redis()
                await redis.publish(ALERTS_CHANNEL, json.dumps(payload))
            except Exception as e:
                logger.warning(f"Failed to publish alert to Redis: {e}")
        except Exception as e:
            logger.error(f"Failed to emit alert for trade {trade.transaction_hash}: {e}")


# Singleton
scoring_engine = ScoringEngine()
