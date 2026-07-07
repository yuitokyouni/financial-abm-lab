#!/usr/bin/env python3
"""unwind-tape / task C — AR/CAR engine.

入力:
    data/parsed/tape/legs.csv                    (Task B の canonical CSV)
    data/parsed/tape/groups.csv
    data/raw/prices/daily_quotes/{code}.jsonl    (jquants_fetch.py の出力)
    data/raw/prices/topix.jsonl
    data/raw/prices/trading_calendar.jsonl
    data/raw/prices/fins_summary/{code}.jsonl
    configs/car.yaml

出力:
    data/parsed/tape/legs_computed.csv           ADV20/60 + market_cap 等
    data/parsed/tape/legs_car.csv                8 CAR 列
    data/parsed/tape/car_report.md               G004/G008 hand-check + サマリ

不変条件:
    - ルックアヘッド禁止: 推定窓の任意 t について、その AR の計算に
      day 0 以降の情報を混入させない。ADV も同様。
    - day 0 規則: announce_datetime を day 0 とする。ただし
      after_close == "TRUE" のとき、または announce_datetime が営業日でないとき、
      翌営業日を day 0 とする。
    - 欠損は空欄のまま出力。data/gaps_report.md に理由を追記。
    - CAR は各 event window の start_offset から end_offset (両端含む) の
      cumulative AR を返す (単純合算)。
    - 市場モデル切替は configs/car.yaml の model.primary で行う。
      (topix_adjusted | market_model)

依存: numpy, pandas, pyyaml, stdlib。他リポパッケージへ import しない。
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    model_primary: str
    model_robustness: list[str]
    return_type: str
    est_start: int
    est_end: int
    est_min_days: int
    alpha_free: bool
    after_close_field: str
    after_close_true_value: str
    after_close_shifts: bool
    non_business_shifts: bool
    event_windows: dict[str, dict[str, list[int]]]
    drift_include_start: bool
    drift_include_end: bool
    recovery_horizons: list[int]
    recovery_transform: str
    ab_window: list[int]
    ab_denom: str
    ab_transform: str
    adv_windows: list[int]
    adv_min_ratio: float
    output_columns: list[str]

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        with path.open("r", encoding="utf-8") as f:
            c = yaml.safe_load(f)
        return cls(
            model_primary=c["model"]["primary"],
            model_robustness=list(c["model"]["robustness"]),
            return_type=c["model"]["return_type"],
            est_start=int(c["estimation_window"]["start"]),
            est_end=int(c["estimation_window"]["end"]),
            est_min_days=int(c["estimation_window"]["min_days"]),
            alpha_free=bool(c["estimation_window"]["alpha_free"]),
            after_close_field=c["day0"]["after_close_field"],
            after_close_true_value=c["day0"]["after_close_true_value"],
            after_close_shifts=bool(c["day0"]["after_close_shifts_to_next_business_day"]),
            non_business_shifts=bool(c["day0"]["non_business_day_shifts_to_next"]),
            event_windows=c["event_windows"],
            drift_include_start=bool(c["drift"]["include_start"]),
            drift_include_end=bool(c["drift"]["include_end"]),
            recovery_horizons=list(c["recovery"]["horizons_business_days"]),
            recovery_transform=c["recovery"]["transform"],
            ab_window=list(c["abnormal_volume"]["window"]),
            ab_denom=c["abnormal_volume"]["denom"],
            ab_transform=c["abnormal_volume"]["transform"],
            adv_windows=list(c["adv"]["windows_business_days"]),
            adv_min_ratio=float(c["adv"]["min_days_ratio"]),
            output_columns=list(c["output_columns"]),
        )


# ---------------------------------------------------------------------------
# data loaders
# ---------------------------------------------------------------------------

class FieldMismatchError(ValueError):
    """想定フィールド名が raw jsonl に一つも見つからない場合に投げる。
    J-Quants V1→V2 移行でフィールド名が変わっている可能性が高いエラーなので、
    黙って NaN で埋めるのではなく実際のキー名を出して気付けるようにする。
    """


# V2 で HolidayDivision → HolDiv に短縮されていることを実データで確認済み。
# 今後また変わっても壊れないよう候補リスト方式にしておく。
HOLIDAY_DIVISION_FIELD_CANDIDATES = ["HolDiv", "HolidayDivision", "hol_div"]


def _first_present_field(raw_rows: list[dict], candidates: list[str]) -> str | None:
    return next((k for k in candidates if any(k in r for r in raw_rows)), None)


def load_trading_calendar(path: Path) -> pd.DataFrame:
    """returns df indexed by Date (str YYYY-MM-DD) with column IsBusinessDay (bool)."""
    raw_rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw_rows.append(json.loads(line))
    if not raw_rows:
        raise FieldMismatchError(f"{path}: no rows")

    hol_field = _first_present_field(raw_rows, HOLIDAY_DIVISION_FIELD_CANDIDATES)
    if hol_field is None:
        raise FieldMismatchError(
            f"{path}: none of {HOLIDAY_DIVISION_FIELD_CANDIDATES} found. "
            f"Sample raw keys: {sorted(raw_rows[0].keys())}"
        )

    rows = [{"Date": e.get("Date"), "HolidayDivision": e.get(hol_field)} for e in raw_rows]
    df = pd.DataFrame(rows)
    if df["Date"].isna().all():
        raise FieldMismatchError(
            f"{path}: 'Date' field entirely missing. Sample raw keys: {sorted(raw_rows[0].keys())}"
        )
    df = df.drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    # HolidayDivision: "0" holiday / "1" business / "2" half day (still trading) / "3" half day non-trading
    # Treat "1" and "2" as business days (立会あり).
    df["IsBusinessDay"] = df["HolidayDivision"].astype(str).isin(("1", "2"))
    return df


# V2 はフィールド名を大胆に短縮する傾向が実データで確認されている
# (HolidayDivision→HolDiv、さらに topix では Close→C, Open→O, High→H, Low→L まで
# 単一文字に短縮されていた)。daily_quotes も同じ命名規則を採る可能性が高いため
# Close/Volume 含め候補リスト方式にする。
CLOSE_FIELD_CANDIDATES = ["Close", "C"]
VOLUME_FIELD_CANDIDATES = ["Volume", "V"]
ADJUSTMENT_CLOSE_FIELD_CANDIDATES = ["AdjustmentClose", "AdjClose", "AC", "AdjC"]
ADJUSTMENT_VOLUME_FIELD_CANDIDATES = ["AdjustmentVolume", "AdjVolume", "AV", "AdjV"]
ADJUSTMENT_FACTOR_FIELD_CANDIDATES = ["AdjustmentFactor", "AdjFactor", "AF", "AdjF"]


def load_daily_quotes(path: Path, log: logging.Logger | None = None) -> pd.DataFrame:
    """returns df indexed by Date str with Close, Volume, AdjustmentClose, AdjustmentVolume, AdjustmentFactor."""
    raw_rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw_rows.append(json.loads(line))
    if not raw_rows:
        raise FieldMismatchError(f"{path}: no rows")

    close_field = _first_present_field(raw_rows, CLOSE_FIELD_CANDIDATES)
    volume_field = _first_present_field(raw_rows, VOLUME_FIELD_CANDIDATES)
    if close_field is None:
        raise FieldMismatchError(
            f"{path}: none of {CLOSE_FIELD_CANDIDATES} found. "
            f"Sample raw keys: {sorted(raw_rows[0].keys())}"
        )
    adj_close_field = _first_present_field(raw_rows, ADJUSTMENT_CLOSE_FIELD_CANDIDATES)
    adj_volume_field = _first_present_field(raw_rows, ADJUSTMENT_VOLUME_FIELD_CANDIDATES)
    adj_factor_field = _first_present_field(raw_rows, ADJUSTMENT_FACTOR_FIELD_CANDIDATES)
    if log and adj_close_field is None:
        log.warning(
            "%s: none of %s found — falling back to unadjusted Close. "
            "Sample raw keys: %s. CAR spanning a stock split may be wrong.",
            path, ADJUSTMENT_CLOSE_FIELD_CANDIDATES, sorted(raw_rows[0].keys()),
        )

    rows = []
    for e in raw_rows:
        rows.append({
            "Date": e.get("Date"),
            "Close": e.get(close_field),
            "Volume": e.get(volume_field) if volume_field else None,
            "AdjustmentClose": e.get(adj_close_field) if adj_close_field else None,
            "AdjustmentVolume": e.get(adj_volume_field) if adj_volume_field else None,
            "AdjustmentFactor": e.get(adj_factor_field) if adj_factor_field else None,
        })
    df = pd.DataFrame(rows)
    df = df.drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    for c in ("Close", "Volume", "AdjustmentClose", "AdjustmentVolume", "AdjustmentFactor"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_topix(path: Path) -> pd.DataFrame:
    raw_rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw_rows.append(json.loads(line))
    if not raw_rows:
        raise FieldMismatchError(f"{path}: no rows")

    close_field = _first_present_field(raw_rows, CLOSE_FIELD_CANDIDATES)
    if close_field is None:
        raise FieldMismatchError(
            f"{path}: none of {CLOSE_FIELD_CANDIDATES} found. "
            f"Sample raw keys: {sorted(raw_rows[0].keys())}"
        )
    rows = [{"Date": e.get("Date"), "Close": e.get(close_field)} for e in raw_rows]
    df = pd.DataFrame(rows)
    df = df.drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return df


# V2 /fins/summary の発行済株式数フィールド名は未確認。複数の候補を順に試し、
# 見つかった最初のものを使う。全滅なら shares_outstanding は空のまま
# (compute_market_cap 側で reason="no_shares" として NaN + 理由を返す — 黙って埋めない)。
SHARES_OUTSTANDING_FIELD_CANDIDATES = [
    "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock",  # V1 field name
    "NumberOfIssuedShares",
    "IssuedShares",
    "SharesOutstanding",
]


def load_fins_shares(path: Path, log: logging.Logger | None = None) -> pd.DataFrame:
    """returns df with DisclosedDate + shares_outstanding.
    フィールド名候補を順に試す。1件も見つからなければ warning を出して空 df を返す
    (raise しない — fins データが本当に空という正常系もあり得るため)。
    """
    if not path.exists():
        return pd.DataFrame(columns=["DisclosedDate", "shares_outstanding"])
    raw_rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw_rows.append(json.loads(line))
    if not raw_rows:
        return pd.DataFrame(columns=["DisclosedDate", "shares_outstanding"])

    field_key = next(
        (k for k in SHARES_OUTSTANDING_FIELD_CANDIDATES if any(k in r for r in raw_rows)),
        None,
    )
    if field_key is None:
        if log:
            log.warning(
                "%s: none of shares_outstanding candidates %s found. Sample keys: %s",
                path, SHARES_OUTSTANDING_FIELD_CANDIDATES, sorted(raw_rows[0].keys()),
            )
        return pd.DataFrame(columns=["DisclosedDate", "shares_outstanding"])

    rows = []
    for e in raw_rows:
        v = e.get(field_key)
        if v in (None, ""):
            continue
        rows.append({
            "DisclosedDate": e.get("DisclosedDate"),
            "shares_outstanding": pd.to_numeric(v, errors="coerce"),
        })
    df = pd.DataFrame(rows, columns=["DisclosedDate", "shares_outstanding"])
    df = df.sort_values("DisclosedDate").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# business-day navigation (no lookahead)
# ---------------------------------------------------------------------------

class BusinessCalendar:
    def __init__(self, cal_df: pd.DataFrame):
        # keep only business days, list of str YYYY-MM-DD, sorted.
        self._bdays = cal_df.loc[cal_df["IsBusinessDay"], "Date"].tolist()
        self._bday_arr = np.array(self._bdays)
        self._bday_set = set(self._bdays)
        self._idx = {d: i for i, d in enumerate(self._bdays)}

    def is_business_day(self, d: str) -> bool:
        return d in self._bday_set

    def next_business_day(self, d: str) -> str | None:
        """next strictly-greater business day; None if end of calendar."""
        # binary search
        i = int(np.searchsorted(self._bday_arr, d, side="right"))
        if i >= len(self._bday_arr):
            return None
        return self._bdays[i]

    def prev_business_day(self, d: str) -> str | None:
        i = int(np.searchsorted(self._bday_arr, d, side="left"))
        if i <= 0:
            return None
        return self._bdays[i - 1]

    def shift_business_days(self, d: str, offset: int) -> str | None:
        """returns d shifted by `offset` business days. offset<0 = past, offset>0 = future.
        d must be a business day (raises otherwise).
        """
        if d not in self._idx:
            # snap to nearest business day (previous). No lookahead when offset<=0.
            snapped_prev = self.prev_business_day(d)
            if snapped_prev is None:
                return None
            i = self._idx[snapped_prev]
        else:
            i = self._idx[d]
        j = i + offset
        if j < 0 or j >= len(self._bdays):
            return None
        return self._bdays[j]

    def range_business_days(self, start: str, end: str) -> list[str]:
        """inclusive both ends. start/end are business days or snap to boundaries.
        Returns [] if range is empty.
        """
        i = int(np.searchsorted(self._bday_arr, start, side="left"))
        j = int(np.searchsorted(self._bday_arr, end, side="right"))
        return self._bdays[i:j]


# ---------------------------------------------------------------------------
# day 0 computation
# ---------------------------------------------------------------------------

def _to_iso(d: Any) -> str:
    if d is None or (isinstance(d, str) and not d.strip()):
        return ""
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    s = str(d).strip()
    # already ISO?
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s


def compute_day0(announce_date: str, after_close: str, cal: BusinessCalendar,
                 cfg: Config) -> str | None:
    """day 0 = 反応可能な最初の立会。仕様:
       - after_close == 'TRUE' → 翌営業日
       - announce_date が営業日でない → 翌営業日
       - どちらも成立しなければ announce_date そのもの
    """
    if not announce_date:
        return None
    d = _to_iso(announce_date)
    # after_close shift
    if cfg.after_close_shifts and str(after_close).upper() == cfg.after_close_true_value.upper():
        return cal.next_business_day(d)
    # non-business-day shift
    if cfg.non_business_shifts and not cal.is_business_day(d):
        return cal.next_business_day(d)
    if not cal.is_business_day(d):
        return None
    return d


# ---------------------------------------------------------------------------
# return series
# ---------------------------------------------------------------------------

def build_return_series(price: pd.DataFrame, kind: str) -> pd.DataFrame:
    """price has columns [Date, AdjustmentClose] (or Close if that's absent).
    Returns df[Date, ret] with ret_t = log(P_t / P_{t-1}) or (P_t / P_{t-1}) - 1.
    NaN in first row (no prior close).
    """
    p = price.copy()
    close = p["AdjustmentClose"].fillna(p["Close"] if "Close" in p.columns else p["AdjustmentClose"])
    if kind == "log_return":
        r = np.log(close / close.shift(1))
    else:
        r = close / close.shift(1) - 1.0
    return pd.DataFrame({"Date": p["Date"], "ret": r})


def build_topix_returns(topix: pd.DataFrame, kind: str) -> pd.DataFrame:
    p = topix.copy()
    if kind == "log_return":
        r = np.log(p["Close"] / p["Close"].shift(1))
    else:
        r = p["Close"] / p["Close"].shift(1) - 1.0
    return pd.DataFrame({"Date": p["Date"], "ret": r})


# ---------------------------------------------------------------------------
# market model estimation (OLS)
# ---------------------------------------------------------------------------

@dataclass
class MMFit:
    alpha: float
    beta: float
    residual_std: float
    n: int
    ok: bool = True
    reason: str = ""


def fit_market_model(y: np.ndarray, x: np.ndarray, alpha_free: bool,
                     min_n: int) -> MMFit:
    """y_t = α + β * x_t + ε_t. Returns fit; ok=False when insufficient data."""
    mask = np.isfinite(y) & np.isfinite(x)
    y = y[mask]
    x = x[mask]
    if len(y) < min_n:
        return MMFit(alpha=math.nan, beta=math.nan, residual_std=math.nan,
                     n=int(len(y)), ok=False, reason=f"n<{min_n}")
    if alpha_free:
        X = np.column_stack([np.ones_like(x), x])
        # OLS via normal equations (small n, fine)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        alpha, beta = float(coef[0]), float(coef[1])
        res = y - (alpha + beta * x)
    else:
        beta = float(np.sum(x * y) / np.sum(x * x)) if np.sum(x * x) > 0 else math.nan
        alpha = 0.0
        res = y - beta * x
    resid_std = float(np.std(res, ddof=2)) if len(res) > 2 else float("nan")
    return MMFit(alpha=alpha, beta=beta, residual_std=resid_std, n=int(len(y)), ok=True)


# ---------------------------------------------------------------------------
# AR series
# ---------------------------------------------------------------------------

def compute_ar_series(stock_ret: pd.DataFrame, mkt_ret: pd.DataFrame,
                      day0: str, cal: BusinessCalendar, cfg: Config,
                      model: str) -> tuple[pd.DataFrame, MMFit | None]:
    """Returns df[Date, ar] and (if model=market_model) the fit for audit.

    Aligns stock_ret and mkt_ret on Date. Estimation window uses only Dates
    strictly BEFORE day 0 (t in [day0 + est_start, day0 + est_end], all negative offsets).
    """
    merged = pd.merge(stock_ret, mkt_ret, on="Date", suffixes=("_s", "_m"))
    merged = merged.sort_values("Date").reset_index(drop=True)
    date_arr = merged["Date"].to_numpy()

    if model == "topix_adjusted":
        # AR_t = r_i,t - r_topix,t. No estimation window needed.
        merged["ar"] = merged["ret_s"] - merged["ret_m"]
        return merged[["Date", "ar"]], None

    if model != "market_model":
        raise ValueError(f"unknown model: {model}")

    # market_model: estimation window in business days [day0+est_start, day0+est_end].
    est_start_date = cal.shift_business_days(day0, cfg.est_start)
    est_end_date = cal.shift_business_days(day0, cfg.est_end)
    if est_start_date is None or est_end_date is None:
        merged["ar"] = math.nan
        return merged[["Date", "ar"]], MMFit(
            alpha=math.nan, beta=math.nan, residual_std=math.nan,
            n=0, ok=False, reason="calendar too shallow for estimation window",
        )

    in_est = (date_arr >= est_start_date) & (date_arr <= est_end_date)
    y_est = merged.loc[in_est, "ret_s"].to_numpy()
    x_est = merged.loc[in_est, "ret_m"].to_numpy()

    fit = fit_market_model(y_est, x_est, cfg.alpha_free, cfg.est_min_days)
    if not fit.ok:
        merged["ar"] = math.nan
        return merged[["Date", "ar"]], fit
    merged["ar"] = merged["ret_s"] - (fit.alpha + fit.beta * merged["ret_m"])
    return merged[["Date", "ar"]], fit


# ---------------------------------------------------------------------------
# CAR aggregation
# ---------------------------------------------------------------------------

def sum_ar_over_window(ar: pd.DataFrame, day0: str, window: tuple[int, int],
                       cal: BusinessCalendar) -> float:
    """Sum AR over business-day offsets [window[0], window[1]] inclusive relative to day 0.
    Returns NaN if any required date is missing.
    """
    lo, hi = window
    dates_needed = []
    for k in range(lo, hi + 1):
        d = cal.shift_business_days(day0, k)
        if d is None:
            return math.nan
        dates_needed.append(d)
    lookup = dict(zip(ar["Date"].tolist(), ar["ar"].tolist()))
    vals = []
    for d in dates_needed:
        v = lookup.get(d)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return math.nan
        vals.append(v)
    return float(sum(vals))


def sum_ar_between(ar: pd.DataFrame, start_day: str, end_day: str,
                   include_start: bool, include_end: bool) -> float:
    if start_day is None or end_day is None:
        return math.nan
    d = ar[(ar["Date"] > start_day if not include_start else ar["Date"] >= start_day)
           & (ar["Date"] < end_day if not include_end else ar["Date"] <= end_day)]
    if d.empty:
        return math.nan
    v = d["ar"].to_numpy()
    if not np.all(np.isfinite(v)):
        return math.nan
    return float(np.sum(v))


# ---------------------------------------------------------------------------
# ADV + market cap + abnormal volume
# ---------------------------------------------------------------------------

def compute_adv(price: pd.DataFrame, day0: str, window_days: int,
                cal: BusinessCalendar, min_ratio: float) -> float:
    """ADV = mean volume over business days [day0 - window_days, day0 - 1].
    Uses AdjustmentVolume if available.
    """
    end = cal.shift_business_days(day0, -1)
    start = cal.shift_business_days(day0, -window_days)
    if end is None or start is None:
        return math.nan
    p = price[(price["Date"] >= start) & (price["Date"] <= end)]
    if p.empty:
        return math.nan
    vol = p["AdjustmentVolume"].fillna(p["Volume"]).to_numpy()
    vol = vol[np.isfinite(vol)]
    expected = window_days
    if len(vol) < expected * min_ratio:
        return math.nan
    return float(np.mean(vol))


def compute_market_cap(price: pd.DataFrame, shares: pd.DataFrame, day0: str,
                       cal: BusinessCalendar) -> tuple[float, str]:
    """time-of-day 0 の直前終値 × forward-fill された shares_outstanding。
    shares_outstanding は fins_summary の値を DisclosedDate 以降 forward-fill。
    """
    prev = cal.shift_business_days(day0, -1)
    if prev is None:
        return math.nan, "no_prev_bday"
    p = price.loc[price["Date"] == prev, "AdjustmentClose"]
    if p.empty or not np.isfinite(p.iloc[0]):
        p = price.loc[price["Date"] == prev, "Close"]
    if p.empty or not np.isfinite(p.iloc[0]):
        return math.nan, "no_price"
    close = float(p.iloc[0])
    if shares.empty:
        return math.nan, "no_shares"
    # pick latest DisclosedDate <= prev
    eligible = shares[shares["DisclosedDate"] <= prev]
    if eligible.empty:
        return math.nan, "no_disclosed_share_before_day0"
    n_shares = float(eligible.iloc[-1]["shares_outstanding"])
    return close * n_shares, f"close={close:.2f} shares={n_shares:.0f}"


def compute_abnormal_volume(price: pd.DataFrame, day0: str, window: tuple[int, int],
                            adv: float, cal: BusinessCalendar,
                            transform: str) -> float:
    lo, hi = window
    dates_needed = []
    for k in range(lo, hi + 1):
        d = cal.shift_business_days(day0, k)
        if d is None:
            return math.nan
        dates_needed.append(d)
    p = price[price["Date"].isin(dates_needed)]
    if p.empty or not np.isfinite(adv) or adv <= 0:
        return math.nan
    vol = p["AdjustmentVolume"].fillna(p["Volume"]).to_numpy()
    if not np.all(np.isfinite(vol)):
        return math.nan
    v_avg = float(np.mean(vol))
    if transform == "log_ratio":
        return math.log(v_avg / adv)
    if transform == "ratio":
        return v_avg / adv
    if transform == "raw_diff":
        return v_avg - adv
    return math.nan


# ---------------------------------------------------------------------------
# recovery
# ---------------------------------------------------------------------------

def compute_recovery(ar: pd.DataFrame, day0: str, horizon: int,
                     cal: BusinessCalendar, transform: str) -> float:
    """recovery_H = cumulative AR over [day0, day0 + H] inclusive (business days)."""
    # PREREG 待ち: 既定は cum AR (符号そのまま)
    return sum_ar_over_window(ar, day0, (0, horizon), cal)


# ---------------------------------------------------------------------------
# per-leg pipeline
# ---------------------------------------------------------------------------

@dataclass
class LegResult:
    event_group_id: str
    event_leg_id: str
    issuer_code: str
    announce_day0: str = ""
    pricing_day0: str = ""
    settlement_day0: str = ""
    model_used: str = ""
    beta: float = math.nan
    alpha: float = math.nan
    est_n: int = 0
    est_reason: str = ""
    ADV20_shares: float = math.nan
    ADV60_shares: float = math.nan
    market_cap_JPY: float = math.nan
    market_cap_detail: str = ""
    announcement_CAR_m1_p1: float = math.nan
    announcement_CAR_0_p1: float = math.nan
    drift_ann_to_pricing: float = math.nan
    pricing_CAR_m1_p1: float = math.nan
    settlement_CAR_m1_p1: float = math.nan
    recovery_5d: float = math.nan
    recovery_20d: float = math.nan
    recovery_60d: float = math.nan
    abnormal_volume_0_p3: float = math.nan
    notes: list[str] = field(default_factory=list)


def process_leg(leg: dict, prices: dict[str, pd.DataFrame],
                shares_map: dict[str, pd.DataFrame],
                topix: pd.DataFrame, cal: BusinessCalendar, cfg: Config,
                log: logging.Logger) -> LegResult:
    gid = leg["event_group_id"]
    lid = leg["event_leg_id"]
    code = leg.get("issuer_code", "").strip()
    r = LegResult(event_group_id=gid, event_leg_id=lid, issuer_code=code)

    if not code or code not in prices:
        r.notes.append(f"no price data for code={code!r}")
        return r
    price = prices[code]
    shares = shares_map.get(code, pd.DataFrame(columns=["DisclosedDate", "shares_outstanding"]))

    # day 0
    announce_iso = _to_iso(leg.get("announce_datetime", ""))
    after_close = leg.get("after_close", "")
    ann_day0 = compute_day0(announce_iso, after_close, cal, cfg)
    if ann_day0 is None:
        r.notes.append(f"could not compute announce_day0 from {announce_iso!r} after_close={after_close!r}")
        return r
    r.announce_day0 = ann_day0

    pricing_iso = _to_iso(leg.get("pricing_date", ""))
    if pricing_iso:
        pd0 = compute_day0(pricing_iso, "FALSE", cal, cfg)
        if pd0 is not None:
            r.pricing_day0 = pd0

    settlement_iso = _to_iso(leg.get("settlement_date", ""))
    if settlement_iso:
        sd0 = compute_day0(settlement_iso, "FALSE", cal, cfg)
        if sd0 is not None:
            r.settlement_day0 = sd0

    # returns
    stock_ret = build_return_series(price, cfg.return_type)
    mkt_ret = build_topix_returns(topix, cfg.return_type)
    ar, fit = compute_ar_series(stock_ret, mkt_ret, ann_day0, cal, cfg, cfg.model_primary)
    r.model_used = cfg.model_primary
    if fit is not None:
        r.alpha = fit.alpha
        r.beta = fit.beta
        r.est_n = fit.n
        if not fit.ok:
            r.est_reason = fit.reason
            r.notes.append(f"market_model fit failed: {fit.reason}")

    # ADV
    for w in cfg.adv_windows:
        adv = compute_adv(price, ann_day0, w, cal, cfg.adv_min_ratio)
        if w == 20:
            r.ADV20_shares = adv
        elif w == 60:
            r.ADV60_shares = adv

    # market_cap
    mc, detail = compute_market_cap(price, shares, ann_day0, cal)
    r.market_cap_JPY = mc
    r.market_cap_detail = detail

    # event windows
    r.announcement_CAR_m1_p1 = sum_ar_over_window(
        ar, ann_day0, tuple(cfg.event_windows["announcement"]["m1_p1"]), cal
    )
    r.announcement_CAR_0_p1 = sum_ar_over_window(
        ar, ann_day0, tuple(cfg.event_windows["announcement"]["zero_p1"]), cal
    )
    if r.pricing_day0:
        r.pricing_CAR_m1_p1 = sum_ar_over_window(
            ar, r.pricing_day0, tuple(cfg.event_windows["pricing"]["m1_p1"]), cal
        )
        r.drift_ann_to_pricing = sum_ar_between(
            ar, r.announce_day0, r.pricing_day0,
            cfg.drift_include_start, cfg.drift_include_end,
        )
    if r.settlement_day0:
        r.settlement_CAR_m1_p1 = sum_ar_over_window(
            ar, r.settlement_day0, tuple(cfg.event_windows["settlement"]["m1_p1"]), cal
        )

    # recovery
    for h in cfg.recovery_horizons:
        val = compute_recovery(ar, ann_day0, h, cal, cfg.recovery_transform)
        if h == 5:
            r.recovery_5d = val
        elif h == 20:
            r.recovery_20d = val
        elif h == 60:
            r.recovery_60d = val

    # abnormal volume
    denom = r.ADV60_shares if cfg.ab_denom == "ADV60" else r.ADV20_shares
    r.abnormal_volume_0_p3 = compute_abnormal_volume(
        price, ann_day0, tuple(cfg.ab_window), denom, cal, cfg.ab_transform
    )

    return r


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _configure_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("unwind_tape.car")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_dir / f"car_engine_{datetime.now().strftime('%Y-%m-%d')}.log",
                              encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh); logger.addHandler(sh)
    return logger


def _fmt(v: float, nd: int = 6) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.{nd}f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "car.yaml")
    args = ap.parse_args(argv)

    log = _configure_logging(args.root / "data" / "logs")
    cfg = Config.from_yaml(args.config)
    log.info("config: primary=%s robustness=%s est=[%d,%d] recovery=%s",
             cfg.model_primary, cfg.model_robustness, cfg.est_start, cfg.est_end,
             cfg.recovery_horizons)

    tape_dir = args.root / "data" / "parsed" / "tape"
    prices_dir = args.root / "data" / "raw" / "prices"
    fins_dir = prices_dir / "fins_summary"

    # load
    cal_path = prices_dir / "trading_calendar.jsonl"
    topix_path = prices_dir / "topix.jsonl"
    if not cal_path.exists() or not topix_path.exists():
        log.error("prices/ not populated. Run jquants_fetch.py first. missing: %s or %s",
                  cal_path, topix_path)
        return 5
    try:
        cal_df = load_trading_calendar(cal_path)
        cal = BusinessCalendar(cal_df)
        topix = load_topix(topix_path)
    except FieldMismatchError as e:
        log.error("field mismatch while loading calendar/topix (V1→V2 rename?): %s", e)
        return 6

    with (tape_dir / "legs.csv").open("r", encoding="utf-8") as f:
        legs = list(csv.DictReader(f))
    log.info("legs=%d unique codes=%d", len(legs),
             len({l.get("issuer_code", "") for l in legs}))

    prices: dict[str, pd.DataFrame] = {}
    shares_map: dict[str, pd.DataFrame] = {}
    for l in legs:
        code = l.get("issuer_code", "").strip()
        if not code or code in prices:
            continue
        p_path = prices_dir / "daily_quotes" / f"{code}.jsonl"
        if p_path.exists():
            try:
                prices[code] = load_daily_quotes(p_path, log)
            except FieldMismatchError as e:
                log.error("[%s] field mismatch loading daily_quotes (V1→V2 rename?): %s", code, e)
        s_path = fins_dir / f"{code}.jsonl"
        shares_map[code] = load_fins_shares(s_path, log) if s_path.exists() else pd.DataFrame(
            columns=["DisclosedDate", "shares_outstanding"])
    log.info("loaded prices for %d codes", len(prices))

    # process
    results: list[LegResult] = []
    for leg in legs:
        r = process_leg(leg, prices, shares_map, topix, cal, cfg, log)
        results.append(r)
        log.info("leg %s/%s day0=%s CAR[-1,+1]=%s ADV20=%s",
                 r.event_group_id, r.event_leg_id, r.announce_day0,
                 _fmt(r.announcement_CAR_m1_p1, 4),
                 _fmt(r.ADV20_shares, 0))

    # write legs_computed.csv
    comp_cols = ["event_group_id", "event_leg_id", "issuer_code",
                 "announce_day0", "pricing_day0", "settlement_day0",
                 "ADV20_shares", "ADV60_shares", "market_cap_JPY", "market_cap_detail",
                 "model_used", "alpha", "beta", "est_n", "est_reason"]
    with (tape_dir / "legs_computed.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(comp_cols)
        for r in results:
            w.writerow([
                r.event_group_id, r.event_leg_id, r.issuer_code,
                r.announce_day0, r.pricing_day0, r.settlement_day0,
                _fmt(r.ADV20_shares, 0), _fmt(r.ADV60_shares, 0),
                _fmt(r.market_cap_JPY, 0), r.market_cap_detail,
                r.model_used, _fmt(r.alpha, 8), _fmt(r.beta, 6),
                r.est_n, r.est_reason,
            ])

    # write legs_car.csv (spec 8 columns + identity)
    car_cols = ["event_group_id", "event_leg_id", "issuer_code"] + cfg.output_columns
    with (tape_dir / "legs_car.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(car_cols)
        for r in results:
            w.writerow([
                r.event_group_id, r.event_leg_id, r.issuer_code,
                _fmt(r.announcement_CAR_m1_p1),
                _fmt(r.announcement_CAR_0_p1),
                _fmt(r.drift_ann_to_pricing),
                _fmt(r.pricing_CAR_m1_p1),
                _fmt(r.settlement_CAR_m1_p1),
                _fmt(r.recovery_5d),
                _fmt(r.recovery_20d),
                _fmt(r.recovery_60d),
                _fmt(r.abnormal_volume_0_p3, 4),
            ])

    # brief report
    rpt = [f"# CAR engine report\n\ngenerated: {datetime.now().isoformat(timespec='seconds')}\n\n"]
    rpt.append(f"- model_primary: {cfg.model_primary}\n")
    rpt.append(f"- estimation window: [{cfg.est_start}, {cfg.est_end}] (min days: {cfg.est_min_days})\n")
    rpt.append(f"- legs processed: {len(results)}\n\n")
    rpt.append("## per-leg summary\n\n| leg | day0 | model | β | ADV20 | ADV60 | CAR[-1,+1] | notes |\n|---|---|---|---:|---:|---:|---:|---|\n")
    for r in results:
        rpt.append(
            f"| {r.event_group_id}/{r.event_leg_id} | {r.announce_day0} | {r.model_used or ''} | "
            f"{_fmt(r.beta, 3)} | {_fmt(r.ADV20_shares, 0)} | {_fmt(r.ADV60_shares, 0)} | "
            f"{_fmt(r.announcement_CAR_m1_p1, 4)} | {'; '.join(r.notes)[:120]} |\n"
        )
    rpt.append("\n## hand-check targets (G004 Honda, G008 Nintendo)\n\n")
    rpt.append("これらは spec (完了条件 3) の突合対象。手計算と一致していることを PREREG.md に確定した窓/モデルで検証すること。\n\n")
    for target in ("G004", "G008"):
        matching = [r for r in results if r.event_group_id == target]
        if not matching:
            continue
        for r in matching:
            rpt.append(f"### {r.event_group_id}/{r.event_leg_id} ({r.issuer_code})\n")
            rpt.append(f"- announce_day0: {r.announce_day0}\n")
            rpt.append(f"- model: {r.model_used}, β={_fmt(r.beta,4)}, α={_fmt(r.alpha,6)}, est_n={r.est_n}\n")
            rpt.append(f"- announcement_CAR_m1_p1: {_fmt(r.announcement_CAR_m1_p1)}\n")
            rpt.append(f"- announcement_CAR_0_p1:  {_fmt(r.announcement_CAR_0_p1)}\n")
            rpt.append(f"- drift_ann_to_pricing:    {_fmt(r.drift_ann_to_pricing)}\n")
            rpt.append(f"- pricing_CAR_m1_p1:       {_fmt(r.pricing_CAR_m1_p1)}\n")
            rpt.append(f"- settlement_CAR_m1_p1:    {_fmt(r.settlement_CAR_m1_p1)}\n")
            rpt.append(f"- recovery 5d/20d/60d:     {_fmt(r.recovery_5d)} / {_fmt(r.recovery_20d)} / {_fmt(r.recovery_60d)}\n")
            rpt.append(f"- abnormal_volume_0_p3:    {_fmt(r.abnormal_volume_0_p3, 4)}\n")
            rpt.append(f"- ADV20 / ADV60:           {_fmt(r.ADV20_shares,0)} / {_fmt(r.ADV60_shares,0)}\n")
            rpt.append(f"- market_cap_JPY:          {_fmt(r.market_cap_JPY,0)} ({r.market_cap_detail})\n\n")
    (tape_dir / "car_report.md").write_text("".join(rpt), encoding="utf-8")

    log.info("wrote legs_computed.csv, legs_car.csv, car_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
