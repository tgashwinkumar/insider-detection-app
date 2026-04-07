from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field
import pymongo


class Trade(Document):
    transaction_hash: Indexed(str, unique=True)  # type: ignore[valid-type]
    block_number: int
    timestamp: int  # Unix seconds
    maker: str  # lowercase hex
    taker: str  # lowercase hex
    maker_asset_id: str
    taker_asset_id: str
    maker_amount_filled: float
    taker_amount_filled: float
    fee: float
    amount_usdc: float  # derived: taker_amount_filled / 1e6
    direction: str  # "yes" | "no"
    condition_id: str  # FK to Market
    source: str = "historical"  # "historical" | "live"
    indexed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "trades"
        indexes = [
            [("condition_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
            [("maker", pymongo.ASCENDING)],
            [("taker", pymongo.ASCENDING)],
            [("timestamp", pymongo.DESCENDING)],
        ]
