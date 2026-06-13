"""古典4モデル (CB/LM/MG/GCMG) の移植 parity (spec 001 O3)。

packages/abm_models の正準コピーが、imported/ の元実装と **bit-identical** な出力を
返すことを検証する (同一 seed・小規模)。局所依存がなく byte-identical 移植のため
完全一致が期待値。元実装を file path で動的 import して比較する。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

_EXP = (
    Path(__file__).resolve().parents[1]
    / "imported" / "speculation-game-info" / "experiments"
)


def _load_original(yh: str) -> ModuleType:
    path = _EXP / yh / "model.py"
    name = f"_orig_{yh}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # dataclass の cls.__module__ 解決のため exec 前に sys.modules へ登録
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_cont_bouchaud_parity():
    from abm_models.cont_bouchaud import simulate as packaged
    orig = _load_original("YH001")
    kw = dict(N=2000, c=0.9, a=0.01, lam=1.0, T=400, seed=42, report_every=10**9)
    a, b = orig.simulate(**kw), packaged(**kw)
    np.testing.assert_array_equal(a["returns"], b["returns"])


def test_lux_marchesi_parity():
    from abm_models.lux_marchesi import simulate as packaged
    orig = _load_original("YH002")
    kw = dict(n_integer_steps=400, steps_per_unit=20, seed=42, n_c_init=50, verbose=False)
    a, b = orig.simulate(**kw), packaged(**kw)
    np.testing.assert_array_equal(a["prices"], b["prices"])
    np.testing.assert_array_equal(a["returns"], b["returns"])


def test_minority_game_parity():
    from abm_models.minority_game import simulate as packaged
    orig = _load_original("YH003")
    kw = dict(N=101, M=4, S=2, T=500, seed=42)
    a, b = orig.simulate(**kw), packaged(**kw)
    np.testing.assert_array_equal(a["attendance"], b["attendance"])


def test_gcmg_parity():
    from abm_models.gcmg import simulate as packaged
    orig = _load_original("YH004")
    kw = dict(N=101, M=2, S=2, T_win=20, T_total=600, r_min_static=0.0, seed=42)
    a, b = orig.simulate(**kw), packaged(**kw)
    np.testing.assert_array_equal(a["attendance"], b["attendance"])
