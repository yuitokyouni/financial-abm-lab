"""推奨再構成器の精度検証 (Task 2 本検証)。

著名議案の ground truth (docs/yh010g_validation_groundtruth.csv) に対し、規則ベース
再構成 (ISS/GL) の推奨方向が実際の推奨と一致するかを測る。属性は同CSVの手動フラグ +
任意の EDINET 属性CSV (build_attributes の出力、政策保有等) をマージして供給する。

    # ここ (キーなし): 手動フラグのみ — 機械的規則は検証、EDINET依存行は「属性不足」
    uv run python -m yh010g.validate_policy
    # ローカル (EDINETキーあり): 財務属性を充填して財務系規則も end-to-end 検証
    uv run python -m yh010g.validate_policy --edinet data/processed/yh010g/attributes.csv

mechanism 列で行を分類し正答率を層別報告する:
  mechanical  — 属性で機械判定 (女性ゼロ・買収防衛策)。ここでも検証可
  financial   — EDINET財務が必要 (政策保有20%)。--edinet で検証可
  judgmental  — 不祥事責任・総合的独立性等。ルール化不能 (既知の範囲外)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from yh010g.attributes import BOOL_FIELDS, NUMERIC_FIELDS
from yh010g.policy import reconstruct_recommendations
from yh010g.schema import UnifiedRecord

GROUND_TRUTH = Path("docs/yh010g_validation_groundtruth.csv")
LABEL_COLS = {"key", "sec_code", "category", "proposer", "mechanism",
              "iss_expected", "gl_expected", "note"}


def _direction(rec_str: str) -> str | None:
    if rec_str.startswith("for"):
        return "for"
    if rec_str.startswith("against"):
        return "against"
    return None


def _parse_key(key: str) -> tuple[str, str, int, int]:
    sec, date, pno, sub = key.split("|")
    return sec, date, int(pno), int(sub)


def load_ground_truth(path: Path) -> tuple[list[UnifiedRecord], dict, list[dict]]:
    records, attrs, labels = [], {}, []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = row["key"].strip()
            sec, date, pno, sub = _parse_key(key)
            records.append(UnifiedRecord(
                manager="gt", sec_code=sec, company_name="", meeting_date=date,
                meeting_type="定時総会", proposal_no=pno, sub_no=sub,
                proposer=row["proposer"], category=row["category"],
                vote=1.0, vote_raw="", reason=""))
            a: dict = {}
            for col, val in row.items():
                if col in LABEL_COLS or val is None or str(val).strip() == "":
                    continue
                s = str(val).strip()
                if col in BOOL_FIELDS:
                    a[col] = s.lower() in ("1", "true", "yes")
                elif col in NUMERIC_FIELDS:
                    a[col] = float(s)
                else:
                    a[col] = s
            attrs[key] = a
            labels.append({"key": key, "mechanism": row["mechanism"],
                           "iss_expected": row["iss_expected"].strip(),
                           "gl_expected": row["gl_expected"].strip(),
                           "note": row.get("note", "")})
    return records, attrs, labels


def _merge_edinet(attrs: dict, edinet_path: str | None) -> dict:
    if not edinet_path:
        return attrs
    from yh010g.attributes import load_attributes_csv
    edinet = load_attributes_csv(edinet_path)  # keyed by sec_code
    merged = {k: dict(v) for k, v in attrs.items()}
    for key, a in merged.items():
        sec = key.split("|")[0]
        if sec in edinet:
            a.update(edinet[sec])  # EDINET財務を上書き
    return merged


def main(edinet_path: str | None = None) -> dict:
    records, attrs, labels = load_ground_truth(GROUND_TRUTH)
    attrs = _merge_edinet(attrs, edinet_path)
    iss = reconstruct_recommendations(records, 2025, attributes=attrs, policy="iss")
    gl = reconstruct_recommendations(records, 2025, attributes=attrs, policy="gl")

    per_row, by_mech = [], defaultdict(lambda: {"iss_hit": 0, "iss_n": 0, "gl_hit": 0, "gl_n": 0})
    for lab in labels:
        k = lab["key"]
        res = {"key": k, "mechanism": lab["mechanism"], "note": lab["note"]}
        for who, recs in (("iss", iss), ("gl", gl)):
            exp = lab[f"{who}_expected"]
            if not exp:
                res[who] = None
                continue
            got = _direction(recs[k].recommendation)
            hit = got == exp
            res[who] = {"expected": exp, "got": got,
                        "rec": recs[k].recommendation, "hit": hit}
            by_mech[lab["mechanism"]][f"{who}_n"] += 1
            by_mech[lab["mechanism"]][f"{who}_hit"] += int(hit)
        per_row.append(res)

    def acc(d, who):
        n = d[f"{who}_n"]
        return round(d[f"{who}_hit"] / n, 3) if n else None
    summary = {m: {"iss_acc": acc(d, "iss"), "iss_n": d["iss_n"],
                   "gl_acc": acc(d, "gl"), "gl_n": d["gl_n"]}
               for m, d in by_mech.items()}
    report = {"edinet_attributes": bool(edinet_path), "by_mechanism": summary,
              "per_row": per_row}

    print(f"=== 推奨再構成 精度検証 (EDINET属性={'あり' if edinet_path else 'なし(手動フラグのみ)'}) ===")
    for m, s in summary.items():
        print(f"[{m:10}] ISS {s['iss_acc']} (n={s['iss_n']})  GL {s['gl_acc']} (n={s['gl_n']})")
    for r in per_row:
        for who in ("iss", "gl"):
            v = r[who]
            if v and not v["hit"]:
                print(f"  MISS {r['key']} [{r['mechanism']}] {who}: "
                      f"expected {v['expected']} got {v['got']} ({v['rec']}) — {r['note']}")
    Path("data/processed/yh010g").mkdir(parents=True, exist_ok=True)
    with open("data/processed/yh010g/validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--edinet", default=None, help="build_attributes 出力CSV (財務属性)")
    args = ap.parse_args()
    main(args.edinet)
