"""Fetch BTC-USD OHLC candles from the Coinbase Exchange public API.

Why Coinbase and not an aggregator: this needs *one venue's own tape*, not a
volume-weighted composite. The model is about the order flow arriving at one
book, and cross-venue aggregation smooths exactly the imbalance dynamics the
estimand lives in.

    python fetch_btc.py --granularity 3600 --start 2016-01-01 --out ../data/btc_usd_1h.csv

Public endpoint, 300 candles per request, no key. Gaps (venue downtime) are
kept as gaps -- never forward-filled -- and reported in the summary line.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://api.exchange.coinbase.com/products/{product}/candles"
MAX_CANDLES = 300


def _get(url: str, tries: int = 5) -> list:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "yh011/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return json.load(fh)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)
    return []


def fetch(product: str, granularity: int, start: datetime, end: datetime) -> list:
    span = timedelta(seconds=granularity * MAX_CANDLES)
    rows: dict[int, list] = {}
    cur = start
    n_req = 0
    while cur < end:
        stop = min(cur + span, end)
        url = (f"{URL.format(product=product)}?granularity={granularity}"
               f"&start={cur.isoformat().replace('+00:00','Z')}"
               f"&end={stop.isoformat().replace('+00:00','Z')}")
        for c in _get(url):
            rows[int(c[0])] = c
        n_req += 1
        if n_req % 25 == 0:
            print(f"  {n_req} requests, {len(rows)} candles, at {cur.date()}",
                  flush=True)
        time.sleep(0.12)          # stay under the public rate limit
        cur = stop
    return [rows[t] for t in sorted(rows)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="BTC-USD")
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = (datetime.now(timezone.utc) if args.end is None
           else datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc))

    rows = fetch(args.product, args.granularity, start, end)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "low", "high", "open", "close", "volume"])
        w.writerows(rows)

    ts = [r[0] for r in rows]
    gaps = sum(1 for a, b in zip(ts, ts[1:]) if b - a != args.granularity)
    print(f"{len(rows)} candles {datetime.fromtimestamp(ts[0], timezone.utc)} "
          f"-> {datetime.fromtimestamp(ts[-1], timezone.utc)}, "
          f"{gaps} gaps (left as gaps), wrote {out}")


if __name__ == "__main__":
    main()
