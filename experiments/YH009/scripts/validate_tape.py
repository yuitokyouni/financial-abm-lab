#!/usr/bin/env python3
"""unwind-tape / task B step 2 — CSV validator.

チェック項目:
  1. enum: 各 enum 列の値が lists.yaml に存在するか (未知値は WARN、空欄は OK)
  2. bool 列: TRUE / FALSE / 空欄のみ (unknown 表記は許可されるフィールドを別扱い)
  3. FK 整合: legs.event_group_id が groups.event_group_id に存在するか
  4. 日付順序 (Tier1_confirmed のみ): announce_datetime ≤ pricing_date ≤ settlement_date
     leg 単位で pairwise、両方存在するときだけ検証。
  5. quantity_basis / value_basis 整合:
     - resolution_max: sold_shares × previous_close_JPY <= sold_value_JPY (許容)
     - 数字が揃わないケースは skip (WARN 出さない — v0.3 は price 未取得のため)
  6. ハードコード数値セルは source_id 必須:
     sold_shares, sold_value_JPY, buyback_size_shares, buyback_value_JPY,
     initial_offer_shares, final_offer_shares, OA_exercised_shares, offer_price_JPY,
     previous_close_JPY のいずれかが埋まっている leg は source_id_primary が
     非空か、または notes に "S<数字>" 参照を含むこと。
  7. Tier2_candidate 行の数値空欄は WARN 抑止 (validator は数値空欄を許可)

出力: data/parsed/tape/validate_report.md
exit: 0 = clean, 3 = WARN only, 4 = ERROR あり
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# columns needing enum check (field -> lists.yaml key)
# ---------------------------------------------------------------------------

ENUM_FIELDS = {
    "status": "status",
    "event_tier": "event_tier",
    "event_role": "event_role",
    "sale_route": "sale_route",
    "offering_type": "offering_type",
    "absorption_route": "absorption_route",
    "seller_type": "seller_type",
    "quantity_basis": "quantity_basis",
    "value_basis": "value_basis",
    "ABM_candidate_flag": "ABM_candidate_flag",
    "confidence_policy_holding": "confidence_policy_holding",
    "activist_pressure": "activist_pressure",
}

BOOL_FIELDS = {
    "support_buyback", "support_OA", "support_lockup", "support_stabilization",
    "after_close", "buyback_cancellation",
}

# hardcoded numeric fields that mandate a source_id
NUMERIC_NEEDS_SOURCE = [
    "initial_offer_shares", "final_offer_shares", "OA_shares_max", "OA_exercised_shares",
    "sold_shares", "sold_value_JPY",
    "buyback_size_shares", "buyback_value_JPY",
    "offer_price_JPY", "previous_close_JPY",
]

TIER1 = "Tier1_confirmed"


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
        return list(r.fieldnames or []), rows


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_enum(rows: list[dict[str, str]], lists: dict[str, list[str]],
               kind: str) -> tuple[list[str], list[str]]:
    """kind = 'group' or 'leg' — used for the log context."""
    errors: list[str] = []
    warnings: list[str] = []
    for r in rows:
        gid = r.get("event_group_id", "?")
        lid = r.get("event_leg_id", "-")
        for field, list_key in ENUM_FIELDS.items():
            v = r.get(field, "").strip()
            if not v:
                continue
            allowed = lists.get(list_key, [])
            if not allowed:
                warnings.append(f"lists.yaml missing key '{list_key}' — skipping enum check for {field}")
                continue
            if v not in allowed:
                warnings.append(f"{kind} {gid}/{lid}: {field}={v!r} not in Lists.{list_key} (allowed: {allowed})")
    return errors, warnings


def check_bool(rows: list[dict[str, str]], kind: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    allowed_true_false = {"TRUE", "FALSE", ""}
    for r in rows:
        gid = r.get("event_group_id", "?")
        lid = r.get("event_leg_id", "-")
        for field in BOOL_FIELDS:
            v = r.get(field, "").strip()
            if v not in allowed_true_false:
                warnings.append(f"{kind} {gid}/{lid}: {field}={v!r} not in {{TRUE, FALSE, empty}}")
    return errors, warnings


def check_fk_group(legs: list[dict[str, str]], groups: list[dict[str, str]]
                  ) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    gids = {g["event_group_id"] for g in groups}
    for l in legs:
        if l["event_group_id"] not in gids:
            errors.append(f"leg {l['event_group_id']}/{l['event_leg_id']}: "
                          f"event_group_id not present in groups.csv")
    return errors, warnings


def _parse_iso(s: str) -> dt.date | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def check_date_order(legs: list[dict[str, str]], groups: list[dict[str, str]]
                    ) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    tier_by_gid = {g["event_group_id"]: g.get("event_tier", "") for g in groups}
    for l in legs:
        gid = l["event_group_id"]
        lid = l["event_leg_id"]
        if tier_by_gid.get(gid, "") != TIER1:
            continue
        a = _parse_iso(l.get("announce_datetime", ""))
        p = _parse_iso(l.get("pricing_date", ""))
        s = _parse_iso(l.get("settlement_date", ""))
        # pairwise: only when both sides exist
        if a and p and a > p:
            errors.append(f"leg {gid}/{lid}: announce_datetime={a} > pricing_date={p}")
        if p and s and p > s:
            errors.append(f"leg {gid}/{lid}: pricing_date={p} > settlement_date={s}")
        if a and s and a > s:
            errors.append(f"leg {gid}/{lid}: announce_datetime={a} > settlement_date={s}")
    return errors, warnings


def _num(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def check_basis_consistency(legs: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """
    quantity_basis / value_basis = resolution_max のとき、
    shares × previous_close_JPY <= sold_value_JPY を検証。
    価格が揃わない場合は skip (WARN 出さない — v0.3 は price 未取得のため)。
    """
    errors: list[str] = []
    warnings: list[str] = []
    for l in legs:
        gid = l["event_group_id"]
        lid = l["event_leg_id"]
        qb = l.get("quantity_basis", "").strip()
        vb = l.get("value_basis", "").strip()
        if qb != "resolution_max" and vb != "resolution_max":
            continue
        shares = _num(l.get("sold_shares", ""))
        px = _num(l.get("previous_close_JPY", ""))
        val = _num(l.get("sold_value_JPY", ""))
        if shares is None or px is None or val is None:
            # cannot check (v0.3 valid —価格未取得)
            continue
        if shares * px > val * 1.01:  # 1% allowance for rounding
            errors.append(
                f"leg {gid}/{lid}: resolution_max but shares × previous_close = "
                f"{shares*px:,.0f} > sold_value_JPY {val:,.0f} (>1% over cap)"
            )
    return errors, warnings


def check_source_required(legs: list[dict[str, str]], groups: list[dict[str, str]]
                         ) -> tuple[list[str], list[str]]:
    """Hardcoded数値セルは source_id 必須。段階的にレポート:
      ERROR: Tier1_confirmed leg with numeric field(s) filled AND NO URL AND NO source_id.
      WARN:  Tier1_confirmed leg with numeric field(s) filled AND URL present but source_id unresolved
             (=> Source_Log に該当 URL を追加する必要がある)。
      SKIP:  Tier2_candidate / Tier3_overhang legs (数値空欄前提)。
    """
    errors: list[str] = []
    warnings: list[str] = []
    tier_by_gid = {g["event_group_id"]: g.get("event_tier", "") for g in groups}
    for l in legs:
        gid = l["event_group_id"]
        lid = l["event_leg_id"]
        if tier_by_gid.get(gid, "") != TIER1:
            continue
        filled = [f for f in NUMERIC_NEEDS_SOURCE if l.get(f, "").strip()]
        if not filled:
            continue
        sid_p = l.get("source_id_primary", "").strip()
        sid_s = l.get("source_id_secondary", "").strip()
        url_p = l.get("source_primary_url", "").strip()
        url_s = l.get("source_secondary_url", "").strip()
        notes = " ".join([l.get("notes", ""), l.get("route_notes", "")])
        has_sid = bool(sid_p or sid_s or re.search(r"\bS\d{3,}\b", notes))
        has_url = bool(url_p or url_s)
        if has_sid:
            continue
        if has_url:
            warnings.append(
                f"leg {gid}/{lid}: numeric filled ({', '.join(filled[:4])}"
                f"{'...' if len(filled) > 4 else ''}) — URL present but no source_id resolved. "
                f"Add to Source_Log: primary_url={url_p or url_s!r}"
            )
        else:
            errors.append(
                f"leg {gid}/{lid}: numeric filled ({', '.join(filled[:4])}"
                f"{'...' if len(filled) > 4 else ''}) but NO source (no URL, no source_id, no S### in notes)"
            )
    return errors, warnings


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "data" / "parsed" / "tape")
    args = ap.parse_args(argv)

    groups_cols, groups = _load_csv(args.tape_dir / "groups.csv")
    legs_cols, legs = _load_csv(args.tape_dir / "legs.csv")
    lists = _load_yaml(args.tape_dir / "lists.yaml")

    all_errors: list[str] = []
    all_warnings: list[str] = []

    for name, fn, argsets in [
        ("enum(groups)",           check_enum, [(groups, lists, "group")]),
        ("enum(legs)",             check_enum, [(legs, lists, "leg")]),
        ("bool(legs)",             check_bool, [(legs, "leg")]),
        ("fk_group",               check_fk_group, [(legs, groups)]),
        ("date_order",             check_date_order, [(legs, groups)]),
        ("basis_consistency",      check_basis_consistency, [(legs,)]),
        ("source_required",        check_source_required, [(legs, groups)]),
    ]:
        for aset in argsets:
            e, w = fn(*aset)
            all_errors.extend((f"[{name}] {msg}" for msg in e))
            all_warnings.extend((f"[{name}] {msg}" for msg in w))

    # write report
    lines: list[str] = []
    lines.append(f"# validate_tape report\n")
    lines.append(f"generated: {dt.datetime.now().isoformat(timespec='seconds')}\n\n")
    lines.append(f"- groups: {len(groups)}\n")
    lines.append(f"- legs: {len(legs)}\n")
    lines.append(f"- errors: {len(all_errors)}\n")
    lines.append(f"- warnings: {len(all_warnings)}\n\n")

    if all_errors:
        lines.append("## errors (must fix)\n")
        for e in all_errors:
            lines.append(f"- {e}\n")
        lines.append("\n")
    if all_warnings:
        lines.append("## warnings\n")
        for w in all_warnings:
            lines.append(f"- {w}\n")
        lines.append("\n")
    if not all_errors and not all_warnings:
        lines.append("clean.\n")

    (args.tape_dir / "validate_report.md").write_text("".join(lines), encoding="utf-8")

    print(f"validate: errors={len(all_errors)} warnings={len(all_warnings)} → {args.tape_dir}/validate_report.md")
    if all_errors:
        return 4
    if all_warnings:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
