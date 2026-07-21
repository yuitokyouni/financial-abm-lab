"""YH007-2: Kronos shared-signal × 2-reading on PAMS CDA LOB.

spec 002 §5 YH007-2: YH007-1 (aggregate) を PAMS CDA 板に乗せ替え、実約定 payoff
にし、stylized facts が出るか baseline を取る。
"""
from .adaptive_agent import KronosAdaptiveAgent
from .agents import KronosFadeAgent, KronosTrendAgent
from .bar_aggregator import build_ohlcv_from_market
from .execution import ChildOrderScheduler
from .model import KronosLOBMarket, build_lob_config
from .predator import PredatorAgent
from .signal_hub import SharedSignalHub
from .spoofer import SpooferAgent

__all__ = [
    "KronosTrendAgent",
    "KronosFadeAgent",
    "KronosAdaptiveAgent",
    "PredatorAgent",
    "SpooferAgent",
    "ChildOrderScheduler",
    "SharedSignalHub",
    "KronosLOBMarket",
    "build_lob_config",
    "build_ohlcv_from_market",
]
