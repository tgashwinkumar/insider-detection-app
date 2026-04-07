"""
Deposit indexer: fetches first USDC.e deposit for each wallet via Etherscan v2.
"""
import asyncio
import logging
from datetime import datetime

from app.models.wallet import Wallet
from app.models.deposit import Deposit
from app.utils.etherscan import etherscan_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
BATCH_PAUSE_SECONDS = 2.0


class DepositIndexer:
    async def index_wallet(self, wallet_address: str) -> None:
        """Fetch and store first USDC.e deposit for a single wallet."""
        # Skip if already indexed
        existing = await Deposit.find_one(Deposit.wallet_address == wallet_address.lower())
        if existing:
            return

        timestamp, amount = await etherscan_client.get_first_usdc_deposit(wallet_address)

        if timestamp is not None:
            deposit = Deposit(
                wallet_address=wallet_address.lower(),
                transaction_hash="",  # Etherscan tokentx doesn't always return hash easily
                block_number=0,
                timestamp=timestamp,
                amount_usdc=amount or 0.0,
            )
            try:
                await deposit.insert()
            except Exception:
                pass  # Already exists (race condition)

            # Update wallet
            wallet = await Wallet.find_one(Wallet.address == wallet_address.lower())
            if wallet:
                wallet.first_deposit_timestamp = timestamp
                wallet.first_deposit_amount_usdc = amount
                if timestamp > 0:
                    wallet.wallet_age_days = None  # Will be computed per-trade
                wallet.last_updated = datetime.utcnow()
                await wallet.save()

    async def index_wallets(self, wallet_addresses: list[str]) -> None:
        """Process wallets in batches with rate-limit pauses."""
        for i in range(0, len(wallet_addresses), BATCH_SIZE):
            batch = wallet_addresses[i : i + BATCH_SIZE]
            tasks = [self.index_wallet(addr) for addr in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            if i + BATCH_SIZE < len(wallet_addresses):
                await asyncio.sleep(BATCH_PAUSE_SECONDS)


deposit_indexer = DepositIndexer()
