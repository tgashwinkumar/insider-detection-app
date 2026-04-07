import logging
from web3 import Web3
from app.config import settings

logger = logging.getLogger(__name__)


class PolygonRPC:
    def __init__(self) -> None:
        self._w3: Web3 | None = None

    @property
    def w3(self) -> Web3:
        if self._w3 is None:
            self._w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        return self._w3

    def get_block_number(self) -> int:
        return self.w3.eth.block_number

    def is_connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def keccak(self, text: str) -> str:
        return Web3.keccak(text=text).hex()


polygon_rpc = PolygonRPC()
