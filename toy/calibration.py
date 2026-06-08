"""calibration — SF-等価 calibration(spec §5、留保1: 相互等価性 anchor)。

Model T を固定点 T* に置き、Model H の母集団比率 β を **SF1-4 距離最小化**で T* に揃える
(留保1、§5.2)。距離は SF1-4(4 次元、留保2)上の per-dim 1-Wasserstein(T* の per-dim std で
標準化)。本実装は coarse grid 版(小 M)。full(M=1000, BO)は perf 後。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from provabm.capture import CaptureLevel, CaptureSink

from toy.agents.herd import build_herd_population
from toy.agents.trend import build_trend_population
from toy.market import MarketParams, run_simulation
from toy.sf_battery import CALIBRATION_SF, measure_sf_battery

# T* 固定点(留保1: 任意のリーズナブルな点。mild SF が出る fund 優勢点)。
T_STAR_ALPHA: tuple[float, float, float] = (0.3, 0.55, 0.15)
CALIB_MARKET = MarketParams(
    n_agents=150, lam=0.05, p_star=100.0, obs_window=40, burn_in=300, measure=1500, init_price=100.0
)


@dataclass(frozen=True, slots=True)
class CalibratedPair:
    """SF-等価点 (T*, H*)。"""

    trend_params: dict[str, float]
    herd_params: dict[str, float]
    distance: float
    sf_t: dict[str, float] = field(default_factory=dict)
    sf_h: dict[str, float] = field(default_factory=dict)


def _sf1_4(returns: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    sf = measure_sf_battery(returns, include_post=False)
    return np.array([sf[k] for k in CALIBRATION_SF], dtype=np.float64)


def sf_distribution(
    model: str,
    mix: tuple[float, float, float],
    params: MarketParams,
    n_runs: int,
    base_seed: int,
) -> npt.NDArray[np.float64]:
    """(model, mix) で n_runs 回まわし SF1-4 ベクトルの分布 (n_runs, 4) を返す。"""
    rows = []
    for ri in range(n_runs):
        ss = np.random.SeedSequence(base_seed + ri).spawn(1 + params.n_agents)
        prng = np.random.default_rng(ss[0])
        agents = (
            build_trend_population(params.n_agents, prng, mix)
            if model == "T"
            else build_herd_population(params.n_agents, prng, mix)
        )
        drngs = [np.random.default_rng(s) for s in ss[1:]]
        result = run_simulation(params, agents, drngs, CaptureSink(CaptureLevel.L0))
        rows.append(_sf1_4(result.returns))
    return np.asarray(rows, dtype=np.float64)


def sliced_wasserstein(ref: npt.NDArray[np.float64], other: npt.NDArray[np.float64]) -> float:
    """SF1-4 の per-dim 1-Wasserstein を ref の per-dim std で標準化して合算(§5.2 距離)。"""
    scale = ref.std(axis=0) + 1e-9
    total = 0.0
    for d in range(ref.shape[1]):
        a = np.sort(ref[:, d]) / scale[d]
        b = np.sort(other[:, d]) / scale[d]
        m = min(a.size, b.size)
        total += float(np.mean(np.abs(a[:m] - b[:m])))
    return total


def _herd_beta_grid() -> list[tuple[float, float, float]]:
    """H の (herder, fundamentalist, noise) 候補(simplex の coarse grid)。"""
    grid: list[tuple[float, float, float]] = []
    for herd in (0.2, 0.3, 0.4, 0.5):
        for fund in (0.3, 0.45, 0.55, 0.65):
            noise = round(1.0 - herd - fund, 2)
            if noise >= 0.05:
                grid.append((herd, fund, noise))
    return grid


def calibrate_sf_equivalent(
    *, seed: int, n_runs: int = 10, params: MarketParams = CALIB_MARKET
) -> tuple[CalibratedPair, list[tuple[tuple[float, float, float], float]]]:
    """T* を固定し、H の β を SF1-4 距離最小化で揃える(coarse grid)。

    返り値: (最良 CalibratedPair, [(beta, distance) ...] 全候補 log)。
    """
    ref = sf_distribution("T", T_STAR_ALPHA, params, n_runs, base_seed=seed)
    sf_t_mean = {k: float(ref[:, i].mean()) for i, k in enumerate(CALIBRATION_SF)}

    log: list[tuple[tuple[float, float, float], float]] = []
    best: CalibratedPair | None = None
    for j, beta in enumerate(_herd_beta_grid()):
        h_dist = sf_distribution("H", beta, params, n_runs, base_seed=seed + 1000 * (j + 1))
        dist = sliced_wasserstein(ref, h_dist)
        log.append((beta, dist))
        if best is None or dist < best.distance:
            best = CalibratedPair(
                trend_params={
                    "chartist": T_STAR_ALPHA[0],
                    "fund": T_STAR_ALPHA[1],
                    "noise": T_STAR_ALPHA[2],
                },
                herd_params={"herder": beta[0], "fund": beta[1], "noise": beta[2]},
                distance=dist,
                sf_t=sf_t_mean,
                sf_h={k: float(h_dist[:, i].mean()) for i, k in enumerate(CALIBRATION_SF)},
            )
    assert best is not None
    return best, log
