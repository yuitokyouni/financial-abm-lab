"""real_refs — fetch real market daily closes, derive log-returns, fingerprint.

These are the *ground-truth landmarks* on the atlas. If the 8 canonical ABMs +
3 synthetic injectors all land far from where real markets land, that tells
us the instrument is calibrated to ABM dialects rather than to real markets —
which is exactly the question the user surfaced.

Source: Yahoo Finance v8 chart API (JSON, free, no API key). We deliberately
do NOT introduce a new dependency (no yfinance, no pandas-datareader); raw
urllib + json is enough and removes a moving part.

Each fetched series spawns multiple fingerprint runs by windowing — a single
real series gives one point on the map, several disjoint windows give a small
*cluster*, which is more informative than a single dot.

Cache: the raw closes are cached to JSON under a configurable directory so a
re-run does not need internet.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Iterator

import numpy as np


YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1={p1}&period2={p2}&interval=1d&events=history"
)


def fetch_yahoo_closes(symbol: str, *, years: float = 6.0,
                       cache_dir: str | None = None,
                       force: bool = False,
                       timeout: float = 20.0) -> tuple[np.ndarray, np.ndarray]:
    """Fetch (timestamps, closes) for `symbol` from Yahoo Finance.

    Caches the raw JSON response under cache_dir keyed by symbol+years; pass
    force=True to bypass the cache.
    """
    end = int(time.time())
    start = end - int(years * 365 * 86400)
    cache_path = (
        os.path.join(cache_dir, f"yahoo_{symbol.replace('^','').replace('-','_')}_{int(years)}y.json")
        if cache_dir else None
    )
    if cache_path and os.path.exists(cache_path) and not force:
        with open(cache_path) as fh:
            payload = json.load(fh)
    else:
        url = YAHOO_URL.format(symbol=symbol.replace("^", "%5E"), p1=start, p2=end)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
        if cache_path:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as fh:
                json.dump(payload, fh)
    res = payload["chart"]["result"][0]
    closes_raw = res["indicators"]["quote"][0]["close"]
    ts_raw = res["timestamp"]
    closes = np.array([np.nan if c is None else float(c) for c in closes_raw], dtype=np.float64)
    ts = np.array(ts_raw, dtype=np.int64)
    # forward-fill the (rare) embedded nulls so log-return diff doesn't propagate them
    if np.isnan(closes).any():
        for i in range(len(closes)):
            if np.isnan(closes[i]) and i > 0:
                closes[i] = closes[i - 1]
        # if the first value is nan, drop the leading nans
        mask = ~np.isnan(closes)
        ts, closes = ts[mask], closes[mask]
    return ts, closes


def log_returns(closes: np.ndarray) -> np.ndarray:
    safe = np.where(closes > 0, closes, np.nan)
    return np.diff(np.log(safe))


def windows(returns: np.ndarray, window_len: int, stride: int) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (start_idx, window_returns) of length `window_len`, stepping by `stride`."""
    n = len(returns)
    if window_len > n:
        yield 0, returns
        return
    for s in range(0, n - window_len + 1, stride):
        yield s, returns[s:s + window_len]


#: Default reference catalog. Each entry produces multiple windowed runs.
#: A `full` window goes in under one label (e.g. `real_spx_full`); each rolling
#: sub-window gets its OWN label (`real_spx_p0`, `real_spx_p1`, ...) so the atlas
#: shows "the real S&P is not one class — it's 6 different sub-periods that may
#: live in different regions of fingerprint space".
DEFAULT_REFS = [
    {"symbol": "^GSPC", "stem": "real_spx", "years": 6.0,
     "sub": {"window_len": 500, "stride": 250}},
    {"symbol": "BTC-USD", "stem": "real_btc", "years": 6.0,
     "sub": {"window_len": 500, "stride": 350}},
]


def iter_reference_runs(refs=DEFAULT_REFS, *, cache_dir: str | None = None
                        ) -> Iterator[dict]:
    """Yield {label, sub_id, series, n_obs, source_meta} for each reference window.

    A single yfinance call per symbol; we then chop the resulting return series.
    The `full` series gets label `<stem>_full`; each rolling sub-window gets its
    own label `<stem>_p<k>` (period k). This makes the atlas treat each period
    as a distinct family so we can SEE whether they cluster (one regime) or
    spread (multiple regimes within "the real S&P").
    """
    for ref in refs:
        sym = ref["symbol"]
        stem = ref["stem"]
        ts, closes = fetch_yahoo_closes(sym, years=ref["years"], cache_dir=cache_dir)
        rets = log_returns(closes)
        # 1 "full" window with its own period label
        yield {
            "label": f"{stem}_full",
            "sub_id": "full",
            "series": rets,
            "n_obs": int(len(rets)),
            "source_meta": {
                "symbol": sym, "years": ref["years"],
                "first_ts": int(ts[0]), "last_ts": int(ts[-1]),
                "n_closes": int(len(closes)), "kind": "yahoo_chart_v8",
            },
        }
        # rolling sub-windows — each becomes its OWN label
        sub = ref.get("sub")
        if sub:
            for k, (start, win) in enumerate(windows(rets, sub["window_len"], sub["stride"])):
                yield {
                    "label": f"{stem}_p{k}",
                    "sub_id": f"w{k}_{start}",
                    "series": win,
                    "n_obs": int(len(win)),
                    "source_meta": {
                        "symbol": sym, "years": ref["years"],
                        "first_ts": int(ts[start]),
                        "last_ts": int(ts[min(start + sub["window_len"], len(ts) - 1)]),
                        "window_start_idx": int(start), "window_len": int(sub["window_len"]),
                        "kind": "yahoo_chart_v8_window",
                    },
                }
