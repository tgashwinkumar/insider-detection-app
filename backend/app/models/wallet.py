from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field
import pymongo


class Wallet(Document):
    address: Indexed(str, unique=True)  # type: ignore[valid-type]
    first_deposit_timestamp: Optional[int] = None  # Unix seconds
    first_deposit_amount_usdc: Optional[float] = None
    wallet_age_days: Optional[float] = None
    total_trades: int = 0
    total_volume_usdc: float = 0.0
    average_trade_size_usdc: float = 0.0
    markets_traded: int = 0
    latest_insider_score: float = 0.0
    classification: str = "clean"  # "insider" | "suspicious" | "clean"
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    first_seen: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "wallets"
        indexes = [
            [("address", pymongo.ASCENDING)],
            [("latest_insider_score", pymongo.DESCENDING)],
            [("classification", pymongo.ASCENDING)],
        ]
