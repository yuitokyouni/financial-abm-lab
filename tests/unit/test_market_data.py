"""Tests for real market data fetcher."""

import numpy as np
import pytest

from prism.data.market_data import make_synthetic_pre_data
from prism.types import MarketData


class TestSyntheticPreData:
    def test_returns_market_data(self):
        md = make_synthetic_pre_data(seed=42)
        assert isinstance(md, MarketData)

    def test_shape(self):
        md = make_synthetic_pre_data(seed=42, n_days=200)
        assert md.n_days == 200
        assert md.n_instruments == 1

    def test_reproducibility(self):
        md1 = make_synthetic_pre_data(seed=99)
        md2 = make_synthetic_pre_data(seed=99)
        np.testing.assert_array_equal(md1.returns, md2.returns)

    def test_different_seeds(self):
        md1 = make_synthetic_pre_data(seed=1)
        md2 = make_synthetic_pre_data(seed=2)
        assert not np.array_equal(md1.returns, md2.returns)

    def test_custom_vol(self):
        md = make_synthetic_pre_data(seed=42, vol=0.05, n_days=1000)
        actual_vol = float(np.std(md.returns))
        assert 0.03 < actual_vol < 0.07


class TestFetchReturns:
    """Tests for yfinance fetch — skipped if no internet or yfinance unavailable."""

    @pytest.fixture
    def can_fetch(self):
        try:
            import yfinance  # noqa: F401

            return True
        except ImportError:
            return False

    def test_fetch_single_ticker(self, can_fetch):
        if not can_fetch:
            pytest.skip("yfinance not available")
        from prism.data.market_data import fetch_returns

        try:
            md = fetch_returns(["SPY"], start="2020-01-01", end="2020-06-01")
            assert isinstance(md, MarketData)
            assert md.n_days > 50
            assert md.n_instruments == 1
        except Exception:
            pytest.skip("Network unavailable")

    def test_fetch_pre_intervention(self, can_fetch):
        if not can_fetch:
            pytest.skip("yfinance not available")
        from prism.data.market_data import fetch_pre_intervention_data

        try:
            md = fetch_pre_intervention_data("US_equity_smallcap", "2016-10-03")
            assert isinstance(md, MarketData)
            assert md.n_days > 100
        except Exception:
            pytest.skip("Network unavailable")
