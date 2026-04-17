"""
Grid-search weight calibration against known insider and clean wallets.
Writes weights_report.json to the backend/ directory.
"""
import json
import logging
import os
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_calibration() -> dict:
    """
    1. Load trades from INSIDER_CALIBRATION_WALLETS and CLEAN_CALIBRATION_WALLETS
    2. Grid-search weight combinations (step 0.05, constrained to sum=1.0)
    3. Optimise: maximise insider mean score - clean mean score
    4. Write weights_report.json
    5. Return optimal_weights dict
    """
    from app.models.insider_score import InsiderScore
    from app.models.trade import Trade
    from app.models.wallet import Wallet
    from app.models.market import Market
    from app.scorer.factors import (
        factor_entry_timing,
        factor_market_count,
        factor_trade_size,
        factor_wallet_age,
        factor_concentration,
    )
    from app.utils.constants import INSIDER_CALIBRATION_WALLETS, CLEAN_CALIBRATION_WALLETS, KNOWN_WALLETS
    from app.config import settings

    logger.info("Starting calibration...")

    # Load trades for all wallets
    all_wallets = INSIDER_CALIBRATION_WALLETS + CLEAN_CALIBRATION_WALLETS

    # Collect scoring data per wallet
    wallet_scores: dict[str, list[dict]] = {}

    for address in all_wallets:
        trades = await Trade.find(Trade.maker == address).to_list()
        if not trades:
            logger.warning(f"No trades found for {address}, skipping in calibration")
            continue

        trade_data_list = []
        for trade in trades:
            wallet = await Wallet.find_one(Wallet.address == address)
            market = await Market.find_one(Market.condition_id == trade.condition_id)
            if not wallet or not market:
                continue

            resolution_ts = market.resolution_timestamp
            if not resolution_ts and market.resolution_date:
                try:
                    dt = datetime.strptime(market.resolution_date, "%Y-%m-%d")
                    resolution_ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
                except ValueError:
                    resolution_ts = trade.timestamp + 86400 * 30

            market_creation_ts = resolution_ts - 86400 * 30 if resolution_ts else trade.timestamp - 86400 * 30

            trade_data_list.append({
                "f_entry": factor_entry_timing(
                    trade.timestamp,
                    resolution_ts or (trade.timestamp + 86400 * 7),
                    market_creation_ts,
                ),
                "f_market": factor_market_count(wallet.markets_traded or 1),
                "f_size": factor_trade_size(
                    trade.amount_usdc,
                    wallet.average_trade_size_usdc or trade.amount_usdc,
                    settings.MIN_TRADE_SIZE_USDC,
                ),
                "f_age": factor_wallet_age(
                    wallet.first_deposit_timestamp,
                    trade.timestamp,
                ),
                "f_concentration": factor_concentration(
                    trade.amount_usdc,
                    wallet.total_volume_usdc or trade.amount_usdc,
                ),
            })

        if trade_data_list:
            wallet_scores[address] = trade_data_list

    if not wallet_scores:
        logger.warning("No calibration data available — using default weights")
        from app.scorer.weights import DEFAULT_WEIGHTS
        return DEFAULT_WEIGHTS

    def compute_mean_score(weights: dict, addresses: list[str]) -> float:
        scores = []
        for addr in addresses:
            if addr not in wallet_scores:
                continue
            for td in wallet_scores[addr]:
                s = (
                    td["f_entry"] * weights["entryTiming"]
                    + td["f_market"] * weights["marketCount"]
                    + td["f_size"] * weights["tradeSize"]
                    + td["f_age"] * weights["walletAge"]
                    + td["f_concentration"] * weights["concentration"]
                )
                scores.append(max(0.0, min(1.0, s)))
        return sum(scores) / len(scores) if scores else 0.0

    # Grid search — step size 0.05, constrained to sum=1.0
    steps = [i / 20 for i in range(1, 20)]  # 0.05 to 0.95

    best_objective = -999.0
    best_weights: dict[str, float] = {}
    keys = ["entryTiming", "marketCount", "walletAge", "tradeSize", "concentration"]

    for v1 in steps:
        for v2 in steps:
            for v3 in steps:
                for v4 in steps:
                    v5 = round(1.0 - v1 - v2 - v3 - v4, 4)
                    if v5 < 0.01 or v5 > 0.95:
                        continue
                    w = {
                        "entryTiming": v1,
                        "marketCount": v2,
                        "walletAge": v3,
                        "tradeSize": v4,
                        "concentration": v5,
                    }
                    insider_mean = compute_mean_score(w, INSIDER_CALIBRATION_WALLETS)
                    clean_mean = compute_mean_score(w, CLEAN_CALIBRATION_WALLETS)
                    objective = insider_mean - clean_mean
                    if objective > best_objective:
                        best_objective = objective
                        best_weights = w.copy()

    if not best_weights:
        from app.scorer.weights import DEFAULT_WEIGHTS
        best_weights = DEFAULT_WEIGHTS

    insider_mean = compute_mean_score(best_weights, INSIDER_CALIBRATION_WALLETS)
    clean_mean = compute_mean_score(best_weights, CLEAN_CALIBRATION_WALLETS)

    # Per-wallet results
    wallets_tested = {}
    for addr in all_wallets:
        label = KNOWN_WALLETS.get(addr)
        wallet_type = "insider" if addr in INSIDER_CALIBRATION_WALLETS else "clean"
        if addr in wallet_scores:
            scores = []
            for td in wallet_scores[addr]:
                s = (
                    td["f_entry"] * best_weights["entryTiming"]
                    + td["f_market"] * best_weights["marketCount"]
                    + td["f_size"] * best_weights["tradeSize"]
                    + td["f_age"] * best_weights["walletAge"]
                    + td["f_concentration"] * best_weights["concentration"]
                )
                scores.append(max(0.0, min(1.0, s)))
            mean_score = sum(scores) / len(scores) if scores else 0.0
        else:
            mean_score = 0.0
        wallets_tested[addr] = {
            "label": label,
            "mean_score": round(mean_score, 4),
            "type": wallet_type,
        }

    report = {
        "model_version": "2.0",
        "generated_at": datetime.utcnow().isoformat(),
        "optimal_weights": {k: round(v, 4) for k, v in best_weights.items()},
        "weight_justification": {
            "entryTiming": "Strongest signal — insiders buy close to resolution",
            "walletAge": "Fresh wallets created specifically for the trade are high-confidence insider tells",
            "marketCount": "Insiders target 1-3 specific markets; legitimate traders diversify",
            "tradeSize": "Insiders commit large capital; small trades below $5K are excluded",
            "concentration": "Insiders go all-in on one outcome; diversified allocations indicate normal behaviour",
        },
        "calibration_results": {
            "insider_wallets_mean_score": round(insider_mean, 4),
            "clean_wallets_mean_score": round(clean_mean, 4),
            "separation_delta": round(insider_mean - clean_mean, 4),
            "wallets_tested": wallets_tested,
        },
        "thresholds": {
            "insider": 0.75,
            "suspicious": 0.50,
        },
    }

    # Write report to backend/ directory
    report_path = Path(__file__).parent.parent.parent / "weights_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(
        f"Calibration complete. Insider mean: {insider_mean:.3f}, "
        f"Clean mean: {clean_mean:.3f}, Delta: {insider_mean - clean_mean:.3f}"
    )
    logger.info(f"Optimal weights: {best_weights}")
    logger.info(f"Report written to {report_path}")

    return best_weights
