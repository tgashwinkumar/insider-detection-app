"""Unit tests for the composite scoring engine."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.scorer.weights import DEFAULT_WEIGHTS


# class TestDefaultWeights:
#     def test_weights_sum_to_one(self):
#         total = sum(DEFAULT_WEIGHTS.values())
#         assert abs(total - 1.0) < 1e-9

#     def test_all_weights_positive(self):
#         for key, val in DEFAULT_WEIGHTS.items():
#             assert val > 0, f"Weight {key} must be positive"

#     def test_has_all_five_factors(self):
#         required = {"entryTiming", "marketCount", "walletAge", "tradeSize", "concentration"}
#         assert required == set(DEFAULT_WEIGHTS.keys())

#     def test_entry_timing_is_highest(self):
#         # entryTiming should be the highest weight
#         assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["marketCount"]
#         assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["tradeSize"]
#         assert DEFAULT_WEIGHTS["entryTiming"] >= DEFAULT_WEIGHTS["concentration"]


# class TestCompositeScoring:
#     def test_all_max_factors_gives_one(self):
#         """Pure math: all factors = 1.0 and weights sum to 1.0 → composite = 1.0"""
#         composite = sum(DEFAULT_WEIGHTS.values()) * 1.0
#         assert abs(composite - 1.0) < 1e-9

#     def test_all_zero_factors_gives_zero(self):
#         composite = sum(v * 0.0 for v in DEFAULT_WEIGHTS.values())
#         assert composite == 0.0

#     def test_insider_profile_scores_high(self):
#         """Simulate an insider wallet profile and verify score >= 0.75"""
#         factors = {
#             "entryTiming": 0.95,
#             "marketCount": 1.0,
#             "walletAge": 0.95,
#             "tradeSize": 0.80,
#             "concentration": 0.90,
#         }
#         composite = sum(DEFAULT_WEIGHTS[k] * v for k, v in factors.items())
#         assert composite >= 0.75, f"Expected >= 0.75, got {composite:.3f}"

#     def test_clean_profile_scores_low(self):
#         """Simulate a clean wallet and verify score < 0.50"""
#         factors = {
#             "entryTiming": 0.05,
#             "marketCount": 0.05,
#             "walletAge": 0.02,
#             "tradeSize": 0.10,
#             "concentration": 0.05,
#         }
#         composite = sum(DEFAULT_WEIGHTS[k] * v for k, v in factors.items())
#         assert composite < 0.50, f"Expected < 0.50, got {composite:.3f}"
