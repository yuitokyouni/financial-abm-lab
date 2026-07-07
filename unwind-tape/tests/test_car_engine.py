"""unwind-tape / task C — CAR engine unit tests.

合成データで engine の math を検証:
  - day 0 規則 (after_close=TRUE → 翌営業日、非営業日 → 翌営業日)
  - business day navigation
  - estimation window OLS (α/β 回復)
  - topix_adjusted AR
  - market_model AR
  - CAR sum over event window
  - drift between two day 0s
  - recovery
  - ADV
  - abnormal volume
  - **ルックアヘッド禁止**: 推定窓に day 0 以降を混ぜないこと (rank test)
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import json  # noqa: E402
import logging  # noqa: E402
from car_engine import (  # noqa: E402
    BusinessCalendar, Config, MMFit, FieldMismatchError,
    load_daily_quotes, load_topix, load_trading_calendar, load_fins_shares,
    compute_day0, compute_ar_series, sum_ar_over_window, sum_ar_between,
    compute_adv, compute_market_cap, compute_abnormal_volume, compute_recovery,
    fit_market_model, build_return_series, build_topix_returns,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _iso(d: date) -> str:
    return d.isoformat()


def make_calendar(start: date, end: date) -> pd.DataFrame:
    """weekdays are business days (Mon-Fri), weekends are not. No holidays."""
    days = []
    d = start
    while d <= end:
        biz = d.weekday() < 5
        days.append({
            "Date": _iso(d),
            "HolidayDivision": "1" if biz else "0",
            "IsBusinessDay": biz,
        })
        d += timedelta(days=1)
    return pd.DataFrame(days)


def make_price_series(cal: pd.DataFrame, start_price: float, ret_seq: dict[str, float]) -> pd.DataFrame:
    """cal has IsBusinessDay; keep only business days; apply per-date returns."""
    bdays = cal.loc[cal["IsBusinessDay"], "Date"].tolist()
    prices = []
    p = start_price
    for i, d in enumerate(bdays):
        r = ret_seq.get(d, 0.0)
        if i > 0:
            p = p * math.exp(r)
        prices.append({"Date": d, "Close": p, "AdjustmentClose": p,
                       "Volume": 1000.0, "AdjustmentVolume": 1000.0,
                       "AdjustmentFactor": 1.0})
    return pd.DataFrame(prices)


@pytest.fixture
def cfg() -> Config:
    return Config(
        model_primary="topix_adjusted",
        model_robustness=["market_model"],
        return_type="log_return",
        est_start=-140, est_end=-21, est_min_days=100, alpha_free=True,
        after_close_field="after_close",
        after_close_true_value="TRUE",
        after_close_shifts=True,
        non_business_shifts=True,
        event_windows={
            "announcement": {"m1_p1": [-1, 1], "zero_p1": [0, 1]},
            "pricing": {"m1_p1": [-1, 1]},
            "settlement": {"m1_p1": [-1, 1]},
        },
        drift_include_start=False, drift_include_end=True,
        recovery_horizons=[5, 20, 60],
        recovery_transform="cum_ar",
        ab_window=[0, 3], ab_denom="ADV60", ab_transform="log_ratio",
        adv_windows=[20, 60], adv_min_ratio=0.8,
        output_columns=[
            "announcement_CAR_m1_p1", "announcement_CAR_0_p1", "drift_ann_to_pricing",
            "pricing_CAR_m1_p1", "settlement_CAR_m1_p1",
            "recovery_5d", "recovery_20d", "recovery_60d", "abnormal_volume_0_p3",
        ],
    )


@pytest.fixture
def cal():
    cal_df = make_calendar(date(2023, 1, 1), date(2024, 12, 31))
    return BusinessCalendar(cal_df)


# ---------------------------------------------------------------------------
# day 0
# ---------------------------------------------------------------------------

def test_day0_business_day_no_after_close(cal, cfg):
    # 2023-03-01 (Wed, business day), after_close=FALSE → same day
    assert compute_day0("2023-03-01", "FALSE", cal, cfg) == "2023-03-01"


def test_day0_after_close_true_shifts_to_next_bday(cal, cfg):
    # 2023-03-01 (Wed) after_close=TRUE → 2023-03-02 (Thu)
    assert compute_day0("2023-03-01", "TRUE", cal, cfg) == "2023-03-02"


def test_day0_after_close_true_over_weekend(cal, cfg):
    # 2023-03-03 (Fri) after_close=TRUE → 2023-03-06 (Mon)
    assert compute_day0("2023-03-03", "TRUE", cal, cfg) == "2023-03-06"


def test_day0_saturday_shifts_to_monday(cal, cfg):
    # 2023-03-04 (Sat) → 2023-03-06 (Mon), regardless of after_close
    assert compute_day0("2023-03-04", "FALSE", cal, cfg) == "2023-03-06"


def test_day0_empty_input(cal, cfg):
    assert compute_day0("", "FALSE", cal, cfg) is None


# ---------------------------------------------------------------------------
# business day navigation
# ---------------------------------------------------------------------------

def test_shift_forward_1_bday(cal):
    assert cal.shift_business_days("2023-03-01", 1) == "2023-03-02"


def test_shift_forward_5_bdays_crosses_weekend(cal):
    # Wed +5 bdays = Wed next week
    assert cal.shift_business_days("2023-03-01", 5) == "2023-03-08"


def test_shift_backward_1_bday(cal):
    assert cal.shift_business_days("2023-03-01", -1) == "2023-02-28"


def test_shift_backward_over_weekend(cal):
    # Mon -1 = Fri
    assert cal.shift_business_days("2023-03-06", -1) == "2023-03-03"


def test_range_business_days(cal):
    r = cal.range_business_days("2023-03-01", "2023-03-08")
    assert r == ["2023-03-01", "2023-03-02", "2023-03-03",
                 "2023-03-06", "2023-03-07", "2023-03-08"]


# ---------------------------------------------------------------------------
# market model OLS: recover known α/β
# ---------------------------------------------------------------------------

def test_fit_market_model_recovers_alpha_beta():
    rng = np.random.default_rng(42)
    x = rng.normal(0.0, 0.01, 200)
    true_alpha, true_beta = 0.0005, 1.3
    eps = rng.normal(0.0, 0.005, 200)
    y = true_alpha + true_beta * x + eps
    fit = fit_market_model(y, x, alpha_free=True, min_n=100)
    assert fit.ok
    assert abs(fit.beta - true_beta) < 0.05
    assert abs(fit.alpha - true_alpha) < 0.001


def test_fit_market_model_insufficient_n_returns_not_ok():
    x = np.array([0.001, 0.002, 0.003])
    y = np.array([0.001, 0.002, 0.003])
    fit = fit_market_model(y, x, alpha_free=True, min_n=100)
    assert not fit.ok
    assert "n<100" in fit.reason


def test_fit_market_model_alpha_zero():
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 0.01, 200)
    true_beta = 0.9
    y = true_beta * x + rng.normal(0, 0.003, 200)
    fit = fit_market_model(y, x, alpha_free=False, min_n=100)
    assert fit.ok
    assert fit.alpha == 0.0
    assert abs(fit.beta - true_beta) < 0.05


# ---------------------------------------------------------------------------
# topix_adjusted AR: AR = r_i - r_m
# ---------------------------------------------------------------------------

def test_topix_adjusted_ar_matches_diff(cal, cfg):
    cal_df = make_calendar(date(2023, 1, 1), date(2024, 12, 31))
    # stock and topix both have known returns
    # e.g. stock rets a series with a spike on 2023-03-01
    ret_seq_stock = {d: 0.0 for d in cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()}
    ret_seq_stock["2023-03-01"] = 0.05
    ret_seq_mkt = {d: 0.0 for d in cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()}
    ret_seq_mkt["2023-03-01"] = 0.01
    stock = make_price_series(cal_df, 1000.0, ret_seq_stock)
    mkt = make_price_series(cal_df, 2000.0, ret_seq_mkt)
    sr = build_return_series(stock, "log_return")
    mr = build_return_series(mkt, "log_return")
    ar, _ = compute_ar_series(sr, mr, "2023-03-01", cal, cfg, "topix_adjusted")
    # find AR for 2023-03-01
    val = ar.loc[ar["Date"] == "2023-03-01", "ar"].iloc[0]
    assert abs(val - (0.05 - 0.01)) < 1e-10


# ---------------------------------------------------------------------------
# market_model AR: uses estimation window only, produces expected AR
# ---------------------------------------------------------------------------

def test_market_model_ar_uses_only_estimation_window(cal):
    """
    Build a stock that in the estimation window follows r_stock = 0.9 * r_mkt (β=0.9),
    but in the event window (day 0 and after) has r_stock = 2.0 * r_mkt.
    If the engine correctly restricts fit to [-140,-21], the estimated β should be ≈0.9,
    NOT ≈ some weighted average that leaks day 0 info.
    """
    cal_df = make_calendar(date(2023, 1, 1), date(2024, 12, 31))
    bdays = cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()
    day0 = "2024-01-15"                                   # deep in the calendar
    day0_idx = bdays.index(day0)

    rng = np.random.default_rng(101)
    mkt_ret_arr = rng.normal(0.0, 0.01, len(bdays))
    stock_ret_arr = np.zeros_like(mkt_ret_arr)
    for i, r in enumerate(mkt_ret_arr):
        if i < day0_idx - 20:
            stock_ret_arr[i] = 0.9 * r + rng.normal(0, 0.001)
        else:
            stock_ret_arr[i] = 2.0 * r + rng.normal(0, 0.001)

    # Cumulative price from returns.
    mkt_close = 1000.0 * np.exp(np.cumsum(mkt_ret_arr))
    stock_close = 1000.0 * np.exp(np.cumsum(stock_ret_arr))
    mkt = pd.DataFrame({"Date": bdays, "Close": mkt_close})
    stock = pd.DataFrame({"Date": bdays, "Close": stock_close,
                          "AdjustmentClose": stock_close,
                          "Volume": 1000.0, "AdjustmentVolume": 1000.0,
                          "AdjustmentFactor": 1.0})
    sr = build_return_series(stock, "log_return")
    mr = build_topix_returns(mkt, "log_return")

    cfg_mm = Config(
        model_primary="market_model", model_robustness=[], return_type="log_return",
        est_start=-140, est_end=-21, est_min_days=100, alpha_free=True,
        after_close_field="after_close", after_close_true_value="TRUE",
        after_close_shifts=True, non_business_shifts=True,
        event_windows={"announcement": {"m1_p1": [-1, 1], "zero_p1": [0, 1]},
                       "pricing": {"m1_p1": [-1, 1]},
                       "settlement": {"m1_p1": [-1, 1]}},
        drift_include_start=False, drift_include_end=True,
        recovery_horizons=[5, 20, 60], recovery_transform="cum_ar",
        ab_window=[0, 3], ab_denom="ADV60", ab_transform="log_ratio",
        adv_windows=[20, 60], adv_min_ratio=0.8,
        output_columns=[],
    )
    ar, fit = compute_ar_series(sr, mr, day0, BusinessCalendar(cal_df), cfg_mm, "market_model")
    assert fit is not None and fit.ok
    # β should reflect only the pre-window slope (~0.9), NOT the post-day-0 (~2.0)
    assert abs(fit.beta - 0.9) < 0.1, f"β leak: got {fit.beta}, expected ≈ 0.9"


# ---------------------------------------------------------------------------
# CAR sum
# ---------------------------------------------------------------------------

def test_sum_ar_over_window_simple(cal):
    # constant AR = 0.01 on 3 days
    dates = ["2023-03-01", "2023-03-02", "2023-03-03"]
    ar = pd.DataFrame({"Date": dates, "ar": [0.01, 0.01, 0.01]})
    # day0 = 2023-03-02, window=(-1, +1) → 3 days = 0.03
    assert abs(sum_ar_over_window(ar, "2023-03-02", (-1, 1), cal) - 0.03) < 1e-10


def test_sum_ar_over_window_zero_p1(cal):
    dates = ["2023-03-02", "2023-03-03"]
    ar = pd.DataFrame({"Date": dates, "ar": [0.05, 0.02]})
    # day0 = 2023-03-02, window=(0, +1) → 2 days sum
    assert abs(sum_ar_over_window(ar, "2023-03-02", (0, 1), cal) - 0.07) < 1e-10


def test_sum_ar_over_window_missing_returns_nan(cal):
    # incomplete AR series → NaN
    ar = pd.DataFrame({"Date": ["2023-03-02"], "ar": [0.05]})
    assert math.isnan(sum_ar_over_window(ar, "2023-03-02", (-1, 1), cal))


def test_sum_ar_between_include_end_exclusive_start(cal):
    dates = ["2023-03-01", "2023-03-02", "2023-03-03"]
    ar = pd.DataFrame({"Date": dates, "ar": [0.01, 0.02, 0.03]})
    # start=2023-03-01 (excl), end=2023-03-03 (incl) → 0.02 + 0.03 = 0.05
    assert abs(sum_ar_between(ar, "2023-03-01", "2023-03-03",
                              include_start=False, include_end=True) - 0.05) < 1e-10


# ---------------------------------------------------------------------------
# ADV / abnormal volume
# ---------------------------------------------------------------------------

def test_compute_adv_20_uses_only_pre_day0(cal):
    cal_df = make_calendar(date(2023, 1, 1), date(2023, 12, 31))
    bdays = cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()
    # volume=100 on all days except day 0 and after where it spikes to 1_000_000
    day0 = "2023-06-15"
    day0_idx = bdays.index(day0)
    vols = []
    for i, d in enumerate(bdays):
        v = 1_000_000.0 if i >= day0_idx else 100.0
        vols.append({"Date": d, "Close": 100.0, "AdjustmentClose": 100.0,
                     "Volume": v, "AdjustmentVolume": v, "AdjustmentFactor": 1.0})
    price = pd.DataFrame(vols)
    adv20 = compute_adv(price, day0, 20, BusinessCalendar(cal_df), 0.8)
    assert abs(adv20 - 100.0) < 1e-6, f"leak detected: got {adv20}, want 100.0"


def test_compute_abnormal_volume_log_ratio(cal):
    cal_df = make_calendar(date(2023, 1, 1), date(2023, 12, 31))
    bdays = cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()
    day0 = "2023-06-15"
    day0_idx = bdays.index(day0)
    vols = []
    for i, d in enumerate(bdays):
        # ADV60 baseline = 100, event window volume = 200 → log(200/100) = ln(2)
        v = 200.0 if i >= day0_idx and i <= day0_idx + 3 else 100.0
        vols.append({"Date": d, "Close": 100.0, "AdjustmentClose": 100.0,
                     "Volume": v, "AdjustmentVolume": v, "AdjustmentFactor": 1.0})
    price = pd.DataFrame(vols)
    adv60 = compute_adv(price, day0, 60, BusinessCalendar(cal_df), 0.8)
    assert abs(adv60 - 100.0) < 1e-6
    ab = compute_abnormal_volume(price, day0, (0, 3), adv60, BusinessCalendar(cal_df), "log_ratio")
    assert abs(ab - math.log(2.0)) < 1e-10


# ---------------------------------------------------------------------------
# recovery
# ---------------------------------------------------------------------------

def test_recovery_is_cum_ar_over_horizon(cal):
    # AR = -0.01 on day 0 then +0.005 for 5 days
    cal_df = make_calendar(date(2023, 1, 1), date(2023, 12, 31))
    day0 = "2023-06-15"
    bcal = BusinessCalendar(cal_df)
    dates = [day0] + [bcal.shift_business_days(day0, i) for i in range(1, 6)]
    ars = [-0.01, 0.005, 0.005, 0.005, 0.005, 0.005]
    ar = pd.DataFrame({"Date": dates, "ar": ars})
    v = compute_recovery(ar, day0, 5, bcal, "cum_ar")
    # sum of 6 values (day 0 + 5) = -0.01 + 5*0.005 = 0.015
    assert abs(v - 0.015) < 1e-10


# ---------------------------------------------------------------------------
# no-lookahead invariant: fit_market_model given a spike ON day 0 in stock
# ---------------------------------------------------------------------------

def test_no_lookahead_market_model_ignores_day0_spike(cal, cfg):
    """
    stock has a *massive* one-day event on day 0 (r=+0.20) that is unrelated to market.
    If estimation window is clean [-140,-21], the fit should be unaffected.
    """
    cal_df = make_calendar(date(2023, 1, 1), date(2024, 12, 31))
    bdays = cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()
    day0 = "2024-06-03"
    day0_idx = bdays.index(day0)

    rng = np.random.default_rng(202)
    mkt_ret = rng.normal(0.0, 0.01, len(bdays))
    stock_ret = 1.2 * mkt_ret + rng.normal(0.0, 0.003, len(bdays))  # true β=1.2
    stock_ret[day0_idx] += 0.20  # event spike

    mkt = pd.DataFrame({"Date": bdays, "Close": 1000.0 * np.exp(np.cumsum(mkt_ret))})
    stock_close = 1000.0 * np.exp(np.cumsum(stock_ret))
    stock = pd.DataFrame({"Date": bdays, "Close": stock_close, "AdjustmentClose": stock_close,
                          "Volume": 1000.0, "AdjustmentVolume": 1000.0, "AdjustmentFactor": 1.0})
    sr = build_return_series(stock, "log_return")
    mr = build_topix_returns(mkt, "log_return")

    cfg_mm = Config(
        model_primary="market_model", model_robustness=[], return_type="log_return",
        est_start=-140, est_end=-21, est_min_days=100, alpha_free=True,
        after_close_field="after_close", after_close_true_value="TRUE",
        after_close_shifts=True, non_business_shifts=True,
        event_windows={"announcement": {"m1_p1": [-1, 1], "zero_p1": [0, 1]},
                       "pricing": {"m1_p1": [-1, 1]},
                       "settlement": {"m1_p1": [-1, 1]}},
        drift_include_start=False, drift_include_end=True,
        recovery_horizons=[5], recovery_transform="cum_ar",
        ab_window=[0, 3], ab_denom="ADV60", ab_transform="log_ratio",
        adv_windows=[20, 60], adv_min_ratio=0.8,
        output_columns=[],
    )
    ar, fit = compute_ar_series(sr, mr, day0, BusinessCalendar(cal_df), cfg_mm, "market_model")
    # β should be ~1.2, not perturbed by the day-0 spike
    assert fit.ok
    assert abs(fit.beta - 1.2) < 0.1, f"day 0 spike leaked into β: got {fit.beta}, expected 1.2"
    # AR on day 0 should recover the ~0.20 abnormality (approx)
    ar_day0 = ar.loc[ar["Date"] == day0, "ar"].iloc[0]
    assert 0.15 < ar_day0 < 0.25, f"day 0 AR should be ≈0.20; got {ar_day0}"


# ---------------------------------------------------------------------------
# loader field-mismatch guards (V1→V2 field rename protection)
# ---------------------------------------------------------------------------

def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_load_daily_quotes_raises_on_missing_close_field(tmp_path):
    p = tmp_path / "quotes.jsonl"
    # V2 renamed 'Close' to something else, e.g. 'close_price' — simulate the mismatch
    _write_jsonl(p, [{"Date": "2024-01-01", "close_price": 100.0, "Volume": 1000}])
    with pytest.raises(FieldMismatchError, match="Close"):
        load_daily_quotes(p)


def test_load_daily_quotes_falls_back_to_adj_close_candidate(tmp_path, caplog):
    p = tmp_path / "quotes.jsonl"
    # simulate V2 renaming AdjustmentClose -> AdjClose (matches the confirmed HolDiv pattern)
    _write_jsonl(p, [{"Date": "2024-01-01", "Close": 100.0, "Volume": 1000, "AdjClose": 99.5}])
    df = load_daily_quotes(p)
    assert df["AdjustmentClose"].iloc[0] == 99.5


def test_load_daily_quotes_ok_when_close_present(tmp_path):
    p = tmp_path / "quotes.jsonl"
    _write_jsonl(p, [{"Date": "2024-01-01", "Close": 100.0, "Volume": 1000,
                      "AdjustmentClose": 100.0, "AdjustmentVolume": 1000, "AdjustmentFactor": 1.0}])
    df = load_daily_quotes(p)
    assert len(df) == 1
    assert df["Close"].iloc[0] == 100.0


def test_load_topix_raises_on_missing_close_field(tmp_path):
    p = tmp_path / "topix.jsonl"
    _write_jsonl(p, [{"Date": "2024-01-01", "index_close": 2000.0}])
    with pytest.raises(FieldMismatchError, match="Close"):
        load_topix(p)


def test_load_trading_calendar_raises_when_no_candidate_matches(tmp_path):
    p = tmp_path / "cal.jsonl"
    _write_jsonl(p, [{"Date": "2024-01-01", "SomeUnknownField": "1"}])
    with pytest.raises(FieldMismatchError):
        load_trading_calendar(p)


def test_load_trading_calendar_ok_when_holiday_division_present(tmp_path):
    p = tmp_path / "cal.jsonl"
    _write_jsonl(p, [{"Date": "2024-01-01", "HolidayDivision": "1"}])
    df = load_trading_calendar(p)
    assert len(df) == 1
    assert bool(df["IsBusinessDay"].iloc[0]) is True


def test_load_trading_calendar_ok_with_v2_hol_div_field(tmp_path):
    """V2 の実データで HolidayDivision → HolDiv に短縮されていることを確認済み (2026-07-08)。"""
    p = tmp_path / "cal.jsonl"
    _write_jsonl(p, [{"Date": "2024-01-01", "HolDiv": "1"}])
    df = load_trading_calendar(p)
    assert len(df) == 1
    assert bool(df["IsBusinessDay"].iloc[0]) is True


def test_load_fins_shares_finds_alternate_field_name(tmp_path):
    p = tmp_path / "fins.jsonl"
    # simulate V2 renaming the shares-outstanding field to a candidate we support
    _write_jsonl(p, [{"DisclosedDate": "2024-06-30", "NumberOfIssuedShares": "1000000"}])
    df = load_fins_shares(p, logging.getLogger("test"))
    assert len(df) == 1
    assert df["shares_outstanding"].iloc[0] == 1000000.0


def test_load_fins_shares_returns_empty_when_no_candidate_matches(tmp_path):
    p = tmp_path / "fins.jsonl"
    _write_jsonl(p, [{"DisclosedDate": "2024-06-30", "SomeUnknownField": "1000000"}])
    df = load_fins_shares(p, logging.getLogger("test"))
    assert df.empty
    assert list(df.columns) == ["DisclosedDate", "shares_outstanding"]
