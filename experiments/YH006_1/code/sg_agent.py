"""Phase 2 SG agent subclasses.

S2 plan v2 §0.3 (Yuito 指示 #3): w_init logging 用 subclass を実装。
S5/S6 用 (q_const, lifetime cap) は別 stage で同じパターンの subclass を追加予定。

Phase 1 monkey patch 禁止 (Brief §4.4) のため subclass で実装。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# Phase 1 SpeculationAgent を read-only で import
HERE = Path(__file__).resolve().parent
YH006 = HERE.parent.parent / "YH006"
if str(YH006) not in sys.path:
    sys.path.insert(0, str(YH006))

from speculation_agent import SpeculationAgent  # noqa: E402  (read-only 流用)


class WInitLoggingSpeculationAgent(SpeculationAgent):
    """w_init (= sg_wealth at setup completion) を agent attribute として永続化。

    Phase 1 SpeculationAgent.setup() は wealth_mode 分岐で sg_wealth を draw する
    が、その値を agent attribute として保存し続けない (sg_wealth は round-trip
    で更新されるため)。本 subclass は setup() 末尾で self.w_init を保存し、
    sim 終了時に agent-level parquet で生涯初期 wealth が直接取れるようにする。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        # super().setup() の末尾で self.sg_wealth = w (uniform / pareto draw 値)
        # が確定している。ここで w_init として永続化する。
        self.w_init: int = int(self.sg_wealth)


class QConstSpeculationAgent(WInitLoggingSpeculationAgent):
    """S4-S5 Ablation A1: open round-trip の q を `q_const` 固定 (wealth 非依存).

    仮説 A (q-pollution 仮説) の因果検証主役 subclass。
    Phase 1 で抽出済の hook `_compute_open_quantity` を override、`max(1, q_const)`
    を返すことで wealth → 注文サイズの伝播経路を遮断する。

    Wealth 機構自体 (sg_wealth の round-trip 累積、bankruptcy 判定) は親と同一、
    `corr(w_init, w_final)` 等の wealth persistence 指標は引き続き観測可能。
    A1 で interaction が消えれば「q 経路が F1 の原因」が確定 (KPI L2)。

    settings["qConst"] に正の整数を渡す (S4 で C3 100 trial から median q を較正)。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        q_const = int(settings.get("qConst", 0))
        if q_const < 1:
            raise ValueError(
                f"QConstSpeculationAgent requires settings['qConst'] >= 1, got {q_const}"
            )
        self.q_const: int = q_const

    def _compute_open_quantity(self) -> int:
        return max(1, int(self.q_const))


class LifetimeCapSpeculationAgent(WInitLoggingSpeculationAgent):
    """S6 Ablation A3: 在籍 τ_max step で強制交代 (lifetime cap)。

    仮説 A revised (「LOB Pareto では initial wealth distribution の persistence が
    dominant 因子」) の direct causal test 主役 subclass。S5.8 で実証された
    「実在する凍結」(延長 8500 step で退場 event 0 件) を人為的に解除し、
    凍結 tail を除くと funnel が agg 水準へ戻るか (bin_var_slope) を見る。

    実装: Phase 1 hook `_should_force_retire` を override。在籍時間は
    `t − self._last_substitute_t` (incarnation 開始 = 直近 substitute、初代は 0)。
    注文 in-flight (pending_intent != None) の step は 1 step 延期して reconcile
    整合を保つ — capped lifetime は τ_max + 数 step まで伸びうる (smoke の
    assertion は slack 付き)。

    注意: 本 hook は predicate だが fire 時に診断 counter を更新する副作用を持つ
    (1 step × 1 market で高々 1 回呼ばれる前提、Phase 1 の呼び出しは reconcile
    直後の 1 箇所のみ)。

    settings["tauMax"] に正の整数を渡す (S6 §3.3 較正値、p25 × 0.5)。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        tau_max = int(settings.get("tauMax", 0))
        if tau_max < 1:
            raise ValueError(
                f"LifetimeCapSpeculationAgent requires settings['tauMax'] >= 1, "
                f"got {tau_max}"
            )
        self.tau_max: int = tau_max
        self.num_forced_retires: int = 0
        self.forced_retire_times: List[int] = []

    def _should_force_retire(self, t: int) -> bool:
        if self.pending_intent is not None:
            return False
        fire = (int(t) - int(self._last_substitute_t)) >= self.tau_max
        if fire:
            self.num_forced_retires += 1
            self.forced_retire_times.append(int(t))
        return fire
