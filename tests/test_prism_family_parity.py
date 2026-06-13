"""CI/ZI/FW (PRISM family) の移植 parity (spec 001 O1)。

packages/abm_models の CI/ZI/FW が、imported/PRISM の元 adapter と bit-identical な
returns を返すことを検証する (verbatim 移植 + 型は _prism_compat に同梱)。
元実装は imported/PRISM/src を path に載せて import する。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_PRISM_SRC = (
    Path(__file__).resolve().parents[1] / "imported" / "PRISM" / "src"
)


@pytest.fixture(scope="module")
def prism_on_path():
    sys.path.insert(0, str(_PRISM_SRC))
    try:
        yield
    finally:
        sys.path.remove(str(_PRISM_SRC))
        for m in [k for k in sys.modules if k == "prism" or k.startswith("prism.")]:
            del sys.modules[m]


def test_zi_parity(prism_on_path):
    from prism.adapters.zi import ZIAdapter as Orig, ZIParams as OP
    from abm_models.zero_intelligence import ZIAdapter as Pkg, ZIParams as PP
    a = Orig(params=OP(n_steps=400)).simulate(seed=42, n_paths=1)
    b = Pkg(params=PP(n_steps=400)).simulate(seed=42, n_paths=1)
    np.testing.assert_array_equal(a.returns, b.returns)


def test_ci_parity(prism_on_path):
    from prism.adapters.ci import CIAdapter as Orig, CIParams as OP
    from abm_models.chiarella_iori import CIAdapter as Pkg, CIParams as PP
    a = Orig(params=OP(n_steps=400)).simulate(seed=42, n_paths=1)
    b = Pkg(params=PP(n_steps=400)).simulate(seed=42, n_paths=1)
    np.testing.assert_array_equal(a.returns, b.returns)


def test_fw_parity(prism_on_path):
    from prism.adapters.fw import FWAdapter as Orig, FWParams as OP
    from abm_models.franke_westerhoff import FWAdapter as Pkg, FWParams as PP
    a = Orig(params=OP(n_steps=400)).simulate(seed=42, n_paths=1)
    b = Pkg(params=PP(n_steps=400)).simulate(seed=42, n_paths=1)
    np.testing.assert_array_equal(a.returns, b.returns)
