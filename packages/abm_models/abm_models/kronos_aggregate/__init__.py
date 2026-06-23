"""YH007-1 aggregate market (Kronos shared signal × 2 reading agents).

spec 002 §5 YH007-1: 板無し即時 clearing で Kronos の同一予測を 2 通りに読む
agent (順張り/逆張り) が決定論的に分岐することを示す最小実装。
"""
from .model import (
    KronosAggregateMarket,
    KronosSignal,
    SignalProvider,
    TrendAgent,
    FadeAgent,
    constant_signal_provider,
)

__all__ = [
    "KronosAggregateMarket",
    "KronosSignal",
    "SignalProvider",
    "TrendAgent",
    "FadeAgent",
    "constant_signal_provider",
]
