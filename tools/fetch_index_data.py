#!/usr/bin/env python
"""fetch_index_data.py — 株価指数の日次終値を取得し sieve reference 形式で保存。

使い方:
    python tools/fetch_index_data.py ^N225 nikkei
    python tools/fetch_index_data.py ^GSPC sp500 --years 15

出力: data/index_cache/<name>_daily.csv (列 = timestamp,price)。
sieve inspect の --reference にそのまま渡せる
(--reference-derive-return log で log return を導出させる)。

取得系は fingerprint_atlas.real_refs (Yahoo Finance v8 chart API, 依存追加なし)
を再利用する。生の JSON レスポンスも同ディレクトリにキャッシュされるので、
再実行はオフラインで済む。CSV の SHA-256 を stdout に出す (redistribution しない
生データの同一性検証用 — sieve financial-daily suite と同じ流儀)。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "fingerprint_atlas"))

from fingerprint_atlas.real_refs import fetch_yahoo_closes  # noqa: E402

CACHE_DIR = REPO_ROOT / "data" / "index_cache"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbol", help="Yahoo Finance symbol, e.g. ^N225, ^GSPC")
    ap.add_argument("name", help="output name, e.g. nikkei -> nikkei_daily.csv")
    ap.add_argument("--years", type=float, default=10.0,
                    help="lookback window in years (default: 10)")
    ap.add_argument("--force", action="store_true",
                    help="bypass the JSON cache and refetch")
    args = ap.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ts, closes = fetch_yahoo_closes(
        args.symbol, years=args.years, cache_dir=str(CACHE_DIR),
        force=args.force,
    )
    if len(closes) == 0:
        raise SystemExit(f"no data returned for {args.symbol}")

    out = CACHE_DIR / f"{args.name}_daily.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "price"])
        for t, c in zip(ts, closes):
            day = dt.datetime.fromtimestamp(int(t), dt.timezone.utc).date()
            w.writerow([day.isoformat(), f"{float(c):.6f}"])

    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{args.symbol}: {len(closes)} daily closes "
          f"({dt.datetime.fromtimestamp(int(ts[0]), dt.timezone.utc).date()} .. "
          f"{dt.datetime.fromtimestamp(int(ts[-1]), dt.timezone.utc).date()})")
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    print(f"sha256 {sha}")


if __name__ == "__main__":
    main()
