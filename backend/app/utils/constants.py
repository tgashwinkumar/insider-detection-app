# Contract addresses (Polygon PoS mainnet)
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKEN_ADDRESS = "0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3"

# Polygon network
POLYGON_CHAIN_ID = 137

# The Graph subgraph ID for Polymarket CTF Exchange
POLYMARKET_SUBGRAPH_ID = "EZCTgSzLPuBSqQcuR3ifeiKHKBnpjHSNbYpty8Mnjm9D"

# Known wallets — for label display
KNOWN_WALLETS: dict[str, str | None] = {
    "0xee50a31c3f5a7c77824b12a941a54388a2827ed6": "AlphaRaccoon",
    "0x6baf05d193692bb208d616709e27442c910a94c5": "SBet365",
    "0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2": "ricosuave",
    "0x7f1329ade2ec162c6f8791dad99125e0dc49801c": "gj1",
    "0xc51eedc01790252d571648cb4abd8e9876de5202": "hogriddahhhh",
    "0x976685b6e867a0400085b1273309e84cd0fc627c": "fromagi",
    "0x55ea982cebff271722419595e0659ef297b48d7c": "flaccidwillie",
    "0x31a56e9e690c621ed21de08cb559e9524cdb8ed9": None,  # Maduro unnamed
}

# Calibration ground truth — sourced directly from the assignment PDF
INSIDER_CALIBRATION_WALLETS: list[str] = [
    "0xee50a31c3f5a7c77824b12a941a54388a2827ed6",  # AlphaRaccoon
    "0x6baf05d193692bb208d616709e27442c910a94c5",  # SBet365
    "0x31a56e9e690c621ed21de08cb559e9524cdb8ed9",  # Unnamed Maduro
    "0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2",  # ricosuave
    "0x7f1329ade2ec162c6f8791dad99125e0dc49801c",  # gj1
    "0x976685b6e867a0400085b1273309e84cd0fc627c",  # fromagi
    "0x55ea982cebff271722419595e0659ef297b48d7c",  # flaccidwillie
]

# NOT an insider — smart trader who scraped data, per assignment PDF
CLEAN_CALIBRATION_WALLETS: list[str] = [
    "0xc51eedc01790252d571648cb4abd8e9876de5202",  # hogriddahhhh
]

# Reference transaction from assignment PDF for validation
SAMPLE_ORDER_FILLED_TX = "0x6599fcc58912b6ea1f3fbed5a801b28399097edfac3216fbf3cbbc9763837273"

# ERC20 Transfer event signature — keccak256("Transfer(address,address,uint256)")
ERC20_TRANSFER_EVENT_SIG = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# OrderFilled event signature for CTF Exchange
# keccak256("OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
ORDERFILLED_EVENT_SIG = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06a058d2cb5f52fc7d7c3b3bc"

# Classification thresholds
INSIDER_THRESHOLD = 0.75
SUSPICIOUS_THRESHOLD = 0.50

# Minimum trade size to score
MIN_TRADE_SIZE_USDC = 5000.0

# Fresh wallet threshold
FRESH_WALLET_DAYS = 7

# Redis pub/sub channel for alerts
ALERTS_CHANNEL = "sentinel:alerts"
