"""Intervention Atlas の抽象 protocol(format scaffold のみ、実装は将来)。

設計ノート §2.4 の弁別ベンチ核オブジェクト:
    既知機構 {M1..Mk} × 介入 battery {do(X1)..do(Xn)} → 応答ベクトル φ-response が
    応答空間で分離するか(機構→応答シグネチャ写像の injectivity)。

ここに置くのは **型と protocol だけ**。スコア機構・leaderboard・Type2 survival test は
v0 スコープ外(CLAUDE.md)。具体実装(SF battery、介入 4 scheme)は `toy/` 側が先に育ち、
安定した時点で本 protocol に逆輸入する(framework-first 禁止、toy-first)。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

# 機構を介入応答空間に写した特徴ベクトル(φ-response)。次元は battery 依存。
ResponseVector = npt.NDArray[np.float64]


@runtime_checkable
class Mechanism(Protocol):
    """既知機構 M_i。ABM の 1 つの生成過程(例: Model T / Model H)を表す抽象。

    Atlas は機構の内部実装に依存しない。識別に必要なのは「介入を受けて応答を返せる」ことだけ。
    """

    name: str

    def reset(self, seed: int) -> None:
        """機構を決定的初期状態に戻す(再現性のため seed 必須)。"""
        ...


@runtime_checkable
class Response(Protocol):
    """機構 × 介入から得られる応答シグネチャの抽象。

    susceptibility curve feature(spec §8.3)など、応答空間の 1 点を表す。
    """

    def as_vector(self) -> ResponseVector:
        """応答を固定次元ベクトルへ。分類器/距離計算はこのベクトル上で行う。"""
        ...


@runtime_checkable
class Battery(Protocol):
    """介入 battery {do(X1)..do(Xn)}。機構に介入を適用し応答を測る抽象。

    背骨は optimal model-discrimination design(T-optimality 等、設計ノート §2.4)だが、
    その選択原理の実装は将来。ここでは interface のみ。
    """

    name: str

    def probe(self, mechanism: Mechanism, seed: int) -> Response:
        """`mechanism` に介入 battery を適用し、応答シグネチャを返す。"""
        ...
