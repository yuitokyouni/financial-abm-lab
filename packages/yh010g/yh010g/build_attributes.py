"""発行体属性CSVの構築 (Task 6 driver)。ローカル実行 (EDINET_API_KEY 必須)。

    uv run python -m yh010g.build_attributes \
        --targets docs/yh010g_validation_targets.csv \
        --manual  docs/yh010g_manual_attributes.csv \
        --out     data/processed/yh010g/attributes.csv

targets CSV 列: sec_code, fiscal_year_end (YYYY-MM-DD), 有報提出日候補 (submit_dates は
';' 区切り、任意)。EDINET から ROE・政策保有・純資産を取得し attr 辞書に写像。
manual CSV (任意, attributes.load_attributes_csv 形式) は候補者/議案レベルのフラグ
(is_top_management 等、EDINET では取得不能なもの) をマージする — EDINET 値が優先。

出力 CSV は agora attributes と同形式 (key 列 + 属性列)。key は sec_code。
結果をコミットすれば、キーのない環境でも validate_policy が回る。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from yh010g.attributes import BOOL_FIELDS, load_attributes_csv
from yh010g.edinet import EdinetClient, extract_attributes


def _submit_date_candidates(fiscal_year_end: str) -> list[str]:
    """有報は決算期末の約3ヶ月後に提出される。fiscal_year_end の +80〜+100 日を候補に。"""
    from datetime import date, timedelta
    y, m, d = (int(x) for x in fiscal_year_end.split("-"))
    base = date(y, m, d)
    return [(base + timedelta(days=off)).isoformat() for off in range(80, 101)]


def build(targets_path: str, out_path: str, manual_path: str | None = None) -> dict:
    client = EdinetClient()
    manual = load_attributes_csv(manual_path) if manual_path else {}
    rows_out: dict[str, dict] = {}
    stats = {"targets": 0, "edinet_ok": 0, "edinet_miss": 0, "unmatched": {}}

    with open(targets_path, encoding="utf-8-sig", newline="") as f:
        for t in csv.DictReader(f):
            sec = (t.get("sec_code") or "").strip()
            if not sec:
                continue
            stats["targets"] += 1
            dates = ([d.strip() for d in (t.get("submit_dates") or "").split(";") if d.strip()]
                     or _submit_date_candidates(t["fiscal_year_end"]))
            doc = client.find_yuho(sec, dates)
            attrs: dict = {}
            if doc:
                ext = extract_attributes(client.download_csv_rows(doc["docID"]), sec)
                attrs = ext.to_attr_dict()
                if ext.unmatched:
                    stats["unmatched"][sec] = ext.unmatched
                stats["edinet_ok"] += 1 if attrs else 0
                stats["edinet_miss"] += 0 if attrs else 1
            else:
                stats["edinet_miss"] += 1
            # manual を下地に EDINET を上書き (EDINET 優先)
            rows_out[sec] = {**manual.get(sec, {}), **attrs}

    _write_attributes_csv(out_path, rows_out)
    print(f"targets={stats['targets']} edinet_ok={stats['edinet_ok']} "
          f"miss={stats['edinet_miss']} -> {out_path}")
    if stats["unmatched"]:
        print("unmatched elements (要素ID要検証):", stats["unmatched"])
    return stats


def _write_attributes_csv(path: str, rows: dict[str, dict]) -> None:
    fields: list[str] = []
    for attrs in rows.values():
        for k in attrs:
            if k not in fields:
                fields.append(k)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", *fields])
        for key, attrs in rows.items():
            row = [key]
            for fld in fields:
                v = attrs.get(fld, "")
                if isinstance(v, bool):
                    v = "true" if v else "false"
                row.append(v)
            w.writerow(row)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manual", default=None)
    args = ap.parse_args()
    try:
        build(args.targets, args.out, args.manual)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
