"""ctx — エージェントの唯一の世界口。

設計ノート §3 の `ctx.observe / ctx.read_own_state / ctx.random / ctx.submit_order`。
honest 性の核:

- **乱数は必ず `ctx.random()` 経由**(seed 捕捉 + 再現性)。素の `np.random` は使わない。
- **出力は必ず `ctx.submit_order()` 経由**(出力チャネルの一意化)。
- すべての呼び出しは `CaptureSink` に記録され、reach/lineage の素材になる。

注意(設計ノート §3.2):ctx 単体は hidden-channel-zero を *解かない*。これは opt-in 規約であって
境界ではない。素 Python の global/closure/`self.x` 直読みは漏れうる。sound な invariance は L3+。
本 v0 は L2(reported reach)まで。
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import numpy.typing as npt

from provabm.capture import CaptureSink, CtxEvent, CtxEventKind

# side 文字列 → 符号付き行動 a ∈ {-1, 0, +1}(spec §3.1)。
_SIDE_TO_SIGN: dict[str, int] = {"sell": -1, "hold": 0, "buy": 1}


class Ctx:
    """1 エージェントに紐づく ctx。step ごとに観測/自状態を rebind して再利用する。

    RNG はエージェント固有 Generator を保持し draw を逐次進める(再現性・並列安全)。
    """

    def __init__(self, agent_id: int, rng: np.random.Generator, capture: CaptureSink) -> None:
        self.agent_id = agent_id
        self._rng = rng
        self._capture = capture
        self._step: int = -1
        self._obs: Mapping[str, npt.NDArray[np.float64]] = {}
        self._own: Mapping[str, float] = {}
        self._order: int | None = None

    def bind_step(
        self,
        step: int,
        observations: Mapping[str, npt.NDArray[np.float64]],
        own_state: Mapping[str, float],
    ) -> None:
        """この step の観測スナップショットと自状態を束ねる(RNG は維持)。"""
        self._step = step
        self._obs = observations
        self._own = own_state
        self._order = None

    # --- 入力チャネル ------------------------------------------------------
    def observe(self, key: str) -> npt.NDArray[np.float64]:
        """観測ベクトル要素を読む(spec §3.3:price/volume/aggregate-action history)。"""
        value = self._obs[key]
        self._capture.record(
            CtxEvent(
                agent_id=self.agent_id,
                step=self._step,
                kind=CtxEventKind.OBSERVE,
                key=key,
                meta={"shape": list(value.shape), "dtype": str(value.dtype)},
            )
        )
        return value

    def read_own_state(self, key: str) -> float:
        """自身の状態(cash/position 等)を読む。"""
        value = self._own[key]
        self._capture.record(
            CtxEvent(
                agent_id=self.agent_id,
                step=self._step,
                kind=CtxEventKind.READ_OWN_STATE,
                key=key,
                meta={"value": float(value)},
            )
        )
        return value

    def random(self, stream: str = "default") -> float:
        """再現可能な一様乱数 U[0,1) を 1 draw。`stream` は log 上のラベル(入力源の名)。

        Bernoulli は `ctx.random() < p`、{-1,0,1} 一様は `int(ctx.random()*3) - 1` で導出する
        (単一 RNG stream を逐次消費 = honest かつ再現可能)。
        """
        draw = float(self._rng.random())
        self._capture.record(
            CtxEvent(
                agent_id=self.agent_id,
                step=self._step,
                kind=CtxEventKind.RANDOM,
                key=stream,
            )
        )
        return draw

    # --- 出力チャネル ------------------------------------------------------
    def submit_order(self, side: str, asset: str = "A", qty: int = 1) -> int:
        """発注(唯一の出力口)。符号付き行動 a ∈ {-1,0,+1} を返す。

        1 step につき 1 回まで。`hold` は qty に依らず 0。
        """
        if side not in _SIDE_TO_SIGN:
            raise ValueError(f"unknown side {side!r}; expected one of {sorted(_SIDE_TO_SIGN)}")
        if qty < 0:
            raise ValueError(f"qty must be non-negative, got {qty}")
        if self._order is not None:
            raise RuntimeError("submit_order called more than once in a single step")
        action = _SIDE_TO_SIGN[side] * (0 if side == "hold" else qty)
        # spec §3.1 では a ∈ {-1,0,+1}。qty>1 は将来拡張余地として符号のみ採用する。
        action = int(np.sign(action))
        self._order = action
        self._capture.record(
            CtxEvent(
                agent_id=self.agent_id,
                step=self._step,
                kind=CtxEventKind.SUBMIT_ORDER,
                key=asset,
                meta={"side": side, "qty": qty, "action": action},
            )
        )
        return action

    @property
    def submitted_order(self) -> int | None:
        """この step に提出された行動(未提出なら None)。market が読む。"""
        return self._order
