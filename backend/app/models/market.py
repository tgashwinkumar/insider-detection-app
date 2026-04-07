from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field
import pymongo


class Market(Document):
    condition_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    slug: Optional[str] = None
    question: str
    resolution_date: str  # "YYYY-MM-DD" string
    resolution_timestamp: Optional[int] = None  # Unix seconds
    creator: Optional[str] = None
    liquidity_usdc: float = 0.0
    volume_usdc: float = 0.0
    outcomes: list[str] = ["YES", "NO"]
    resolved: bool = False
    resolution: Optional[str] = None
    verdict: str = "clean"  # "insider" | "suspicious" | "clean"
    direction: Optional[str] = None
    confidence: int = 0  # 0-100
    manipulability: float = 0.0
    trader_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "markets"
        indexes = [
            [("condition_id", pymongo.ASCENDING)],
            [("slug", pymongo.ASCENDING)],
        ]
