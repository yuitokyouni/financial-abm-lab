"""厚生指標 (YH010g_HANDOFF §6、2026-07-23 ユーザー決定)。

主 = 決議の情報集約効率: 多数決の結果が sign(mu) と一致した議案の割合。
    相関下のコンドルセ陪審定理の劣化がここに現れる (追随が増えると
    実効独立票数が減り、多数決の正答率が個票の正答率に近づいて落ちる)。
従 = K-R 型選択品質: 個票が sign(mu) と一致した割合 (投資家×議案平均)。

モノカルチャー指標 (agora_engine.monoculture) とは別物として実装する —
指標は相関構造の量、厚生は決議の質。両者の関係こそが研究の主対象。
"""

from __future__ import annotations

import numpy as np

from yh010g.sim.engine import SimResult


def aggregation_efficiency(res: SimResult) -> float:
    """多数決が正しい方向 (sign(mu)) に決まった議案の割合。同数は 0.5 扱い。"""
    correct_sign = np.sign(res.mu)
    hit = (res.outcomes == correct_sign).astype(float)
    hit[res.outcomes == 0] = 0.5
    return float(hit.mean())


def selection_quality(res: SimResult) -> float:
    """個票の正答率 (K-R 型選択品質、投資家×議案平均)。"""
    correct_sign = np.sign(res.mu)[None, :]
    return float((res.dm.values == correct_sign).mean())
