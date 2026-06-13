"""YH003 (MG) / YH004 (GCMG) を importlib で遅延 load し、SG と比較可能な形に揃える.

役割:
  - YH003/YH004 の `model.py` を別名で import (同名 'model' モジュールの衝突回避)
  - reconstruct_price(): excess 時系列 → 仮想価格 (p = p0 + cumsum(excess / N)) を計算
  - run_mg / run_gcmg: 3 モデル比較スクリプトから薄く呼べるラッパ

符号規約 (Step 2-9-7 確認済み):
  YH003: action ∈ ±1 (A=+1 / B=-1), excess = preds.sum() = 2*attendance - N.
         "A 側優勢で excess > 0" を "buy 優勢 (SG の D > 0)" と識別して採用 (一致)
  YH004: action ∈ {-1, 0, +1}, excess = actions.sum() (直接返される).
         "buy 優勢で excess > 0" で SG と符号一致. 符号反転不要.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


_YH005_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_DIR = _YH005_DIR.parent


def _load_external_model(yh_id: str):
    """experiments/<yh_id>/model.py を固有名で load (衝突回避)."""
    p = _EXPERIMENTS_DIR / yh_id / "model.py"
    assert p.exists(), f"{p} not found"
    spec = importlib.util.spec_from_file_location(f"{yh_id}_model", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_yh003_model = _load_external_model("YH003")
_yh004_model = _load_external_model("YH004")


def reconstruct_price(excess: np.ndarray, N: int, p0: float = 100.0) -> np.ndarray:
    """excess 時系列 → 仮想価格 (SG 規約: Δp = D/N, p = p0 + cumsum Δp)."""
    dp = excess.astype(np.float64) / float(N)
    return p0 + np.cumsum(dp)


def run_mg(N: int, M: int, T: int, seed: int, S: int = 1, p0: float = 100.0) -> dict:
    """YH003 MG を S=1 で走らせて SG と同じ形式の dict を返す."""
    res = _yh003_model.simulate(N=N, M=M, S=S, T=T, seed=seed, record_attendance=True)
    excess = (2 * res["attendance"].astype(np.int64)) - N
    prices = reconstruct_price(excess, N, p0)
    return {
        "prices": prices,
        "excess": excess,
        "raw": res,
    }


def run_gcmg(
    N: int,
    M: int,
    T: int,
    seed: int,
    S: int = 1,
    T_win: int = 50,
    r_min_static: float = 0.0,
    p0: float = 100.0,
) -> dict:
    """YH004 GCMG を S=1, r_min=0 で走らせる."""
    res = _yh004_model.simulate(
        N=N, M=M, S=S, T_win=T_win, T_total=T,
        r_min_static=r_min_static, seed=seed,
    )
    excess = res["excess"].astype(np.int64)
    prices = reconstruct_price(excess, N, p0)
    return {
        "prices": prices,
        "excess": excess,
        "active": res["active"],
        "raw": res,
    }
