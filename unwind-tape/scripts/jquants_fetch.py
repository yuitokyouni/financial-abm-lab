#!/usr/bin/env python3
"""unwind-tape / task C — J-Quants Light API fetcher.

必要データ:
  - /prices/daily_quotes            per code (11 issuer)
  - /indices/topix (or bars/daily/topix) — market proxy
  - /markets/trading_calendar       — JST 営業日
  - /fins/statements                per code — 発行済株式数 (size 分母)
  - /listed/info                    per code — snapshot (issuer_market 等)

出力:
  data/raw/prices/daily_quotes/{code}.jsonl           一日一行 JSON
  data/raw/prices/topix.jsonl                          一日一行
  data/raw/prices/trading_calendar.jsonl               全カレンダー
  data/raw/prices/fins_statements/{code}.jsonl         期次
  data/raw/prices/listed_info.jsonl                    snapshot
  data/raw/prices/manifest.jsonl                       fetch ごとに追記

冪等: 既存 jsonl の末尾 date より新しい分だけ append。
リトライ: 指数バックオフ (base=2s, factor=2, retries=4)。
Rate limit: Light = 60 件/分 → 呼び出し間に 1.1 秒 sleep で余裕を持たせる。

認証 (優先度順):
  1. env JQUANTS_API_KEY          — V2 ダッシュボード発行の単一キー。交換不要、
                                     そのまま Bearer で使う (2025-12-22 以降の
                                     新規登録者はこれのみ発行される)
  2. env JQUANTS_ID_TOKEN         — V1。そのまま Bearer で使う
  3. env JQUANTS_REFRESH_TOKEN    — V1。/token/auth_refresh で id_token を取得
  4. env JQUANTS_MAIL + JQUANTS_PASSWORD — V1。/token/auth_user でログイン
どれもなければエラー終了。

V1/V2 の endpoint path 差異 (要注意):
  V2 API キーでも base_url が V1 のままだと 404 する可能性がある。
  その場合は --base-url https://api.jquants.com/v2 を試すか、
  実際に返ってきたエラー本文を見て path を調整すること
  (本スクリプトは事前に V2 の全 path 一覧を検証していない未確認箇所)。
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


DEFAULT_BASE_URL = "https://api.jquants.com/v1"   # 2025-12 以降新規は V2 だが、V1 パスも当面互換維持
RATE_LIMIT_SLEEP_SEC = 1.1                          # Light 60/min の余裕マージン
DEFAULT_RETRIES = 4
BACKOFF_BASE = 2.0
BACKOFF_FACTOR = 2.0


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
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "unwind-tape/0.1 (financial-abm-lab; +https://github.com/yuitokyouni/financial-abm-lab)",
            "Accept": "application/json",
        })
        self.id_token: str | None = None
        self.log = log or logging.getLogger("unwind_tape.jquants")

    def authenticate(self) -> None:
        if self.id_token:
            return
        api_key = os.getenv("JQUANTS_API_KEY")
        if api_key:
            # V2: ダッシュボード発行の単一キーをそのまま Bearer として使う。
            # 交換ステップ (auth_user / auth_refresh) は不要。
            self.log.info("auth: using JQUANTS_API_KEY (V2 direct Bearer)")
            self.id_token = api_key
            return
        id_token = os.getenv("JQUANTS_ID_TOKEN")
        if id_token:
            self.log.info("auth: using JQUANTS_ID_TOKEN from env")
            self.id_token = id_token
        elif os.getenv("JQUANTS_REFRESH_TOKEN"):
            self.log.info("auth: exchanging JQUANTS_REFRESH_TOKEN → id_token")
            r = self._post(
                f"{self.base}/token/auth_refresh",
                params={"refreshtoken": os.getenv("JQUANTS_REFRESH_TOKEN")},
                anon=True,
            )
            self.id_token = r["idToken"]
        elif os.getenv("JQUANTS_MAIL") and os.getenv("JQUANTS_PASSWORD"):
            self.log.info("auth: logging in with JQUANTS_MAIL/PASSWORD")
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
            self.id_token = r2["idToken"]
        else:
            raise EnvironmentError(
                "Set one of: JQUANTS_API_KEY | JQUANTS_ID_TOKEN | JQUANTS_REFRESH_TOKEN | "
                "(JQUANTS_MAIL + JQUANTS_PASSWORD)"
            )

    def _headers(self) -> dict[str, str]:
        if not self.id_token:
            self.authenticate()
        return {"Authorization": f"Bearer {self.id_token}"}

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
                if r.status_code == 401 and self.id_token:
                    # token expired mid-run — re-auth
                    self.log.info("401 — refreshing id_token")
                    self.id_token = None
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
    items = client.get_all_pages(
        "/prices/daily_quotes",
        {"code": code, "from": from_date, "to": to_date},
        key="daily_quotes",
    )
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
    # V1: /indices/topix, V2: /indices/bars/daily/topix. Try V1 first — fall back to V2 shape.
    try:
        items = client.get_all_pages(
            "/indices/topix", {"from": from_date, "to": to_date}, key="topix",
        )
    except Exception as e:
        log.warning("topix V1 path failed (%s); trying V2 shape", e)
        items = client.get_all_pages(
            "/indices/bars/daily/topix", {"from": from_date, "to": to_date}, key="indices",
        )
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
    items = client.get_all_pages(
        "/markets/trading_calendar",
        {"from": from_date, "to": to_date},
        key="trading_calendar",
    )
    new = [it for it in items if str(it.get("Date")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("trading_calendar fetched=%d appended=%d", len(items), added)
    return {"endpoint": "trading_calendar", "fetched": len(items), "appended": added,
            "path": str(dest.relative_to(root))}


def fetch_fins_statements(client: JQuantsClient, root: Path, code: str,
                          log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "fins_statements" / f"{code}.jsonl"
    # fins は disclosure 単位。code だけで全期間取れる (from/to は無視される endpoint 仕様)
    existing = _load_existing_dates(dest, date_field="DisclosedDate")
    items = client.get_all_pages("/fins/statements", {"code": code}, key="statements")
    new = [it for it in items if str(it.get("DisclosedDate")) not in existing]
    added = _append_jsonl(dest, new)
    log.info("[%s] fins_statements fetched=%d appended=%d", code, len(items), added)
    return {"code": code, "fetched": len(items), "appended": added,
            "path": str(dest.relative_to(root))}


def fetch_listed_info(client: JQuantsClient, root: Path, codes: list[str],
                      log: logging.Logger) -> dict:
    dest = root / "data" / "raw" / "prices" / "listed_info.jsonl"
    # snapshot なので毎回全上書き
    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    out: list[dict] = []
    for c in codes:
        try:
            data = client._get("/listed/info", {"code": c})
        except Exception as e:
            log.warning("listed_info %s failed: %s", c, e)
            continue
        for it in data.get("info", []):
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
                             "fins_statements", "listed_info"])
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

    if "fins_statements" not in args.skip:
        for code in args.codes:
            try:
                r = fetch_fins_statements(client, args.root, code, log)
                _record(r)
                results.append(r)
            except Exception as e:
                log.error("fins_statements %s failed: %s", code, e)
                _record({"code": code, "endpoint": "fins_statements",
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
