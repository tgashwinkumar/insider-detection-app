from beanie import Document, Indexed
import pymongo


class Deposit(Document):
    wallet_address: Indexed(str, unique=True)  # type: ignore[valid-type]
    transaction_hash: str
    block_number: int
    timestamp: int  # Unix seconds
    amount_usdc: float

    class Settings:
        name = "deposits"
        indexes = [
            [("wallet_address", pymongo.ASCENDING)],
        ]
