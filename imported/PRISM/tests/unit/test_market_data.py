"""Tests for real market data fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from prism.data.market_data import fetch_returns, make_synthetic_pre_data
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


class TestFetchReturnsMocked:
    """Tests for fetch_returns using mocked yfinance (no network required)."""

    def test_import_error_when_yfinance_missing(self):
        import builtins
        import importlib

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "yfinance":
                raise ImportError("No module named 'yfinance'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            import prism.data.market_data as mdm

            importlib.reload(mdm)
            with pytest.raises(ImportError, match="yfinance is required"):
                mdm.fetch_returns(["SPY"], start="2020-01-01", end="2020-06-01")
        importlib.reload(mdm)

    @patch("prism.data.market_data.yf", create=True)
    def test_single_ticker(self, mock_yf: MagicMock):
        prices = np.array([100.0, 101.0, 102.0, 101.5, 103.0]).reshape(-1, 1)
        index = pd.date_range("2020-01-01", periods=5)
        df = pd.DataFrame(prices, index=index, columns=["Close"])
        mock_yf.download.return_value = df
        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            md = fetch_returns(["SPY"], start="2020-01-01", end="2020-01-06")
        assert isinstance(md, MarketData)
        assert md.n_days == 4
        assert md.n_instruments == 1

    def test_empty_data_raises(self):

        mock_yf = MagicMock()
        mock_yf.download.return_value = pd.DataFrame()
        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            with pytest.raises(ValueError, match="No data returned"):
                fetch_returns(["FAKE"], start="2020-01-01", end="2020-01-06")

    def test_insufficient_data_raises(self):

        mock_yf = MagicMock()
        prices = np.array([100.0]).reshape(-1, 1)
        index = pd.date_range("2020-01-01", periods=1)
        df = pd.DataFrame(prices, index=index, columns=["Close"])
        mock_yf.download.return_value = df
        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            with pytest.raises(ValueError, match="Insufficient price data"):
                fetch_returns(["SPY"], start="2020-01-01", end="2020-01-02")

    def test_multi_ticker(self):
        mock_yf = MagicMock()
        prices = np.array([[100.0, 200.0], [101.0, 202.0], [102.0, 201.0]])
        index = pd.date_range("2020-01-01", periods=3)
        cols = pd.MultiIndex.from_tuples([("Close", "SPY"), ("Close", "IWM")])
        df = pd.DataFrame(prices, index=index, columns=cols)
        mock_yf.download.return_value = df
        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            md = fetch_returns(["SPY", "IWM"], start="2020-01-01", end="2020-01-04")
        assert isinstance(md, MarketData)
        assert md.n_instruments == 2
        assert md.n_days == 2


class TestFetchReturnsLive:
    """Tests for yfinance fetch — skipped if no internet or yfinance unavailable."""

    @pytest.fixture
    def can_fetch(self):
        try:
            import yfinance  # noqa: F401

            return True
        except ImportError:
            return False

    def test_fetch_single_ticker(self, can_fetch: bool):
        if not can_fetch:
            pytest.skip("yfinance not available")

        try:
            md = fetch_returns(["SPY"], start="2020-01-01", end="2020-06-01")
            assert isinstance(md, MarketData)
            assert md.n_days > 50
            assert md.n_instruments == 1
        except Exception:
            pytest.skip("Network unavailable")

    def test_fetch_pre_intervention(self, can_fetch: bool):
        if not can_fetch:
            pytest.skip("yfinance not available")
        from prism.data.market_data import fetch_pre_intervention_data

        try:
            md = fetch_pre_intervention_data("US_equity_smallcap", "2016-10-03")
            assert isinstance(md, MarketData)
            assert md.n_days > 100
        except Exception:
            pytest.skip("Network unavailable")
