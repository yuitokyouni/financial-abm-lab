#!/usr/bin/env python3
"""unwind-tape / Task D step 4 — draft(include=Y) を groups/legs/転記シートに merge。

step3 の tier2_offering_draft.csv で人が include=Y にした offering(=TDnet で政策保有と確認済)を、
canonical な groups.csv / legs.csv / transcription/disclosure_transcription.csv に **Tier2_candidate**
として追加する。数値は EDINET 暫定(創作しない)。発表時刻・確定 offer/pricing/売出株数 は転記で一次確認。

安全策:
  - 既定は **ドライラン**(preview を data/parsed/edinet/merge_preview/ に書くだけ)。--apply で実追記。
  - **重複ガード**: (発行体 × 条件決定日) が既存 legs に在れば skip。既知の Aisin(G003)/Honda(G004)/
    Nintendo(G008) や再実行の二重登録を防ぐ。
  - 新規 group_id は既存最大 +1 から連番(G012…)。event_leg_id は L001。
  - --apply 後は validate_tape.py を回して壊れていないか各自確認(このスクリプトは追記のみ)。

依存: stdlib のみ。他 Task を import しない。
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# EDINET discovery tier → tape の confidence_policy_holding enum(保守的に。人が転記で昇格)
_CONF_MAP = {"A_explicit": "B_strong_inference", "B_inference": "C_possible_only"}


def confidence_from_tier(tier: str) -> str:
    return _CONF_MAP.get(tier, "C_possible_only")


def next_group_number(existing_ids: list[str]) -> int:
    nums = [int(g[1:]) for g in existing_ids if g.startswith("G") and g[1:].isdigit()]
    return max(nums, default=0) + 1


def _key(code: str, name: str, pricing: str) -> tuple[str, str]:
    """重複判定キー(発行体, 条件決定日)。code 優先、無ければ name。"""
    return ((code or "").strip() or (name or "").strip(), (pricing or "").strip())


def existing_offering_keys(groups: list[dict], legs: list[dict]) -> set[tuple[str, str]]:
    code_by_gid = {g["event_group_id"]: (g.get("issuer_code", ""), g.get("issuer_name", "")) for g in groups}
    keys: set[tuple[str, str]] = set()
    for l in legs:
        code, name = code_by_gid.get(l.get("event_group_id", ""), ("", ""))
        keys.add(_key(code, name, l.get("pricing_date", "")))
    return keys


def build_rows(draft: dict, gid: str, groups_cols: list[str], legs_cols: list[str],
               ws_cols: list[str]) -> tuple[dict, dict, dict]:
    """draft 1行 → (group行, leg行, worksheet行)。既知の列だけ埋め、他は空。"""
    code = draft.get("issuer_code", "")
    name = draft.get("issuer_name", "")
    announce = draft.get("announce_date", "")
    pricing = draft.get("pricing_date", "")
    shares = draft.get("sold_shares_est", "")
    price = draft.get("offer_price_est", "")
    docids = draft.get("edinet_all_docids", "")
    conf = confidence_from_tier(draft.get("tier", ""))

    g = {c: "" for c in groups_cols}
    g.update({"event_group_id": gid, "issuer_code": code, "issuer_name": name,
              "event_tier": "Tier2_candidate", "confidence_policy_holding": conf,
              "ABM_candidate_flag": "Maybe"})

    l = {c: "" for c in legs_cols}
    l.update({"event_group_id": gid, "event_leg_id": "L001", "status": "candidate",
              "sale_route": "secondary_offering", "seller_type": "unknown",
              "announce_datetime": announce, "pricing_date": pricing})
    if "sold_shares" in l and shares:
        l["sold_shares"] = shares
        if "quantity_basis" in l:
            l["quantity_basis"] = "announced_total"
    if "offer_price_JPY" in l and price:
        l["offer_price_JPY"] = price
    if "source_primary_url" in l:
        l["source_primary_url"] = ("EDINET:" + docids.split(" ")[0]) if docids else ""
    if "notes" in l:
        l["notes"] = f"Task D discovery(EDINET {docids})。暫定値=要一次確認。announce/pricing=EDINET本文。"

    w = {c: "" for c in ws_cols}
    w.update({"event_group_id": gid, "event_leg_id": "L001", "issuer_code": code,
              "issuer_name": name, "sale_route": "secondary_offering",
              "announce_datetime": announce, "pricing_date": pricing})
    if "offer_price_JPY" in w:
        w["offer_price_JPY"] = price
    if "needs" in w:
        w["needs"] = "offering: disclosure_time/after_close(TDnet) + offer/pricing/売出株数 一次確認"
    if "source_docs_to_obtain" in w:
        w["source_docs_to_obtain"] = f"EDINET {docids}"
    if "note" in w:
        w["note"] = f"Task D自動下書き。EDINET暫定: 売出株数={shares or '—'} / 発行価格={price or '—'}。政策保有はTDnetで確認済(include=Y)。"
    return g, l, w


def _read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
        return list(r.fieldnames or []), rows


def _append(path: Path, cols: list[str], new_rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        for r in new_rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("y", "yes", "true", "1", "✓")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="draft(include=Y) を tape へ merge (Task D step4)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--draft", type=Path, default=None)
    ap.add_argument("--apply", action="store_true", help="canonical CSV に実追記(既定はドライラン)")
    args = ap.parse_args(argv)

    root = args.root
    tape = root / "data" / "parsed" / "tape"
    draft_path = args.draft or (root / "data" / "parsed" / "edinet" / "tier2_offering_draft.csv")
    if not draft_path.exists():
        print(f"{draft_path} が無い。先に edinet_to_worksheet.py。", file=sys.stderr)
        return 2

    _, drafts = _read(draft_path)
    included = [d for d in drafts if _truthy(d.get("include", ""))]
    if not included:
        print("include=Y の行が無い。draft の include 列を Y にしてから再実行。")
        return 0

    g_cols, groups = _read(tape / "groups.csv")
    l_cols, legs = _read(tape / "legs.csv")
    ws_path = root / "transcription" / "disclosure_transcription.csv"
    w_cols, _ = _read(ws_path)

    exist = existing_offering_keys(groups, legs)
    n = next_group_number([g["event_group_id"] for g in groups])
    new_g, new_l, new_w, skipped = [], [], [], []
    for d in sorted(included, key=lambda x: (x.get("pricing_date", ""), x.get("issuer_name", ""))):
        k = _key(d.get("issuer_code", ""), d.get("issuer_name", ""), d.get("pricing_date", ""))
        if k in exist:
            skipped.append(d)
            continue
        gid = f"G{n:03d}"
        n += 1
        g, l, w = build_rows(d, gid, g_cols, l_cols, w_cols)
        new_g.append(g); new_l.append(l); new_w.append(w)
        exist.add(k)

    print(f"include=Y {len(included)} 件 → 追加 {len(new_g)} / 重複skip {len(skipped)}"
          f"（既知 Aisin/Honda/Nintendo 等）")
    for g in new_g:
        print(f"  + {g['event_group_id']} {g['issuer_code'] or '----':>5} {g['issuer_name']} "
              f"[{g['confidence_policy_holding']}]")
    if skipped:
        print("  skip(既存):", ", ".join(f"{d.get('issuer_name','')}({d.get('pricing_date','')})" for d in skipped))

    if not args.apply:
        pv = root / "data" / "parsed" / "edinet" / "merge_preview"
        _write(pv / "groups_add.csv", g_cols, new_g)
        _write(pv / "legs_add.csv", l_cols, new_l)
        _write(pv / "worksheet_add.csv", w_cols, new_w)
        print(f"\n[ドライラン] preview を {pv}/ に出力。問題なければ --apply で追記。")
        return 0

    _append(tape / "groups.csv", g_cols, new_g)
    _append(tape / "legs.csv", l_cols, new_l)
    _append(ws_path, w_cols, new_w)
    print(f"\n[--apply] groups/legs/worksheet に {len(new_g)} 件追記。"
          f"\n次: python3 scripts/validate_tape.py で整合を確認 → 転記で一次確定 → shortfall/residual。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
