from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field
import pymongo


class InsiderScore(Document):
    trade_id: str  # transaction_hash reference
    wallet_address: str
    condition_id: str
    # 5 factor scores
    factor_entry_timing: float
    factor_market_count: float
    factor_trade_size: float
    factor_wallet_age: float
    factor_concentration: float
    # Composite
    composite_score: float  # 0.0-1.0
    classification: str  # "insider" | "suspicious" | "clean"
    weights_used: dict
    model_version: str = "2.0"
    calculated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"protected_namespaces": ()}

    class Settings:
        name = "insider_scores"
        indexes = [
            [("trade_id", pymongo.ASCENDING)],
            [("wallet_address", pymongo.ASCENDING)],
            [("condition_id", pymongo.ASCENDING)],
            [("composite_score", pymongo.DESCENDING)],
        ]
