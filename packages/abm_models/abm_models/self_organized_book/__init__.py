"""YH007-8 自己組織化板 (Chiarella-Iori × Kronos) パッケージ。

spec 003 (v2) のルートコーズ修正: 全 LIMIT 化 + 内生流動性 (MMFCN 廃止) +
Kronos quantile-rank 評価値。002 の naïve 設計 (kronos_lob/) を artifact 起源として
退避し、本パッケージは「信用できる SF 測定土台」を作る。

Phase 構成 (spec 003 §7):
  P0  ✅ LimitAgentBase + ZIAgent (warmup 兼 control) + SelfOrganizedBookMarket
  P1     ZI-matched + tick 較正 + power analysis pilot
  P1.5   aggressive rate auto-tune
  P2     CI×Kronos quantile-rank 評価値
"""
from .base_agent import LimitAgentBase, AgentEvaluation
from .kronos_agent import KronosCIAgent, KronosQuantileHub
from .kronos_quantile import KronosQuantilePredictor, quantile_to_eval
from .model import SelfOrganizedBookMarket
from .zi_agent import ZIAgent

__all__ = [
    "LimitAgentBase",
    "AgentEvaluation",
    "ZIAgent",
    "KronosCIAgent",
    "KronosQuantileHub",
    "KronosQuantilePredictor",
    "quantile_to_eval",
    "SelfOrganizedBookMarket",
]
