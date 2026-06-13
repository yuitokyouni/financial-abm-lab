"""REGISTRY の全モデルが ABMModel protocol に準拠し core から動く (spec 001 O1/O2)。

新モデル追加 = REGISTRY に1クラス足して protocol 準拠させるだけ、を保証する。
各モデルを小規模パラメータで実体化し run(seed) が dict を返すことを確認。
"""

from __future__ import annotations

import numpy as np

from abm_models import (
    ABMModel,
    ChiarellaIori,
    ContBouchaud,
    FrankeWesterhoff,
    GrandCanonicalMG,
    LuxMarchesi,
    MinorityGame,
    SpeculationGame,
    ZeroIntelligence,
    REGISTRY,
)

# 各モデルの「小規模・高速」インスタンス
SMALL = [
    SpeculationGame(N=40, M=2, S=2, T=200),
    ContBouchaud(N=1000, c=0.9, T=300, report_every=10**9),
    LuxMarchesi(n_integer_steps=300, steps_per_unit=20),
    MinorityGame(N=51, M=3, S=2, T=300),
    GrandCanonicalMG(N=51, M=2, S=2, T_win=10, T_total=400, r_min_static=0.0),
    ChiarellaIori(n_steps=300),
    ZeroIntelligence(n_steps=300),
    FrankeWesterhoff(n_steps=300),
]


def test_registry_covers_all_models():
    names = {m.name for m in SMALL}
    assert set(REGISTRY) == names


def test_all_models_conform_and_run():
    for model in SMALL:
        assert isinstance(model, ABMModel), f"{model.name} not ABMModel"
        res = model.run(seed=7)
        assert isinstance(res, dict) and res, f"{model.name} returned empty"
        # 何らかの系列 (prices/returns/attendance) を持つ
        assert any(k in res for k in ("prices", "returns", "attendance")), model.name


def test_returns_or_prices_extractable_for_price_models():
    from abm_models.base import returns_of
    for model in (SpeculationGame(N=40, M=2, S=2, T=200), ContBouchaud(N=1000, T=300, report_every=10**9),
                  LuxMarchesi(n_integer_steps=300, steps_per_unit=20)):
        r = returns_of(model.run(seed=7))
        assert isinstance(r, np.ndarray) and r.size > 0
