"""Unit tests for the 5 insider detection factor functions."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.scorer.factors import (
    factor_entry_timing,
    factor_market_count,
    factor_trade_size,
    factor_wallet_age,
    factor_concentration,
    compute_market_manipulability,
)

# Reference timestamps
MARKET_START = 1_700_000_000
MARKET_END = 1_700_000_000 + 86400 * 30  # 30 days


class TestEntryTiming:
    def test_extreme_late_entry(self):
        # Trade in last 5% of market life
        ts = MARKET_START + int((MARKET_END - MARKET_START) * 0.97)
        score = factor_entry_timing(ts, MARKET_END, MARKET_START)
        assert score == 1.0

    def test_post_resolution(self):
        score = factor_entry_timing(MARKET_END + 100, MARKET_END, MARKET_START)
        assert score == 0.0

    def test_early_entry(self):
        ts = MARKET_START + int((MARKET_END - MARKET_START) * 0.20)
        score = factor_entry_timing(ts, MARKET_END, MARKET_START)
        assert score == 0.05

    def test_score_in_range(self):
        for pct in [0.1, 0.4, 0.6, 0.75, 0.85, 0.92, 0.97]:
            ts = MARKET_START + int((MARKET_END - MARKET_START) * pct)
            score = factor_entry_timing(ts, MARKET_END, MARKET_START)
            assert 0.0 <= score <= 1.0


class TestMarketCount:
    def test_single_market(self):
        assert factor_market_count(1) == 1.0

    def test_two_markets(self):
        assert factor_market_count(2) == 0.85

    def test_three_markets(self):
        assert factor_market_count(3) == 0.65

    def test_many_markets(self):
        assert factor_market_count(10) == 0.05

    def test_score_in_range(self):
        for n in range(1, 15):
            score = factor_market_count(n)
            assert 0.0 <= score <= 1.0


class TestTradeSize:
    def test_below_minimum(self):
        assert factor_trade_size(1000, 5000, 5000) == 0.0

    def test_five_x_average(self):
        score = factor_trade_size(50000, 10000, 5000)
        assert score >= 0.80  # 5x + $50k bonus

    def test_large_absolute_bonus(self):
        score_big = factor_trade_size(150000, 10000, 5000)
        score_small = factor_trade_size(20000, 10000, 5000)
        assert score_big >= score_small

    def test_score_in_range(self):
        for amount in [5000, 10000, 50000, 100000, 500000]:
            score = factor_trade_size(amount, 10000, 5000)
            assert 0.0 <= score <= 1.0


class TestWalletAge:
    def test_unknown_age(self):
        score = factor_wallet_age(None, 1_700_000_000)
        assert score == 0.50

    def test_same_day(self):
        ts = 1_700_000_000
        score = factor_wallet_age(ts, ts)
        assert score == 1.0

    def test_very_old_wallet(self):
        ts = 1_700_000_000
        deposit = ts - 86400 * 200  # 200 days ago
        score = factor_wallet_age(deposit, ts)
        assert score == 0.02

    def test_negative_age(self):
        ts = 1_700_000_000
        deposit = ts + 86400  # deposit AFTER trade — data error
        score = factor_wallet_age(deposit, ts)
        assert score == 0.0

    def test_score_in_range(self):
        base_ts = 1_700_000_000
        for days in [0, 1, 3, 7, 14, 30, 90, 180]:
            deposit_ts = base_ts - 86400 * days
            score = factor_wallet_age(deposit_ts, base_ts)
            assert 0.0 <= score <= 1.0


class TestConcentration:
    def test_zero_total_volume(self):
        assert factor_concentration(10000, 0) == 0.0

    def test_full_concentration(self):
        score = factor_concentration(10000, 10000)
        assert score == 1.0

    def test_low_concentration(self):
        score = factor_concentration(1000, 100000)
        assert score == 0.05

    def test_score_in_range(self):
        for pct in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0]:
            score = factor_concentration(pct * 100000, 100000)
            assert 0.0 <= score <= 1.0


class TestManipulability:
    def test_tiny_market(self):
        assert compute_market_manipulability(5000) == 0.95

    def test_large_market(self):
        assert compute_market_manipulability(2_000_000) == 0.05

    def test_in_range(self):
        for liq in [1000, 10000, 50000, 100000, 500000, 1000000, 5000000]:
            score = compute_market_manipulability(liq)
            assert 0.0 <= score <= 1.0
