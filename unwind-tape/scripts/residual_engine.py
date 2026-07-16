#!/usr/bin/env python3
"""unwind-tape / 残差エンジン(最小プロトタイプ)— 実測(s2+s3) vs 標準TCA(√則)。

docs/TCA_BASELINE_SPEC.md の成果物②の配管。N<30 の間は**記述のみ**:係数 Y は当てはめず、
各 leg が要求する **implied_Y = (s2+s3) / (σ·√(Q/V))** を並べる。
  - implied_Y が participation(Q/V=size/ADV20)で**上昇** → √則が外す**非線形の兆候**。
  - **flat** → √則が効いている。
相転移点 τ / べき α の推定は N ゲート(≥30、主要方式2系統×各10)通過後(spec §3)。ここでは推定しない。

入力:
    data/parsed/tape/legs_shortfall.csv   (shortfall_engine の出力: s2/s3, parent_day0, split_in_window)
    data/parsed/tape/legs.csv             (sold_shares)
    data/parsed/tape/groups.csv           (issuer_code)
    data/raw/prices/daily_quotes/{code}.jsonl, trading_calendar.jsonl
    configs/tca.yaml

出力:
    data/parsed/benchmark/residual_detail.csv / residual_report.md

除外(measured=s2+s3 が無い/汚染): degenerate、split_in_window=TRUE、status≠ok、s2 or s3 欠。

participation の基準合わせ: Q=sold_shares(day0 基準・未調整)と V=ADV20(最新基準・調整出来高)の
基準ズレを補正する。発表の**後**に分割/権利落ちがあると AdjVol が窓を遡及的に膨らませ Q/V が過小に
なる(古河電工 5801=2026-07-01 の 1→10 分割で Q/ADV20 が 0.42→0.042 に見えた例)。**day0 より後の
AdjustmentFactor だけ**の逆積 factor=1/Π(AF:Date>day0) で Q を最新基準へ写す(発表前・ADV窓内の分割は
開示 Q に既に反映済なので数えない=窓内 mean 比を使うと過補正)。σ・s1/s2/s3 は分割中立で不変。

依存: numpy, pandas, PyYAML + car_engine の日付/価格ユーティリティ + benchmark_engine.size_bucket。
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
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import (  # noqa: E402
    BusinessCalendar, load_trading_calendar, load_daily_quotes, compute_adv,
)
from benchmark_engine import size_bucket  # noqa: E402


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def compute_sigma(price_df, day0: str, window: int, cal: BusinessCalendar,
                  min_ratio: float) -> float | None:
    """直前 [day0-window, day0-1] の日次 log リターン標準偏差。調整終値(分割安全)。"""
    end = cal.shift_business_days(day0, -1)
    start = cal.shift_business_days(day0, -window)
    if end is None or start is None:
        return None
    p = price_df[(price_df["Date"] >= start) & (price_df["Date"] <= end)]
    close = p["AdjustmentClose"].fillna(p["Close"]).to_numpy()
    close = close[np.isfinite(close) & (close > 0)]
    if len(close) < window * min_ratio:
        return None
    r = np.diff(np.log(close))
    if len(r) < 2:
        return None
    return float(np.std(r, ddof=1))


def _window_vol_ratio(price_df, day0: str, window: int, cal: BusinessCalendar,
                      min_ratio: float) -> float | None:
    """診断用: 窓 [day0-window, day0-1] の mean(AdjustmentVolume)/mean(Volume)。
    分割 ex-date が窓の**外(day0 より後)**なら日次一定 = 発表後分割の累積係数に一致する。
    窓の**中**に ex-date が入ると前半(調整済)と後半(未調整)が混ざり **非整数**になる
    = ADV20 自体が分割を跨いでいる兆候(straddle)。出来高欠は None(fail-loud)。"""
    end = cal.shift_business_days(day0, -1)
    start = cal.shift_business_days(day0, -window)
    if end is None or start is None:
        return None
    p = price_df[(price_df["Date"] >= start) & (price_df["Date"] <= end)]
    if p.empty:
        return None
    adj = p["AdjustmentVolume"].to_numpy(); raw = p["Volume"].to_numpy()
    m = np.isfinite(adj) & np.isfinite(raw) & (raw > 0)
    if int(m.sum()) < window * min_ratio:
        return None
    mean_raw = float(np.mean(raw[m]))
    if mean_raw <= 0:
        return None
    return float(np.mean(adj[m])) / mean_raw


def participation_basis(price_df, day0: str, window: int, cal: BusinessCalendar,
                        min_ratio: float) -> dict:
    """Q(発表時開示の未調整株数)を ADV20(=調整出来高, 最新基準)と同じ基準へ写す係数を返す。

    **なぜ必要か**: participation = Q/V で V=ADV20 は*調整*出来高だが、Q=sold_shares は開示時点の
    *未調整*株数。両者は「発表日(day0)より後」の分割・権利落ちのぶんだけ基準がズレる。
    発表**後**に分割があると J-Quants の AdjustmentVolume が窓を遡及的に膨らませ、V だけ増えて
    Q/V が過小になる(古河 5801=2026-07-01 の 1→10 分割で 0.42→0.042 に潰れた)。

    **正しい係数は「day0 より後の AdjustmentFactor だけ」**の逆積: factor = 1/Π(AF: Date>day0)。
    - 発表**後**の分割/権利落ちのみ Q を持ち上げる(古河=×10)。
    - 発表**前**・ADV窓内の分割は **開示 Q に既に織り込み済**(Q は分割後株数)なので数えない。
      窓内 mean(AdjVol)/mean(Vol) を係数に使うと、この窓内分割まで二重計上して**過補正**になる
      (例: アシックス 7936 の窓内比 ×1.56 は非整数=窓跨ぎで、Q への係数としては誤り)。
    σ・s1/s2/s3 は log リターン/調整終値で分割中立なので participation だけを補正する。

    返り値 dict: factor(適用係数、Q_adj=Q*factor)、window_ratio(診断)、note:
      '' 通常 / 'straddle'(window_ratio と factor が不一致=分割 ex-date が ADV窓内。ADV20 は
      分割跨ぎだが Q への factor は正しい)/ 'af_missing'(AdjustmentFactor 欠で係数算出不可、
      補正せず nominal のまま=fail-loud)。
    """
    window_ratio = _window_vol_ratio(price_df, day0, window, cal, min_ratio)
    after = price_df[price_df["Date"] > day0]
    af = after["AdjustmentFactor"].to_numpy() if "AdjustmentFactor" in after else np.array([])
    af_fin = af[np.isfinite(af)]
    note = ""
    if int(after.shape[0]) > 0 and af_fin.shape[0] == 0:
        factor, note = None, "af_missing"          # 列欠 → 係数不可、補正しない
    else:
        prod = float(np.prod(af_fin)) if af_fin.shape[0] else 1.0
        factor = 1.0 / prod if prod > 0 else None
    if factor is not None and window_ratio is not None \
            and abs(window_ratio - factor) > max(0.05, 0.05 * factor):
        note = "straddle"                           # 窓内に分割 ex-date(ADV20 が分割跨ぎ)
    return {"factor": factor, "window_ratio": window_ratio, "note": note}


RESIDUAL_COLUMNS = ["event_group_id", "event_leg_id", "issuer_code", "sale_route",
                    "Q_shares", "Q_nominal_shares", "adv_split_ratio",
                    "adv_window_ratio", "basis_note", "ADV20",
                    "participation", "sigma",
                    "stage2_cost", "stage3_cost",
                    "measured_s2s3", "sqrt_shape", "implied_Y", "implied_Y_s2",
                    "size_bucket", "status"]


def compute_residual_row(gid: str, lid: str, code: str, route: str,
                         s2: float | None, s3: float | None, Q: float | None,
                         V: float | None, sigma: float | None, edges: list[float]) -> dict:
    """純関数: 与えられた s2,s3,Q,V,σ から participation/shape/implied_Y を出す。
    √則の**非線形テストは implied_Y_s2 = s2/(σ√(Q/V)) を主に見る**(2026-07 決定)。
    s3 は発行ディスカウント層(引受の手腕・需要の強弱=市場清算価格ではない、需要弱で拡大)なので
    √則の判定から外し、内訳として別掲。implied_Y(s2+s3)は総実現コスト側の参考として残す。"""
    row = {"event_group_id": gid, "event_leg_id": lid, "issuer_code": code, "sale_route": route,
           "Q_shares": Q, "Q_nominal_shares": Q, "adv_split_ratio": None,
           "adv_window_ratio": None, "basis_note": "",
           "ADV20": V, "participation": None, "sigma": sigma,
           "stage2_cost": s2, "stage3_cost": s3,
           "measured_s2s3": None, "sqrt_shape": None, "implied_Y": None, "implied_Y_s2": None,
           "size_bucket": "", "status": ""}
    if s2 is None or s3 is None:
        row["status"] = "skip:no_s2s3"
        return row
    measured = s2 + s3
    row["measured_s2s3"] = measured
    if not Q or not V or V <= 0:
        row["status"] = "skip:no_Q_or_ADV"
        return row
    part = Q / V
    row["participation"] = part
    row["size_bucket"] = size_bucket(part, edges)
    if sigma is None or sigma <= 0:
        row["status"] = "skip:no_sigma"
        return row
    shape = sigma * math.sqrt(part)
    row["sqrt_shape"] = shape
    row["implied_Y"] = measured / shape if shape > 0 else None
    row["implied_Y_s2"] = s2 / shape if shape > 0 else None   # ← √則 非線形テストの主指標
    row["status"] = "ok"
    return row


def _f(v, nd=6):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "tca.yaml")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    edges = [float(x) for x in cfg["size_over_adv_edges"]]
    sw = int(cfg["sigma_window_days"]); aw = int(cfg["adv_window_days"])
    amr = float(cfg["adv_min_ratio"])

    tape = args.root / "data" / "parsed" / "tape"
    prices = args.root / "data" / "raw" / "prices"
    sf_path = tape / "legs_shortfall.csv"
    if not sf_path.exists():
        print(f"{sf_path} not found — run shortfall_engine.py first.", file=sys.stderr)
        return 2
    cal_path = prices / "trading_calendar.jsonl"
    if not cal_path.exists():
        print(f"{cal_path} not found — run jquants_fetch.py first.", file=sys.stderr)
        return 2
    cal = BusinessCalendar(load_trading_calendar(cal_path))

    sold_by = {}
    with (tape / "legs.csv").open(encoding="utf-8") as f:
        for l in csv.DictReader(f):
            sold_by[(l["event_group_id"], l["event_leg_id"])] = _num(l.get("sold_shares", ""))

    price_cache: dict[str, object] = {}

    def price_df(code: str):
        if code not in price_cache:
            p = prices / "daily_quotes" / f"{code}.jsonl"
            price_cache[code] = load_daily_quotes(p) if p.exists() else None
        return price_cache[code]

    rows = []
    with sf_path.open(encoding="utf-8") as f:
        for sr in csv.DictReader(f):
            gid, lid = sr["event_group_id"], sr["event_leg_id"]
            code = sr.get("issuer_code", "").strip()
            route = sr.get("sale_route", "").strip()
            # 対象は「s2+s3 が生きている」leg のみ: ok・非degenerate・非split
            if sr.get("status") != "ok" or sr.get("degenerate") == "TRUE" \
                    or sr.get("split_in_window") == "TRUE":
                continue
            s2 = _num(sr.get("stage2_cost", "")); s3 = _num(sr.get("stage3_cost", ""))
            day0 = sr.get("parent_day0", "").strip()
            Q_nominal = sold_by.get((gid, lid))
            V = sigma = None
            pb = {"factor": None, "window_ratio": None, "note": ""}
            df = price_df(code)
            if df is not None and day0:
                V = compute_adv(df, day0, aw, cal, amr)
                sigma = compute_sigma(df, day0, sw, cal, amr)
                pb = participation_basis(df, day0, aw, cal, amr)
            # 発表後分割の基準合わせ: Q(未調整=day0基準) を ADV20(最新基準)へ持ち上げる。
            # factor は day0 より後の AdjustmentFactor だけの逆積(発表前・窓内分割は Q に既に反映済)。
            # factor 取得不可(af_missing)は補正せず nominal のまま(fail-loud、note に残す)。
            factor = pb["factor"]
            Q = Q_nominal * factor if (Q_nominal is not None and factor is not None) else Q_nominal
            r = compute_residual_row(gid, lid, code, route, s2, s3, Q, V, sigma, edges)
            r["Q_nominal_shares"] = Q_nominal
            r["adv_split_ratio"] = factor
            r["adv_window_ratio"] = pb["window_ratio"]
            r["basis_note"] = pb["note"]
            rows.append(r)

    out_detail = args.root / cfg["output"]["detail_csv"]
    out_detail.parent.mkdir(parents=True, exist_ok=True)
    with out_detail.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESIDUAL_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: _f(r[k]) for k in RESIDUAL_COLUMNS})

    ok = [r for r in rows if r["status"] == "ok"]
    _write_report(args.root / cfg["output"]["report_md"], ok, rows, sw, aw)
    print(f"residual: legs={len(rows)} ok={len(ok)}  wrote {cfg['output']['detail_csv']} / {cfg['output']['report_md']}")
    for r in ok:
        print(f"  {r['event_group_id']}/{r['event_leg_id']} {r['sale_route']} "
              f"Q/ADV20={_f(r['participation'],3)} σ={_f(r['sigma'],4)} "
              f"s2={_f(r['stage2_cost'],4)} implied_Y_s2={_f(r['implied_Y_s2'],3)} "
              f"(s2+s3={_f(r['measured_s2s3'],4)} implied_Y={_f(r['implied_Y'],3)})")
    flagged = [r for r in rows if r.get("adv_split_ratio") is not None
               and abs(r["adv_split_ratio"] - 1.0) > 0.01]
    if flagged:
        print("  ── 発表後分割の基準補正(day0 後の AdjustmentFactor で Q を ADV20 基準へ) ──")
        for r in flagged:
            wr = r.get("adv_window_ratio")
            print(f"    {r['event_group_id']}/{r['event_leg_id']} code={r['issuer_code']} "
                  f"factor×{_f(r['adv_split_ratio'],2)} (窓内比×{_f(wr,2) if wr is not None else '—'})  "
                  f"Q_nominal={_f(r['Q_nominal_shares'],0)} → Q_adj={_f(r['Q_shares'],0)}  "
                  f"Q/ADV20={_f(r['participation'],3)} ({r['status']})")
    warned = [r for r in rows if r.get("basis_note")]
    for r in warned:
        if r["basis_note"] == "straddle":
            print(f"  ⚠ {r['event_group_id']}/{r['event_leg_id']} code={r['issuer_code']}: "
                  f"ADV窓が分割跨ぎ(窓内比×{_f(r.get('adv_window_ratio'),2)} ≠ factor×{_f(r['adv_split_ratio'],2)})。"
                  f"Q への係数は day0 後のみで正しいが、ADV20 は分割前後の混成。要目視。")
        elif r["basis_note"] == "af_missing":
            print(f"  ⚠ {r['event_group_id']}/{r['event_leg_id']} code={r['issuer_code']}: "
                  f"AdjustmentFactor 欠で発表後分割を判定できず、Q は未補正(nominal)。")
    return 0


def _write_report(path: Path, ok: list[dict], allrows: list[dict], sw: int, aw: int) -> None:
    L = []
    L.append("# TCAベースライン残差(プロトタイプ) — 実測 s2 vs √則\n\n")
    L.append(f"generated: {datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')}\n\n")
    L.append(f"- ok legs: {len(ok)} / {len(allrows)}  (σ窓={sw}bd, ADV{aw}, 調整終値/調整出来高)\n\n")
    L.append("> **N<30 のため記述のみ(TCA_BASELINE §8)**。係数 Y は当てはめず、各 leg が要求する\n"
             "> **`implied_Y_s2 = s2 / (σ·√(Q/V))`** を並べる(2026-07 決定: √則の非線形テストは **s2 側**で見る。\n"
             "> s3 は発行ディスカウント層=引受手腕・需要の強弱で、市場清算価格ではない → √則判定から外し別掲)。\n"
             "> participation(Q/V)で implied_Y_s2 が **上昇 → √則が外す非線形の兆候**、**flat → √則が効いている**。\n"
             "> `implied_Y`(s2+s3)は総実現コスト側の参考。相転移点 τ / べき α の推定は N ゲート通過後(§3)。\n"
             "> ここでは τ を出さない。s1 は残差に含めない(系統Aへ)。\n\n")
    L.append("| leg | 方式 | Q/ADV20 | σ(日次) | s2(ドリフト) | s3(ディスカウント) | σ√(Q/V) | **implied_Y_s2** | implied_Y(s2+s3) | bucket |\n")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n")
    if not ok:
        L.append("| (まだ計算対象 leg 無し — 転記が進み s2/s3 が揃えば埋まる) | | | | | | | | | |\n")
    for r in sorted(ok, key=lambda x: (x["participation"] or 0)):
        L.append(f"| {r['event_group_id']}/{r['event_leg_id']} | {r['sale_route']} | "
                 f"{_f(r['participation'],3)} | {_f(r['sigma'],4)} | {_f(r['stage2_cost'],4)} | "
                 f"{_f(r['stage3_cost'],4)} | {_f(r['sqrt_shape'],4)} | "
                 f"**{_f(r['implied_Y_s2'],3)}** | {_f(r['implied_Y'],3)} | {r['size_bucket']} |\n")

    # s3 のクラスタリング検出(方式ごと): offering の s3 が「制度的にほぼ一定」なら √ 判定を汚す
    L.append("\n## 観察: s3(執行ギャップ)は方式内でほぼ一定か\n")
    by_route: dict[str, list[float]] = {}
    for r in ok:
        v = r.get("stage3_cost")
        if v is not None:
            by_route.setdefault(r["sale_route"], []).append(v)
    for route, vals in sorted(by_route.items()):
        if len(vals) < 2:
            L.append(f"- `{route}`: n={len(vals)}(判定は n≥2 から)\n")
            continue
        lo, hi = min(vals), max(vals)
        spread = hi - lo
        note = ""
        if spread < 0.01:
            note = " → **ほぼ一定 = 発行ディスカウント(制度固定)の疑い**"
        elif spread >= 0.015:
            note = " → **バラつく = 需要の強弱で拡縮(固定ではない。帯外=需要弱で深い)**"
        L.append(f"- `{route}`: s3 ∈ [{lo:.4f}, {hi:.4f}]、幅 {spread:.4f}(n={len(vals)}){note}\n")
    L.append("\n> **なぜ s3 を √則テストから外すか(2026-07 決定)**: s3(執行ギャップ)は発行ディスカウント層。\n"
             "> ほぼ一定なら固定 s3 を σ√(Q/V) で割って implied_Y が size で機械的に低下し、非線形判定を汚す。\n"
             "> バラついても、その拡縮は**引受の手腕・需要の強弱(帯外は需要弱で深い)= 市場清算価格ではない裏事情**で、\n"
             "> √則(市場インパクト)とは別レイヤ。→ 非線形は **implied_Y_s2 = s2/(σ√(Q/V))** で見る(s2=オーバーハング吸収)。\n")
    # 発表後分割の基準補正(participation のみ)
    flagged = [r for r in allrows if r.get("adv_split_ratio") is not None
               and abs(r["adv_split_ratio"] - 1.0) > 0.01]
    warned = [r for r in allrows if r.get("basis_note")]
    L.append("\n## 発表後分割の基準補正(participation)\n")
    if not flagged and not warned:
        L.append("- 該当なし(全 leg で day0 後の AdjustmentFactor=1、発表後の分割・権利落ちなし)。\n")
    else:
        L.append("> Q=sold_shares は開示時点(day0 基準)の**未調整**実数、V=ADV20 は**調整**出来高(最新基準)。\n"
                 "> 両者は **day0 より後**の分割・権利落ちのぶんだけ基準がズレる。factor = 1/Π(AdjustmentFactor:\n"
                 "> Date>day0) で Q を最新基準へ写して是正(発表前・窓内分割は開示 Q に織り込み済なので数えない)。\n"
                 "> σ・s1/s2/s3 は分割中立で不変。`窓内比`=mean(AdjVol)/mean(Vol) は診断: factor と食い違えば\n"
                 "> 分割 ex-date が ADV窓内(ADV20 が分割跨ぎ=straddle)。\n\n")
        L.append("| leg | code | factor× | 窓内比× | note | Q_nominal | Q_adj | Q/ADV20 |\n")
        L.append("|---|---|---:|---:|---|---:|---:|---:|\n")
        seen = set()
        for r in sorted(flagged + warned, key=lambda x: x["event_group_id"]):
            k = (r["event_group_id"], r["event_leg_id"])
            if k in seen:
                continue
            seen.add(k)
            L.append(f"| {r['event_group_id']}/{r['event_leg_id']} | {r['issuer_code']} | "
                     f"{_f(r['adv_split_ratio'],2)} | {_f(r.get('adv_window_ratio'),2)} | "
                     f"{r.get('basis_note') or '—'} | {_f(r['Q_nominal_shares'],0)} | "
                     f"{_f(r['Q_shares'],0)} | {_f(r['participation'],3)} |\n")
    L.append("\n## 読み方 / 参照分布との突合\n")
    L.append("- **√則テストは implied_Y_s2(s2 側)**: participation で上昇なら非線形、flat なら √則。s3 は別レイヤ。\n")
    L.append("- **売り手の s3 の平時水準**は参照分布 `off_both × discount`(`benchmark_summary.csv`、"
             "p90≈3.4% / 分売 3.0%)。実測 offering の s3 がこの裾に載るか、需要弱で深化するかを併読。\n")
    L.append("- **除外**: degenerate(即日型)・`split_in_window=TRUE`(窓内分割で s1/s2 段差)・"
             "s2 or s3 欠 は residual 対象外(創作しない)。Q(sold_shares)欠でも skip:no_Q_or_ADV。\n")
    L.append("- **次段(N≥30)**: implied_Y_s2 を participation の関数として segmented / べき α で当て、"
             "相転移点 τ を CI つきで推定(TCA_BASELINE §3)。\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
