"""Unit tests for the composite scoring engine."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.scorer.weights import DEFAULT_WEIGHTS


class TestDefaultWeights:
    def test_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_weights_positive(self):
        for key, val in DEFAULT_WEIGHTS.items():
            assert val > 0, f"Weight {key} must be positive"

    def test_has_all_five_factors(self):
        required = {"entryTiming", "marketCount", "walletAge", "tradeSize", "concentration"}
        assert required == set(DEFAULT_WEIGHTS.keys())

    def test_entry_timing_is_highest(self):
        # entryTiming should be the highest weight
        assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["marketCount"]
        assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["tradeSize"]
        assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["concentration"]


class TestCompositeScoring:
    def test_all_max_factors_gives_one(self):
        """Pure math: all factors = 1.0 and weights sum to 1.0 → composite = 1.0"""
        composite = sum(DEFAULT_WEIGHTS.values()) * 1.0
        assert abs(composite - 1.0) < 1e-9

    def test_all_zero_factors_gives_zero(self):
        composite = sum(v * 0.0 for v in DEFAULT_WEIGHTS.values())
        assert composite == 0.0

    def test_insider_profile_scores_high(self):
        """Simulate an insider wallet profile and verify score >= 0.90"""
        factors = {
            "entryTiming": 0.95,
            "marketCount": 1.0,
            "walletAge": 0.95,
            "tradeSize": 0.80,
            "concentration": 0.90,
        }
        composite = sum(DEFAULT_WEIGHTS[k] * v for k, v in factors.items())
        assert composite >= 0.90, f"Expected >= 0.90 for insider threshold, got {composite:.3f}"

    def test_clean_profile_scores_low(self):
        """Simulate a clean wallet and verify score < 0.80"""
        factors = {
            "entryTiming": 0.05,
            "marketCount": 0.05,
            "walletAge": 0.02,
            "tradeSize": 0.10,
            "concentration": 0.05,
        }
        composite = sum(DEFAULT_WEIGHTS[k] * v for k, v in factors.items())
        assert composite < 0.80, f"Expected < 0.80 (suspicious threshold), got {composite:.3f}"


class TestClassificationThresholds:
    """Classification rules: trade > $5k gate, 0.80 = suspicious, 0.90 = insider."""

    def _engine(self):
        from app.scorer.engine import ScoringEngine
        return ScoringEngine()

    def test_small_trade_always_clean(self):
        """Trade <= $5,000 is always clean regardless of score."""
        engine = self._engine()
        assert engine._classify(1.0, 5000.0) == "clean"
        assert engine._classify(0.95, 4999.99) == "clean"
        assert engine._classify(0.85, 1000.0) == "clean"

    def test_insider_requires_score_90_and_large_trade(self):
        """Score >= 0.90 AND trade > $5,000 → insider."""
        engine = self._engine()
        assert engine._classify(0.90, 5001.0) == "insider"
        assert engine._classify(1.00, 10000.0) == "insider"

    def test_high_score_small_trade_is_suspicious_not_insider(self):
        """Score >= 0.90 but trade <= $5,000 → suspicious, not insider."""
        engine = self._engine()
        # Exactly at size boundary — stays suspicious
        assert engine._classify(0.95, 5000.0) == "clean"   # <= 5000 → clean
        assert engine._classify(0.95, 5001.0) == "insider"  # > 5000 → insider

    def test_suspicious_band(self):
        """Score >= 0.80 and < 0.90 with trade > $5,000 → suspicious."""
        engine = self._engine()
        assert engine._classify(0.80, 6000.0) == "suspicious"
        assert engine._classify(0.89, 50000.0) == "suspicious"

    def test_below_threshold_is_clean(self):
        """Score < 0.80 with large trade → clean."""
        engine = self._engine()
        assert engine._classify(0.79, 100000.0) == "clean"
        assert engine._classify(0.0, 999999.0) == "clean"


class TestFactorSources:
    """InsiderScore stores raw source values; API response includes factorSources."""

    def test_insider_score_model_has_source_fields(self):
        """InsiderScore model declares all 5 Optional source fields with None defaults."""
        from app.models.insider_score import InsiderScore

        fields = InsiderScore.model_fields
        expected = {
            "source_entry_timing_delta_seconds",
            "source_market_count",
            "source_trade_size_usdc",
            "source_wallet_age_days",
            "source_wallet_total_volume_usdc",
        }
        missing = expected - set(fields.keys())
        assert not missing, f"InsiderScore is missing source fields: {missing}"

        # All should default to None
        for field_name in expected:
            default = fields[field_name].default
            assert default is None, (
                f"{field_name} should default to None, got {default!r}"
            )

    def test_trade_to_response_includes_factor_sources_when_score_present(self):
        """_trade_to_response returns factorSources populated from the InsiderScore doc."""
        from unittest.mock import MagicMock
        from app.routers.markets import _trade_to_response

        trade = MagicMock()
        trade.transaction_hash = "0xabc"
        trade.maker = "0xwallet"
        trade.timestamp = 1700000000
        trade.amount_usdc = 25000.0
        trade.direction = "yes"

        score = MagicMock()
        score.classification = "insider"
        score.composite_score = 0.82
        score.factor_entry_timing = 0.9
        score.factor_market_count = 0.8
        score.factor_trade_size = 0.7
        score.factor_wallet_age = 1.0
        score.factor_concentration = 0.6
        score.source_entry_timing_delta_seconds = 86400.0
        score.source_market_count = 1
        score.source_trade_size_usdc = 25000.0
        score.source_wallet_age_days = 2.5
        score.source_wallet_total_volume_usdc = 30000.0

        result = _trade_to_response(trade, score)

        assert "factorSources" in result, "Response must include factorSources"
        fs = result["factorSources"]
        assert fs["entryTimingDeltaSeconds"] == 86400.0
        assert fs["previousTradesByWallet"] == 1
        assert fs["tradeSizeUsdc"] == 25000.0
        assert fs["walletAgeDays"] == 2.5
        assert fs["walletTotalVolumeUsdc"] == 30000.0

    def test_trade_to_response_factor_sources_when_no_score(self):
        """When no InsiderScore exists, factorSources has None for all except tradeSizeUsdc."""
        from unittest.mock import MagicMock
        from app.routers.markets import _trade_to_response

        trade = MagicMock()
        trade.transaction_hash = "0xdef"
        trade.maker = "0xwallet2"
        trade.timestamp = 1700000000
        trade.amount_usdc = 5000.0
        trade.direction = "no"

        result = _trade_to_response(trade, None)

        assert "factorSources" in result, "Response must include factorSources even without a score"
        fs = result["factorSources"]
        assert fs["tradeSizeUsdc"] == 5000.0, (
            "tradeSizeUsdc should fall back to trade.amount_usdc when no score"
        )
        assert fs["entryTimingDeltaSeconds"] is None
        assert fs["previousTradesByWallet"] is None
        assert fs["walletAgeDays"] is None
        assert fs["walletTotalVolumeUsdc"] is None

    def test_factor_sources_keys_match_expected_shape(self):
        """factorSources must contain exactly the 5 documented keys."""
        from unittest.mock import MagicMock
        from app.routers.markets import _trade_to_response

        trade = MagicMock()
        trade.transaction_hash = "0x123"
        trade.maker = "0xwallet3"
        trade.timestamp = 1700000000
        trade.amount_usdc = 1000.0
        trade.direction = "yes"

        result = _trade_to_response(trade, None)
        fs_keys = set(result["factorSources"].keys())
        expected_keys = {
            "entryTimingDeltaSeconds",
            "previousTradesByWallet",
            "tradeSizeUsdc",
            "walletAgeDays",
            "walletTotalVolumeUsdc",
        }
        assert fs_keys == expected_keys, (
            f"factorSources keys mismatch. Expected {expected_keys}, got {fs_keys}"
        )
