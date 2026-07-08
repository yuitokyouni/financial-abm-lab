"""unwind-tape / 系統B shortfall_engine の単体テスト (MEASUREMENT_SPEC v0.2)。

合成データで検証:
  - 恒等分解 IS_raw = s1 + s2 + s3 が厳密に閉じる (最重要)
  - secondary_offering の s3 = discount(生)、符号
  - toSTNeT_3 の s3 ≡ 0、degenerate 扱い、aux_protection の符号
  - TOPIX total 調整 IS_adj
  - measurable_flag=FALSE (share_forward)
  - 日付順序ガード
  - 欠損時の skip(創作しない)
  - 生終値を使う(調整後を混ぜない)ことの回帰: 分割銘柄で s3 が壊れないこと
"""
from __future__ import annotations

import csv
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from car_engine import BusinessCalendar, Config  # noqa: E402
import shortfall_engine as se  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def make_cal(start=date(2024, 1, 1), end=date(2024, 12, 31)) -> BusinessCalendar:
    import pandas as pd
    rows = []
    d = start
    while d <= end:
        rows.append({"Date": d.isoformat(), "HolidayDivision": "1" if d.weekday() < 5 else "0",
                     "IsBusinessDay": d.weekday() < 5})
        d += timedelta(days=1)
    return BusinessCalendar(pd.DataFrame(rows))


def car_cfg() -> Config:
    return Config(
        model_primary="topix_adjusted", model_robustness=[], return_type="log_return",
        est_start=-140, est_end=-21, est_min_days=100, alpha_free=True,
        after_close_field="after_close", after_close_true_value="TRUE",
        after_close_shifts=True, non_business_shifts=True,
        event_windows={}, drift_include_start=False, drift_include_end=True,
        recovery_horizons=[], recovery_transform="cum_ar",
        ab_window=[0, 3], ab_denom="ADV60", ab_transform="log_ratio",
        adv_windows=[20, 60], adv_min_ratio=0.8, output_columns=[],
    )


def scfg() -> se.ShortfallConfig:
    return se.ShortfallConfig(
        stage1_forward_days=1,
        measurable_routes={"secondary_offering", "offauction_distribution", "toSTNeT_3"},
        non_measurable_routes={"open_market_sale", "share_forward", "market_sale_undetermined",
                               "mixed", "unknown"},
    )


def ohlc(close_map: dict[str, float], open_map: dict[str, float] | None = None) -> dict[str, dict]:
    open_map = open_map or {}
    dates = set(close_map) | set(open_map)
    return {d: {"close": close_map.get(d), "open": open_map.get(d)} for d in dates}


# ---------------------------------------------------------------------------
# secondary_offering — 恒等分解
# ---------------------------------------------------------------------------

def test_secondary_offering_identity_holds_exactly():
    cal = make_cal()
    # parent day0 = 2024-06-05 (Wed). announce with after_close=FALSE → day0 = announce day.
    # P_ref = close[2024-06-04]. day0+1 = 2024-06-06. pricing = 2024-06-11. offer = 950.
    closes = {
        "2024-06-04": 1000.0,   # P_ref
        "2024-06-06": 980.0,    # close[day0+a]
        "2024-06-11": 970.0,    # pricing close (P_exec_ref)
    }
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE",
           "pricing_date": "2024-06-11", "offer_price_JPY": "950"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc(closes), {}, cal, scfg())
    assert r.status == "ok", r.status
    # identity
    assert abs((r.stage1_cost + r.stage2_cost + r.stage3_cost) - r.IS_raw) < 1e-12
    # explicit values
    assert abs(r.IS_raw - (math.log(1000.0) - math.log(950.0))) < 1e-12
    assert abs(r.stage1_cost - (math.log(1000.0) - math.log(980.0))) < 1e-12
    assert abs(r.stage2_cost - (math.log(980.0) - math.log(970.0))) < 1e-12
    # s3 = discount (生): pricing close 970 vs offer 950 → 正 (コスト)
    assert abs(r.stage3_cost - (math.log(970.0) - math.log(950.0))) < 1e-12
    assert r.stage3_cost > 0


def test_secondary_offering_missing_offer_price_skips():
    cal = make_cal()
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE",
           "pricing_date": "2024-06-11", "offer_price_JPY": ""}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05",
                                 ohlc({"2024-06-04": 1000.0}), {}, cal, scfg())
    assert r.status.startswith("skip:missing_offer_price")
    assert r.IS_raw is None  # 創作しない


def test_secondary_offering_missing_pricing_date_skips():
    cal = make_cal()
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE",
           "pricing_date": "", "offer_price_JPY": "950"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05",
                                 ohlc({"2024-06-04": 1000.0}), {}, cal, scfg())
    assert r.status.startswith("skip:missing_pricing_date")


# ---------------------------------------------------------------------------
# toSTNeT_3 — s3≡0, degenerate, aux
# ---------------------------------------------------------------------------

def test_tostnet3_degenerate_s3_zero_and_aux_sign():
    cal = make_cal()
    # parent day0 = 2024-06-05. trade_date = 2024-06-05 (same day) → exec_ref = 2024-06-04 (prev close)
    # exec_ref (06-04) < day0+a (06-06) → degenerate.
    closes = {"2024-06-04": 1000.0}          # P_ref AND P_exec (前日終値=約定値)
    opens = {"2024-06-05": 1010.0}           # trade day open; exec(1000) < open(1010) → aux>0 (有利)
    leg = {"event_group_id": "G", "event_leg_id": "L2", "sale_route": "toSTNeT_3",
           "event_role": "buyback_result", "trade_date": "2024-06-05",
           "sold_shares": "500", "buyback_size_shares": "1000"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc(closes, opens), {}, cal, scfg())
    assert r.degenerate == "TRUE"
    assert r.status.startswith("ok:degenerate")
    # stages not split
    assert r.stage1_cost is None and r.stage2_cost is None and r.stage3_cost is None
    # IS_raw = ln(P_ref) - ln(P_exec) = ln(1000) - ln(1000) = 0
    assert abs(r.IS_raw) < 1e-12
    # aux_protection = ln(P_exec / open) = ln(1000/1010) < 0? wait: 正=有利.
    # spec: aux = ln(P_exec / open[trade]). exec=1000, open=1010 → ln(1000/1010) < 0.
    # 「正=市場(始値)より有利」の解釈: 売り手は高く約定できたら有利。exec(1000) < open(1010)
    # なので始値で売る方が高い=ToSTNeT約定は不利 → aux<0。符号は spec 式通り。
    assert r.aux_protection is not None
    assert abs(r.aux_protection - math.log(1000.0 / 1010.0)) < 1e-12
    # fill_ratio = 500/1000
    assert abs(r.fill_ratio - 0.5) < 1e-12


def test_tostnet3_non_degenerate_s3_is_zero():
    cal = make_cal()
    # 作為的に exec_ref を day0+a より後ろにする: trade_date を離す
    # parent day0 = 2024-06-05, day0+a = 06-06. trade_date = 06-14 → exec_ref = 06-13 (> 06-06) → 非degenerate
    closes = {
        "2024-06-04": 1000.0,   # P_ref
        "2024-06-06": 990.0,    # close[day0+a]
        "2024-06-13": 970.0,    # exec_ref = P_exec = 前日終値(約定値)
    }
    leg = {"event_group_id": "G", "event_leg_id": "L2", "sale_route": "toSTNeT_3",
           "event_role": "trade", "trade_date": "2024-06-14",
           "sold_shares": "", "buyback_size_shares": ""}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc(closes), {}, cal, scfg())
    assert r.status == "ok", r.status
    assert r.degenerate == ""
    # s3 ≡ 0 (P_exec_ref == P_exec)
    assert abs(r.stage3_cost) < 1e-12
    # identity
    assert abs((r.stage1_cost + r.stage2_cost + r.stage3_cost) - r.IS_raw) < 1e-12
    # fill_ratio blank (分母無し → 創作しない)
    assert r.fill_ratio is None


# ---------------------------------------------------------------------------
# TOPIX total 調整
# ---------------------------------------------------------------------------

def test_is_adj_removes_topix_drift():
    cal = make_cal()
    closes = {"2024-06-04": 1000.0, "2024-06-06": 980.0, "2024-06-11": 970.0}
    topix = {"2024-06-04": 2000.0, "2024-06-11": 1980.0}  # market fell over holding period
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE",
           "pricing_date": "2024-06-11", "offer_price_JPY": "950"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc(closes), topix, cal, scfg())
    drift = math.log(2000.0) - math.log(1980.0)
    assert abs(r.IS_adj - (r.IS_raw - drift)) < 1e-12


# ---------------------------------------------------------------------------
# measurable_flag / guards
# ---------------------------------------------------------------------------

def test_share_forward_is_non_measurable():
    cal = make_cal()
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "share_forward",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc({"2024-06-04": 1000.0}), {}, cal, scfg())
    assert r.measurable_flag == "FALSE"
    assert r.status == "non_measurable_route"
    assert r.IS_raw is None


def test_parent_day0_unresolved_skips():
    cal = make_cal()
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "",
           "pricing_date": "2024-06-11", "offer_price_JPY": "950"}
    # parent_day0=None simulates after_close blank
    r = se.compute_leg_shortfall(leg, "1234", None, ohlc({"2024-06-04": 1000.0}), {}, cal, scfg())
    assert r.measurable_flag == "TRUE"
    assert r.status.startswith("skip:parent_day0_unresolved")


# ---------------------------------------------------------------------------
# raw-vs-adjusted regression: 分割があっても s3 が discount のまま壊れない
# ---------------------------------------------------------------------------

def test_raw_close_keeps_s3_as_true_discount_across_a_later_split():
    """イベント後に 1:3 分割があった銘柄を想定。生終値を使えば s3 は真の discount
    (offer が pricing close の 5% 下)のまま。調整後を混ぜていたら ln(3) ぶんずれる。
    ここでは生終値のみをエンジンに渡す=実装が生を使う契約を回帰テストで固定する。
    """
    cal = make_cal()
    # 真の(生)価格: pricing close 1000, offer 950 → discount = ln(1000/950) ≈ 0.0513
    closes = {"2024-06-04": 1050.0, "2024-06-06": 1030.0, "2024-06-11": 1000.0}
    leg = {"event_group_id": "G", "event_leg_id": "L1", "sale_route": "secondary_offering",
           "event_role": "announcement", "announce_datetime": "2024-06-05", "after_close": "FALSE",
           "pricing_date": "2024-06-11", "offer_price_JPY": "950"}
    r = se.compute_leg_shortfall(leg, "1234", "2024-06-05", ohlc(closes), {}, cal, scfg())
    true_discount = math.log(1000.0) - math.log(950.0)
    assert abs(r.stage3_cost - true_discount) < 1e-12
    # もし調整後(/3)を close に、生を offer に混ぜていたら s3 は true_discount - ln(3) になり壊れる:
    broken = true_discount - math.log(3.0)
    assert abs(r.stage3_cost - broken) > 1.0   # 壊れていないことを明示
