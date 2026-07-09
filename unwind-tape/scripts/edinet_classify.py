#!/usr/bin/env python3
"""unwind-tape / Task D step 2 — EDINET 書類本文の分類(株式の売出し × 政策保有)。

step1 の candidates.csv(値決め書類 030/040/100/190、非IPO)を入力に、各書類の本文
(EDINET の CSV=type5、無ければ XBRL)を DL して、次を判定する:
  (i)  売出し(secondary)か  … 売出人/売出株式数 の有無
  (ii) 株式か(社債のみ除外) … 株券/株式 の有無
  (iii)売出人が銀行/保険/信託/事業会社か … ファンド/個人は非政策保有
  (iv) 本文に政策保有/縮減/純投資目的以外 等があるか
→ confidence_policy_holding を A_explicit / B_inference / none で付与。
**数値(売出株数・発行価格)は本文からの転記のみ**。ここは lead を出すだけで、確定は人の一次確認。

規律(Task A/C/D-step1 と統一): API キーは env、data/raw は gitignore、retry=指数バックオフ、
冪等(取得済み docID は再取得しない)、sha256 manifest、構造変化(空/未知形式)は fail-loud。

まず本文の構造を実データで確認する:
  python3 scripts/edinet_classify.py --dump S100XXXXXX     # 1件 DL して項目名/値をダンプ
その後、全件分類:
  python3 scripts/edinet_classify.py                        # candidates.csv 非IPO を全件分類

出力(configs/edinet.yaml の classify.output):
  data/raw/edinet/docs/{docID}.zip           取得本文(gitignore)
  data/parsed/edinet/classify_detail.csv     全候補の分類結果
  data/parsed/edinet/tier2_candidates.csv    政策保有×株式売出(確定 lead → 転記シートへ)
  data/parsed/edinet/classify_report.md
依存: requests, PyYAML + stdlib(zipfile)。他 Task を import しない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

JST = ZoneInfo("Asia/Tokyo")

CLASSIFY_COLUMNS = [
    "docID", "submit_date", "docTypeCode", "issuer_code", "issuer_name",
    "is_equity_uridashi", "is_bond", "sellers", "seller_types",
    "policy_explicit", "confidence_policy_holding",
    "uridashi_shares", "offer_price_JPY", "note",
]


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# EDINET CSV(zip)パース
# ---------------------------------------------------------------------------

def parse_edinet_csv_zip(zip_bytes: bytes) -> list[dict]:
    """EDINET の type=5 zip を (要素ID, 項目名, 値) の行リストに落とす。
    CSV は UTF-16 の TSV(タブ区切り)。ヘッダ: 要素ID 項目名 … 値。
    構造が読めない場合は空リスト(呼び出し側で fail-loud/記録)。"""
    rows: list[dict] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return rows
    for name in zf.namelist():
        if not name.lower().endswith(".csv"):
            continue
        raw = zf.read(name)
        text = None
        for enc in ("utf-16", "utf-16-le", "utf-8-sig", "cp932"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            continue
        lines = text.splitlines()
        if not lines:
            continue
        header = lines[0].split("\t")
        # 値カラムの index(通常末尾「値」)。無ければ最終列。
        try:
            vi = header.index("値")
        except ValueError:
            vi = len(header) - 1
        for ln in lines[1:]:
            cols = ln.split("\t")
            if len(cols) <= vi:
                continue
            rows.append({
                "element": cols[0].strip() if cols else "",
                "item": cols[1].strip() if len(cols) > 1 else "",
                "value": cols[vi].strip(),
                "source_csv": name.split("/")[-1],
            })
    return rows


# ---------------------------------------------------------------------------
# 純関数(分類ロジック。ネットワーク不要 = 単体テスト対象)
# ---------------------------------------------------------------------------

def classify_seller_type(name: str, rules: dict[str, list[str]]) -> str:
    """売出人名から属性を返す。bank/insurance/trust/securities/fund/business/other。"""
    n = name or ""
    for typ in ("bank", "insurance", "trust", "securities", "fund"):
        for kw in rules.get(typ, []):
            if kw in n:
                return typ
    if any(k in n for k in ("株式会社", "有限会社", "合同会社", "株式會社")):
        return "business"          # 事業会社(銀行/保険/ファンドでない法人)= 政策保有の売り手候補
    if any(k in n for k in ("組合", "基金", "機構")):
        return "fund"
    return "other"                 # 個人等


def _norm_num(s: str) -> str:
    """全角/カンマ/単位を除いた数値文字列。数値化できなければ ''。"""
    if not s:
        return ""
    s = s.translate(str.maketrans("０１２３４５６７８９，．", "0123456789,."))
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", s)
    return m.group(0).replace(",", "") if m else ""


def _extract_after(text: str, labels: list[str], pattern: str, window: int = 60) -> str:
    """text 中の label 出現直後 window 文字から pattern を拾って数値化。EDINET は値が
    テキストブロックの自由文に埋まる(例『(2)売出数 7,788,400株』)ため、項目名でなく本文を見る。"""
    for lb in labels:
        idx = text.find(lb)
        while idx >= 0:
            m = re.search(pattern, text[idx + len(lb): idx + len(lb) + window])
            if m:
                return _norm_num(m.group(1))
            idx = text.find(lb, idx + 1)
    return ""


def _extract_sellers(rows: list[dict], rules: dict) -> list[str]:
    """売出人(売り手)を抽出。EDINET本文には無いことが多い(seller は TDnet 側)→ best effort。"""
    sellers: list[str] = []
    for r in rows:
        it = r.get("item", "") or ""
        v = (r.get("value", "") or "").strip()
        if not v or v in ("―", "-", "－", "該当事項はありません。"):
            continue
        if "売出人" in it and ("氏名" in it or "名称" in it):
            if v not in sellers:
                sellers.append(v)
    return sellers


def classify_doc(rows: list[dict], cfg: dict) -> dict:
    """本文行から分類結果 dict を返す。純関数。
    EDINET本文で確実に判るのは『株式の売出しか(社債・募集でない)＋発行体＋おおよその株数』まで。
    政策保有か否かは本文にほぼ無い(TDnet側)→ 株式売出は tier2 に載せ、政策保有は人が一次確認。"""
    policy_kw = cfg.get("policy_keywords", [])
    eq_phrases = cfg.get("uridashi_equity_phrases", ["株式の売出", "普通株式の売出", "株券の売出"])
    na_markers = cfg.get("uridashi_na_markers", ["該当事項はありません", "該当なし"])
    bond_markers = cfg.get("bond_markers", ["社債券", "無担保社債"])
    rules = cfg.get("seller_type_rules", {})

    fulltext = " ".join((r.get("value", "") or "") for r in rows)

    def item_val(substr: str) -> str:
        for r in rows:
            if substr in (r.get("item", "") or ""):
                return r.get("value", "") or ""
        return ""

    sec_type = item_val("有価証券の種類")
    youkou = item_val("売出要項")
    youkou_na = any(m in youkou for m in na_markers) if youkou else False

    # 株式の売出し判定: 「株式の売出」表現があり、売出要項が『該当なし』でない
    has_eq_uridashi_phrase = any(p in fulltext for p in eq_phrases)
    is_equity_uridashi = has_eq_uridashi_phrase and not youkou_na
    # 社債判定(有価証券の種類=社債、または社債固有語)。株式売出が立っていれば社債扱いしない
    is_bond = (("社債" in sec_type) or any(b in fulltext for b in bond_markers)) and not is_equity_uridashi

    sellers = _extract_sellers(rows, rules)
    seller_types = sorted({classify_seller_type(s, rules) for s in sellers}) if sellers else []
    policy_explicit = any(k in fulltext for k in policy_kw)

    # 数値の暫定抽出(自由文から。確定は転記シートで一次確認)
    shares = _extract_after(fulltext, ["売出数", "売出しをする株式の数", "売出株式数"], r"([\d,]+)\s*株")
    price = _extract_after(fulltext, ["売出価格"], r"([\d,]+(?:\.\d+)?)")

    if not is_equity_uridashi:
        tier = "none"
    elif policy_explicit:
        tier = "A_explicit"
    else:
        tier = "B_inference"        # 株式売出だが政策保有明示なし → 人が TDnet で確認

    return {
        "is_equity_uridashi": "TRUE" if is_equity_uridashi else "FALSE",
        "is_bond": "TRUE" if is_bond else "FALSE",
        "sellers": " / ".join(sellers),
        "seller_types": ",".join(seller_types),
        "policy_explicit": "TRUE" if policy_explicit else "FALSE",
        "confidence_policy_holding": tier,
        "uridashi_shares": shares,
        "offer_price_JPY": price,
        "note": "",
    }


def is_tier2(result: dict) -> bool:
    """転記シートに流す lead か: 株式の売出し(政策保有は人が確認するので A/B 両方載せる)。"""
    return (result.get("is_equity_uridashi") == "TRUE"
            and result.get("confidence_policy_holding") in ("A_explicit", "B_inference"))


# ---------------------------------------------------------------------------
# ネットワーク(Mac 実行)
# ---------------------------------------------------------------------------

class DocClient:
    def __init__(self, base_url, api_key, *, retries, backoff_base, backoff_factor,
                 sleep_sec, log):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.retries = retries
        self.bo_base = backoff_base
        self.bo_factor = backoff_factor
        self.sleep = sleep_sec
        self.log = log
        self.session = requests.Session()

    def fetch_doc(self, docid: str, doc_type: str) -> bytes | None:
        """/documents/{docID}?type=.. の生バイト。404 は None(本文形式が無い)。"""
        url = f"{self.base}/documents/{docid}"
        params = {"type": doc_type, "Subscription-Key": self.key}
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.sleep)
                r = self.session.get(url, params=params, timeout=60)
                if r.status_code == 429:
                    raise RuntimeError("HTTP 429 rate limited")
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.content
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                non_retryable = status is not None and 400 <= status < 500 and status != 429
                if non_retryable or attempt >= self.retries:
                    raise
                wait = self.bo_base * (self.bo_factor ** attempt)
                self.log.warning("GET doc %s failed (%s); retry %d/%d in %.1fs",
                                 docid, e, attempt + 1, self.retries, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")


def _load_done(manifest: Path) -> set[str]:
    done: set[str] = set()
    if not manifest.exists():
        return done
    for line in manifest.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("docID") and e.get("status") in ("ok", "no_body"):
            done.add(e["docID"])
    return done


def _append(manifest: Path, entry: dict) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="EDINET 本文分類 (Task D step 2)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "edinet.yaml")
    ap.add_argument("--dump", type=str, help="この docID を1件 DL して項目/値をダンプ(構造確認)")
    ap.add_argument("--limit", type=int, default=0, help="先頭 N 件だけ処理(試験用)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("edinet-classify")

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    key = os.environ.get(cfg["api_key_env"], "").strip()
    if not key:
        log.error("env %s が未設定。", cfg["api_key_env"])
        return 2
    ccfg = cfg["classify"]
    client = DocClient(cfg["base_url"], key, retries=int(cfg.get("retries", 4)),
                       backoff_base=float(cfg.get("backoff_base_sec", 2.0)),
                       backoff_factor=float(cfg.get("backoff_factor", 2.0)),
                       sleep_sec=float(cfg.get("request_sleep_sec", 0.3)), log=log)
    doc_type = str(ccfg.get("doc_type", "5"))

    # --- ダンプモード(構造確認) ---
    if args.dump:
        raw = client.fetch_doc(args.dump, doc_type)
        if raw is None:
            log.error("docID %s は type=%s の本文が無い(404)", args.dump, doc_type)
            return 1
        rows = parse_edinet_csv_zip(raw)
        print(f"# docID={args.dump}  bytes={len(raw)}  rows={len(rows)}  csvs={sorted({r['source_csv'] for r in rows})}")
        kw = (ccfg.get("policy_keywords", []) + ccfg.get("uridashi_equity_phrases", [])
              + ["有価証券の種類", "売出要項", "提出理由", "報告内容", "売出数", "売出価格", "売出人"])
        print("## 値が非空の行(項目 | 値):")
        for r in rows:
            v = r.get("value", "")
            if v and v not in ("―", "-", "－"):
                mark = " *" if any(k in (r.get("item", "") + v) for k in kw) else ""
                print(f"  [{r['element']}] {r['item']} | {v[:80]}{mark}")
        res = classify_doc(rows, ccfg)
        print("## classify_doc():", json.dumps(res, ensure_ascii=False))
        return 0

    # --- 全件分類 ---
    cand_csv = args.root / cfg["output"]["candidates_csv"]
    if not cand_csv.exists():
        log.error("%s が無い。先に edinet_fetch.py を回す。", cand_csv)
        return 2
    docs_dir = args.root / ccfg["output"]["raw_docs_dir"]
    manifest = args.root / ccfg["output"]["manifest"]
    docs_dir.mkdir(parents=True, exist_ok=True)

    with cand_csv.open(encoding="utf-8") as f:
        cands = [r for r in csv.DictReader(f) if r.get("is_ipo") != "TRUE"]
    if args.limit:
        cands = cands[:args.limit]
    done = _load_done(manifest)
    log.info("classify: %d 非IPO候補(%d 済スキップ)", len(cands), len(done))

    results: list[dict] = []
    for i, c in enumerate(cands):
        docid = c["docID"]
        cached = docs_dir / f"{docid}.zip"
        if docid in done and cached.exists():
            raw = cached.read_bytes()
        else:
            try:
                raw = client.fetch_doc(docid, doc_type)
            except Exception as e:
                _append(manifest, {"docID": docid, "status": "fetch_error", "error": str(e),
                                   "ts": datetime.now(JST).isoformat()})
                continue
            if raw is None:
                _append(manifest, {"docID": docid, "status": "no_body",
                                   "ts": datetime.now(JST).isoformat()})
                continue
            cached.write_bytes(raw)
            _append(manifest, {"docID": docid, "status": "ok", "sha256": _sha256(raw),
                               "bytes": len(raw), "ts": datetime.now(JST).isoformat()})
        rows = parse_edinet_csv_zip(raw)
        res = classify_doc(rows, ccfg)
        res.update({"docID": docid, "submit_date": c.get("submit_date", ""),
                    "docTypeCode": c.get("docTypeCode", ""),
                    "issuer_code": c.get("code4", ""), "issuer_name": c.get("filerName", "")})
        if not rows:
            res["note"] = "本文パース不可(構造要確認)"
        results.append(res)
        if (i + 1) % 200 == 0:
            log.info("  %d/%d 処理", i + 1, len(cands))

    _write_detail(args.root / ccfg["output"]["detail_csv"], results)
    tier2 = [r for r in results if is_tier2(r)]
    _write_tier2(args.root / ccfg["output"]["tier2_csv"], tier2)
    _write_report(args.root / ccfg["output"]["report_md"], results, tier2)
    log.info("done: %d 分類 → tier2(政策保有×株式売出) %d 件。 %s",
             len(results), len(tier2), ccfg["output"]["tier2_csv"])
    return 0


def _write_detail(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLASSIFY_COLUMNS)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in CLASSIFY_COLUMNS})


def _write_tier2(path: Path, tier2: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLASSIFY_COLUMNS)
        w.writeheader()
        for r in sorted(tier2, key=lambda x: (x.get("submit_date", ""), x.get("issuer_code", ""))):
            w.writerow({k: r.get(k, "") for k in CLASSIFY_COLUMNS})


def _write_report(path: Path, results: list[dict], tier2: list[dict]) -> None:
    from collections import Counter
    n = len(results)
    eq = sum(1 for r in results if r["is_equity_uridashi"] == "TRUE")
    bond = sum(1 for r in results if r["is_bond"] == "TRUE")
    by_tier = Counter(r["confidence_policy_holding"] for r in results)
    unparsed = sum(1 for r in results if r.get("note", "").startswith("本文パース不可"))
    L = ["# Task D step2 — 本文分類(株式の売出し抽出 → 政策保有は人が確認)\n\n",
         f"generated: {datetime.now(JST).isoformat(timespec='seconds')}\n\n",
         f"- 分類 {n} 件: **株式売出 {eq}** / 社債 {bond} / 本文パース不可 {unparsed}\n",
         f"- tier: A_explicit(政策保有明示) {by_tier.get('A_explicit',0)} / B_inference(株式売出だが要確認) {by_tier.get('B_inference',0)} / none {by_tier.get('none',0)}\n",
         f"- **tier2(株式の売出し=転記シートへ流す lead)= {len(tier2)} 件** ← 政策保有かは TDnet で人が確認\n\n",
         "## tier2 一覧(docTypeCode: 190=臨時報告値決め / 040=届出値決め / 100=発行登録追補 / 030=届出)\n\n",
         "| date | code | issuer | tier | 売出人(type) | 売出株数 | 価格 |\n|---|---|---|---|---|---:|---:|\n"]
    for r in sorted(tier2, key=lambda x: (x.get("submit_date",""), x.get("issuer_code",""))):
        L.append(f"| {r.get('submit_date','')} | {r.get('issuer_code','')} | {r.get('issuer_name','')[:16]} | "
                 f"{r.get('confidence_policy_holding','')} | {r.get('sellers','')[:30]}({r.get('seller_types','')}) | "
                 f"{r.get('uridashi_shares','')} | {r.get('offer_price_JPY','')} |\n")
    L.append("\n## 注意\n")
    L.append("- **確定は人の一次確認**。tier2 は lead。数値(売出株数/価格)は本文抽出の暫定 → 転記シートで一次確認。\n")
    L.append("- **B_inference は要検証**(売出人が事業会社/銀行等でも純投資売却の可能性)。A_explicit を主、A+B を感度で N ゲート。\n")
    L.append("- 本文パース不可が多い場合は CSV(type5) が無い書類 → XBRL(type1) fallback を要検討。\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
