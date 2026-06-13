"""ABM-Microstructure harness。

実験A（001、検証済）: `run(SimConfig) -> RunResult`、anchor は `anchors`。
実験B（002）: `train(LearnConfig)` → `measure`/`impulse_response`/`certify`、
分母・floor は `benchmarks`、地図と予算は `designmap`、較正は `calibrations`。
"""
from __future__ import annotations

from .config import SimConfig
from .engine import RunResult, measure_competitive_spread, run
from .learnconfig import LearnConfig
from .qlearn import TrainResult, train
from .verdict import (CellMeasurement, CollusionVerdict, IRResult, certify,
                      impulse_response, measure, memory_threshold)
from .designmap import (BudgetLedger, DesignMapPoint, compare_conditions,
                        run_cell, write_csv)

__all__ = [
    "SimConfig", "RunResult", "run", "measure_competitive_spread",
    "LearnConfig", "TrainResult", "train",
    "CellMeasurement", "CollusionVerdict", "IRResult",
    "measure", "impulse_response", "certify", "memory_threshold",
    "BudgetLedger", "DesignMapPoint", "compare_conditions", "run_cell", "write_csv",
]
