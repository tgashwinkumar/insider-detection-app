"""Unit tests for wallet label lookup and constants."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils.constants import KNOWN_WALLETS, INSIDER_CALIBRATION_WALLETS, CLEAN_CALIBRATION_WALLETS


class TestKnownWallets:
    def test_alpha_raccoon_label(self):
        assert KNOWN_WALLETS["0xee50a31c3f5a7c77824b12a941a54388a2827ed6"] == "AlphaRaccoon"

    def test_hogriddahhhh_label(self):
        assert KNOWN_WALLETS["0xc51eedc01790252d571648cb4abd8e9876de5202"] == "hogriddahhhh"

    def test_unnamed_wallet_is_none(self):
        assert KNOWN_WALLETS["0x31a56e9e690c621ed21de08cb559e9524cdb8ed9"] is None

    def test_seven_insider_wallets(self):
        assert len(INSIDER_CALIBRATION_WALLETS) == 7

    def test_one_clean_wallet(self):
        assert len(CLEAN_CALIBRATION_WALLETS) == 1
        assert CLEAN_CALIBRATION_WALLETS[0] == "0xc51eedc01790252d571648cb4abd8e9876de5202"

    def test_hogriddahhhh_is_clean_not_insider(self):
        hogriddahhhh = "0xc51eedc01790252d571648cb4abd8e9876de5202"
        assert hogriddahhhh not in INSIDER_CALIBRATION_WALLETS
        assert hogriddahhhh in CLEAN_CALIBRATION_WALLETS

    def test_no_overlap_between_insider_and_clean(self):
        insider_set = set(INSIDER_CALIBRATION_WALLETS)
        clean_set = set(CLEAN_CALIBRATION_WALLETS)
        assert len(insider_set & clean_set) == 0
