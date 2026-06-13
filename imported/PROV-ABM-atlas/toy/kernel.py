"""kernel — ベクトル化/Numba 高速シミュレーション経路(bulk screening 用)。

`market.run_simulation` は ctx 経由で全 agent の観測/乱数を honest 記録する**参照実装**
(L2 provenance、最終報告 run 用)。本モジュールはその核(per-step × per-agent 判断 +
価格更新)を Numba `@njit` で機械語化した**高速経路**で、honest 記録を省く代わりに
桁違いに速い。screening/calibration/sweep の数万 run はこちらで回す。

**忠実性の規律**: 本経路は参照と **bit 一致ではない**(noise の RNG threading が異なる)。
保証するのは (i) seed 固定で決定的(同一 seed → bit 同一の高速経路出力)、(ii) 同一モデル
則の忠実実装、(iii) **SF1-4 分布が参照と統計的に等価**(tests/unit/test_kernel_faithful.py
で pin)。padding-in-mean の burn-in 微差は捨てる(measure 期間には伝播しない)。

機構則(spec §3.2、agents/{trend,herd}.py と一致):
- comp 0 = chartist(T)/ herder(H)、comp 1 = fundamentalist(共有)、comp 2 = noise(共有)。
- chartist: 正規化トレンド mean/std を return 窓で、|trend|>θ なら sign。
- herder:   集約行動窓の mean の符号(閾値なし)。
- fundamentalist: 誤価格 log(p*/level) 窓の mean、|m|>θ なら sign。
- noise: 一様 {-1,0,+1}。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from toy.agents.herd import HComponent, build_herd_population
from toy.agents.trend import TComponent, build_trend_population
from toy.market import MarketParams, njit

# 成分コード(参照モデルの component を int 化)。
COMP_SPEC = 0  # chartist(T) / herder(H)
COMP_FUND = 1  # fundamentalist
COMP_NOISE = 2


@njit(cache=True)
def _run_kernel(
    component: npt.NDArray[np.int64],
    horizon: npt.NDArray[np.int64],
    theta: npt.NDArray[np.float64],
    model_code: int,  # 0=T(chartist), 1=H(herder)
    lam: float,
    p_star: float,
    n: int,
    obs_window: int,
    burn_in: int,
    measure: int,
    init_price: float,
    seed: int,
) -> npt.NDArray[np.float64]:
    """高速 step ループ。measure 期間の log-return 系列を返す。"""
    np.random.seed(seed)
    total = burn_in + measure
    returns_full = np.zeros(total)
    agg_full = np.zeros(total)
    price_full = np.empty(total + 1)
    price_full[0] = init_price
    out = np.zeros(measure)
    n_out = 0
    price = init_price

    for t in range(total):
        ed = 0.0
        for i in range(n):
            comp = component[i]
            limit = horizon[i] if horizon[i] < obs_window else obs_window  # min(h, obs_window)
            a = 0
            if comp == COMP_NOISE:
                a = int(np.random.random() * 3.0) - 1
            elif comp == COMP_FUND:
                cnt = t + 1  # 価格 level 数(price_full[0..t])
                ll = limit if limit < cnt else cnt
                s = 0.0
                for j in range(t + 1 - ll, t + 1):
                    s += np.log(p_star / price_full[j])
                m = s / ll
                if m > theta[i] or -m > theta[i]:
                    a = 1 if m > 0.0 else -1
            else:  # COMP_SPEC
                cnt = t  # returns/agg 数(index 0..t-1)
                if cnt > 0:
                    ll = limit if limit < cnt else cnt
                    if model_code == 0:  # chartist: 正規化トレンド
                        s = 0.0
                        for j in range(t - ll, t):
                            s += returns_full[j]
                        mean = s / ll
                        var = 0.0
                        for j in range(t - ll, t):
                            d = returns_full[j] - mean
                            var += d * d
                        sd = np.sqrt(var / ll)
                        if sd > 0.0:
                            trend = mean / sd
                            if trend > theta[i] or -trend > theta[i]:
                                a = 1 if trend > 0.0 else -1
                    else:  # herder: 集約行動 mean の符号、閾値 theta[i] で間欠化
                        s = 0.0
                        for j in range(t - ll, t):
                            s += agg_full[j]
                        mean = s / ll
                        if mean > theta[i] or -mean > theta[i]:
                            a = 1 if mean > 0.0 else -1
            ed += a

        new_price = price * np.exp(lam * ed / n)
        returns_full[t] = np.log(new_price / price)
        agg_full[t] = ed / n
        price_full[t + 1] = new_price
        price = new_price
        if t >= burn_in:
            out[n_out] = returns_full[t]
            n_out += 1
    return out


def _extract_arrays(
    model: str,
    mix: tuple[float, float, float],
    n: int,
    prng: np.random.Generator,
    hs_range: tuple[int, int] | None,
    theta_h_range: tuple[float, float] | None,
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], npt.NDArray[np.float64], int]:
    """参照の build 関数で集団を生成し、(component_code, horizon, theta, model_code) を抽出。

    build 関数を共有するので population サンプリングは参照と**同一**(noise の threading のみ差)。
    """
    if model == "T":
        agents_t = build_trend_population(n, prng, mix)
        cmap_t = {
            TComponent.CHARTIST: COMP_SPEC,
            TComponent.FUNDAMENTALIST: COMP_FUND,
            TComponent.NOISE: COMP_NOISE,
        }
        comp = np.array([cmap_t[a.component] for a in agents_t], dtype=np.int64)
        horizon = np.array([a.horizon for a in agents_t], dtype=np.int64)
        theta = np.array([a.theta for a in agents_t], dtype=np.float64)
        return comp, horizon, theta, 0
    agents_h = build_herd_population(n, prng, mix, hs_range, theta_h_range)
    cmap_h = {
        HComponent.HERDER: COMP_SPEC,
        HComponent.FUNDAMENTALIST: COMP_FUND,
        HComponent.NOISE: COMP_NOISE,
    }
    comp = np.array([cmap_h[a.component] for a in agents_h], dtype=np.int64)
    horizon = np.array([a.horizon for a in agents_h], dtype=np.int64)
    theta = np.array([a.theta for a in agents_h], dtype=np.float64)
    return comp, horizon, theta, 1


def run_fast(
    params: MarketParams,
    model: str,
    mix: tuple[float, float, float],
    *,
    seed: int,
    hs_range: tuple[int, int] | None = None,
    theta_h_range: tuple[float, float] | None = None,
) -> npt.NDArray[np.float64]:
    """高速経路で 1 run。measure 期間の log-return 系列を返す(参照 run_simulation と等価目的)。

    population は参照と同一サンプリング。kernel の noise RNG は seed から決定的に派生。
    """
    ss = np.random.SeedSequence(seed).spawn(1 + params.n_agents)
    prng = np.random.default_rng(ss[0])
    comp, horizon, theta, model_code = _extract_arrays(
        model, mix, params.n_agents, prng, hs_range, theta_h_range
    )
    kernel_seed = int(np.random.SeedSequence(seed + 999_983).generate_state(1)[0])
    return _run_kernel(
        comp,
        horizon,
        theta,
        model_code,
        params.lam,
        params.p_star,
        params.n_agents,
        params.obs_window,
        params.burn_in,
        params.measure,
        params.init_price,
        kernel_seed,
    )
