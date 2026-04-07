"""
Wallet enrichment orchestration service.
"""
import logging
from datetime import datetime

from app.models.wallet import Wallet

logger = logging.getLogger(__name__)


class WalletService:
    async def get_or_create_wallet(self, address: str) -> Wallet:
        address = address.lower()
        wallet = await Wallet.find_one(Wallet.address == address)
        if not wallet:
            wallet = Wallet(address=address)
            await wallet.insert()
        return wallet

    async def update_wallet_stats(self, address: str) -> None:
        """
        Recompute aggregate stats for a wallet from The Graph subgraph —
        covers the wallet's COMPLETE on-chain history, not just the trades
        we have ingested locally into MongoDB.
        """
        address = address.lower()
        wallet = await self.get_or_create_wallet(address)

        from app.services.indexer.subgraph import subgraph_indexer

        # 1. Full trade history from The Graph (standard + NegRisk exchanges)
        all_events = await subgraph_indexer.fetch_wallet_all_trades(address)

        if not all_events:
            # No on-chain history found — keep whatever stats are already stored
            logger.info(f"No subgraph events found for {address}; skipping stat update")
            return

        # 2. Total trades and USDC volume
        #    takerAmountFilled / 1e6 is the USDC notional — same convention as backfill.py
        total_trades = len(all_events)
        total_volume = sum(
            float(e.get("takerAmountFilled") or 0) / 1e6
            for e in all_events
        )
        avg_size = total_volume / total_trades if total_trades else 0.0

        # 3. Unique markets traded — resolve all token IDs to condition IDs
        token_ids: set[str] = set()
        for e in all_events:
            if e.get("takerAssetId"):
                token_ids.add(e["takerAssetId"])
            if e.get("makerAssetId"):
                token_ids.add(e["makerAssetId"])

        token_to_condition = await subgraph_indexer.resolve_token_conditions(
            list(token_ids)
        )
        # Unique condition IDs = unique markets (collateral token "0" has no MarketData entry
        # so it's automatically excluded from the count)
        markets_traded = len(set(token_to_condition.values()))

        # 4. Persist
        wallet.total_trades = total_trades
        wallet.total_volume_usdc = round(total_volume, 2)
        wallet.average_trade_size_usdc = round(avg_size, 2)
        wallet.markets_traded = markets_traded
        wallet.last_updated = datetime.utcnow()
        await wallet.save()

        logger.info(
            f"Wallet stats updated for {address}: "
            f"{total_trades} trades, ${total_volume:,.2f} USDC, {markets_traded} markets"
        )

    async def enrich_wallet(self, address: str) -> Wallet:
        """Full enrichment: deposit lookup + stats update."""
        from app.services.indexer.deposit_indexer import deposit_indexer
        await deposit_indexer.index_wallet(address)
        await self.update_wallet_stats(address)
        wallet = await self.get_or_create_wallet(address)
        return wallet


wallet_service = WalletService()
