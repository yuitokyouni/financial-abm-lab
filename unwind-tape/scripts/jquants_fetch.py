#!/usr/bin/env python3
"""unwind-tape / task C — J-Quants API fetcher (V2 既定, V1 は互換のみ)。

2026-07 時点で V1 API は決済/認証方式ごと実質廃止されている
(旧 /markets/trading_calendar が 410 Gone を返すことを実機で確認済み)。
新規登録者のダッシュボードには「API キー」が1個だけ発行され、
x-api-key ヘッダーで直接使う (V1 の refresh→id token 交換は無い)。
このスクリプトは V2 を既定にし、V1 の資格情報が設定された場合のみ
V1 の path/認証にフォールバックする。

V2 endpoint (公式 quick-start notebook
https://github.com/J-Quants/jquants-api-quick-start より確認済み):
  - /equities/bars/daily            per code (11 issuer) — 株価四本値 (調整後込み)
  - /indices/bars/daily/topix       — market proxy
  - /markets/calendar                — JST 営業日 (V1 の /markets/trading_calendar 相当)
  - /fins/summary                    per code — 決算短信サマリー (発行済株式数を含むか要確認)
  - /equities/master                 per code — 上場銘柄一覧 snapshot

V2 のレスポンス envelope は全 endpoint 共通で {"data": [...], "pagination_key"?: str}。
V1 は endpoint ごとに異なるキー名 ("daily_quotes", "topix", "trading_calendar", ...) だった。

出力:
  data/raw/prices/daily_quotes/{code}.jsonl           一日一行 JSON
  data/raw/prices/topix.jsonl                          一日一行
  data/raw/prices/trading_calendar.jsonl               全カレンダー
  data/raw/prices/fins_summary/{code}.jsonl            期次
  data/raw/prices/listed_info.jsonl                    snapshot
  data/raw/prices/manifest.jsonl                       fetch ごとに追記

冪等: 既存 jsonl の末尾 date より新しい分だけ append。
リトライ: 指数バックオフ (base=2s, factor=2, retries=4)。
Rate limit: Light = 60 件/分 → 呼び出し間に 1.1 秒 sleep で余裕を持たせる。

認証 (優先度順):
  1. env JQUANTS_API_KEY          — V2。ダッシュボード発行の単一キー。
                                     x-api-key ヘッダーでそのまま使う。交換不要。
  2. env JQUANTS_ID_TOKEN         — V1 (レガシー)。Bearer でそのまま使う
  3. env JQUANTS_REFRESH_TOKEN    — V1 (レガシー)。/token/auth_refresh で id_token を取得
  4. env JQUANTS_MAIL + JQUANTS_PASSWORD — V1 (レガシー)。/token/auth_user でログイン
どれもなければエラー終了。

未検証箇所 (実データで要確認):
  - /fins/summary の実際のフィールド名 (発行済株式数の項目名は V1 の
    NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock
    から変わっている可能性がある)
  - daily_quotes / topix の JSON フィールド名 (Date/Close/Volume/Adjustment* 等)
    が V1 と同じ表記かどうか
  実行後、car_engine.py 側のローダーが値をすべて NaN で返す場合はここが原因。
  一件 jsonl を目視して car_engine.py の load_* 関数のフィールド名を合わせること。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests


DEFAULT_BASE_URL = "https://api.jquants.com/v2"   # V1 は実質廃止 (410 Gone 実機確認済み)
RATE_LIMIT_SLEEP_SEC = 1.1                          # Light 60/min の余裕マージン
DEFAULT_RETRIES = 4
BACKOFF_BASE = 2.0
BACKOFF_FACTOR = 2.0

# endpoint path + response envelope key の version 別マッピング。
# V2 は全 endpoint で envelope key = "data" 固定。V1 は endpoint ごとに異なった。
ENDPOINTS: dict[str, dict[str, tuple[str, str]]] = {
    "v2": {
        "daily_quotes":     ("/equities/bars/daily", "data"),
        "topix":            ("/indices/bars/daily/topix", "data"),
        "trading_calendar": ("/markets/calendar", "data"),
        "fins":             ("/fins/summary", "data"),
        "listed_info":      ("/equities/master", "data"),
    },
    "v1": {
        "daily_quotes":     ("/prices/daily_quotes", "daily_quotes"),
        "topix":            ("/indices/topix", "topix"),
        "trading_calendar": ("/markets/trading_calendar", "trading_calendar"),
        "fins":             ("/fins/statements", "statements"),
        "listed_info":      ("/listed/info", "info"),
    },
}


# ---------------------------------------------------------------------------
# util
# ---------------------------------------------------------------------------

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso(d: date | datetime | str) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def _configure_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    log_path = log_dir / f"jquants_fetch_{now.strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger("unwind_tape.jquants")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------

class JQuantsClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, log: logging.Logger | None = None):
        self.base = base_url.rstrip("/")
        self.api_version = "v2" if "/v2" in self.base else "v1"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "unwind-tape/0.1 (financial-abm-lab; +https://github.com/yuitokyouni/financial-abm-lab)",
            "Accept": "application/json",
        })
        self.credential: str | None = None
        self.auth_mode: str | None = None   # "v2_api_key" | "v1_bearer"
        self.log = log or logging.getLogger("unwind_tape.jquants")

    def endpoint(self, name: str) -> tuple[str, str]:
        """name in {'daily_quotes','topix','trading_calendar','fins','listed_info'}
        → (path, response_envelope_key) for the active api_version.
        """
        return ENDPOINTS[self.api_version][name]

    def authenticate(self) -> None:
        if self.credential:
            return
        api_key = os.getenv("JQUANTS_API_KEY")
        if api_key:
            # V2: ダッシュボード発行の単一キーを x-api-key ヘッダーでそのまま使う。
            # 交換ステップ (auth_user / auth_refresh) は無い。
            self.log.info("auth: using JQUANTS_API_KEY (V2 x-api-key)")
            self.credential = api_key
            self.auth_mode = "v2_api_key"
            return
        id_token = os.getenv("JQUANTS_ID_TOKEN")
        if id_token:
            self.log.info("auth: using JQUANTS_ID_TOKEN from env (V1 Bearer)")
            self.credential = id_token
            self.auth_mode = "v1_bearer"
        elif os.getenv("JQUANTS_REFRESH_TOKEN"):
            self.log.info("auth: exchanging JQUANTS_REFRESH_TOKEN → id_token (V1)")
            r = self._post(
                f"{self.base}/token/auth_refresh",
                params={"refreshtoken": os.getenv("JQUANTS_REFRESH_TOKEN")},
                anon=True,
            )
            self.credential = r["idToken"]
            self.auth_mode = "v1_bearer"
        elif os.getenv("JQUANTS_MAIL") and os.getenv("JQUANTS_PASSWORD"):
            self.log.info("auth: logging in with JQUANTS_MAIL/PASSWORD (V1)")
            r = self._post(
                f"{self.base}/token/auth_user",
                json_body={"mailaddress": os.getenv("JQUANTS_MAIL"),
                           "password": os.getenv("JQUANTS_PASSWORD")},
                anon=True,
            )
            refresh_token = r["refreshToken"]
            r2 = self._post(
                f"{self.base}/token/auth_refresh",
                params={"refreshtoken": refresh_token},
                anon=True,
            )
            self.credential = r2["idToken"]
            self.auth_mode = "v1_bearer"
        else:
            raise EnvironmentError(
                "Set one of: JQUANTS_API_KEY | JQUANTS_ID_TOKEN | JQUANTS_REFRESH_TOKEN | "
                "(JQUANTS_MAIL + JQUANTS_PASSWORD)"
            )

    def _headers(self) -> dict[str, str]:
        if not self.credential:
            self.authenticate()
        if self.auth_mode == "v2_api_key":
            return {"x-api-key": self.credential}
        return {"Authorization": f"Bearer {self.credential}"}

    def _post(self, url: str, *, params: dict | None = None,
              json_body: dict | None = None, anon: bool = False) -> dict:
        headers = {} if anon else self._headers()
        for attempt in range(DEFAULT_RETRIES + 1):
            try:
                r = self.session.post(url, params=params, json=json_body,
                                      headers=headers, timeout=30)
                if r.status_code == 429:
                    raise RuntimeError("HTTP 429 rate limited")
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt >= DEFAULT_RETRIES:
                    raise
                wait = BACKOFF_BASE * (BACKOFF_FACTOR ** attempt)
                self.log.warning("POST %s failed (%s); retry %d/%d in %.1fs",
                                 url, e, attempt+1, DEFAULT_RETRIES, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base}{path}"
        for attempt in range(DEFAULT_RETRIES + 1):
            try:
                time.sleep(RATE_LIMIT_SLEEP_SEC)
                r = self.session.get(url, params=params, headers=self._headers(), timeout=30)
                if r.status_code == 429:
                    raise RuntimeError("HTTP 429 rate limited")
                if r.status_code == 401 and self.credential and self.auth_mode == "v1_bearer":
                    # V1 id_token expired mid-run (最短6時間) — re-auth して再試行。
                    # V2 API key は static なので再認証しても無意味 (鍵自体が無効/失効の場合はここに来ない設計)。
                    self.log.info("401 — refreshing V1 id_token")
                    self.credential = None
                    r = self.session.get(url, params=params, headers=self._headers(), timeout=30)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt >= DEFAULT_RETRIES:
                    raise
                wait = BACKOFF_BASE * (BACKOFF_FACTOR ** attempt)
                self.log.warning("GET %s params=%s failed (%s); retry %d/%d in %.1fs",
                                 url, params, e, attempt+1, DEFAULT_RETRIES, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def get_all_pages(self, path: str, params: dict, key: str) -> list[dict]:
        out: list[dict] = []
        pk: str | None = None
        page = 0
        while True:
            p = dict(params)
            if pk is not None:
                p["pagination_key"] = pk
            data = self._get(path, p)
            items = data.get(key, [])
            out.extend(items)
            page += 1
            pk = data.get("pagination_key")
            if not pk:
                break
            if page > 200:
                self.log.warning("pagination stopped at page 200 for %s params=%s", path, params)
                break
        return out


# ---------------------------------------------------------------------------
# fetch drivers per endpoint
# ---------------------------------------------------------------------------

def _load_existing_dates(path: Path, date_field: str = "Date") -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                d = e.get(date_field)
                if d:
                    out.add(str(d))
            except json.JSONDecodeError:
                continue
    return out


def _append_jsonl(path: Path, records: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def fetch_daily_quotes(client: JQuantsClient, root: Path, code: str,
                       from_date: str, to_date: str, log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "daily_quotes" / f"{code}.jsonl"
    existing = _load_existing_dates(dest)
    log.info("[%s] daily_quotes existing=%d from=%s to=%s", code, len(existing), from_date, to_date)
    path, key = client.endpoint("daily_quotes")
    items = client.get_all_pages(path, {"code": code, "from": from_date, "to": to_date}, key=key)
    new = [it for it in items if str(it.get("Date")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("[%s] daily_quotes fetched=%d appended=%d dest=%s",
             code, len(items), added, dest.relative_to(root))
    return {"code": code, "fetched": len(items), "appended": added, "path": str(dest.relative_to(root))}


def fetch_topix(client: JQuantsClient, root: Path,
                from_date: str, to_date: str, log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "topix.jsonl"
    existing = _load_existing_dates(dest)
    log.info("topix existing=%d from=%s to=%s", len(existing), from_date, to_date)
    path, key = client.endpoint("topix")
    items = client.get_all_pages(path, {"from": from_date, "to": to_date}, key=key)
    new = [it for it in items if str(it.get("Date")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("topix fetched=%d appended=%d", len(items), added)
    return {"endpoint": "topix", "fetched": len(items), "appended": added, "path": str(dest.relative_to(root))}


def fetch_trading_calendar(client: JQuantsClient, root: Path,
                           from_date: str, to_date: str, log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "trading_calendar.jsonl"
    # calendar は不変 (未来分だけ稀に追加) なので既存 date は skip
    existing = _load_existing_dates(dest)
    log.info("trading_calendar existing=%d from=%s to=%s", len(existing), from_date, to_date)
    path, key = client.endpoint("trading_calendar")
    items = client.get_all_pages(path, {"from": from_date, "to": to_date}, key=key)
    new = [it for it in items if str(it.get("Date")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("trading_calendar fetched=%d appended=%d", len(items), added)
    return {"endpoint": "trading_calendar", "fetched": len(items), "appended": added,
            "path": str(dest.relative_to(root))}


def fetch_fins_summary(client: JQuantsClient, root: Path, code: str,
                       log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "fins_summary" / f"{code}.jsonl"
    # fins は disclosure 単位。code だけで全期間取れる (from/to は無視される endpoint 仕様)
    existing = _load_existing_dates(dest, date_field="DisclosedDate")
    path, key = client.endpoint("fins")
    items = client.get_all_pages(path, {"code": code}, key=key)
    new = [it for it in items if str(it.get("DisclosedDate")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("[%s] fins_summary fetched=%d appended=%d", code, len(items), added)
    return {"code": code, "fetched": len(items), "appended": added,
            "path": str(dest.relative_to(root))}


def fetch_listed_info(client: JQuantsClient, root: Path, codes: list[str],
                      log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "listed_info.jsonl"
    # snapshot なので毎回全上書き
    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    path, key = client.endpoint("listed_info")
    out: list[dict] = []
    for c in codes:
        try:
            data = client._get(path, {"code": c})
        except Exception as e:
            log.warning("listed_info %s failed: %s", c, e)
            continue
        for it in data.get(key, []):
            it["_captured_at"] = now
            out.append(it)
    if out:
        # rewrite (overwrite) for snapshot semantics
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as f:
            for it in out:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    log.info("listed_info fetched=%d", len(out))
    return {"endpoint": "listed_info", "fetched": len(out), "path": str(dest.relative_to(root))}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--from-date", default="2022-07-01",
                    help="estimation window [-140,-21] confirmed by 2023-01-01 events")
    ap.add_argument("--to-date", default=None,
                    help="default: today (JST)")
    ap.add_argument("--codes", nargs="*",
                    default=["6902", "6201", "7259", "7267", "8154", "3950",
                             "4246", "7974", "4063", "4062", "2871"],
                    help="issuer codes (Task B の 11 銘柄)")
    ap.add_argument("--skip", nargs="*", default=[],
                    choices=["daily_quotes", "topix", "trading_calendar",
                             "fins_summary", "listed_info"])
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = ap.parse_args(argv)

    log = _configure_logging(args.root / "data" / "logs")
    if args.to_date is None:
        args.to_date = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")

    log.info("unwind-tape jquants fetch start: codes=%d from=%s to=%s base=%s",
             len(args.codes), args.from_date, args.to_date, args.base_url)

    client = JQuantsClient(base_url=args.base_url, log=log)
    try:
        client.authenticate()
    except Exception as e:
        log.error("authentication failed: %s", e)
        return 5

    manifest_path = args.root / "data" / "raw" / "prices" / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    exit_code = 0

    def _record(entry: dict) -> None:
        entry["captured_at"] = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
        with manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # trading_calendar (nearly required by every downstream step)
    if "trading_calendar" not in args.skip:
        try:
            r = fetch_trading_calendar(client, args.root, args.from_date, args.to_date, log)
            _record(r)
            results.append(r)
        except Exception as e:
            log.error("trading_calendar failed: %s", e)
            _record({"endpoint": "trading_calendar", "status": "error", "detail": str(e)})
            exit_code = max(exit_code, 4)

    # topix
    if "topix" not in args.skip:
        try:
            r = fetch_topix(client, args.root, args.from_date, args.to_date, log)
            _record(r)
            results.append(r)
        except Exception as e:
            log.error("topix failed: %s", e)
            _record({"endpoint": "topix", "status": "error", "detail": str(e)})
            exit_code = max(exit_code, 4)

    # per-code
    if "daily_quotes" not in args.skip:
        for code in args.codes:
            try:
                r = fetch_daily_quotes(client, args.root, code, args.from_date, args.to_date, log)
                _record(r)
                results.append(r)
            except Exception as e:
                log.error("daily_quotes %s failed: %s", code, e)
                _record({"code": code, "endpoint": "daily_quotes",
                         "status": "error", "detail": str(e)})
                exit_code = max(exit_code, 4)

    if "fins_summary" not in args.skip:
        for code in args.codes:
            try:
                r = fetch_fins_summary(client, args.root, code, log)
                _record(r)
                results.append(r)
            except Exception as e:
                log.error("fins_summary %s failed: %s", code, e)
                _record({"code": code, "endpoint": "fins_summary",
                         "status": "error", "detail": str(e)})
                exit_code = max(exit_code, 4)

    if "listed_info" not in args.skip:
        try:
            r = fetch_listed_info(client, args.root, args.codes, log)
            _record(r)
            results.append(r)
        except Exception as e:
            log.error("listed_info failed: %s", e)
            _record({"endpoint": "listed_info", "status": "error", "detail": str(e)})
            exit_code = max(exit_code, 4)

    log.info("done — %d endpoint fetches, exit=%d", len(results), exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
