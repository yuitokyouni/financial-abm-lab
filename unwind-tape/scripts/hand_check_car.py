#!/usr/bin/env python3
"""unwind-tape / task C5 — G004(Honda)/G008(Nintendo) の CAR 手計算突合。

car_engine.py とは独立した実装で同じ raw jsonl から CAR[-1,+1] を計算し直し、
legs_car.csv (car_engine.py の最新出力) の数値と一致するか検証する。

**独立性についての注記 (2026-07-08 review 指摘への対応)**:
以前のバージョンは対象 leg の announce_datetime/after_close を本スクリプト内に
ハードコードしていた。これは「独立した計算」ではなく、car_engine.py の出力に
後付けで合わせた値を使っていただけで、day0 解決ロジック自体のバグ
(after_close 空欄を暗黙に同日扱いする欠陥)を検出できない構造だった。
本バージョンは legs.csv / groups.csv から実際の値を読み、day0 解決も
car_engine.compute_day0 を呼ぶ(BusinessCalendar だけでなく判定ロジックも共用)。
共用部分にバグがあれば「両方が同じ誤答」を出し得る点は変わらないため、
**真の独立検証にはならない**。人間が day0/window の実日付を外部一次資料と
突き合わせることが最終的な担保になる (car_report.md の day0/window 出力を見よ)。

使い方:
    python3 unwind-tape/scripts/hand_check_car.py [event_group_id/event_leg_id ...]
    (引数なしなら G004/L001, G008/L001, G008/L002 を対象にする)

出力: 各 leg について day-2..day+1 の4営業日の Close を表示し、
      3日分の日次 AR (topix_adjusted = r_stock - r_topix) と
      その合計 (= CAR[-1,+1]) を、legs_car.csv の値と並べて表示する。
      day0 が未確定 (after_close 空欄等) の leg は SKIP と表示し、
      exit code には含めない。
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import BusinessCalendar, load_trading_calendar, compute_day0, Config  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "raw" / "prices"
TAPE = ROOT / "data" / "parsed" / "tape"

DEFAULT_TARGETS = ["G004/L001", "G008/L001", "G008/L002"]


def load_closes(path: Path) -> dict[str, float]:
    out = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            c = e.get("C", e.get("Close"))
            if c is not None:
                out[e["Date"]] = float(c)
    return out


def load_leg_rows() -> tuple[dict[str, dict], dict[str, dict]]:
    with (TAPE / "groups.csv").open("r", encoding="utf-8") as f:
        groups = {g["event_group_id"]: g for g in csv.DictReader(f)}
    with (TAPE / "legs.csv").open("r", encoding="utf-8") as f:
        legs = {f"{l['event_group_id']}/{l['event_leg_id']}": l for l in csv.DictReader(f)}
    return groups, legs


def load_reported_car() -> dict[str, float]:
    out = {}
    car_csv = TAPE / "legs_car.csv"
    if not car_csv.exists():
        return out
    with car_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = f"{row['event_group_id']}/{row['event_leg_id']}"
            v = row.get("announcement_CAR_m1_p1", "")
            if v:
                out[key] = float(v)
    return out


def hand_check(key: str, code: str, announce_date: str, after_close: str,
               cal: BusinessCalendar, cfg: Config) -> float | None:
    day0 = compute_day0(announce_date, after_close, cal, cfg)
    print(f"\n=== {key} (code={code}, announce={announce_date!r}, after_close={after_close!r}) ===")
    if day0 is None:
        print(f"  day0 = None (ambiguous after_close, or missing announce_datetime) — SKIP")
        return None
    print(f"day0 = {day0}")

    dates = [cal.shift_business_days(day0, k) for k in (-2, -1, 0, 1)]
    print(f"dates used (day0-2 .. day0+1): {dates}")
    if any(d is None for d in dates):
        print("  insufficient calendar depth around day0 — SKIP")
        return None

    stock = load_closes(PRICES / "daily_quotes" / f"{code}.jsonl")
    topix = load_closes(PRICES / "topix.jsonl")

    car = 0.0
    for i in range(1, len(dates)):
        d_prev, d = dates[i - 1], dates[i]
        if d not in stock or d_prev not in stock or d not in topix or d_prev not in topix:
            print(f"  missing price data for {d_prev} or {d} — SKIP")
            return None
        r_s = math.log(stock[d] / stock[d_prev])
        r_t = math.log(topix[d] / topix[d_prev])
        ar = r_s - r_t
        car += ar
        print(f"  {d}: stock_close={stock[d]:.2f} (prev {stock[d_prev]:.2f}) "
              f"r_stock={r_s:+.6f}  topix r={r_t:+.6f}  AR={ar:+.6f}")
    print(f"  --> hand-computed CAR[-1,+1] = {car:+.6f}")
    return car


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else DEFAULT_TARGETS

    if not (TAPE / "groups.csv").exists() or not (TAPE / "legs.csv").exists():
        print(f"groups.csv/legs.csv not found under {TAPE} — run Task B pipeline first.", file=sys.stderr)
        return 2
    if not (PRICES / "trading_calendar.jsonl").exists():
        print(f"trading_calendar.jsonl not found under {PRICES} — run jquants_fetch.py first.", file=sys.stderr)
        return 2

    groups, legs = load_leg_rows()
    reported = load_reported_car()

    cal_df = load_trading_calendar(PRICES / "trading_calendar.jsonl")
    cal = BusinessCalendar(cal_df)
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

    print("legs.csv / groups.csv の実データを読み、car_engine.py とは別実装で "
          "CAR[-1,+1] を再計算する。legs_car.csv (最新の car_engine.py 出力) と突合:\n")

    n_match, n_skip, n_mismatch = 0, 0, 0
    for key in targets:
        if key not in legs:
            print(f"\n=== {key} === leg not found in legs.csv — SKIP")
            n_skip += 1
            continue
        leg = legs[key]
        gid = leg["event_group_id"]
        code = groups.get(gid, {}).get("issuer_code", "").strip()
        announce = leg.get("announce_datetime", "")
        after_close = leg.get("after_close", "")

        if not code:
            print(f"\n=== {key} === no issuer_code resolved via groups.csv join — SKIP")
            n_skip += 1
            continue

        car = hand_check(key, code, announce, after_close, cal, cfg)
        if car is None:
            n_skip += 1
            continue

        expected = reported.get(key)
        if expected is None:
            print(f"  legs_car.csv value = (not present / blank) — nothing to compare")
            n_skip += 1
            continue
        diff = abs(car - expected)
        ok = diff < 1e-4
        if ok:
            n_match += 1
        else:
            n_mismatch += 1
        print(f"  legs_car.csv value  = {expected:+.6f}  diff = {diff:.6f}  "
              f"{'MATCH' if ok else 'MISMATCH!!'}")

    print(f"\n{n_match} match / {n_skip} skipped (day0 未確定 or データ欠損) / {n_mismatch} mismatch")
    if n_mismatch:
        print("MISMATCH DETECTED — car_engine.py と本スクリプトの実装を見直すこと。")
        return 1
    if n_match == 0:
        print("MATCH できた leg が0件。after_close 等のデータ拡充が先に必要。")
        return 3
    print("すべて MATCH (mismatch なし)。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
