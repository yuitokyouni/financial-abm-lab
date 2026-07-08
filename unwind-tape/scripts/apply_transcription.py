#!/usr/bin/env python3
"""unwind-tape / apply_transcription — 開示転記シート → legs.csv 反映(検証付き)。

transcription/disclosure_transcription.csv(埋めるだけのシート)の**非空セルのみ**を
legs.csv の該当 leg に上書きする。反映するのは
    disclosure_time, after_close, pricing_date, offer_price_JPY, OA_exercised_shares
の5列だけ(それ以外の legs.csv セルは一切触らない)。time_source は legs.csv に載せず、
シートを出所台帳(provenance)として保持する。

検証(BENCHMARK/転記 spec):
  ERROR(そのセルは書かない):
    - disclosure_time があるのに time_source が enum 外 / 空欄 / inferred(推定は不可)
    - after_close が disclosure_time と矛盾(開示時刻≥15:00 → TRUE のはず)
  WARN(確認フラグ、書き込みは行う):
    - offering の discount が 2〜5% 帯の外((pricing終値−offer)/pricing終値、生終値)
    - pricing_date が announce day0 の 5〜15営業日後の外
  空欄はそのまま(=day0 未確定の fail-loud を維持。創作しない)。

使い方:
    python3 scripts/apply_transcription.py --check   # 検証のみ(legs.csv は触らない)
    python3 scripts/apply_transcription.py --apply   # ERROR 以外を legs.csv に反映(冪等)

依存: car_engine の日付/価格ユーティリティ + stdlib。他リポパッケージへ import しない。
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import (  # noqa: E402
    BusinessCalendar, load_trading_calendar, compute_day0, Config, load_daily_quotes,
)

TIME_SOURCE_ENUM = {"pdf_header", "tdnet", "yahoo_archive", "kabutan", "media", "nikkei_nkd"}
MERGE_FIELDS = ["disclosure_time", "after_close", "pricing_date", "offer_price_JPY",
                "OA_exercised_shares"]
DISCOUNT_LO, DISCOUNT_HI = 0.02, 0.05
LAG_LO, LAG_HI = 5, 15


def _blank(v) -> bool:
    return v is None or str(v).strip() == ""


def _derive_after_close(t: str) -> str | None:
    """'15:40' → 'TRUE'(≥15:00) / '09:00' → 'FALSE'。形式不正なら None。"""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(t).strip())
    if not m:
        return None
    return "TRUE" if int(m.group(1)) >= 15 else "FALSE"


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _biz_lag(day0: str, pricing: str, cal: BusinessCalendar) -> int | None:
    if not day0 or not pricing:
        return None
    span = cal.range_business_days(day0, pricing)
    if not span:
        return None
    return max(0, len(span) - 1)


def plan_and_validate(ws_rows, legs_by_id, code_by_gid, cal, cfg,
                      prices) -> tuple[dict, list[tuple]]:
    """returns (plan: {(gid,lid): {field: value}}, issues: [(level, gid, lid, field, msg)])."""
    plan: dict[tuple[str, str], dict[str, str]] = {}
    issues: list[tuple] = []

    for w in ws_rows:
        gid, lid = w["event_group_id"].strip(), w["event_leg_id"].strip()
        key = (gid, lid)
        if key not in legs_by_id:
            issues.append(("ERROR", gid, lid, "-", "leg が legs.csv に無い"))
            continue
        cell: dict[str, str] = {}
        dtime = w.get("disclosure_time", "")
        tsrc = str(w.get("time_source", "")).strip()

        # --- disclosure_time / time_source / after_close ---
        if not _blank(dtime):
            if tsrc == "inferred":
                issues.append(("ERROR", gid, lid, "time_source",
                               "推定(inferred)は不可。一次で出所を取れないなら空欄のままに"))
            elif tsrc not in TIME_SOURCE_ENUM:
                issues.append(("ERROR", gid, lid, "time_source",
                               f"time_source が enum 外/空欄 ({tsrc!r})。disclosure_time は書かない"))
            else:
                cell["disclosure_time"] = str(dtime).strip()
                derived = _derive_after_close(dtime)
                ac = str(w.get("after_close", "")).strip().upper()
                if _blank(ac):
                    if derived:
                        cell["after_close"] = derived         # 時刻から機械導出(推定ではない)
                elif derived and ac != derived:
                    issues.append(("ERROR", gid, lid, "after_close",
                                   f"after_close={ac} が開示時刻 {dtime} と矛盾(導出={derived})"))
                elif ac in ("TRUE", "FALSE"):
                    cell["after_close"] = ac
        else:
            # disclosure_time 空 → after_close 単体が入っていれば通す(G002 の FALSE 等)
            ac = str(w.get("after_close", "")).strip().upper()
            if ac in ("TRUE", "FALSE"):
                cell["after_close"] = ac

        # --- pricing_date / offer_price_JPY / OA ---
        for fld in ("pricing_date", "offer_price_JPY", "OA_exercised_shares"):
            if not _blank(w.get(fld)):
                cell[fld] = str(w[fld]).strip()

        if not cell:
            continue

        # --- WARN: discount 2〜5% ---
        pricing = cell.get("pricing_date", legs_by_id[key].get("pricing_date", ""))
        offer = _num(cell.get("offer_price_JPY", legs_by_id[key].get("offer_price_JPY", "")))
        code = code_by_gid.get(gid, "")
        if pricing and offer and code in prices:
            close = prices[code].get(pricing)
            if close and close > 0:
                disc = (close - offer) / close
                if not (DISCOUNT_LO <= disc <= DISCOUNT_HI):
                    issues.append(("WARN", gid, lid, "discount",
                                   f"discount={disc*100:.2f}% が {DISCOUNT_LO*100:.0f}〜"
                                   f"{DISCOUNT_HI*100:.0f}% 帯の外(pricing終値={close:.0f}, offer={offer:.0f})"))

        # --- WARN: pricing lag 5〜15営業日(要 trading_calendar。無ければ skip) ---
        if pricing and cal is not None:
            leg = legs_by_id[key]
            announce = leg.get("announce_datetime", "")
            ac_for_day0 = cell.get("after_close", leg.get("after_close", ""))
            day0 = compute_day0(announce, ac_for_day0, cal, cfg) if announce else None
            lag = _biz_lag(day0, pricing, cal) if day0 else None
            if lag is not None and not (LAG_LO <= lag <= LAG_HI):
                issues.append(("WARN", gid, lid, "pricing_lag",
                               f"pricing_date が announce day0({day0}) の {lag} 営業日後。"
                               f"{LAG_LO}〜{LAG_HI} 帯の外"))

        plan[key] = cell

    # ERROR のあったフィールドは plan から除外(そのセルは書かない)
    err_cells = {(g, l, fld) for (lvl, g, l, fld, _m) in issues if lvl == "ERROR"}
    for (g, l, fld) in err_cells:
        plan.get((g, l), {}).pop(fld, None)
    return plan, issues


def apply_to_legs(legs_path: Path, legs_rows: list[dict], plan: dict) -> int:
    """plan の非空セルを legs_rows に上書きして書き戻す。返り値=更新セル数。"""
    fieldnames = list(legs_rows[0].keys())
    idx = {(r["event_group_id"], r["event_leg_id"]): r for r in legs_rows}
    n = 0
    for key, cell in plan.items():
        row = idx.get(key)
        if row is None:
            continue
        for fld, val in cell.items():
            if fld in row and str(row.get(fld, "")).strip() != val:
                row[fld] = val
                n += 1
            elif fld in row and _blank(row.get(fld)):
                row[fld] = val
                n += 1
    with legs_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(legs_rows)
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "car.yaml")
    ap.add_argument("--check", action="store_true", help="検証のみ(legs.csv は触らない)")
    ap.add_argument("--apply", action="store_true", help="ERROR 以外を legs.csv に反映")
    args = ap.parse_args(argv)
    if not args.check and not args.apply:
        args.check = True  # 既定は安全側(検証のみ)

    root = args.root
    tape = root / "data" / "parsed" / "tape"
    prices_dir = root / "data" / "raw" / "prices"
    ws_path = root / "transcription" / "disclosure_transcription.csv"
    legs_path = tape / "legs.csv"
    for p in (ws_path, legs_path, tape / "groups.csv"):
        if not p.exists():
            print(f"missing: {p}", file=sys.stderr)
            return 2

    cfg = Config.from_yaml(args.config)
    cal_path = prices_dir / "trading_calendar.jsonl"
    cal = BusinessCalendar(load_trading_calendar(cal_path)) if cal_path.exists() else None
    if cal is None:
        print("warn: trading_calendar 無し → pricing lag の検証は skip", file=sys.stderr)

    ws_rows = _read_csv(ws_path)
    legs_rows = _read_csv(legs_path)
    legs_by_id = {(r["event_group_id"], r["event_leg_id"]): r for r in legs_rows}
    groups = _read_csv(tape / "groups.csv")
    code_by_gid = {g["event_group_id"]: g.get("issuer_code", "").strip() for g in groups}

    # pricing 終値ルックアップ(discount 検証用)。bars が無ければ空。
    prices: dict[str, dict[str, float]] = {}
    for code in sorted({c for c in code_by_gid.values() if c}):
        p = prices_dir / "daily_quotes" / f"{code}.jsonl"
        if p.exists():
            df = load_daily_quotes(p)
            prices[code] = dict(zip(df["Date"].tolist(), df["Close"].tolist()))

    # cal is None のときは pricing lag の WARN だけ skip(disclosure/discount 検証は動く)。
    plan, issues = plan_and_validate(ws_rows, legs_by_id, code_by_gid, cal, cfg, prices)

    errors = [i for i in issues if i[0] == "ERROR"]
    warns = [i for i in issues if i[0] == "WARN"]
    for lvl, gid, lid, fld, msg in issues:
        mark = "❌" if lvl == "ERROR" else "⚠️"
        print(f"{mark} {lvl} {gid}/{lid} [{fld}] {msg}")

    n_cells = sum(len(c) for c in plan.values())
    print(f"\nplan: {len(plan)} legs / {n_cells} cells to write  "
          f"(ERROR={len(errors)}, WARN={len(warns)})")

    if args.apply:
        if errors:
            print("ERROR があるため、該当セルは除外して残りのみ反映します。")
        written = apply_to_legs(legs_path, legs_rows, plan)
        print(f"applied: {written} cells → {legs_path.relative_to(root)}")
        print("次: car_engine.py / shortfall_engine.py を再計算。")
    else:
        print("(--check モード: legs.csv は未変更。--apply で反映)")
    return 1 if errors and args.apply else 0


if __name__ == "__main__":
    sys.exit(main())
