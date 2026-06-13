"""測定と認定 — measure / impulse-response gate / certify（research D-B6/D-B7）。

認定 gate は本 harness の検証の中心。分類器の検出力自体を合成 policy
（grim-trigger=PASS すべき / 固定高止まり=FAIL すべき）で test に固定する
（tests/test_verdict_gate.py。001 の「anchor は sim と独立」に対応する B の規律）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import benchmarks
from .env import MarketEnv, derive_rngs
from .learnconfig import LearnConfig
from .qlearn import TrainResult, encode, initial_history, run_greedy, _MEASURE_BURN_IN

# IR の seed 横断集約: pass 率がこの閾値以上で cell 認定（D-B7 実装注記）
IR_PASS_FRAC = 0.8


@dataclass
class CellMeasurement:
    seed: int
    realized_spread: float        # 期ごとの勝者 half-spread の平均
    markup: float                 # (realized − nash) / nash（nash = 同機構 benchmarks）
    extraction_rate: float        # 単位時間あたり（001 extraction_rate と同基準）
    mm_pnl: float                 # 測定窓の MM 合計 PnL
    floors: dict[str, float]      # {"zi", "nash", "monopoly"}（ZI は中間参照点、D-B5 訂正）
    exited: bool                  # 全員 grid 上限張り付き（事実上の退出）
    converged: bool


@dataclass
class IRResult:
    punished: bool
    punish_lag: int | None        # 懲罰初出までの期数（未検出 None）
    deviation_profitable: bool    # 逸脱の累積利得 > counterfactual（同一フロー対比較）
    restored: bool
    baseline_profile: tuple[int, ...]
    deviation_action: int
    profiles: list = field(repr=False, default_factory=list)


@dataclass
class CollusionVerdict:
    markup_mean: float
    markup_se: float
    markup_significant: bool
    ir_pass_frac: float
    converged_all: bool
    certified: bool
    n_seeds: int


def measure(cfg: LearnConfig, result: TrainResult) -> CellMeasurement:
    """収束 policy 上の測定（ε=0・学習停止・K=measure_periods 期、burn-in 100 期）。"""
    seeds = derive_rngs(cfg)
    env = MarketEnv(cfg, seeds["measure_env"])
    pols = [p.frozen() for p in result.policies]
    total = _MEASURE_BURN_IN + cfg.measure_periods
    profiles, rewards, infos = run_greedy(env, pols, cfg, total)
    keep = slice(_MEASURE_BURN_IN, total)
    winner_h = np.array([info["winner_h"] for info in infos[keep]])
    extraction = float(sum(info["extraction"] for info in infos[keep]))
    nash = benchmarks.myopic_nash_spread(cfg)
    realized = float(winner_h.mean())
    top = cfg.n_actions - 1
    exited = min(min(p) for p in profiles[keep]) == top
    return CellMeasurement(
        seed=cfg.seed,
        realized_spread=realized,
        markup=(realized - nash) / nash,
        extraction_rate=extraction / (cfg.measure_periods * cfg.period_steps * cfg.dt),
        mm_pnl=float(rewards[keep].sum()),
        floors={"zi": benchmarks.zi_floor(cfg), "nash": nash,
                "monopoly": benchmarks.monopoly_grid(cfg)},
        exited=exited,
        converged=result.converged,
    )


def _rollout(policies: list, cfg: LearnConfig, periods: int,
             history: tuple, forced: dict[int, dict[int, int]] | None = None
             ) -> list[tuple[int, ...]]:
    """frozen policy の決定論 rollout（state = action 履歴のみ。flow 乱数は動学に無関係）。"""
    profiles = []
    for t in range(periods):
        state = encode(history, cfg.n_actions)
        actions = tuple(p.greedy(state) for p in policies)
        if forced and t in forced:
            a = list(actions)
            for i, ai in forced[t].items():
                a[i] = ai
            actions = tuple(a)
        profiles.append(actions)
        if cfg.memory > 0:
            history = (history[1:] + (actions,)) if cfg.memory > 1 else (actions,)
    return profiles


def impulse_response(cfg: LearnConfig, result: TrainResult) -> IRResult:
    """deviation+punishment 検査（D-B7、決定論版）。

    Q 凍結・ε=0 の policy は決定論で、state は action 履歴のみ（flow は動学に
    影響しない）。よって rollout は乱数不要、逸脱の収支は**期待 stage payoff
    （benchmarks、解析）**の累積で厳密に評価する——realized reward で測ると
    たかだか数期の到着ノイズに収支が沈み判定が flaky になる（分散ゼロ化）。
    探索ノイズの混入は構造的に起きない（frozen＝update も explore も無い）。
    """
    pols = [p.frozen() for p in result.policies]
    total = cfg.ir_pre + cfg.ir_horizon
    h0 = initial_history(cfg)

    # counterfactual（逸脱なし）
    prof_cf = _rollout(pols, cfg, total, h0)
    baseline = prof_cf[cfg.ir_pre - 1]

    # 逸脱 action = baseline の他者に対する myopic 最良応答（解析、D-B7）
    br = max(range(cfg.n_actions),
             key=lambda a: benchmarks.stage_payoff(a, tuple(baseline[1:]), cfg))

    # deviation: ir_pre 期目（0-index）に agent 0 を強制
    prof_dev = _rollout(pols, cfg, total, h0, forced={cfg.ir_pre: {0: br}})

    # 懲罰: 逸脱後 ir_punish_lag 期以内に相手側が baseline よりタイト化（index 減）
    punish_lag = None
    for tau in range(1, cfg.ir_punish_lag + 1):
        t = cfg.ir_pre + tau
        if t >= total:
            break
        if any(prof_dev[t][i] < baseline[i] for i in range(1, cfg.n_mm)):
            punish_lag = tau
            break

    # 逸脱の収支: 期待 stage payoff の累積差（逸脱期以降、厳密）
    def _cum(profiles: list[tuple[int, ...]]) -> float:
        s = 0.0
        for p in profiles[cfg.ir_pre:]:
            others = p[1:]
            s += benchmarks.stage_payoff(p[0], tuple(others), cfg)
        return s

    # 再確立: 末尾 ir_restore_tail 期、全員 baseline ±1 grid step
    tail = prof_dev[total - cfg.ir_restore_tail:]
    restored = all(abs(p[i] - baseline[i]) <= 1
                   for p in tail for i in range(cfg.n_mm))

    return IRResult(
        punished=punish_lag is not None,
        punish_lag=punish_lag,
        deviation_profitable=_cum(prof_dev) > _cum(prof_cf) + 1e-12,
        restored=restored,
        baseline_profile=tuple(baseline),
        deviation_action=br,
        profiles=prof_dev,
    )


def memory_threshold(verdicts: dict[int, CollusionVerdict]) -> int:
    """C2: collusion 維持に必要な最小 memory（認定通過点のみから決定、A3×C2 gate）。

    入力 = {memory 水準: その水準の CollusionVerdict}。認定された水準がひとつも
    無ければ閾値は**定義されない**——その場合に数値を返すのは「artifact の閾値を
    測る」gate 違反なので ValueError で拒否する（原則IV）。非認定の低 memory 水準は
    「閾値未満」の証拠であって違反ではない。
    """
    if not verdicts:
        raise ValueError("memory_threshold: empty input")
    certified = [m for m, v in verdicts.items() if v.certified]
    if not certified:
        raise ValueError(
            "memory_threshold: no certified memory level — 閾値は未定義（gate 違反を拒否。"
            "認定された点が出てから測る）")
    return min(certified)


def certify(cells: list[CellMeasurement], irs: list[IRResult],
            markup_floor: float | None = None) -> CollusionVerdict:
    """認定 = markup 有意（mean − 2SE > floor）∧ IR pass 率 ≥ 0.8 ∧ 全 seed 収束（D-B7）。"""
    if len(cells) < 2:
        raise ValueError("certify needs >= 2 seeds (SE が定義できない)")
    floor = 0.05 if markup_floor is None else markup_floor
    markups = np.array([c.markup for c in cells])
    mean = float(markups.mean())
    se = float(markups.std(ddof=1) / math.sqrt(len(markups)))
    significant = (mean - 2.0 * se) > floor
    ir_pass = [ir.punished and not ir.deviation_profitable and ir.restored for ir in irs]
    frac = sum(ir_pass) / len(ir_pass) if ir_pass else 0.0
    converged_all = all(c.converged for c in cells)
    return CollusionVerdict(
        markup_mean=mean,
        markup_se=se,
        markup_significant=significant,
        ir_pass_frac=frac,
        converged_all=converged_all,
        certified=significant and frac >= IR_PASS_FRAC and converged_all,
        n_seeds=len(cells),
    )
