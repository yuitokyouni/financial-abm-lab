"""stylized_facts — Cont (2001) の stylized facts 計算 (統一実装)。

speculation-game-info/YH005 の analysis.py を core に昇格。全 experiments がこの
単一実装を import する (spec 001 O1)。plotting 関数 (Phase 1 mechanism figures) も
`core` に同梱。
"""

from __future__ import annotations

from .core import (
    ccdf,
    hill_mle_tail_index,
    kurtosis_windowed,
    log_returns_from_prices,
    return_acf,
    stylized_facts_summary,
    volatility_acf,
)

__all__ = [
    "log_returns_from_prices",
    "return_acf",
    "volatility_acf",
    "ccdf",
    "hill_mle_tail_index",
    "kurtosis_windowed",
    "stylized_facts_summary",
]
