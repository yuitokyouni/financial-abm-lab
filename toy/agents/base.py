"""base — Agent 抽象と ctx 出力強制。

`decide(ctx)` は観測/乱数を **ctx 経由でのみ** 読み、意図行動 a ∈ {-1,0,+1} を返す。
`act(ctx)` がそれを `ctx.submit_order` に流す = 出力チャネルを一意化(honest)。
agent が直接 submit_order を呼ぶ実装は許さない(act が唯一の発注経路)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from provabm.ctx import Ctx

# 符号付き行動 → side 文字列。
_ACTION_TO_SIDE: dict[int, str] = {1: "buy", -1: "sell", 0: "hold"}


class Agent(ABC):
    """機構モデルの抽象基底。"""

    @abstractmethod
    def decide(self, ctx: Ctx) -> int:
        """ctx 経由の観測/乱数から意図行動 a ∈ {-1,0,+1} を返す(発注はしない)。"""

    def act(self, ctx: Ctx) -> int:
        """意図行動を ctx.submit_order に流す。返り値は確定行動。"""
        intent = self.decide(ctx)
        if intent not in _ACTION_TO_SIDE:
            raise ValueError(f"decide() は {{-1,0,1}} を返すこと、got {intent!r}")
        return ctx.submit_order(_ACTION_TO_SIDE[intent])
