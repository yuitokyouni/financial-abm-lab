"""unwind-tape / apply_transcription の単体テスト。

- disclosure_time + 正しい time_source → plan に入り after_close を機械導出
- inferred / enum外 / 空欄 time_source → ERROR(disclosure_time は書かない)
- after_close が開示時刻と矛盾 → ERROR
- discount が 2〜5% 帯の外 → WARN、pricing lag が 5〜15 帯の外 → WARN(拒否ではない)
- 空欄は触らない(創作しない)
- apply_to_legs が非空セルのみ上書き
"""
from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from car_engine import BusinessCalendar, Config  # noqa: E402
import apply_transcription as at  # noqa: E402


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


def leg(gid="G004", lid="L001", **kw):
    base = {"event_group_id": gid, "event_leg_id": lid, "announce_datetime": "",
            "disclosure_time": "", "after_close": "", "pricing_date": "",
            "offer_price_JPY": "", "OA_exercised_shares": ""}
    base.update(kw)
    return base


def _plan(ws, legs, code_by_gid=None, prices=None):
    legs_by_id = {(r["event_group_id"], r["event_leg_id"]): r for r in legs}
    return at.plan_and_validate(ws, legs_by_id, code_by_gid or {}, make_cal(), car_cfg(),
                                prices or {})


# ---------------------------------------------------------------------------
# derive after_close
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t,expected", [
    ("15:40", "TRUE"), ("15:00", "TRUE"), ("14:59", "FALSE"), ("09:00", "FALSE"),
    ("bad", None), ("", None),
])
def test_derive_after_close(t, expected):
    assert at._derive_after_close(t) == expected


# ---------------------------------------------------------------------------
# disclosure_time / time_source
# ---------------------------------------------------------------------------

def test_valid_disclosure_derives_after_close():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "15:40",
           "after_close": "", "time_source": "kabutan", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg(announce_datetime="2024-07-04")])
    assert not [i for i in issues if i[0] == "ERROR"]
    assert plan[("G004", "L001")]["disclosure_time"] == "15:40"
    assert plan[("G004", "L001")]["after_close"] == "TRUE"


def test_inferred_time_source_is_error_and_not_written():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "15:40",
           "after_close": "", "time_source": "inferred", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg()])
    assert any(i[0] == "ERROR" and i[3] == "time_source" for i in issues)
    assert "disclosure_time" not in plan.get(("G004", "L001"), {})


def test_blank_time_source_with_time_is_error():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "15:40",
           "after_close": "", "time_source": "", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg()])
    assert any(i[0] == "ERROR" for i in issues)
    assert "disclosure_time" not in plan.get(("G004", "L001"), {})


def test_after_close_mismatch_is_error():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "15:40",
           "after_close": "FALSE", "time_source": "kabutan", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg()])
    assert any(i[0] == "ERROR" and i[3] == "after_close" for i in issues)
    assert "after_close" not in plan.get(("G004", "L001"), {})       # 矛盾セルは書かない
    assert plan[("G004", "L001")]["disclosure_time"] == "15:40"      # time は有効なので残る


def test_bare_after_close_false_passes():
    # G002 share_forward: disclosure_time 無しで after_close=FALSE 単体
    ws = [{"event_group_id": "G002", "event_leg_id": "L001", "disclosure_time": "",
           "after_close": "FALSE", "time_source": "", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg(gid="G002")])
    assert not [i for i in issues if i[0] == "ERROR"]
    assert plan[("G002", "L001")]["after_close"] == "FALSE"


def test_blank_row_writes_nothing():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "",
           "after_close": "", "time_source": "", "pricing_date": "",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    plan, issues = _plan(ws, [leg()])
    assert ("G004", "L001") not in plan


# ---------------------------------------------------------------------------
# WARN: discount / pricing lag
# ---------------------------------------------------------------------------

def test_discount_out_of_band_warns():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "",
           "after_close": "", "time_source": "", "pricing_date": "2024-07-10",
           "offer_price_JPY": "900", "OA_exercised_shares": ""}]
    prices = {"7267": {"2024-07-10": 1030.0}}    # discount = 12.6% → WARN
    plan, issues = _plan(ws, [leg()], code_by_gid={"G004": "7267"}, prices=prices)
    assert any(i[0] == "WARN" and i[3] == "discount" for i in issues)
    assert plan[("G004", "L001")]["pricing_date"] == "2024-07-10"   # WARN でも書く


def test_discount_in_band_no_warn():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "",
           "after_close": "", "time_source": "", "pricing_date": "2024-07-10",
           "offer_price_JPY": "1000", "OA_exercised_shares": ""}]
    prices = {"7267": {"2024-07-10": 1030.0}}    # discount = 2.9% → OK
    plan, issues = _plan(ws, [leg()], code_by_gid={"G004": "7267"}, prices=prices)
    assert not [i for i in issues if i[3] == "discount"]


def test_pricing_lag_out_of_band_warns():
    ws = [{"event_group_id": "G004", "event_leg_id": "L001", "disclosure_time": "",
           "after_close": "", "time_source": "", "pricing_date": "2024-07-05",
           "offer_price_JPY": "", "OA_exercised_shares": ""}]
    # announce 2024-07-04 (Thu) after_close TRUE → day0 07-05; pricing 07-05 → lag 0 < 5 → WARN
    lg = leg(announce_datetime="2024-07-04", after_close="TRUE")
    plan, issues = _plan(ws, [lg])
    assert any(i[0] == "WARN" and i[3] == "pricing_lag" for i in issues)


# ---------------------------------------------------------------------------
# apply merge
# ---------------------------------------------------------------------------

def test_apply_to_legs_writes_only_nonblank(tmp_path):
    legs = [leg(announce_datetime="2024-07-04"), leg(gid="G003")]
    p = tmp_path / "legs.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(legs[0].keys()))
        w.writeheader()
        w.writerows(legs)
    plan = {("G004", "L001"): {"disclosure_time": "15:40", "after_close": "TRUE"}}
    n = at.apply_to_legs(p, legs, plan)
    assert n == 2
    out = {(r["event_group_id"], r["event_leg_id"]): r for r in _read(p)}
    assert out[("G004", "L001")]["after_close"] == "TRUE"
    assert out[("G003", "L001")]["after_close"] == ""   # 触っていない


def test_new_meta_fields_pass_through():
    legs = [leg("G012", "L001")]
    ws = [{"event_group_id": "G012", "event_leg_id": "L001", "disclosure_time": "", "after_close": "",
           "time_source": "", "pricing_date": "", "offer_price_JPY": "", "OA_exercised_shares": "",
           "seller_type": "financial_institutions", "absorption_route": "public_offering",
           "offering_type": "overseas_ABB", "leak_date": "2025-02-26"}]
    plan, issues = _plan(ws, legs)
    cell = plan[("G012", "L001")]
    assert cell["seller_type"] == "financial_institutions"
    assert cell["absorption_route"] == "public_offering"
    assert cell["offering_type"] == "overseas_ABB"
    assert cell["leak_date"] == "2025-02-26"
    assert not [i for i in issues if i[0] == "ERROR"]


def test_leak_date_bad_format_is_error():
    legs = [leg("G012", "L001")]
    ws = [{"event_group_id": "G012", "event_leg_id": "L001", "disclosure_time": "", "after_close": "",
           "time_source": "", "pricing_date": "", "offer_price_JPY": "", "OA_exercised_shares": "",
           "leak_date": "2025/02/26"}]   # スラッシュ区切り = 不正
    plan, issues = _plan(ws, legs)
    assert any(i[0] == "ERROR" and i[3] == "leak_date" for i in issues)
    assert "leak_date" not in plan.get(("G012", "L001"), {})   # ERROR セルは書かない


def _read(p):
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
