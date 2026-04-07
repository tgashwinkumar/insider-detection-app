"""
Wallet enrichment orchestration service.
"""
import logging
from datetime import datetime
from typing import Optional

from app.models.wallet import Wallet
from app.models.trade import Trade

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
        """Recompute aggregate stats for a wallet from trades in MongoDB."""
        address = address.lower()
        wallet = await self.get_or_create_wallet(address)

        trades = await Trade.find(Trade.maker == address).to_list()
        if not trades:
            return

        total_trades = len(trades)
        total_volume = sum(t.amount_usdc for t in trades)
        avg_size = total_volume / total_trades if total_trades else 0.0
        markets = len({t.condition_id for t in trades})
        first_trade_ts = min(t.timestamp for t in trades) if trades else 0

        wallet.total_trades = total_trades
        wallet.total_volume_usdc = total_volume
        wallet.average_trade_size_usdc = avg_size
        wallet.markets_traded = markets
        wallet.last_updated = datetime.utcnow()
        await wallet.save()

    async def enrich_wallet(self, address: str) -> Wallet:
        """Full enrichment: deposit lookup + stats update."""
        from app.services.indexer.deposit_indexer import deposit_indexer
        await deposit_indexer.index_wallet(address)
        await self.update_wallet_stats(address)
        wallet = await self.get_or_create_wallet(address)
        return wallet


wallet_service = WalletService()
