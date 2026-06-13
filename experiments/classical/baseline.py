"""古典4モデル baseline — core を import する薄いラッパー (spec 001 O1)。

旧 imported/speculation-game-info/experiments/YH001-004 は各々が model.py を持って
いた。本版はそれらを再実装せず `abm_models` の正準実装 (REGISTRY) と
`stylized_facts` の統一 SF を import するだけ。価格系列を持つモデル (CB/LM) は
stylized facts を、出席数モデル (MG/GCMG) は volatility 系指標を出す。

実行:
    uv run python -m experiments.classical.baseline
"""

from __future__ import annotations

import numpy as np

from abm_models import ContBouchaud, GrandCanonicalMG, LuxMarchesi, MinorityGame
from abm_models.base import returns_of
from stylized_facts import hill_mle_tail_index, kurtosis_windowed


def run_cont_bouchaud(seed: int = 42) -> dict:
    res = ContBouchaud(N=10000, c=0.9, T=20000).run(seed=seed)
    r = returns_of(res)
    return {
        "model": "cont_bouchaud",
        "excess_kurtosis": kurtosis_windowed(r, 1),
        "hill_alpha": hill_mle_tail_index(r),
    }


def run_lux_marchesi(seed: int = 42) -> dict:
    res = LuxMarchesi(n_integer_steps=20000).run(seed=seed)
    r = returns_of(res)
    return {
        "model": "lux_marchesi",
        "excess_kurtosis": kurtosis_windowed(r, 1),
        "hill_alpha": hill_mle_tail_index(r),
        "zbar": float(res.get("zbar", float("nan"))),
    }


def _sigma2_over_N(attendance: np.ndarray, N: int, burn: int) -> float:
    a = np.asarray(attendance[burn:], dtype=np.float64)
    return float(a.var() / N)


def run_minority_game(seed: int = 42) -> dict:
    N, T, burn = 101, 10000, 2000
    res = MinorityGame(N=N, M=6, S=2, T=T).run(seed=seed)
    return {"model": "minority_game", "sigma2_over_N": _sigma2_over_N(res["attendance"], N, burn)}


def run_gcmg(seed: int = 42) -> dict:
    N = 101
    res = GrandCanonicalMG(N=N, M=2, S=2, T_win=50, T_total=21000, r_min_static=0.0).run(seed=seed)
    active = np.asarray(res["active"], dtype=np.float64)
    return {"model": "gcmg", "mean_active": float(active[1000:].mean())}


def run_all(seed: int = 42) -> list[dict]:
    out = [run_cont_bouchaud(seed), run_lux_marchesi(seed), run_minority_game(seed), run_gcmg(seed)]
    for row in out:
        print(row)
    return out


if __name__ == "__main__":
    run_all()
