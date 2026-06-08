"""market — 単一資産市場と価格ダイナミクス(spec §3.1)。

価格更新: ``p_{t+1} = p_t · exp(λ · ED_t / N)``、ED_t = Σ_i a_{i,t}、a ∈ {-1,0,+1}。

hot loop(`price_update`)は Numba `@njit`。``NUMBA_DISABLE_JIT=1`` または numba 不在でも
素 Python 経路で同値に動く(CI は JIT を切る)。

注意(スコープ): full-scale(N=500 × 11000 step)を 1 run/sec に載せるには agent decision の
ベクトル化 njit カーネルが要るが、それは後続 week の最適化。本 v0 は agent を Python で回す
参照実装(L2 で ctx 捕捉可能)に留める。
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar, cast

import numpy as np
import numpy.typing as npt
from provabm.capture import CaptureSink
from provabm.ctx import Ctx

from toy.observation import build_observation

if TYPE_CHECKING:
    from toy.agents.base import Agent

_F = TypeVar("_F", bound=Callable[..., Any])


# --- njit + fallback -------------------------------------------------------
def _passthrough_njit(*_args: Any, **_kwargs: Any) -> Callable[[_F], _F]:
    """numba 不在時の no-op デコレータ factory(signature を保つ)。"""

    def wrap(func: _F) -> _F:
        return func

    return wrap


try:
    from numba import njit as _raw_njit
except ImportError:  # pragma: no cover - numba は通常 dep に存在
    _raw_njit = _passthrough_njit


def njit(*args: Any, **kwargs: Any) -> Callable[[_F], _F]:
    """`@njit(...)` を型を保つ identity decorator として見せる薄い wrapper。

    実体は numba の njit(JIT)。``NUMBA_DISABLE_JIT=1`` でも numba 不在でも、被デコレート
    関数の signature はそのまま(素 Python 実行)。
    """
    return cast("Callable[[_F], _F]", _raw_njit(*args, **kwargs))


@njit(cache=True)
def price_update(price: float, ed: float, lam: float, n: int) -> float:
    """超過需要から次価格を求める(spec §3.1)。"""
    return price * math.exp(lam * ed / n)


@dataclass(frozen=True, slots=True)
class MarketParams:
    """市場パラメータ。pre-registered な実験値は experiments/conf/market/default.yaml を参照。"""

    n_agents: int
    lam: float
    p_star: float
    obs_window: int
    burn_in: int
    measure: int
    init_price: float = 100.0


@dataclass(frozen=True, slots=True)
class RunResult:
    """measure 期間の per-step 系列。parquet 出力の元。"""

    steps: npt.NDArray[np.int64]
    price: npt.NDArray[np.float64]
    returns: npt.NDArray[np.float64]
    excess_demand: npt.NDArray[np.float64]
    volume: npt.NDArray[np.float64]
    agg_action: npt.NDArray[np.float64]


class Market:
    """価格・出来高・集約行動の履歴を保持し、行動ベクトルで 1 step 進める。"""

    def __init__(self, params: MarketParams) -> None:
        self.params = params
        self.price: float = params.init_price
        self.return_hist: list[float] = []
        self.volume_hist: list[float] = []
        self.agg_action_hist: list[float] = []
        self.price_hist: list[float] = [params.init_price]  # 価格 *水準* 履歴(誤価格観測の元)

    def step(self, actions: npt.NDArray[np.int64]) -> float:
        """行動ベクトル a_{·,t} から ED を集約し価格を更新。ED を返す。"""
        ed = float(actions.sum())
        new_price = price_update(self.price, ed, self.params.lam, self.params.n_agents)
        self.return_hist.append(math.log(new_price / self.price))
        self.volume_hist.append(float(np.abs(actions).sum()))
        self.agg_action_hist.append(float(actions.mean()))
        self.price = new_price
        self.price_hist.append(new_price)
        return ed


def run_simulation(
    params: MarketParams,
    agents: Sequence[Agent],
    decision_rngs: Sequence[np.random.Generator],
    capture: CaptureSink,
    obs_transform: Callable[
        [dict[str, npt.NDArray[np.float64]], int], dict[str, npt.NDArray[np.float64]]
    ]
    | None = None,
) -> RunResult:
    """burn-in + measure step を回し、measure 期間の系列を返す。

    各 agent は自分の ``Ctx``(固有 RNG + 共有 CaptureSink)を通じてのみ観測・乱数・発注する。
    観測スナップショットは市場全体履歴から step ごとに 1 度だけ構築し全 agent で共有する。

    ``obs_transform`` を渡すと、各 step で全 agent が観測する前に観測 dict を変換する
    (B2 介入フック、spec §7。介入無しの既定では恒等)。
    """
    if len(agents) != params.n_agents or len(decision_rngs) != params.n_agents:
        raise ValueError("agents / decision_rngs の数が n_agents と一致しない")

    market = Market(params)
    ctxs = [Ctx(i, rng, capture) for i, rng in enumerate(decision_rngs)]
    total = params.burn_in + params.measure

    rec_steps: list[int] = []
    rec_price: list[float] = []
    rec_ret: list[float] = []
    rec_ed: list[float] = []
    rec_vol: list[float] = []
    rec_agg: list[float] = []

    actions = np.empty(params.n_agents, dtype=np.int64)
    for t in range(total):
        obs = build_observation(
            market.return_hist,
            market.agg_action_hist,
            market.volume_hist,
            market.price_hist,
            params.p_star,
            params.obs_window,
        )
        if obs_transform is not None:
            obs = obs_transform(obs, t)
        for i, (agent, ctx) in enumerate(zip(agents, ctxs, strict=True)):
            ctx.bind_step(t, obs, {})
            actions[i] = agent.act(ctx)
        ed = market.step(actions)
        if t >= params.burn_in:
            rec_steps.append(t)
            rec_price.append(market.price)
            rec_ret.append(market.return_hist[-1])
            rec_ed.append(ed)
            rec_vol.append(market.volume_hist[-1])
            rec_agg.append(market.agg_action_hist[-1])

    return RunResult(
        steps=np.asarray(rec_steps, dtype=np.int64),
        price=np.asarray(rec_price, dtype=np.float64),
        returns=np.asarray(rec_ret, dtype=np.float64),
        excess_demand=np.asarray(rec_ed, dtype=np.float64),
        volume=np.asarray(rec_vol, dtype=np.float64),
        agg_action=np.asarray(rec_agg, dtype=np.float64),
    )
