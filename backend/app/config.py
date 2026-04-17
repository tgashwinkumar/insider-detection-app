from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    API_PORT: int = 8000
    # Stored as comma-separated string in .env, parsed via property
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS_STR.split(",") if o.strip()]

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017/sentinel_insider"
    MONGODB_DB_NAME: str = "sentinel_insider"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Etherscan v2
    ETHERSCAN_API_KEY: str = ""
    ETHERSCAN_API_URL: str = "https://api.etherscan.io/v2/api"

    # The Graph
    THEGRAPH_API_KEY: str = "1e8ca4741dd5cd3726e2423ee784265a"
    POLYMARKET_SUBGRAPH_URL: str = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket"

    # Polymarket APIs
    POLYMARKET_GAMMA_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_URL: str = "https://clob.polymarket.com"

    # Polygon RPC
    POLYGON_RPC_URL: str = "https://polygon.rpc.thirdweb.com"
    POLYGON_RPC_URL: str = "https://eth-mainnet.g.alchemy.com/v2/oZ1e_DUQ4aPfNuNKKuOxn"
    POLYGON_WS_URL: str = "wss://polygon-bor-rpc.publicnode.com"

    # Contract addresses
    CTF_EXCHANGE_ADDRESS: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    USDC_E_ADDRESS: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

    # Scoring
    # Trades below MIN_TRADE_SIZE_USDC are always "clean" regardless of score.
    # Above this threshold: score >= INSIDER_THRESHOLD → "insider",
    # score >= SUSPICIOUS_THRESHOLD → "suspicious", else "clean".
    MIN_TRADE_SIZE_USDC: float = 5000.0   # gate for factor scoring AND classification
    INSIDER_THRESHOLD: float = 0.90
    SUSPICIOUS_THRESHOLD: float = 0.80
    FRESH_WALLET_DAYS: int = 7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
