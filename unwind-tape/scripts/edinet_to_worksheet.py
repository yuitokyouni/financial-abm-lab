#!/usr/bin/env python3
"""unwind-tape / Task D step 3 — tier2(株式売出) を offering 単位にまとめ、転記の下書きを作る。

step2 の tier2_candidates.csv は「1 offering が 030届出+040/190値決め で複数行」になっている。
これを**発行体×日付近接でまとめ**、各 offering について EDINET 値決め書類の本文(キャッシュ済)から
  - 発表日(announce)  = 本文の『提出日、表紙』(FilingDateCoverPage。訂正なら元=発表の提出日)
  - 条件決定日(pricing) = 値決め書類(040/190/100)の submit_date
  - 売出株数 / 発行価格  = 本文から暫定抽出(**確定は転記シートで人が一次確認**)
を引いて、offering 1行の下書き CSV(include 列つき)を出す。

人は draft を見て:
  1. `include` を Y にする(政策保有と確認できた offering だけ。TDnet で主要株主異動/政策保有を確認)
  2. 暫定値(売出株数/発行価格)と発表時刻(EDINETに無い→TDnet)を一次で確定
→ 採用行を groups.csv / legs.csv / 転記シートに流す(step4=merge、承認後)。

数値は暫定。**創作しない**(取れなければ空欄)。政策保有か否かは EDINET本文で決まらない(設計通り人が確認)。
依存: edinet_classify(本文パース)+ stdlib。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edinet_classify import parse_edinet_csv_zip, _norm_num  # noqa: E402

PRICING_DOCTYPES = {"040", "190", "100"}   # 値決めの書類(訂正届出/訂正臨時報告/発行登録追補)

DRAFT_COLUMNS = [
    "include", "tier", "issuer_code", "issuer_name", "sale_route",
    "announce_date", "pricing_date", "sold_shares_est", "offer_price_est",
    "n_docs", "doctypes", "edinet_pricing_docid", "edinet_all_docids", "note",
]


# ---------------------------------------------------------------------------
# 純関数(クラスタリング / 本文抽出。単体テスト対象)
# ---------------------------------------------------------------------------

def _offering_key(row: dict) -> str:
    """発行体キー。secCode 由来の 4桁があればそれ、無ければ発行体名。"""
    return (row.get("issuer_code") or "").strip() or (row.get("issuer_name") or "").strip()


def cluster_offerings(rows: list[dict], gap_days: int) -> list[list[dict]]:
    """発行体ごとに submit_date 昇順で並べ、gap_days を超える空きで別 offering に分割。"""
    from collections import defaultdict
    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_key[_offering_key(r)].append(r)
    clusters: list[list[dict]] = []
    for _, rs in by_key.items():
        rs = sorted(rs, key=lambda x: x.get("submit_date", ""))
        cur: list[dict] = []
        prev: date | None = None
        for r in rs:
            d = _parse_date(r.get("submit_date", ""))
            if cur and prev is not None and d is not None and (d - prev).days > gap_days:
                clusters.append(cur)
                cur = []
            cur.append(r)
            if d is not None:
                prev = d
        if cur:
            clusters.append(cur)
    return clusters


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _find_all_after(text: str, labels: list[str], pattern: str, window: int = 40) -> list[str]:
    """text 中の各 label 出現直後 window 文字から pattern を全て拾って数値化して返す。"""
    out: list[str] = []
    for lb in labels:
        idx = text.find(lb)
        while idx >= 0:
            m = re.search(pattern, text[idx + len(lb): idx + len(lb) + window])
            if m:
                v = _norm_num(m.group(1))
                if v:
                    out.append(v)
            idx = text.find(lb, idx + 1)
    return out


def extract_body_fields(rows: list[dict], min_offer_price: float) -> dict:
    """パース済み本文行から announce_date / sold_shares / offer_price を暫定抽出。"""
    announce = ""
    for r in rows:
        if r.get("element", "").endswith("FilingDateCoverPage"):
            v = (r.get("value", "") or "").strip()
            if re.match(r"\d{4}-\d{2}-\d{2}", v):
                announce = v[:10]
                break
    fulltext = " ".join((r.get("value", "") or "") for r in rows)
    shares_cands = _find_all_after(fulltext, ["売出数", "売出しをする株式の数", "売出株式数"], r"([\d,]+)\s*株")
    shares = str(max((int(s) for s in shares_cands), default="")) if shares_cands else ""
    price_cands = [float(p) for p in _find_all_after(fulltext, ["売出価格"], r"([\d,]+(?:\.\d+)?)\s*円")]
    price_cands = [p for p in price_cands if p >= min_offer_price]
    price = ("%g" % max(price_cands)) if price_cands else ""
    return {"announce_date": announce, "sold_shares_est": shares, "offer_price_est": price}


def build_draft_row(cluster: list[dict], body: dict) -> dict:
    """1 offering クラスタ + 値決め本文抽出 → draft 行。"""
    cluster = sorted(cluster, key=lambda x: x.get("submit_date", ""))
    first = cluster[0]
    doctypes = [c.get("docTypeCode", "") for c in cluster]
    pricing = next((c for c in reversed(cluster) if c.get("docTypeCode") in PRICING_DOCTYPES), cluster[-1])
    tier = "A_explicit" if any(c.get("confidence_policy_holding") == "A_explicit" for c in cluster) else "B_inference"
    # sold_shares: 本文抽出 > step2 の各行 uridashi_shares の最大
    step2_shares = [int(c["uridashi_shares"]) for c in cluster if (c.get("uridashi_shares") or "").isdigit()]
    sold = body.get("sold_shares_est") or (str(max(step2_shares)) if step2_shares else "")
    announce = body.get("announce_date", "")
    pricing_date = pricing.get("submit_date", "")
    note = []
    if not announce:
        note.append("発表日=本文に無し(TDnet/親180で確認)")
    if announce and announce == pricing_date:
        note.append("発表=条件決定日(発行登録追補等、実発表はTDnetで前)")
    return {
        "include": "",
        "tier": tier,
        "issuer_code": first.get("issuer_code", ""),
        "issuer_name": first.get("issuer_name", ""),
        "sale_route": "secondary_offering",
        "announce_date": announce,
        "pricing_date": pricing_date,
        "sold_shares_est": sold,
        "offer_price_est": body.get("offer_price_est", ""),
        "n_docs": len(cluster),
        "doctypes": "/".join(sorted(set(doctypes))),
        "edinet_pricing_docid": pricing.get("docID", ""),
        "edinet_all_docids": " ".join(c.get("docID", "") for c in cluster),
        "note": "; ".join(note),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="tier2 → offering 下書き (Task D step 3)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "edinet.yaml")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    ccfg = cfg["classify"]
    s3 = cfg["step3"]
    tier2_path = args.root / ccfg["output"]["tier2_csv"]
    docs_dir = args.root / ccfg["output"]["raw_docs_dir"]
    out_path = args.root / s3["output"]["draft_csv"]
    if not tier2_path.exists():
        print(f"{tier2_path} が無い。先に edinet_classify.py を回す。", file=sys.stderr)
        return 2

    with tier2_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    clusters = cluster_offerings(rows, int(s3.get("cluster_gap_days", 45)))
    min_price = float(s3.get("min_offer_price_yen", 50))

    drafts = []
    for cl in clusters:
        cl_sorted = sorted(cl, key=lambda x: x.get("submit_date", ""))
        pricing = next((c for c in reversed(cl_sorted) if c.get("docTypeCode") in PRICING_DOCTYPES), cl_sorted[-1])
        body = {}
        zpath = docs_dir / f"{pricing.get('docID','')}.zip"
        if zpath.exists():
            body = extract_body_fields(parse_edinet_csv_zip(zpath.read_bytes()), min_price)
        drafts.append(build_draft_row(cl, body))

    drafts.sort(key=lambda d: (-(int(d["sold_shares_est"]) if d["sold_shares_est"].isdigit() else 0),
                               d["pricing_date"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DRAFT_COLUMNS)
        w.writeheader()
        w.writerows(drafts)
    with_shares = sum(1 for d in drafts if d["sold_shares_est"])
    with_announce = sum(1 for d in drafts if d["announce_date"])
    print(f"step3: {len(rows)} tier2行 → {len(drafts)} offering。売出株数取得 {with_shares}, "
          f"発表日取得 {with_announce}。 → {s3['output']['draft_csv']}")
    print("次: draft の include を Y にし(政策保有と確認できたもの)、暫定値を一次確認 → groups/legs へ merge。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
