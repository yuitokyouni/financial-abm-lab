#!/usr/bin/env python3
"""unwind-tape / 系統B — implementation shortfall 分解エンジン (MEASUREMENT_SPEC v0.2)。

系統A(car_engine.py の CAR)とは独立。measurable な子 leg について、親イベント
発表 day0 を起点に seller の実現コスト IS を stage 分解する。

    P_ref = 親 day0 の前営業日 (生)終値
    IS_raw = ln(P_ref) - ln(P_exec)                      正 = コスト
    IS_raw = s1 + s2 + s3   (恒等分解、構成上厳密)
      s1 = ln(P_ref)       - ln(close[day0+a])           発表インパクト
      s2 = ln(close[day0+a]) - ln(P_exec_ref)            ドリフト
      s3 = ln(P_exec_ref)  - ln(P_exec)                  執行ギャップ (生の契約量)
    IS_adj = IS_raw - [ln(TOPIX@P_ref日) - ln(TOPIX@P_exec_ref日)]   (total 調整)

価格基準は**生終値 (C)**。調整後を混ぜると分割銘柄で s3 が壊れる (MEASUREMENT_SPEC 実装ノート)。

day0 の解決は car_engine.compute_day0 を共用(系統Aと同一の親 day0 を使う)。
測定不能 route (open_market_sale / share_forward 等) は measurable_flag=FALSE。
データ欠損・日付順序違反は status に理由を出して skip(近似値の創作はしない)。

出力: data/parsed/tape/legs_shortfall.csv
依存: numpy 不要(pure stdlib + car_engine の日付ユーティリティ + PyYAML)。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import BusinessCalendar, load_trading_calendar, compute_day0, Config  # noqa: E402


# ---------------------------------------------------------------------------
# price loading (raw OHLC)
# ---------------------------------------------------------------------------

def _first_key(d: dict, cands: list[str]):
    for k in cands:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def load_raw_ohlc(path: Path) -> dict[str, dict[str, float]]:
    """returns {Date: {"open": float|None, "close": float|None}} using RAW (unadjusted) fields."""
    out: dict[str, dict[str, float]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            date = e.get("Date")
            if not date:
                continue
            c = _first_key(e, ["Close", "C"])
            o = _first_key(e, ["Open", "O"])
            af = _first_key(e, ["AdjustmentFactor", "AdjFactor", "AF"])
            out[date] = {
                "close": float(c) if c is not None else None,
                "open": float(o) if o is not None else None,
                "adj_factor": float(af) if af is not None else None,
            }
    return out


def load_raw_close(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            date = e.get("Date")
            c = _first_key(e, ["Close", "C"])
            if date and c is not None:
                out[date] = float(c)
    return out


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class ShortfallConfig:
    stage1_forward_days: int
    measurable_routes: set[str]
    non_measurable_routes: set[str]

    @classmethod
    def from_yaml(cls, path: Path) -> "ShortfallConfig":
        with path.open("r", encoding="utf-8") as f:
            c = yaml.safe_load(f)
        s = c.get("shortfall", {})
        return cls(
            stage1_forward_days=int(s.get("stage1_forward_days", 1)),
            measurable_routes=set(s.get("measurable_routes", [])),
            non_measurable_routes=set(s.get("non_measurable_routes", [])),
        )


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

def _blank(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


@dataclass
class ShortfallResult:
    event_group_id: str
    event_leg_id: str
    issuer_code: str
    sale_route: str
    measurable_flag: str = ""          # TRUE / FALSE
    parent_day0: str = ""
    P_ref_date: str = ""
    exec_ref_date: str = ""
    degenerate: str = ""               # TRUE / "" — 即日型 (exec_ref < day0+a)
    split_in_window: str = ""          # TRUE / FALSE — [P_ref, exec_ref] に分割 → s1/s2/IS が段差
    stage1_cost: float | None = None
    stage2_cost: float | None = None
    stage3_cost: float | None = None
    IS_raw: float | None = None
    IS_adj: float | None = None
    aux_protection: float | None = None
    fill_ratio: float | None = None
    status: str = ""                   # ok | skip:<reason>

    def row(self) -> dict[str, str]:
        return {
            "event_group_id": self.event_group_id,
            "event_leg_id": self.event_leg_id,
            "issuer_code": self.issuer_code,
            "sale_route": self.sale_route,
            "measurable_flag": self.measurable_flag,
            "parent_day0": self.parent_day0,
            "P_ref_date": self.P_ref_date,
            "exec_ref_date": self.exec_ref_date,
            "degenerate": self.degenerate,
            "split_in_window": self.split_in_window,
            "stage1_cost": _blank(self.stage1_cost),
            "stage2_cost": _blank(self.stage2_cost),
            "stage3_cost": _blank(self.stage3_cost),
            "IS_raw": _blank(self.IS_raw),
            "IS_adj": _blank(self.IS_adj),
            "aux_protection": _blank(self.aux_protection),
            "fill_ratio": _blank(self.fill_ratio),
            "status": self.status,
        }


COLUMNS = ["event_group_id", "event_leg_id", "issuer_code", "sale_route",
           "measurable_flag", "parent_day0", "P_ref_date", "exec_ref_date", "degenerate",
           "split_in_window", "stage1_cost", "stage2_cost", "stage3_cost", "IS_raw", "IS_adj",
           "aux_protection", "fill_ratio", "status"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _iso(s: str) -> str:
    s = (s or "").strip()
    return s[:10] if len(s) >= 10 and s[4] == "-" else s


def _num(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _split_in_window(ohlc: dict[str, dict], cal: BusinessCalendar,
                     start: str | None, end: str | None) -> bool:
    """[start, end] の営業日(start 当日は除く)に AdjustmentFactor≠1(分割/割当 ex-date)が
    あるか。start 当日の分割は P_ref も新基準になり段差にならないため除外する。"""
    if not start or not end or start >= end:
        return False
    for d in cal.range_business_days(start, end):
        if d == start:
            continue
        af = ohlc.get(d, {}).get("adj_factor")
        if af is not None and abs(af - 1.0) > 1e-9:
            return True
    return False


def resolve_group_day0(legs_in_group: list[dict], cal: BusinessCalendar, cfg: Config) -> str | None:
    """親(意思決定)の day0。event_role=announcement の leg の announce_datetime/after_close で決める。
    無ければ announce_datetime を持つ最初の leg にフォールバック。
    """
    ann = [l for l in legs_in_group if l.get("event_role", "").strip() == "announcement"]
    cand = ann or [l for l in legs_in_group if _iso(l.get("announce_datetime", ""))]
    if not cand:
        return None
    leg = cand[0]
    return compute_day0(_iso(leg.get("announce_datetime", "")), leg.get("after_close", ""), cal, cfg)


# ---------------------------------------------------------------------------
# per-leg shortfall
# ---------------------------------------------------------------------------

def compute_leg_shortfall(leg: dict, code: str, parent_day0: str | None,
                          ohlc: dict[str, dict[str, float]] | None,
                          topix: dict[str, float],
                          cal: BusinessCalendar, scfg: ShortfallConfig) -> ShortfallResult:
    gid = leg["event_group_id"]
    lid = leg["event_leg_id"]
    route = leg.get("sale_route", "").strip()
    r = ShortfallResult(event_group_id=gid, event_leg_id=lid, issuer_code=code, sale_route=route)

    # measurable_flag
    if route in scfg.non_measurable_routes:
        r.measurable_flag = "FALSE"
        r.status = "non_measurable_route"
        return r
    if route not in scfg.measurable_routes:
        r.measurable_flag = "FALSE"
        r.status = f"skip:unknown_route({route!r})"
        return r
    r.measurable_flag = "TRUE"

    if not code or ohlc is None:
        r.status = f"skip:no_price_data(code={code!r})"
        return r
    if parent_day0 is None:
        r.status = "skip:parent_day0_unresolved(need after_close/disclosure_time)"
        return r
    r.parent_day0 = parent_day0

    def close(d: str | None) -> float | None:
        return ohlc.get(d, {}).get("close") if d else None

    def open_(d: str | None) -> float | None:
        return ohlc.get(d, {}).get("open") if d else None

    # P_ref = 親 day0 の前営業日 生終値
    p_ref_date = cal.prev_business_day(parent_day0)
    P_ref = close(p_ref_date)
    if P_ref is None:
        r.status = f"skip:no_P_ref_close({p_ref_date})"
        return r
    r.P_ref_date = p_ref_date

    a = scfg.stage1_forward_days
    d_a = cal.shift_business_days(parent_day0, a)   # close[day0+a]

    # --- route 別に P_exec, P_exec_ref, aux を決める ---
    P_exec: float | None = None
    P_exec_ref: float | None = None
    exec_ref_date: str | None = None

    if route == "secondary_offering":
        pricing_date = _iso(leg.get("pricing_date", ""))
        offer = _num(leg.get("offer_price_JPY", ""))
        if not pricing_date:
            r.status = "skip:missing_pricing_date(要一次PDF転記)"
            return r
        if offer is None:
            r.status = "skip:missing_offer_price_JPY(要一次PDF転記)"
            return r
        exec_ref_date = pricing_date
        P_exec_ref = close(exec_ref_date)
        if P_exec_ref is None:
            r.status = f"skip:no_pricing_close({exec_ref_date})"
            return r
        P_exec = offer

    elif route == "offauction_distribution":
        # 分売価格は現行 tape schema に列が無い(Task A capture 由来。将来 legs に distribution_price を足す)
        r.status = "skip:distribution_price_not_in_schema"
        return r

    elif route == "toSTNeT_3":
        trade_date = _iso(leg.get("trade_date", ""))
        if not trade_date:
            r.status = "skip:missing_trade_date"
            return r
        exec_ref_date = cal.prev_business_day(trade_date)   # 前日終値 = 約定値
        P_exec = close(exec_ref_date)
        if P_exec is None:
            r.status = f"skip:no_prev_close_for_trade({exec_ref_date})"
            return r
        P_exec_ref = P_exec                                 # s3 ≡ 0 (構成上)
        # aux_protection = ln(P_exec / open[trade_date]); 正 = 市場(始値)より有利に執行
        o_trade = open_(trade_date)
        if o_trade is not None and o_trade > 0:
            r.aux_protection = math.log(P_exec / o_trade)
        # fill_ratio: 約定株数 / 上限株数。上限が tape に一意に無い場合は空欄(創作しない)
        sold = _num(leg.get("sold_shares", ""))
        upper = _num(leg.get("buyback_size_shares", ""))
        if sold is not None and upper is not None and upper > 0:
            r.fill_ratio = sold / upper
    else:
        r.status = f"skip:route_not_handled({route})"
        return r

    r.exec_ref_date = exec_ref_date

    # 窓内分割ガード: [P_ref_date, exec_ref_date] に分割 ex-date があると、P_ref(分割前)と
    # P_exec(分割後)が別基準になり IS_raw/s1/s2/IS_adj が段差で壊れる(生終値ベースの窓内版)。
    # s3(offering=pricing-local / toSTNeT=≡0)は分割の影響を受けないので保持し、残りは NA + フラグ。
    r.split_in_window = "FALSE"
    if _split_in_window(ohlc, cal, p_ref_date, exec_ref_date):
        r.split_in_window = "TRUE"
        if route == "secondary_offering":
            r.stage3_cost = math.log(P_exec_ref) - math.log(P_exec)   # pricing-local、分割影響なし
        elif route == "toSTNeT_3":
            r.stage3_cost = 0.0                                       # 構成上
        r.status = "ok:split_in_window(s1/s2/IS_raw/IS_adj=NA, s3のみ有効)"
        return r

    # IS_raw (恒等)
    r.IS_raw = math.log(P_ref) - math.log(P_exec)

    # 日付順序ガード: P_ref_date < day0+a <= exec_ref_date
    order_ok = (p_ref_date < d_a <= exec_ref_date) if (d_a and exec_ref_date) else False
    if not order_ok:
        # 即日型 (exec_ref が day0+a より前) → degenerate: stage 分解せず IS_raw + 補助のみ
        r.degenerate = "TRUE"
        r.status = "ok:degenerate(no_stage_split)"
    else:
        c_da = close(d_a)
        if c_da is None:
            r.status = f"skip:no_close_day0+a({d_a})"
            return r
        r.stage1_cost = math.log(P_ref) - math.log(c_da)
        r.stage2_cost = math.log(c_da) - math.log(P_exec_ref)
        r.stage3_cost = math.log(P_exec_ref) - math.log(P_exec)
        # 恒等性の内部検証(構成上厳密に閉じるはず)
        recon = r.stage1_cost + r.stage2_cost + r.stage3_cost
        if abs(recon - r.IS_raw) > 1e-9:
            r.status = f"skip:identity_broken(Σstage={recon:.9f} vs IS_raw={r.IS_raw:.9f})"
            return r
        r.status = "ok"

    # IS_adj = IS_raw - TOPIX drift over [P_ref_date, exec_ref_date]
    t_ref = topix.get(p_ref_date)
    t_exec = topix.get(exec_ref_date)
    if t_ref is not None and t_exec is not None and t_ref > 0 and t_exec > 0:
        r.IS_adj = r.IS_raw - (math.log(t_ref) - math.log(t_exec))

    return r


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "car.yaml")
    args = ap.parse_args(argv)

    tape = args.root / "data" / "parsed" / "tape"
    prices = args.root / "data" / "raw" / "prices"

    if not (tape / "legs.csv").exists() or not (tape / "groups.csv").exists():
        print(f"legs.csv/groups.csv not found under {tape} — run Task B first.", file=sys.stderr)
        return 2
    if not (prices / "trading_calendar.jsonl").exists() or not (prices / "topix.jsonl").exists():
        print(f"prices not populated under {prices} — run jquants_fetch.py first.", file=sys.stderr)
        return 2

    car_cfg = Config.from_yaml(args.config)
    scfg = ShortfallConfig.from_yaml(args.config)
    cal = BusinessCalendar(load_trading_calendar(prices / "trading_calendar.jsonl"))
    topix = load_raw_close(prices / "topix.jsonl")

    with (tape / "groups.csv").open("r", encoding="utf-8") as f:
        groups = {g["event_group_id"]: g for g in csv.DictReader(f)}
    with (tape / "legs.csv").open("r", encoding="utf-8") as f:
        legs = list(csv.DictReader(f))

    # group -> legs
    by_group: dict[str, list[dict]] = {}
    for l in legs:
        by_group.setdefault(l["event_group_id"], []).append(l)
    group_day0 = {gid: resolve_group_day0(g_legs, cal, car_cfg) for gid, g_legs in by_group.items()}

    ohlc_cache: dict[str, dict] = {}
    results: list[ShortfallResult] = []
    for leg in legs:
        gid = leg["event_group_id"]
        code = groups.get(gid, {}).get("issuer_code", "").strip()
        ohlc = None
        if code:
            if code not in ohlc_cache:
                p = prices / "daily_quotes" / f"{code}.jsonl"
                ohlc_cache[code] = load_raw_ohlc(p) if p.exists() else {}
            ohlc = ohlc_cache[code] or None
        r = compute_leg_shortfall(leg, code, group_day0.get(gid), ohlc, topix, cal, scfg)
        results.append(r)

    out = tape / "legs_shortfall.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in results:
            w.writerow(r.row())

    # summary
    ok = [r for r in results if r.status.startswith("ok")]
    nonmeas = [r for r in results if r.measurable_flag == "FALSE"]
    skipped = [r for r in results if r.status.startswith("skip")]
    print(f"legs={len(results)}  ok={len(ok)}  non_measurable={len(nonmeas)}  skipped={len(skipped)}")
    print(f"wrote {out.relative_to(args.root)}")
    print("\n-- ok legs --")
    for r in ok:
        print(f"  {r.event_group_id}/{r.event_leg_id} {r.sale_route} "
              f"IS_raw={_blank(r.IS_raw)} IS_adj={_blank(r.IS_adj)} "
              f"s=[{_blank(r.stage1_cost)},{_blank(r.stage2_cost)},{_blank(r.stage3_cost)}] "
              f"aux={_blank(r.aux_protection)} {r.status}")
    print("\n-- skipped (要データ) --")
    for r in skipped:
        print(f"  {r.event_group_id}/{r.event_leg_id} {r.sale_route}: {r.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
