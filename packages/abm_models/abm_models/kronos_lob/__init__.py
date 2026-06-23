"""YH007-2: Kronos shared-signal × 2-reading on PAMS CDA LOB.

spec 002 §5 YH007-2: YH007-1 (aggregate) を PAMS CDA 板に乗せ替え、実約定 payoff
にし、stylized facts が出るか baseline を取る。
"""
from .agents import KronosFadeAgent, KronosTrendAgent
from .bar_aggregator import build_ohlcv_from_market
from .model import KronosLOBMarket, build_lob_config
from .signal_hub import SharedSignalHub

__all__ = [
    "KronosTrendAgent",
    "KronosFadeAgent",
    "SharedSignalHub",
    "KronosLOBMarket",
    "build_lob_config",
    "build_ohlcv_from_market",
]
