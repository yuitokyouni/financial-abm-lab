"""Phase 2 主 runner: 1 trial 単位の sim 実行 + 3 種 parquet 出力.

Brief §3 S2: signature `(cond_id, seed, **overrides) -> SimResult`。
S2 では aggregate (C0u/C0p) のみ active、LOB は smoke のみ。

CLI:
    python -m code.run_experiment --cond C0u --seed 1000 --out data/C0u
or as library:
    from code.run_experiment import run_one_trial
    result = run_one_trial("C0u", 1000, out_dir=Path("data/C0u"))
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
YH006 = YH006_1.parent / "YH006"
YH005 = YH006_1.parent / "YH005"
for p in (YH006, YH006_1, YH005, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from aggregate_sim import simulate_aggregate  # noqa: E402  (Phase 1、後方互換拡張済)

try:
    from code.config import (  # noqa: E402
        CONDITIONS, AGG_PARAMS, PARETO_ALPHA, PARETO_XMIN, aggregate_kwargs,
    )
    from code.adapter import (  # noqa: E402
        round_trips_to_df, agents_to_df, agent_lifetime_samples_to_df, wealth_ts_to_df,
    )
except ImportError:
    sys.path.insert(0, str(HERE))
    from config import (  # type: ignore[no-redef]
        CONDITIONS, AGG_PARAMS, PARETO_ALPHA, PARETO_XMIN, aggregate_kwargs,
    )
    from adapter import (  # type: ignore[no-redef]
        round_trips_to_df, agents_to_df, agent_lifetime_samples_to_df, wealth_ts_to_df,
    )


@dataclass
class SimResult:
    cond: str
    seed: int
    rt_df: pd.DataFrame
    agents_df: pd.DataFrame
    lifetime_samples_df: pd.DataFrame
    wealth_ts_df: pd.DataFrame
    runtime_sec: float
    n_round_trips: int
    n_substitutions: int

    def to_parquets(self, out_dir: Path) -> Dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "rt": out_dir / f"trial_{self.seed:04d}.parquet",
            "agents": out_dir / f"agents_{self.seed:04d}.parquet",
            "lifetimes": out_dir / f"lifetimes_{self.seed:04d}.parquet",
            "wealth_ts": out_dir / f"wealth_ts_{self.seed:04d}.parquet",
        }
        self.rt_df.to_parquet(paths["rt"], index=False)
        self.agents_df.to_parquet(paths["agents"], index=False)
        self.lifetime_samples_df.to_parquet(paths["lifetimes"], index=False)
        self.wealth_ts_df.to_parquet(paths["wealth_ts"], index=False)
        return paths


# ---------------------------------------------------------------------------
# aggregate (C0u, C0p) 経路
# ---------------------------------------------------------------------------

def _replay_w_init_aggregate(seed: int, params: Dict[str, Any]) -> np.ndarray:
    """aggregate_sim と同じ RNG 消費順を replicate して w_init を抽出.

    S1 reanalyze_phase1.reconstruct_w_init_aggregate と同経路、test_aggregate_parity
    で uniform mode の bit-一致が verified 済。
    """
    N = params["N"]; M = params["M"]; S = params["S"]; B = params["B"]
    K = 5 ** M
    rng = np.random.default_rng(seed)
    _ = rng.choice([-1, 0, 1], size=(N, S, K)).astype(np.int8)
    init_u100 = rng.integers(0, 100, size=N)
    _ = rng.integers(0, S, size=N).astype(np.int64)
    _ = int(rng.integers(0, K))
    if params.get("wealth_mode", "uniform") == "uniform":
        return (int(B) + init_u100).astype(np.int64)
    u_pareto = rng.uniform(0.0, 1.0, size=N)
    w_float = params.get("pareto_xmin", PARETO_XMIN) * (
        u_pareto ** (-1.0 / params.get("pareto_alpha", PARETO_ALPHA))
    )
    w = w_float.astype(np.int64)
    w[w < int(B)] = int(B)
    return w


def run_aggregate_trial(cond_name: str, seed: int) -> SimResult:
    cond = CONDITIONS[cond_name]
    assert cond.world == "agg", f"{cond_name} is not aggregate"
    params = aggregate_kwargs(cond)

    snapshots: List[Tuple[int, np.ndarray]] = []
    def _snap(t: int, w_arr: np.ndarray) -> None:
        snapshots.append((int(t), w_arr.copy()))

    t0 = time.perf_counter()
    res = simulate_aggregate(
        seed=seed,
        snapshot_callback=_snap,
        log_substitutes=True,
        **params,
    )
    elapsed = time.perf_counter() - t0

    # T 終了時の snapshot も追加 (callback は t % (T // 10) == 0 のみ取るので
    # 正確に 10 個 + t=0 の合計 11 snapshot になる。本実装は T-1 を含めない
    # = 過去 t/snapshots を信用、最終 wealth は final_wealth で別途取れる。
    # Brief §2.3 の "T/10, 2T/10, ..., T" 仕様に合わせ、t=T (= sim 終了直後の w) を追加
    snapshots.append((int(params["T"]), res["final_wealth"].copy()))

    # w_init を replay で抽出 (Phase 1 sim は agent w を log しないので)
    w_init = _replay_w_init_aggregate(seed, params)

    sub_events: List[Tuple[int, int, int, int]] = res.get("substitute_events", [])

    # Build DataFrames
    agent_w_init_map = {i: int(w_init[i]) for i in range(params["N"])}
    rt_df = round_trips_to_df(
        round_trips=res["round_trips"],
        cond=cond_name, seed=seed,
        agent_w_init=agent_w_init_map,
        substitute_events=sub_events,
    )
    agents_df = agents_to_df(
        cond=cond_name, seed=seed,
        N_total=params["N"],
        w_init=w_init,
        final_wealth=np.asarray(res["final_wealth"]),
        rt_df=rt_df,
        substitute_events=sub_events,
        T_total=params["T"],
    )
    lifetime_samples_df = agent_lifetime_samples_to_df(
        cond=cond_name, seed=seed,
        N_total=params["N"],
        substitute_events=sub_events,
        T_total=params["T"],
    )
    wealth_ts_df = wealth_ts_to_df(
        cond=cond_name, seed=seed, snapshots=snapshots,
    )

    return SimResult(
        cond=cond_name, seed=seed,
        rt_df=rt_df, agents_df=agents_df,
        lifetime_samples_df=lifetime_samples_df,
        wealth_ts_df=wealth_ts_df,
        runtime_sec=elapsed,
        n_round_trips=int(res["round_trips"]["close_t"].size),
        n_substitutions=int(res["num_substitutions"]),
    )


# ---------------------------------------------------------------------------
# LOB (C2/C3) 経路 — S2 では smoke のみ、本格 100 trial は S3
# ---------------------------------------------------------------------------

def run_lob_trial_smoke(
    cond_name: str,
    seed: int,
    warmup_steps: int = 200,
    main_steps: int = 200,
    num_fcn: int = 30,
    num_sg: int = 100,
    max_normal_orders: int = 500,
    c_ticks: float = 28.0,
    q_const: Optional[int] = None,
    mmfcn_order_volume: Optional[int] = None,
) -> SimResult:
    """LOB smoke (S2 plan v2 §3.5 / 修正 4): WInitLoggingSpeculationAgent の
    wiring 動作確認用。短縮 sim 長で agent parquet に w_init non-NaN を assertion。

    S4-S5 (ablation A1): `q_const` を非 None で渡すと QConstSpeculationAgent に切替、
    cond の `q_rule == "const"` 必須。S6 (A3) は別 subclass で同 pattern。

    本関数は PAMS が import 可能な環境でのみ動く (Mac / pams 入り Linux)。
    Windows env では ImportError、smoke は skip して diff.md で記録する。
    """
    import random as _stdlib_random  # noqa: E501  PAMS 内部で使うが seed 固定
    try:
        from pams.runners import SequentialRunner  # type: ignore
    except ImportError as e:
        raise ImportError(
            "PAMS 0.2.2 unavailable on this env — LOB smoke は Mac でのみ実行可。"
        ) from e

    cond = CONDITIONS[cond_name]
    assert cond.world == "lob", f"{cond_name} is not LOB"
    is_ablation_a1 = (cond.q_rule == "const")
    if is_ablation_a1 and q_const is None:
        raise ValueError(
            f"cond={cond_name} has q_rule='const' but q_const arg not provided. "
            f"S4 較正値を渡してください。"
        )

    # Phase 1 configs を流用、ただし SG agent class を WInitLogging 版に差し替える
    if cond.wealth_mode == "uniform":
        from configs.c2 import make_config as _make_cfg
        cfg = _make_cfg(
            warmup_steps=warmup_steps, main_steps=main_steps,
            num_sg_agents=num_sg, c_ticks=c_ticks,
            max_normal_orders=max_normal_orders,
        )
    else:
        from configs.c3 import make_config as _make_cfg
        cfg = _make_cfg(
            warmup_steps=warmup_steps, main_steps=main_steps,
            num_sg_agents=num_sg, c_ticks=c_ticks,
            max_normal_orders=max_normal_orders,
        )
    cfg["FCNAgents"]["numAgents"] = num_fcn
    # S5.6: MMFCN orderVolume override (Phase 1 後方互換、None 経路は既存挙動 bit-一致)
    if mmfcn_order_volume is not None:
        cfg["FCNAgents"]["orderVolume"] = int(mmfcn_order_volume)
    # S2: w_init logging subclass。S4-S5: A1 ablation で QConst subclass へ差替。
    if is_ablation_a1:
        cfg["SGAgents"]["class"] = "QConstSpeculationAgent"
        cfg["SGAgents"]["qConst"] = int(q_const)
    else:
        cfg["SGAgents"]["class"] = "WInitLoggingSpeculationAgent"

    from custom_saver import OrderTrackingSaver  # type: ignore
    from mm_fcn_agent import MMFCNAgent  # type: ignore
    from sg_agent import WInitLoggingSpeculationAgent, QConstSpeculationAgent  # YH006_1 内 subclass

    saver = OrderTrackingSaver()
    runner = SequentialRunner(
        settings=cfg, prng=_stdlib_random.Random(seed), logger=saver,
    )
    runner.class_register(WInitLoggingSpeculationAgent)
    runner.class_register(QConstSpeculationAgent)
    runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    # SG agent 群から w_init を抽出
    sgs = [
        a for a in runner.simulator.agents
        if isinstance(a, WInitLoggingSpeculationAgent)
    ]
    N_sg = len(sgs)
    w_init = np.array([int(a.w_init) for a in sgs], dtype=np.int64)
    final_wealth = np.array([int(a.sg_wealth) for a in sgs], dtype=np.int64)

    # round_trips を agent から集約 (warmup 引いた main session 内のみ)
    all_rt = {
        "agent_idx": [], "open_t": [], "close_t": [],
        "entry_action": [], "entry_quantity": [], "delta_G": [],
    }
    for a in sgs:
        for rt in a.round_trips:
            if rt["open_t"] < warmup_steps or rt["close_t"] < warmup_steps:
                continue
            all_rt["agent_idx"].append(rt["agent_idx"])
            all_rt["open_t"].append(rt["open_t"] - warmup_steps)
            all_rt["close_t"].append(rt["close_t"] - warmup_steps)
            all_rt["entry_action"].append(rt["entry_action"])
            all_rt["entry_quantity"].append(rt["entry_quantity"])
            all_rt["delta_G"].append(rt["delta_G"])
    for k in all_rt:
        all_rt[k] = np.asarray(all_rt[k], dtype=np.int64 if k != "entry_action" else np.int8)

    # substitute_events を agent から
    sub_events: List[Tuple[int, int, int, int]] = []
    for a in sgs:
        for ev in a.substitute_events:
            t, dead_w, new_w = ev
            if t >= warmup_steps:
                sub_events.append((int(t - warmup_steps), int(a.agent_id), int(dead_w), int(new_w)))

    agent_w_init_map = {int(a.agent_id): int(a.w_init) for a in sgs}

    rt_df = round_trips_to_df(
        round_trips=all_rt, cond=cond_name, seed=seed,
        agent_w_init=agent_w_init_map, substitute_events=sub_events,
    )
    agents_df = agents_to_df(
        cond=cond_name, seed=seed, N_total=N_sg,
        w_init=w_init, final_wealth=final_wealth,
        rt_df=rt_df, substitute_events=sub_events, T_total=main_steps,
    )
    lifetime_samples_df = agent_lifetime_samples_to_df(
        cond=cond_name, seed=seed, N_total=N_sg,
        substitute_events=sub_events, T_total=main_steps,
    )
    wealth_ts_df = wealth_ts_to_df(
        cond=cond_name, seed=seed, snapshots=[(main_steps, final_wealth.copy())],
    )

    return SimResult(
        cond=cond_name, seed=seed,
        rt_df=rt_df, agents_df=agents_df,
        lifetime_samples_df=lifetime_samples_df,
        wealth_ts_df=wealth_ts_df,
        runtime_sec=elapsed,
        n_round_trips=len(rt_df),
        n_substitutions=len(sub_events),
    )


# ---------------------------------------------------------------------------
# LOB full-length runner (S3 plan v2 §3.2、Mac でのみ実行可、PAMS 必要)
# ---------------------------------------------------------------------------

def run_lob_trial(
    cond_name: str, seed: int,
    q_const: Optional[int] = None,
    mmfcn_order_volume: Optional[int] = None,
) -> SimResult:
    """LOB full-length 1 trial (warmup=200, main=1500、Phase 1 default 設定)。

    `run_lob_trial_smoke` を `LOB_PARAMS` で driven。S4-S5 で `q_const` を渡すと A1
    ablation 経路 (QConstSpeculationAgent 切替) が有効。S5.6 で `mmfcn_order_volume`
    を渡すと MMFCN sensitivity scan 経路 (cfg["FCNAgents"]["orderVolume"] override)。
    両者とも None 経路は既存挙動と bit-一致 (Phase 1 後方互換 protocol、S4 §0.4 と同)。
    wealth_ts は終了時 1 snapshot のみ取る (smoke と同じ実装)。
    """
    from config import LOB_PARAMS, CONDITIONS as _CONDS  # noqa: E402
    p = LOB_PARAMS
    cond = _CONDS[cond_name]
    if cond.q_rule == "const" and q_const is None:
        raise ValueError(
            f"cond={cond_name} requires q_const (q_rule='const'). "
            f"S4 較正値を呼び出し側 (ablation_ensemble.py) で指定する。"
        )
    return run_lob_trial_smoke(
        cond_name, seed,
        warmup_steps=p["warmup_steps"],
        main_steps=p["main_steps"],
        num_fcn=p["num_fcn"],
        num_sg=p["N_sg"],
        max_normal_orders=p["max_normal_orders"],
        c_ticks=p["c_ticks"],
        q_const=q_const,
        mmfcn_order_volume=mmfcn_order_volume,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_one_trial(
    cond_name: str, seed: int, out_dir: Optional[Path] = None,
    is_lob_smoke: bool = False, q_const: Optional[int] = None,
    mmfcn_order_volume: Optional[int] = None,
) -> SimResult:
    cond = CONDITIONS[cond_name]
    if cond.world == "agg":
        result = run_aggregate_trial(cond_name, seed)
    elif cond.world == "lob":
        if is_lob_smoke:
            result = run_lob_trial_smoke(
                cond_name, seed, q_const=q_const,
                mmfcn_order_volume=mmfcn_order_volume,
            )
        else:
            result = run_lob_trial(
                cond_name, seed, q_const=q_const,
                mmfcn_order_volume=mmfcn_order_volume,
            )
    else:
        raise ValueError(f"unknown world: {cond.world}")

    if out_dir is not None:
        result.to_parquets(out_dir)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cond", required=True, choices=list(CONDITIONS.keys()))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, default=None,
                        help="出力ディレクトリ (省略時は parquet 出力 skip)")
    parser.add_argument("--lob-smoke", action="store_true",
                        help="LOB smoke (S2): warmup=200/main=200")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("run_experiment")
    logger.info(f"start: cond={args.cond} seed={args.seed} out={args.out} lob_smoke={args.lob_smoke}")

    result = run_one_trial(args.cond, args.seed, args.out, is_lob_smoke=args.lob_smoke)

    logger.info(
        f"done: cond={args.cond} seed={args.seed}  "
        f"runtime={result.runtime_sec:.1f}s  "
        f"n_rt={result.n_round_trips}  n_sub={result.n_substitutions}"
    )


if __name__ == "__main__":
    main()
