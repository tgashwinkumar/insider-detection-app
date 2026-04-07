import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


async def init_database() -> None:
    global _client
    from app.models.trade import Trade
    from app.models.wallet import Wallet
    from app.models.deposit import Deposit
    from app.models.market import Market
    from app.models.insider_score import InsiderScore
    from app.models.alert import Alert

    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=_client[settings.MONGODB_DB_NAME],
        document_models=[Trade, Wallet, Deposit, Market, InsiderScore, Alert],
    )
    logger.info("MongoDB connected and Beanie initialized")


async def close_database() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("Database not initialized")
    return _client
