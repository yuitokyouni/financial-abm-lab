#!/usr/bin/env python3
"""unwind-tape / イベント条件付き stylized facts エンジン(YH009)。

コスト分布の形(s1/s2/s3/IS の尖度・歪度・二群)は artifact 側で出す。こちらは
**日次生バーが要る**「売出しイベント前後の二次モーメント・裾」= この現象固有の署名:

  1. 実現ボラのスパイクと減衰: 各 leg の窓別 日次ボラ
       pre=[-25,-6]  run-in=[-5,-1]  event=[0,+5]  drift=[+6,+25]  (day0 相対営業日)
       spike = rv_event / rv_pre ,  decay = rv_drift / rv_pre
  2. 出来高の署名: event 窓の平均出来高 / ADV20(pre)  = abnormal volume
  3. 左裾: 全 leg の event+drift 日次リターンをプールし、-2*rv_pre を割る頻度
       (無イベントの pre 窓を対照に。正規なら片側 ~2.3%)

入力:
    data/parsed/tape/legs_shortfall.csv   (issuer_code, parent_day0, status, degenerate)
    data/raw/prices/daily_quotes/{code}.jsonl, trading_calendar.jsonl
出力:
    data/parsed/benchmark/stylized_event.csv / stylized_report.md

**推定禁止・欠損は空欄/skip。創作しない。** 依存: numpy + car_engine のローダ。
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import (  # noqa: E402
    BusinessCalendar, load_trading_calendar, load_daily_quotes, compute_adv,
)

# day0-relative business-day windows
WINDOWS = {"pre": (-25, -6), "runin": (-5, -1), "event": (0, 5), "drift": (6, 25)}


def _close_window(df, day0, a, b, cal):
    start = cal.shift_business_days(day0, a)
    end = cal.shift_business_days(day0, b)
    if start is None or end is None:
        return None
    p = df[(df["Date"] >= start) & (df["Date"] <= end)]
    c = p["AdjustmentClose"].fillna(p["Close"]).to_numpy()
    c = c[np.isfinite(c) & (c > 0)]
    return c if len(c) >= 2 else None


def _rv(df, day0, a, b, cal):
    """日次 log リターン標準偏差(調整終値)。"""
    c = _close_window(df, day0, a, b, cal)
    if c is None:
        return None
    r = np.diff(np.log(c))
    return float(np.std(r, ddof=1)) if len(r) > 1 else None


def _rets(df, day0, a, b, cal):
    c = _close_window(df, day0, a, b, cal)
    return np.diff(np.log(c)) if c is not None else np.array([])


def _mean_vol(df, day0, a, b, cal):
    start = cal.shift_business_days(day0, a)
    end = cal.shift_business_days(day0, b)
    if start is None or end is None:
        return None
    p = df[(df["Date"] >= start) & (df["Date"] <= end)]
    v = p["AdjustmentVolume"].fillna(p["Volume"]).to_numpy()
    v = v[np.isfinite(v)]
    return float(np.mean(v)) if len(v) else None


def _f(v, nd=4):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    return f"{v:.{nd}f}"


COLUMNS = ["event_group_id", "event_leg_id", "issuer_code",
           "rv_pre", "rv_runin", "rv_event", "rv_drift",
           "spike", "decay", "vol_abn", "n_left_tail", "n_event_drift", "status"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args(argv)
    tape = args.root / "data" / "parsed" / "tape"
    prices = args.root / "data" / "raw" / "prices"
    sf = tape / "legs_shortfall.csv"
    cal_path = prices / "trading_calendar.jsonl"
    for p in (sf, cal_path):
        if not p.exists():
            print(f"{p} not found — run jquants_fetch.py / shortfall_engine.py first.", file=sys.stderr)
            return 2
    cal = BusinessCalendar(load_trading_calendar(cal_path))

    cache: dict[str, object] = {}

    def price_df(code):
        if code not in cache:
            p = prices / "daily_quotes" / f"{code}.jsonl"
            cache[code] = load_daily_quotes(p) if p.exists() else None
        return cache[code]

    rows, pooled_event, pooled_pre_sd = [], [], []
    with sf.open(encoding="utf-8") as f:
        for sr in csv.DictReader(f):
            if sr.get("status") != "ok" or sr.get("degenerate") == "TRUE" \
                    or sr.get("split_in_window") == "TRUE":
                continue
            code = sr.get("issuer_code", "").strip()
            day0 = sr.get("parent_day0", "").strip()
            df = price_df(code)
            row = {c: "" for c in COLUMNS}
            row.update(event_group_id=sr["event_group_id"], event_leg_id=sr["event_leg_id"],
                       issuer_code=code, status="skip:no_data")
            if df is None or not day0:
                rows.append(row)
                continue
            rv = {k: _rv(df, day0, a, b, cal) for k, (a, b) in WINDOWS.items()}
            adv = compute_adv(df, day0, 20, cal, 0.8)
            mv_ev = _mean_vol(df, day0, *WINDOWS["event"], cal)
            row["rv_pre"] = _f(rv["pre"]); row["rv_runin"] = _f(rv["runin"])
            row["rv_event"] = _f(rv["event"]); row["rv_drift"] = _f(rv["drift"])
            if rv["pre"] and rv["pre"] > 0:
                if rv["event"] is not None:
                    row["spike"] = _f(rv["event"] / rv["pre"], 3)
                if rv["drift"] is not None:
                    row["decay"] = _f(rv["drift"] / rv["pre"], 3)
                # left tail: event+drift daily returns beyond -2*rv_pre
                ed = np.concatenate([_rets(df, day0, *WINDOWS["event"], cal),
                                     _rets(df, day0, *WINDOWS["drift"], cal)])
                if len(ed):
                    n_lt = int(np.sum(ed < -2.0 * rv["pre"]))
                    row["n_left_tail"] = str(n_lt); row["n_event_drift"] = str(len(ed))
                    pooled_event.append(ed / rv["pre"])   # standardised by pre vol
                    pooled_pre_sd.append(_rets(df, day0, *WINDOWS["pre"], cal) / rv["pre"])
            if adv and adv > 0 and mv_ev is not None:
                row["vol_abn"] = _f(mv_ev / adv, 3)
            row["status"] = "ok"
            rows.append(row)

    out = args.root / "data" / "parsed" / "benchmark" / "stylized_event.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)

    ok = [r for r in rows if r["status"] == "ok"]
    _report(args.root / "data" / "parsed" / "benchmark" / "stylized_report.md",
            ok, pooled_event, pooled_pre_sd)

    def med(key):
        xs = [float(r[key]) for r in ok if r[key] != ""]
        return float(np.median(xs)) if xs else float("nan")
    print(f"stylized: ok legs={len(ok)}/{len(rows)}  wrote stylized_event.csv / stylized_report.md")
    print(f"  median spike (rv_event/rv_pre) = {med('spike'):.2f}   "
          f"median decay (rv_drift/rv_pre) = {med('decay'):.2f}   "
          f"median vol_abn = {med('vol_abn'):.2f}")
    if pooled_event:
        pe = np.concatenate(pooled_event); pp = np.concatenate(pooled_pre_sd)
        print(f"  left-tail (<-2*rv_pre): event+drift={np.mean(pe < -2):.1%}  "
              f"pre(control)={np.mean(pp < -2):.1%}  (Gaussian ~2.3%)")
    return 0


def _report(path, ok, pooled_event, pooled_pre_sd):
    L = ["# イベント条件付き stylized facts — 売出し前後の二次モーメント・裾\n\n",
         f"generated: {datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')}\n\n",
         f"- ok legs: {len(ok)}  窓(営業日, day0相対): pre[-25,-6] run-in[-5,-1] event[0,+5] drift[+6,+25]\n\n"]

    def stat(key):
        xs = np.array([float(r[key]) for r in ok if r[key] != ""])
        return (np.median(xs), np.mean(xs), len(xs)) if len(xs) else (float("nan"),) * 3

    L.append("## 1. 実現ボラのスパイクと減衰\n")
    sm, sa, sn = stat("spike"); dm, da, dn = stat("decay")
    L.append(f"- **spike = rv_event/rv_pre**: median {sm:.2f} (mean {sa:.2f}, n={sn}) "
             f"→ 発表窓でボラが約 {sm:.1f}倍\n")
    L.append(f"- **decay = rv_drift/rv_pre**: median {dm:.2f} → drift 窓で "
             f"{'まだ高止まり' if dm > 1.2 else 'ほぼ平時へ減衰'}\n\n")
    L.append("## 2. 出来高の署名\n")
    vm, va, vn = stat("vol_abn")
    L.append(f"- **vol_abn = event 平均出来高 / ADV20(pre)**: median {vm:.2f}倍\n\n")
    L.append("## 3. 左裾(暴落頻度)\n")
    if pooled_event:
        pe = np.concatenate(pooled_event); pp = np.concatenate(pooled_pre_sd)
        L.append(f"- event+drift の日次リターン(pre ボラで標準化)で **< -2σ の頻度 = {np.mean(pe < -2):.1%}**"
                 f"、対照(pre 窓)= {np.mean(pp < -2):.1%}、正規理論 ~2.3%。\n")
        L.append(f"- < -3σ: event+drift {np.mean(pe < -3):.1%} vs pre {np.mean(pp < -3):.1%}。"
                 f"（左に厚い＝協調・予告供給の先回りが作る暴落側の裾）\n\n")
    L.append("> **注意**: 全て日次・調整終値。窓内に決算等の別イベントが入る leg は交絡。"
             "spike/decay は rv_pre 正規化なので銘柄横断で可比。\n")
    Path(path).write_text("".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
