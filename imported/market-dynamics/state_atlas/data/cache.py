"""Parquet cache for PriceSource output.

Key strategy: sha256({sorted(tickers), start, end_or_today})[:12]
- Same universe + range → same cache file.
- Different universe → different file (no overwriting). Phase 4.5 runs multiple
  universes in parallel; caches must not collide.

Old cache files are never deleted (reproducibility). Use force_refresh=True to
write a new file with the same key.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from state_atlas.data.base import MarketDataFrame, validate

log = logging.getLogger(__name__)


def cache_key(tickers: list[str], start: str, end: str | None) -> str:
    end_resolved = end if end is not None else dt.date.today().isoformat()
    payload = {
        "tickers": sorted(tickers),
        "start": start,
        "end": end_resolved,
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def cache_paths(cache_dir: str | Path, key: str) -> tuple[Path, Path]:
    base = Path(cache_dir)
    return base / f"{key}.parquet", base / f"{key}.meta.json"


def load(cache_dir: str | Path, key: str) -> MarketDataFrame | None:
    parquet_path, meta_path = cache_paths(cache_dir, key)
    if not parquet_path.exists() or not meta_path.exists():
        return None
    df = pd.read_parquet(parquet_path)
    # parquet round-trips MultiIndex columns natively when written via to_parquet(...).
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    mdf = MarketDataFrame(df=df, has_volume=meta["has_volume"])
    validate(mdf)
    return mdf


def save(mdf: MarketDataFrame, cache_dir: str | Path, key: str) -> Path:
    base = Path(cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    parquet_path, meta_path = cache_paths(base, key)
    mdf.df.to_parquet(parquet_path)
    meta = {
        "has_volume": mdf.has_volume,
        "tickers": mdf.tickers,
        "n_rows": mdf.n_rows,
        "range": [str(mdf.date_range[0].date()), str(mdf.date_range[1].date())],
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return parquet_path
