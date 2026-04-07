"""
5-factor insider detection functions.
All return float in [0.0, 1.0]. Higher = more suspicious.
"""
from typing import Optional


def factor_entry_timing(
    trade_timestamp: int,
    resolution_timestamp: int,
    market_creation_timestamp: int,
) -> float:
    """
    Signal: Did this wallet enter close to market resolution?
    Position of trade within market lifetime. Near 1.0 = suspicious.
    """
    if trade_timestamp > resolution_timestamp:
        return 0.0  # Post-resolution — irrelevant

    lifetime = resolution_timestamp - market_creation_timestamp
    # Clamp to avoid division weirdness on very short markets
    if lifetime < 3600:
        lifetime = 3600

    position = (trade_timestamp - market_creation_timestamp) / lifetime
    position = max(0.0, min(1.0, position))

    if position >= 0.95:
        return 1.0
    elif position >= 0.90:
        return 0.85
    elif position >= 0.80:
        return 0.65
    elif position >= 0.70:
        return 0.45
    elif position >= 0.50:
        return 0.20
    else:
        return 0.05


def factor_market_count(
    markets_traded: int,
    trades_in_window: int = 1,
) -> float:
    """
    Signal: Has this wallet traded in very few markets?
    Insiders target 1-3 specific markets; legitimate traders diversify.
    """
    if markets_traded <= 0:
        markets_traded = 1

    if markets_traded == 1:
        return 1.0
    elif markets_traded == 2:
        return 0.85
    elif markets_traded == 3:
        return 0.65
    elif markets_traded == 4:
        return 0.40
    elif markets_traded == 5:
        return 0.20
    else:
        return 0.05


def factor_trade_size(
    amount_usdc: float,
    wallet_avg_usdc: float,
    min_threshold: float = 5000.0,
) -> float:
    """
    Signal: Is this trade significantly larger than this wallet's average?
    Insiders commit capital decisively.
    """
    if amount_usdc < min_threshold:
        return 0.0

    denominator = max(wallet_avg_usdc, min_threshold)
    ratio = amount_usdc / denominator

    if ratio >= 5.0:
        score = 1.0
    elif ratio >= 3.0:
        score = 0.80
    elif ratio >= 2.0:
        score = 0.60
    elif ratio >= 1.5:
        score = 0.40
    elif ratio >= 1.0:
        score = 0.20
    else:
        score = 0.10

    # Absolute size bonus
    if amount_usdc >= 100_000:
        score = min(1.0, score + 0.10)
    elif amount_usdc >= 50_000:
        score = min(1.0, score + 0.05)

    return score


def factor_wallet_age(
    first_deposit_timestamp: Optional[int],
    trade_timestamp: int,
    fresh_threshold_days: int = 7,
) -> float:
    """
    Signal: Was this wallet newly created relative to the trade date?
    Insiders often use fresh wallets to avoid detection.
    """
    if first_deposit_timestamp is None:
        return 0.50  # Unknown age — neutral

    age_at_trade_days = (trade_timestamp - first_deposit_timestamp) / 86400

    if age_at_trade_days < 0:
        return 0.0  # Data error — wallet created after trade

    if age_at_trade_days == 0:
        return 1.0
    elif age_at_trade_days <= 1:
        return 0.95
    elif age_at_trade_days <= 3:
        return 0.85
    elif age_at_trade_days <= 7:
        return 0.70
    elif age_at_trade_days <= 14:
        return 0.45
    elif age_at_trade_days <= 30:
        return 0.25
    elif age_at_trade_days <= 90:
        return 0.10
    else:
        return 0.02


def factor_concentration(
    trade_amount_usdc: float,
    wallet_total_volume_usdc: float,
) -> float:
    """
    Signal: Is this trade a disproportionate share of wallet's total volume?
    Insiders bet everything on one outcome.
    """
    if wallet_total_volume_usdc <= 0:
        return 0.0

    share = trade_amount_usdc / wallet_total_volume_usdc
    share = min(1.0, share)

    if share >= 0.90:
        return 1.0
    elif share >= 0.75:
        return 0.85
    elif share >= 0.60:
        return 0.70
    elif share >= 0.50:
        return 0.55
    elif share >= 0.35:
        return 0.35
    elif share >= 0.20:
        return 0.15
    else:
        return 0.05


def compute_market_manipulability(liquidity_usdc: float) -> float:
    """
    Market-level manipulability score based on liquidity.
    Not a per-trade factor — stored on Market document.
    """
    if liquidity_usdc < 10_000:
        return 0.95
    elif liquidity_usdc < 50_000:
        return 0.75
    elif liquidity_usdc < 100_000:
        return 0.55
    elif liquidity_usdc < 500_000:
        return 0.35
    elif liquidity_usdc < 1_000_000:
        return 0.15
    else:
        return 0.05
