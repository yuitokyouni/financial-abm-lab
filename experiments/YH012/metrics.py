"""Phase 1 出口基準用の統計。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lobcore import mid_from_record


@dataclass
class WorldStats:
    n_events: int
    n_fills: int
    spread_positive_frac: float
    mean_spread: float
    volatility: float
    mid_f_corr: float
    n_mid_obs: int


def _unique_time_snapshots(log: np.ndarray) -> list[np.void]:
    """同一 received_at の最後のレコードを採用。"""
    if len(log) == 0:
        return []
    order = np.argsort(log["received_at"], kind="mergesort")
    sorted_log = log[order]
    snaps: list[np.void] = []
    last_t = None
    for rec in sorted_log:
        t = int(rec["received_at"])
        if last_t is None or t != last_t:
            snaps.append(rec)
            last_t = t
        else:
            snaps[-1] = rec
    return snaps


def compute_world_stats(
    log: np.ndarray,
    fundamental_values: list[int],
    *,
    burn_in_frac: float = 0.1,
) -> WorldStats:
    snaps = _unique_time_snapshots(log)
    n_fills = int(np.sum(log["kind"] == 1)) if len(log) else 0

    if snaps:
        t0 = int(snaps[0]["received_at"])
        t1 = int(snaps[-1]["received_at"])
        burn_t = t0 + int((t1 - t0) * burn_in_frac)
        snaps = [s for s in snaps if int(s["received_at"]) >= burn_t]

    spreads: list[float] = []
    mids: list[float] = []
    fs: list[float] = []
    returns: list[float] = []
    prev_mid: float | None = None

    # 時刻で重み付け: イベント直後の片側枯れを過大評価しない
    spread_time = 0
    total_time = 0

    for i, rec in enumerate(snaps):
        bid_q = int(rec["best_bid_qty"])
        ask_q = int(rec["best_ask_qty"])
        bid_p = int(rec["best_bid_price"])
        ask_p = int(rec["best_ask_price"])
        has_spread = bid_q > 0 and ask_q > 0 and ask_p >= bid_p
        if has_spread:
            spreads.append(float(ask_p - bid_p))

        if i + 1 < len(snaps):
            dt = int(snaps[i + 1]["received_at"]) - int(rec["received_at"])
            if dt > 0:
                total_time += dt
                if has_spread:
                    spread_time += dt

        mid = mid_from_record(rec)
        if mid is None:
            continue
        t = int(rec["received_at"])
        f = fundamental_values[min(t, len(fundamental_values) - 1)]
        mids.append(mid)
        fs.append(float(f))
        if prev_mid is not None and prev_mid != 0:
            returns.append((mid - prev_mid) / prev_mid)
        prev_mid = mid

    spread_frac = (spread_time / total_time) if total_time > 0 else 0.0
    mean_spread = float(np.mean(spreads)) if spreads else 0.0
    vol = float(np.std(returns)) if len(returns) >= 2 else 0.0
    if len(mids) >= 2 and np.std(mids) > 0 and np.std(fs) > 0:
        corr = float(np.corrcoef(mids, fs)[0, 1])
    else:
        corr = 0.0

    return WorldStats(
        n_events=len(log),
        n_fills=n_fills,
        spread_positive_frac=spread_frac,
        mean_spread=mean_spread,
        volatility=vol,
        mid_f_corr=corr,
        n_mid_obs=len(mids),
    )


def orders_of_magnitude_compatible(values: list[float], *, min_positive: float = 1e-12) -> bool:
    """最大/最小が 100 倍以内（ゼロは除外）。オーダーが同種かの粗い判定。"""
    pos = [v for v in values if v > min_positive]
    if len(pos) < 2:
        return len(pos) >= 1
    return (max(pos) / min(pos)) <= 100.0
