#!/usr/bin/env python3
"""unwind-tape / task C5 — G004(Honda)/G008(Nintendo) の CAR 手計算突合。

car_engine.py とは独立した実装で同じ raw jsonl から CAR[-1,+1] を計算し直し、
car_report.md の数値と一致するか検証する。日付ナビゲーションだけ
car_engine.BusinessCalendar を再利用するが、AR/CAR の算術は別実装。

使い方:
    python3 unwind-tape/scripts/hand_check_car.py

出力: 各 leg について day-2..day+1 の4営業日の Close を表示し、
      3日分の日次 AR (topix_adjusted = r_stock - r_topix) と
      その合計 (= CAR[-1,+1]) を、car_report.md の値と並べて表示する。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import BusinessCalendar, load_trading_calendar, compute_day0, Config  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "raw" / "prices"


def load_closes(path: Path) -> dict[str, float]:
    out = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            c = e.get("C", e.get("Close"))
            if c is not None:
                out[e["Date"]] = float(c)
    return out


def hand_check(label: str, code: str, announce_date: str, after_close: str, cal: BusinessCalendar) -> float:
    cfg = Config(
        model_primary="topix_adjusted", model_robustness=[], return_type="log_return",
        est_start=-140, est_end=-21, est_min_days=100, alpha_free=True,
        after_close_field="after_close", after_close_true_value="TRUE",
        after_close_shifts=True, non_business_shifts=True,
        event_windows={}, drift_include_start=False, drift_include_end=True,
        recovery_horizons=[], recovery_transform="cum_ar",
        ab_window=[0, 3], ab_denom="ADV60", ab_transform="log_ratio",
        adv_windows=[20, 60], adv_min_ratio=0.8, output_columns=[],
    )
    day0 = compute_day0(announce_date, after_close, cal, cfg)
    print(f"\n=== {label} (code={code}, announce={announce_date}, after_close={after_close}) ===")
    print(f"day0 = {day0}")

    # need day0-2 .. day0+1 (4 dates) to compute 3 daily returns covering [-1,+1]
    dates = [cal.shift_business_days(day0, k) for k in (-2, -1, 0, 1)]
    print(f"dates used: {dates}")

    stock = load_closes(PRICES / "daily_quotes" / f"{code}.jsonl")
    topix = load_closes(PRICES / "topix.jsonl")

    car = 0.0
    for i in range(1, len(dates)):
        d_prev, d = dates[i - 1], dates[i]
        r_s = math.log(stock[d] / stock[d_prev])
        r_t = math.log(topix[d] / topix[d_prev])
        ar = r_s - r_t
        car += ar
        print(f"  {d}: stock_close={stock[d]:.2f} (prev {stock[d_prev]:.2f}) "
              f"r_stock={r_s:+.6f}  topix r={r_t:+.6f}  AR={ar:+.6f}")
    print(f"  --> hand-computed CAR[-1,+1] = {car:+.6f}")
    return car


def main() -> int:
    cal_df = load_trading_calendar(PRICES / "trading_calendar.jsonl")
    cal = BusinessCalendar(cal_df)

    targets = [
        ("G004/L001 Honda",    "7267", "2024-07-04", "FALSE"),
        ("G008/L001 Nintendo", "7974", "2026-02-27", "TRUE"),
        ("G008/L002 Nintendo", "7974", "2026-03-03", "FALSE"),
    ]
    reported = {
        "G004/L001 Honda": -0.010755,
        "G008/L001 Nintendo": 0.011071,
        "G008/L002 Nintendo": 0.047487,
    }

    print("car_report.md との突合 (許容誤差 1e-4 = 丸め込み分):\n")
    all_ok = True
    for label, code, announce, after_close in targets:
        car = hand_check(label, code, announce, after_close, cal)
        expected = reported[label]
        diff = abs(car - expected)
        ok = diff < 1e-4
        all_ok &= ok
        print(f"  car_report.md value = {expected:+.6f}  diff = {diff:.6f}  "
              f"{'MATCH' if ok else 'MISMATCH!!'}")

    print(f"\n{'ALL MATCH' if all_ok else 'MISMATCH DETECTED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
