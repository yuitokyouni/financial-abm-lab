"""BTC-USD hourly returns from the Coinbase tape, cut into clean windows.

Gaps in the venue's tape (21 of them over 2016-2026) are never bridged: a
return is only formed between two adjacent candles one granularity apart, and
a window is only emitted if it is gap-free. Bridging a gap would manufacture
one large "return" that no trader ever faced, and the tail statistics this
whole exercise turns on are exactly what such a fake print would move.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"


def load(path: Path | str = DATA / "btc_usd_1h.csv", granularity: int = 3600):
    rows = []
    with open(path) as fh:
        for rec in csv.DictReader(fh):
            rows.append((int(rec["time"]), float(rec["close"])))
    rows.sort()
    ts = np.array([r[0] for r in rows])
    px = np.array([r[1] for r in rows])
    contiguous = np.diff(ts) == granularity
    r = np.where(contiguous, np.diff(np.log(px)), np.nan)
    return ts[1:], r


def windows(ts: np.ndarray, r: np.ndarray, length: int):
    """Non-overlapping, gap-free windows of `length` returns."""
    out = []
    i = 0
    while i + length <= len(r):
        seg = r[i:i + length]
        if np.isfinite(seg).all():
            out.append({"start": int(ts[i]), "end": int(ts[i + length - 1]),
                        "returns": seg,
                        "label": datetime.fromtimestamp(ts[i], timezone.utc)
                                         .strftime("%Y-%m")})
            i += length
        else:
            i += int(np.argmax(~np.isfinite(seg))) + 1
    return out


if __name__ == "__main__":
    ts, r = load()
    ok = np.isfinite(r)
    print(f"{len(r)} hourly returns, {int((~ok).sum())} dropped at tape gaps")
    print(f"span {datetime.fromtimestamp(ts[0], timezone.utc):%Y-%m-%d} .. "
          f"{datetime.fromtimestamp(ts[-1], timezone.utc):%Y-%m-%d}")
    for L in (1000, 2000, 4000):
        print(f"  windows of {L}: {len(windows(ts, r, L))}")
