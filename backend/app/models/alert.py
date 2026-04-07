from datetime import datetime
from beanie import Document
from pydantic import Field
import pymongo


class Alert(Document):
    trade_id: str
    wallet_address: str
    condition_id: str
    score: float
    classification: str
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    notified: bool = False

    class Settings:
        name = "alerts"
        indexes = [
            [("triggered_at", pymongo.DESCENDING)],
            [("classification", pymongo.ASCENDING)],
            [("trade_id", pymongo.ASCENDING)],
        ]
