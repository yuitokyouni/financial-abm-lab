"""Per-bar shared Kronos signal hub.

YH007-2 では Trend と Fade で **同一の** Kronos 信号を使う (§7 地雷 4 のレイテンシ
分析が前提とした「共有 1 シグナル + 異種解釈」アーキ)。Agent ごとに Kronos を呼ぶと
N × 推論で重いので、bar 内では cache し、bar が進んだら再計算する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from ..kronos_aggregate.model import KronosSignal, SignalProvider


@dataclass
class SharedSignalHub:
    """全 KronosTrendAgent / KronosFadeAgent が共有する signal cache。

    Parameters
    ----------
    provider : SignalProvider
        OHLCV DataFrame → KronosSignal の callable (mock or 実 Kronos)。
    bar_size : int
        N step = 1 bar。bar_index が変わったら signal を再計算する。
    lookback : int
        Kronos の lookback。history bar が lookback 未満なら signal を返さず None。
    """

    provider: SignalProvider
    bar_size: int
    lookback: int
    _current_signal: Optional[KronosSignal] = field(default=None, init=False)
    _current_bar_index: int = field(default=-1, init=False)
    _signal_log: list[tuple[int, Optional[KronosSignal]]] = field(default_factory=list, init=False)

    def get_or_update(self, current_step: int, history_df: pd.DataFrame) -> Optional[KronosSignal]:
        bar_index = current_step // self.bar_size
        if bar_index == self._current_bar_index:
            return self._current_signal
        if len(history_df) < self.lookback:
            self._current_signal = None
        else:
            self._current_signal = self.provider(history_df)
        self._current_bar_index = bar_index
        self._signal_log.append((bar_index, self._current_signal))
        return self._current_signal

    def signal_log(self) -> list[tuple[int, Optional[KronosSignal]]]:
        return list(self._signal_log)

    def reset(self) -> None:
        self._current_signal = None
        self._current_bar_index = -1
        self._signal_log.clear()
