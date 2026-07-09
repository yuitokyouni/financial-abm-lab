#!/usr/bin/env python3
"""unwind-tape / Task D step 1 — EDINET 売出し系書類の網羅発見(discovery)。

docs/TASK_D_DESIGN.md の主源。EDINET API v2 の書類一覧(documents.json)を対象期間で
日次に舐め、有価証券届出書系(募集・売出し)を**候補(lead)**として抽出する。

**このスクリプトが出すのは候補だけ。** offer/pricing/disclosure_time 等の数値は
一次本文からの転記でのみ埋まる(transcription パイプライン)。ここでは創作しない。
政策保有 該当の本文判定は step 2(本文DL+分類)。step 1 は metadata レベルの前フィルタ。

規律(Task A/C と統一):
  - API キーは env(既定 EDINET_API_KEY)のみ。data/raw は gitignore。
  - リトライ = 指数バックオフ(base=2s, factor=2, retries=4)。429 はリトライ、その他 4xx は即 raise。
  - 冪等: 既に取得済み(manifest に status=ok)の日付は再取得しない(--force で上書き)。
  - 構造変化検知: metadata.status≠"200"(データ無し 404 除く)や results がリストでない等は fail-loud。
  - sha256 を manifest.jsonl に必ず追記。

出力(configs/edinet.yaml):
  data/raw/edinet/documents/{YYYY-MM-DD}.json   生レスポンス
  data/raw/edinet/manifest.jsonl                sha256 付き台帳(append-only)
  data/parsed/edinet/candidates.csv             候補一覧(docTypeCode/売出タグ/secCode 等)
  data/parsed/edinet/edinet_report.md           件数・方式内訳・選択バイアス注記

使い方(Mac、EDINET_API_KEY を export 済み):
  python3 scripts/edinet_fetch.py --date 2024-07-04     # 1日だけ疎通確認
  python3 scripts/edinet_fetch.py                        # config の期間を全舐め(冪等・再開可)
  python3 scripts/edinet_fetch.py --from 2024-01-01 --to 2024-12-31
依存: requests, PyYAML + stdlib。他リポ/他 Task を import しない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

JST = ZoneInfo("Asia/Tokyo")

# candidates.csv の列(metadata から機械抽出できるものだけ。数値転記は別)
CANDIDATE_COLUMNS = [
    "submit_date", "submit_datetime", "docID", "docTypeCode", "formCode",
    "ordinanceCode", "secCode", "code4", "edinetCode", "filerName",
    "docDescription", "has_uridashi", "is_ipo", "parentDocID",
    "xbrlFlag", "csvFlag", "pdfFlag",
]

# metadata レベルで存在を要求するキー(構造変化検知)。欠けたら schema_mismatch。
_REQUIRED_RESULT_KEYS = ("docID", "docTypeCode", "docDescription")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# 純関数(ネットワーク不要 = 単体テスト対象)
# ---------------------------------------------------------------------------

def has_uridashi(desc: str | None, keywords: list[str]) -> bool:
    """docDescription に売出(売出し)を含むか。※有価証券届出書は本文に募集/売出があり
    docDescription では判別できないことが多い(弱いタグ扱い。確定は step2 本文)。"""
    d = desc or ""
    return any(k in d for k in keywords)


def is_ipo(desc: str | None, keywords: list[str]) -> bool:
    """新規公開(IPO)か。IPO は政策保有解消でない → step2 で除外するためタグ付け。"""
    d = desc or ""
    return any(k in d for k in keywords)


def _code4(sec_code: str | None) -> str:
    """EDINET secCode は5桁(例 72030)。4桁の証券コードに落とす(末尾0を1桁除く)。"""
    s = (sec_code or "").strip()
    if len(s) == 5 and s.isdigit():
        return s[:4]
    if len(s) == 4 and s.isdigit():
        return s
    return ""


def result_to_candidate(r: dict, uridashi_kw: list[str], ipo_kw: list[str]) -> dict:
    """EDINET results の1件を candidates.csv 行(flat)に落とす。純関数。"""
    submit_dt = (r.get("submitDateTime") or "").strip()
    submit_date = submit_dt.split(" ")[0] if submit_dt else ""
    desc = r.get("docDescription")
    return {
        "submit_date": submit_date,
        "submit_datetime": submit_dt,
        "docID": r.get("docID") or "",
        "docTypeCode": r.get("docTypeCode") or "",
        "formCode": r.get("formCode") or "",
        "ordinanceCode": r.get("ordinanceCode") or "",
        "secCode": r.get("secCode") or "",
        "code4": _code4(r.get("secCode")),
        "edinetCode": r.get("edinetCode") or "",
        "filerName": r.get("filerName") or "",
        "docDescription": desc or "",
        "has_uridashi": "TRUE" if has_uridashi(desc, uridashi_kw) else "FALSE",
        "is_ipo": "TRUE" if is_ipo(desc, ipo_kw) else "FALSE",
        "parentDocID": r.get("parentDocID") or "",
        "xbrlFlag": r.get("xbrlFlag") or "",
        "csvFlag": r.get("csvFlag") or "",
        "pdfFlag": r.get("pdfFlag") or "",
    }


def extract_candidates(results: list[dict], target_codes: list[str], target_ords: list[str],
                       uridashi_kw: list[str], ipo_kw: list[str]) -> list[dict]:
    """事業会社(ordinanceCode∈target_ords、投資信託 030 を除外)の届出系(docTypeCode∈target_codes)
    だけ候補に。撤回済み(withdrawalStatus≠'0')は除外。募集/売出/policy-holding の確定は step2 本文。"""
    tc, oc = set(target_codes), set(target_ords)
    out = []
    for r in results:
        if (r.get("docTypeCode") or "") not in tc:
            continue
        if (r.get("ordinanceCode") or "") not in oc:      # 事業会社(株式)に限定。投資信託を除外
            continue
        if (r.get("withdrawalStatus") or "0") != "0":     # 撤回書類は lead にしない
            continue
        out.append(result_to_candidate(r, uridashi_kw, ipo_kw))
    return out


def validate_envelope(data: object) -> tuple[list[dict], str]:
    """EDINET レスポンスの構造検証。(results, status) を返す。
    schema 不一致(results 非リスト、必須キー欠落、status 異常)は ValueError で fail-loud。"""
    if not isinstance(data, dict):
        raise ValueError(f"response is not a JSON object: {type(data).__name__}")
    meta = data.get("metadata")
    if not isinstance(meta, dict):
        raise ValueError("metadata section missing/invalid")
    status = str(meta.get("status", ""))
    results = data.get("results")
    if results is None:
        results = []
    if not isinstance(results, list):
        raise ValueError(f"results is not a list: {type(results).__name__}")
    for r in results:
        if not isinstance(r, dict):
            raise ValueError("results item is not an object")
        missing = [k for k in _REQUIRED_RESULT_KEYS if k not in r]
        if missing:
            raise ValueError(f"results item missing keys {missing} (schema change?)")
    return results, status


def business_days(d_from: date, d_to: date):
    """月〜金だけ(祝日は EDINET が空 results を返すので呼んで問題ない)。"""
    d = d_from
    while d <= d_to:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------------------
# ネットワーク(Mac 実行。ここは単体テスト対象外)
# ---------------------------------------------------------------------------

class EdinetClient:
    def __init__(self, base_url: str, api_key: str, *, retries: int,
                 backoff_base: float, backoff_factor: float, sleep_sec: float,
                 log: logging.Logger):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.retries = retries
        self.bo_base = backoff_base
        self.bo_factor = backoff_factor
        self.sleep = sleep_sec
        self.log = log
        self.session = requests.Session()

    def fetch_documents_raw(self, day: date) -> bytes:
        """documents.json?date=..&type=2 の生バイトを返す(冪等判定に sha256 したいので bytes)。"""
        url = f"{self.base}/documents.json"
        params = {"date": day.isoformat(), "type": "2", "Subscription-Key": self.key}
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.sleep)
                r = self.session.get(url, params=params, timeout=30)
                if r.status_code == 429:
                    raise RuntimeError("HTTP 429 rate limited")
                # EDINET は将来日付など未提供日に 404 を返し得る → 空扱いにしたいので個別処理
                if r.status_code == 404:
                    return b'{"metadata":{"status":"404"},"results":[]}'
                r.raise_for_status()
                return r.content
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                non_retryable = status is not None and 400 <= status < 500 and status != 429
                if non_retryable or attempt >= self.retries:
                    raise
                wait = self.bo_base * (self.bo_factor ** attempt)
                self.log.warning("GET documents %s failed (%s); retry %d/%d in %.1fs",
                                 day, e, attempt + 1, self.retries, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")


def _load_manifest_ok_dates(manifest: Path) -> set[str]:
    ok: set[str] = set()
    if not manifest.exists():
        return ok
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("status") == "ok" and e.get("date"):
            ok.add(e["date"])
    return ok


def _append_manifest(manifest: Path, entry: dict) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="EDINET 売出し系書類 discovery (Task D step 1)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "edinet.yaml")
    ap.add_argument("--date", type=str, help="この1日だけ取得(疎通確認用)")
    ap.add_argument("--from", dest="d_from", type=str, help="開始日 override")
    ap.add_argument("--to", dest="d_to", type=str, help="終了日 override")
    ap.add_argument("--force", action="store_true", help="取得済みでも再取得")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("edinet")

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    key = os.environ.get(cfg["api_key_env"], "").strip()
    if not key:
        log.error("env %s が未設定。EDINET サブスクリプションキーを export してください。",
                  cfg["api_key_env"])
        return 2

    if args.date:
        d_from = d_to = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        d_from = datetime.strptime(args.d_from or cfg["date_from"], "%Y-%m-%d").date()
        d_to = datetime.strptime(args.d_to or cfg["date_to"], "%Y-%m-%d").date()

    target_codes = [str(c) for c in cfg["target_doc_type_codes"]]
    target_ords = [str(c) for c in cfg["target_ordinance_codes"]]
    keywords = list(cfg["uridashi_keywords"])
    ipo_kw = list(cfg.get("ipo_keywords", []))
    out = cfg["output"]
    raw_dir = args.root / out["raw_dir"]
    manifest = args.root / out["manifest"]
    cand_csv = args.root / out["candidates_csv"]
    report_md = args.root / out["report_md"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    client = EdinetClient(cfg["base_url"], key, retries=int(cfg.get("retries", 4)),
                          backoff_base=float(cfg.get("backoff_base_sec", 2.0)),
                          backoff_factor=float(cfg.get("backoff_factor", 2.0)),
                          sleep_sec=float(cfg.get("request_sleep_sec", 0.3)), log=log)

    done = set() if args.force else _load_manifest_ok_dates(manifest)
    days = [d for d in business_days(d_from, d_to) if d.isoformat() not in done]
    log.info("scan %s..%s : %d business days (%d already done, skipped)",
             d_from, d_to, len(days), 0 if args.force else len(done))

    all_candidates: list[dict] = []
    n_fetched = n_docs = 0
    for day in days:
        ds = day.isoformat()
        try:
            raw = client.fetch_documents_raw(day)
        except Exception as e:
            log.error("fetch failed %s: %s", ds, e)
            _append_manifest(manifest, {"date": ds, "status": "fetch_error",
                                        "error": str(e), "ts": datetime.now(JST).isoformat()})
            continue
        try:
            data = json.loads(raw)
            results, status = validate_envelope(data)
        except (json.JSONDecodeError, ValueError) as e:
            # 構造変化 → 生だけ保存して schema_mismatch で記録(黙って空を書かない)
            (raw_dir / f"{ds}.json").write_bytes(raw)
            _append_manifest(manifest, {"date": ds, "status": "schema_mismatch",
                                        "error": str(e), "sha256": _sha256(raw),
                                        "ts": datetime.now(JST).isoformat()})
            log.error("schema_mismatch %s: %s", ds, e)
            continue

        (raw_dir / f"{ds}.json").write_bytes(raw)
        cands = extract_candidates(results, target_codes, target_ords, keywords, ipo_kw)
        all_candidates.extend(cands)
        n_fetched += 1
        n_docs += len(results)
        _append_manifest(manifest, {"date": ds, "status": "ok", "http_status": status,
                                    "n_results": len(results), "n_candidates": len(cands),
                                    "sha256": _sha256(raw), "ts": datetime.now(JST).isoformat()})

    # candidates.csv は「今回取得分」を上書きではなく、全 raw から再集計して一貫させる
    all_candidates = _rebuild_candidates_from_raw(
        raw_dir, target_codes, target_ords, keywords, ipo_kw) or all_candidates
    _write_candidates(cand_csv, all_candidates)
    _write_report(report_md, all_candidates, d_from, d_to, n_fetched, n_docs, target_codes)
    log.info("done: fetched %d days, %d docs, %d candidates → %s",
             n_fetched, n_docs, len(all_candidates), out["candidates_csv"])
    return 0


def _rebuild_candidates_from_raw(raw_dir: Path, target_codes: list[str], target_ords: list[str],
                                 keywords: list[str], ipo_kw: list[str]) -> list[dict]:
    """保存済み全 {date}.json から候補を再構築(冪等: 途中再開・フィルタ変更後も candidates.csv が完全になる)。"""
    out: list[dict] = []
    for p in sorted(raw_dir.glob("*.json")):
        try:
            results, _ = validate_envelope(json.loads(p.read_bytes()))
        except (json.JSONDecodeError, ValueError):
            continue
        out.extend(extract_candidates(results, target_codes, target_ords, keywords, ipo_kw))
    return out


def _write_candidates(path: Path, cands: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cands = sorted(cands, key=lambda c: (c["submit_date"], c["docID"]))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANDIDATE_COLUMNS)
        w.writeheader()
        for c in cands:
            w.writerow(c)


def _write_report(path: Path, cands: list[dict], d_from: date, d_to: date,
                  n_days: int, n_docs: int, target_codes: list[str]) -> None:
    from collections import Counter
    by_type = Counter(c["docTypeCode"] for c in cands)
    by_form = Counter((c["docTypeCode"], c["formCode"]) for c in cands)
    ipo = [c for c in cands if c["is_ipo"] == "TRUE"]
    non_ipo = [c for c in cands if c["is_ipo"] != "TRUE"]
    with_code = [c for c in non_ipo if c["code4"]]           # 上場企業(secCode 有)= step2 対象の中核
    top_filers = Counter(c["filerName"] for c in with_code).most_common(20)
    L = []
    L.append("# Task D — EDINET 事業会社の届出系 discovery（step 1: 候補抽出）\n\n")
    L.append(f"generated: {datetime.now(JST).isoformat(timespec='seconds')}\n\n")
    L.append(f"- 対象期間: {d_from} .. {d_to}（取得済 {n_days} 営業日 / 総書類 {n_docs}）\n")
    L.append(f"- フィルタ: **ordinanceCode=010(事業会社=株式、投資信託 030 は除外)** × "
             f"docTypeCode∈{{{', '.join(target_codes)}}}(030 届出書 / 040 訂正 / 100 発行登録追補)\n")
    L.append(f"- **候補 {len(cands)} 件** = IPO {len(ipo)} + 非IPO {len(non_ipo)}"
             f"(うち secCode 有 = 上場企業 {len(with_code)} 件)\n")
    L.append("> 有価証券届出書は本文に募集/売出があり docDescription では判別不可 → **売出/policy-holding の確定は step2**。\n"
             "> 母集団=事業会社の届出(公募増資・売出し・shelf takedown)。ここから政策保有の**売出し**を step2 で絞る。\n\n")
    L.append("## docTypeCode 内訳\n\n| code | 件数 |\n|---|---:|\n")
    for tc in sorted(by_type):
        L.append(f"| {tc} | {by_type[tc]} |\n")
    L.append("\n## (docType, formCode) 内訳（offering の様式を見る: 021参照/022組込 が既存企業の増資・売出、024=IPO 系）\n\n")
    L.append("| docType | formCode | 件数 |\n|---|---|---:|\n")
    for (tc, fc), n in sorted(by_form.items(), key=lambda x: (-x[1], x[0])):
        L.append(f"| {tc} | {fc} | {n} |\n")
    L.append("\n## 上位 filer（非IPO・上場企業。発行体/届出人。lead であり確定ではない）\n\n")
    L.append("| code | filer | 件数 |\n|---|---|---:|\n")
    for name, n in top_filers:
        codes = {c["code4"] for c in with_code if c["filerName"] == name}
        L.append(f"| {'/'.join(sorted(codes))} | {name} | {n} |\n")
    L.append("\n## 次段 / 注意\n")
    L.append("- **step 2（本文分類）**: 非IPO候補の本文(XBRL/CSV)を DL し、(i) 募集でなく**売出し**か、"
             "(ii) **売出人が銀行/保険/事業提携先**か、(iii) 本文に「政策保有」「純投資目的以外」「縮減」等があるかで "
             "policy-holding を判定し `confidence_policy_holding`(A_explicit/B_inference) を付与。**数値は一次本文から転記のみ**。\n")
    L.append("- **選択バイアス**: EDINET は届出**閾値超**の売出しを拾う → 母集団は offering/大口に偏る。"
             "小口の市場内売却は届出書に出ず観測されない → **線形域(小 size)が過小**。相転移点推定の限界"
             "(TCA_BASELINE §3、TASK_D_DESIGN §3)。\n")
    L.append("- **N ゲート**: A+B 合算を主 / A_explicit 単独を併記の2系列で追跡(TASK_D_DESIGN 確定事項2)。\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
