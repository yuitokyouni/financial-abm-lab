"""State classifier on top of the frozen F atlas.

States:
  CALM       F < p50 AND term_slope ≥ 0
  ELEVATED   p50 ≤ F < p90 AND (any slope), OR (F < p50 AND term_slope < 0)
  STRESS     F ≥ p90 OR term_slope < 0 (and not already CALM)

The ``persistent_stress`` flag is independent: it fires when backwardation
has lasted ``backw_persist_days`` consecutive bars, OR when F has been above
its p99 threshold for ``F_p99_persist_days`` consecutive bars. It is meant
as the strategy kill-switch (Step 3 design).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from state_atlas.online.monitor import TrainedAtlas

StateLabel = Literal["CALM", "ELEVATED", "STRESS"]


@dataclass(frozen=True)
class StateConfig:
    backw_persist_days: int = 10
    F_p99_persist_days: int = 5


_DEFAULT_STATE_CFG = StateConfig()


@dataclass(frozen=True)
class State:
    label: StateLabel
    persistent_stress: bool
    F: float
    term_slope: float
    backw_run: int
    F_p99_run: int


def _bucket(F: float, slope: float, atlas: TrainedAtlas) -> StateLabel:
    """Pure label, no persistence tracking."""
    if F >= atlas.F_p90 or slope < 0:
        # backwardation OR very high F → STRESS regardless of which trigger
        if F < atlas.F_p50 and slope < 0:
            # mild F but inverted curve = early warning, classify as ELEVATED
            return "ELEVATED"
        return "STRESS"
    if F >= atlas.F_p50:
        return "ELEVATED"
    return "CALM"


def classify(
    F: float,
    term_slope: float,
    backw_run: int,
    F_p99_run: int,
    atlas: TrainedAtlas,
    cfg: StateConfig = _DEFAULT_STATE_CFG,
) -> State:
    """One-bar classifier. Caller maintains the run-length counters."""
    label = _bucket(F, term_slope, atlas)
    persistent = (term_slope < 0 and backw_run >= cfg.backw_persist_days) or (
        F >= atlas.F_p99 and F_p99_run >= cfg.F_p99_persist_days
    )
    return State(
        label=label,
        persistent_stress=bool(persistent),
        F=float(F),
        term_slope=float(term_slope),
        backw_run=int(backw_run),
        F_p99_run=int(F_p99_run),
    )


def classify_series(
    F_series: pd.Series,
    slope_series: pd.Series,
    atlas: TrainedAtlas,
    cfg: StateConfig = _DEFAULT_STATE_CFG,
) -> pd.DataFrame:
    """Walk a (F, slope) timeseries causally and return state per bar.

    The run-length counters are maintained left-to-right; no peek beyond t.
    """
    if not F_series.index.equals(slope_series.index):
        raise ValueError("F_series and slope_series must share an index")
    backw_run = 0
    F_p99_run = 0
    out_label: list[str] = []
    out_persist: list[bool] = []
    out_backw_run: list[int] = []
    out_F_p99_run: list[int] = []
    F_p99 = atlas.F_p99
    for f, s in zip(F_series.values, slope_series.values, strict=True):
        backw_run = backw_run + 1 if s < 0 else 0
        F_p99_run = F_p99_run + 1 if f >= F_p99 else 0
        st = classify(float(f), float(s), backw_run, F_p99_run, atlas, cfg)
        out_label.append(st.label)
        out_persist.append(st.persistent_stress)
        out_backw_run.append(backw_run)
        out_F_p99_run.append(F_p99_run)
    return pd.DataFrame(
        {
            "F": F_series.values,
            "term_slope": slope_series.values,
            "label": out_label,
            "persistent_stress": out_persist,
            "backw_run": out_backw_run,
            "F_p99_run": out_F_p99_run,
        },
        index=F_series.index,
    )
