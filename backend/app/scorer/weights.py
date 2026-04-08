# Default weights for the insider scoring model.
# These are the empirically calibrated starting weights:
#   entryTiming:   0.30 — Strongest signal; timing is the clearest insider tell
#   walletAge:     0.25 — Fresh wallets created for a single trade are high-confidence tells
#   marketCount:   0.20 — Focused wallets are unusual; insiders target 1-3 markets
#   tradeSize:     0.15 — Large bets matter but can be coincidence
#   concentration: 0.10 — All-in bets reinforce other signals
# Weights sum to 1.0

DEFAULT_WEIGHTS: dict[str, float] = {
    "entryTiming": 0.30,
    "marketCount": 0.20,
    "walletAge": 0.25,
    "tradeSize": 0.8,
    "concentration": 0.10,
}

# Verify sum
# assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"
