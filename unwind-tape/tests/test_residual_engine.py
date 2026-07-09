"""unwind-tape / residual_engine の単体テスト(TCA_BASELINE 残差プロトタイプ)。

- compute_residual_row: implied_Y = (s2+s3)/(σ√(Q/V))、participation、bucket、skip 経路
- compute_sigma: 窓内の調整終値 log リターン標準偏差(ddof=1)、データ不足で None
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from car_engine import BusinessCalendar  # noqa: E402
import residual_engine as re_  # noqa: E402

EDGES = [0.25, 0.5, 1.0, 2.0]


def make_cal(start=date(2024, 1, 1), end=date(2024, 12, 31)) -> BusinessCalendar:
    import pandas as pd
    rows = []
    d = start
    while d <= end:
        rows.append({"Date": d.isoformat(), "HolidayDivision": "1" if d.weekday() < 5 else "0",
                     "IsBusinessDay": d.weekday() < 5})
        d += timedelta(days=1)
    return BusinessCalendar(pd.DataFrame(rows))


def _bd(start, end):
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# compute_residual_row
# ---------------------------------------------------------------------------

def test_residual_row_implied_Y():
    r = re_.compute_residual_row("G", "L1", "7203", "secondary_offering",
                                 s2=0.01, s3=0.02, Q=1_000_000.0, V=500_000.0, sigma=0.02, edges=EDGES)
    assert r["status"] == "ok"
    assert r["participation"] == pytest.approx(2.0)
    assert r["measured_s2s3"] == pytest.approx(0.03)
    assert r["sqrt_shape"] == pytest.approx(0.02 * math.sqrt(2.0))
    assert r["implied_Y"] == pytest.approx(0.03 / (0.02 * math.sqrt(2.0)))
    assert r["size_bucket"] == ">=2"


def test_residual_row_skips():
    assert re_.compute_residual_row("G", "L", "1", "r", None, 0.02, 1e6, 5e5, 0.02, EDGES)["status"] == "skip:no_s2s3"
    assert re_.compute_residual_row("G", "L", "1", "r", 0.01, 0.02, None, 5e5, 0.02, EDGES)["status"] == "skip:no_Q_or_ADV"
    assert re_.compute_residual_row("G", "L", "1", "r", 0.01, 0.02, 1e6, 5e5, None, EDGES)["status"] == "skip:no_sigma"
    # measured は s2/s3 が揃えば skip でも入る
    r = re_.compute_residual_row("G", "L", "1", "r", 0.01, 0.02, None, 5e5, 0.02, EDGES)
    assert r["measured_s2s3"] == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# compute_sigma
# ---------------------------------------------------------------------------

def test_compute_sigma_matches_windowed_std():
    import pandas as pd
    cal = make_cal()
    bd = _bd(date(2024, 1, 1), date(2024, 2, 29))
    closes = [1000.0 * (1.0 + 0.002 * ((i % 7) - 3)) for i in range(len(bd))]  # 変動あり
    df = pd.DataFrame({"Date": bd, "AdjustmentClose": closes, "Close": closes})
    day0 = "2024-03-01"
    sig = re_.compute_sigma(df, day0, 20, cal, 0.8)
    end = cal.shift_business_days(day0, -1)
    start = cal.shift_business_days(day0, -20)
    win = [c for d, c in zip(bd, closes) if start <= d <= end]
    exp = float(np.std(np.diff(np.log(win)), ddof=1))
    assert sig == pytest.approx(exp)
    assert sig > 0


def test_compute_sigma_insufficient_data_none():
    import pandas as pd
    cal = make_cal()
    bd = _bd(date(2024, 2, 20), date(2024, 2, 29))   # 数日しかない
    df = pd.DataFrame({"Date": bd, "AdjustmentClose": [1000.0] * len(bd), "Close": [1000.0] * len(bd)})
    assert re_.compute_sigma(df, "2024-03-01", 20, cal, 0.8) is None   # window*0.8 未満
