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
    hs_range: tuple[int, int] | None = None,
    fast: bool = False,
) -> npt.NDArray[np.float64]:
    """(model, mix[, hs_range]) で n_runs 回まわし SF1-4 ベクトルの分布 (n_runs, 4) を返す。

    fast=True で kernel.run_fast(高速経路)。calibration の bulk run 用。
    """
    rows = []
    for ri in range(n_runs):
        if fast:
            from toy.kernel import run_fast

            returns = run_fast(params, model, mix, seed=base_seed + ri, hs_range=hs_range)
        else:
            ss = np.random.SeedSequence(base_seed + ri).spawn(1 + params.n_agents)
            prng = np.random.default_rng(ss[0])
            agents = (
                build_trend_population(params.n_agents, prng, mix)
                if model == "T"
                else build_herd_population(params.n_agents, prng, mix, hs_range)
            )
            drngs = [np.random.default_rng(s) for s in ss[1:]]
            returns = run_simulation(params, agents, drngs, CaptureSink(CaptureLevel.L0)).returns
        rows.append(_sf1_4(returns))
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
    *, seed: int, n_runs: int = 10, params: MarketParams = CALIB_MARKET, fast: bool = False
) -> tuple[CalibratedPair, list[tuple[tuple[float, float, float], float]]]:
    """T* を固定し、H の β を SF1-4 距離最小化で揃える(coarse grid)。

    fast=True で kernel 高速経路。返り値: (最良 CalibratedPair, [(beta, distance) ...] 全候補 log)。
    """
    ref = sf_distribution("T", T_STAR_ALPHA, params, n_runs, base_seed=seed, fast=fast)
    sf_t_mean = {k: float(ref[:, i].mean()) for i, k in enumerate(CALIBRATION_SF)}

    log: list[tuple[tuple[float, float, float], float]] = []
    best: CalibratedPair | None = None
    for j, beta in enumerate(_herd_beta_grid()):
        h_dist = sf_distribution(
            "H", beta, params, n_runs, base_seed=seed + 1000 * (j + 1), fast=fast
        )
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


@dataclass(frozen=True, slots=True)
class HerdCandidate:
    """探索した H の点(β + horizon レンジ)。"""

    beta: tuple[float, float, float]
    hs_range: tuple[int, int]
    distance: float
    sf_h: dict[str, float]


def calibrate_search(
    *,
    seed: int,
    n_trials: int = 60,
    n_runs: int = 10,
    params: MarketParams = CALIB_MARKET,
    fast: bool = False,
) -> tuple[HerdCandidate, dict[str, float], list[HerdCandidate]]:
    """T* を固定し、H の (β, horizon レンジ) をランダム探索で SF1-4 距離最小化(§5.2 拡張)。

    β 単独の grid では SF1/SF2 が埋まらなかったため、horizon レンジも探索空間に入れる。
    fast=True で kernel 高速経路。返り値: (最良 HerdCandidate, T* の SF1-4 平均, 全 trial log)。
    """
    ref = sf_distribution("T", T_STAR_ALPHA, params, n_runs, base_seed=seed, fast=fast)
    sf_t_mean = {k: float(ref[:, i].mean()) for i, k in enumerate(CALIBRATION_SF)}
    srng = np.random.default_rng(seed)

    log: list[HerdCandidate] = []
    best: HerdCandidate | None = None
    for trial in range(n_trials):
        herder = float(srng.uniform(0.15, 0.55))
        fund = float(srng.uniform(0.30, 0.70))
        noise = round(1.0 - herder - fund, 3)
        if noise < 0.05:
            continue
        beta = (round(herder, 3), round(fund, 3), noise)
        lo = int(srng.integers(3, 21))
        hi = int(srng.integers(lo + 5, 61))
        h_dist = sf_distribution(
            "H",
            beta,
            params,
            n_runs,
            base_seed=seed + 1000 * (trial + 1),
            hs_range=(lo, hi),
            fast=fast,
        )
        dist = sliced_wasserstein(ref, h_dist)
        cand = HerdCandidate(
            beta=beta,
            hs_range=(lo, hi),
            distance=dist,
            sf_h={k: float(h_dist[:, i].mean()) for i, k in enumerate(CALIBRATION_SF)},
        )
        log.append(cand)
        if best is None or dist < best.distance:
            best = cand
    assert best is not None
    return best, sf_t_mean, log
