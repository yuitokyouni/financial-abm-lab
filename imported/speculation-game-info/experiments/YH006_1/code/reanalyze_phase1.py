"""Stage S1 (tentative) — Phase 1 データ再分析.

役割 (S1 plan v2 §0.3 / §1):
  (a) 5 主指標 + plan B 先取り指標の実装 sanity check
  (b) Phase 1 → Phase 2 schema アダプタ確定 (w_open/w_close 再構成、w_init 抽出)
  (c) 桁感の事前確認

S2/S3 は本 S1 結果に関わらず実行され、plan A/B 分岐判定は S1-secondary
(S3 完了後の 100 trial bootstrap CI) でのみ行う。

入力: experiments/YH006_1/data/_phase1_imported/{c0u,c0p,C2,C3}_result.pkl
出力:
  - data/phase1_reanalysis_round_trips.parquet (RT 単位、4 条件 merge)
  - data/phase1_reanalysis_agents.parquet (agent 単位、4 条件 merge)
  - outputs/tables/tab_S1_phase1_reanalysis.csv (条件 × 指標 + interaction 行)
  - outputs/figures/fig_S1_indicator_comparison.png (bar chart)
  - README.md (本 Stage の結果サマリ、200 字)

ガード節 (S1 plan v2 §1 注意点 1): C2/C3 が無い段階の試走では warn を出して skip、
4 条件揃ってから interaction 計算は実行可能。最終実装ではこのガード節は撤去する
(= 4 条件揃った前提で例外を投げる)。

Run:
  cd experiments/YH006_1
  python -m code.reanalyze_phase1
or:
  python code/reanalyze_phase1.py
"""

from __future__ import annotations

import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
sys.path.insert(0, str(YH006_1))

# 直接実行と -m 実行の両対応
try:
    from code.analysis import (
        corr_pearson, corr_spearman, corr_kendall,
        bin_variance_slope, quantile_slope_diff,
        hill_estimator, skewness_high_low_diff, corr_winit_h_spearman,
    )
except ImportError:
    sys.path.insert(0, str(HERE))
    from analysis import (  # type: ignore[no-redef]
        corr_pearson, corr_spearman, corr_kendall,
        bin_variance_slope, quantile_slope_diff,
        hill_estimator, skewness_high_low_diff, corr_winit_h_spearman,
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONDITIONS: List[str] = ["C0u", "C0p", "C2", "C3"]

DATA_DIR = YH006_1 / "data" / "_phase1_imported"
OUT_DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

PKL_FILENAMES: Dict[str, str] = {
    "C0u": "c0u_result.pkl",
    "C0p": "c0p_result.pkl",
    "C2":  "C2_result.pkl",
    "C3":  "C3_result.pkl",
}

# Phase 1 expected reference values (experiments/YH006/README.md の Phase 1 表より)
EXPECTED: Dict[str, Dict[str, float]] = {
    "C0u": {"num_round_trips": 1_041_712, "alpha_hill_p90": 3.910, "min_size_mb": 40.0},
    "C0p": {"num_round_trips": 1_049_903, "alpha_hill_p90": 4.068, "min_size_mb": 40.0},
    "C2":  {"num_round_trips": 879,        "alpha_hill_p90": 1.98,  "min_size_mb": 0.05},
    "C3":  {"num_round_trips": 1_080,      "alpha_hill_p90": 1.91,  "min_size_mb": 0.05},
}

# Phase 1 sim parameters (w_init reconstruction + agent-level retire_step 用)
PHASE1_PARAMS: Dict[str, Dict[str, Any]] = {
    "C0u": {"world": "agg", "wealth_mode": "uniform", "N": 100, "B": 9, "seed": 777,
            "p0": 100.0, "M": 5, "S": 2, "T": 50_000},
    "C0p": {"world": "agg", "wealth_mode": "pareto", "N": 100, "B": 9, "seed": 777,
            "p0": 100.0, "M": 5, "S": 2, "T": 50_000,
            "pareto_alpha": 1.5, "pareto_xmin": 9},
    "C2":  {"world": "lob", "wealth_mode": "uniform", "N_sg": 100, "B": 9, "seed": 777,
            "T_main": 1500, "warmup": 200, "M": 5, "S": 2},
    "C3":  {"world": "lob", "wealth_mode": "pareto", "N_sg": 100, "B": 9, "seed": 777,
            "T_main": 1500, "warmup": 200, "M": 5, "S": 2,
            "pareto_alpha": 1.5, "pareto_xmin": 9.0},
}

# 5 main indicators + plan B preemptive
MAIN_INDICATORS: Tuple[str, ...] = (
    "rho_pearson",
    "rho_spearman",
    "tau_kendall",
    "bin_var_slope",
    "qreg_slope_diff",
)
PLAN_B_INDICATORS: Tuple[str, ...] = (
    "corr_winit_h",
    "skew_high_low_diff",
    "hill_alpha_dG",
)


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "errors").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S1")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(LOGS_DIR / "runtime" / f"{ts}_S1_reanalyze_phase1.log",
                             encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Step 1: pkl integrity check (S1 plan v2 §0.7)
# ---------------------------------------------------------------------------

def _hill_alpha_p90(final_wealth: np.ndarray) -> float:
    fw = np.asarray(final_wealth, dtype=np.float64)
    fw_pos = fw[fw > 0]
    if fw_pos.size <= 10:
        return float("nan")
    xmin = float(np.percentile(fw_pos, 90))
    tail = fw_pos[fw_pos >= xmin]
    if tail.size < 2 or xmin <= 0:
        return float("nan")
    log_ratio = float(np.log(tail / xmin).mean())
    return 1.0 / log_ratio if log_ratio > 0 else float("nan")


def integrity_check(
    cond: str, pkl_path: Path, logger: logging.Logger,
) -> Dict[str, Any]:
    """Return loaded pkl dict if all checks pass, else raise.

    最終実装 (plan v2 §1 注意点 1): 4 条件揃った前提。pkl 不在 / size 不足 /
    schema 不整合 / RT 数不一致 はすべて例外で停止。
    """
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"[integrity] {cond}: pkl missing at {pkl_path}. "
            f"4 conditions are required; transfer C2/C3 from Mac to "
            f"experiments/YH006_1/data/_phase1_imported/."
        )
    file_size_mb = pkl_path.stat().st_size / 1e6
    if file_size_mb < EXPECTED[cond]["min_size_mb"]:
        raise ValueError(
            f"[integrity] {cond}: file_size = {file_size_mb:.3f} MB < "
            f"expected min {EXPECTED[cond]['min_size_mb']} MB. pkl may be truncated."
        )
    logger.info(f"[integrity] {cond}: file_size = {file_size_mb:.2f} MB OK")

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    if "round_trips" not in data:
        raise KeyError(f"[integrity] {cond}: pkl missing 'round_trips' key")
    n_rt = int(data["round_trips"]["close_t"].size)
    expected_rt = EXPECTED[cond]["num_round_trips"]
    rel_err = abs(n_rt - expected_rt) / max(expected_rt, 1)
    if rel_err > 0.01:
        raise ValueError(
            f"[integrity] {cond}: num_round_trips mismatch — got {n_rt}, "
            f"expected {expected_rt} (rel_err={rel_err:.4f}) > 1%"
        )
    logger.info(
        f"[integrity] {cond}: num_round_trips = {n_rt} (expected {expected_rt}, rel_err={rel_err:.5f}) OK"
    )

    fw = data.get("final_wealth")
    if fw is not None:
        alpha_obs = _hill_alpha_p90(np.asarray(fw))
        alpha_exp = EXPECTED[cond]["alpha_hill_p90"]
        if np.isfinite(alpha_obs):
            rel_err_a = abs(alpha_obs - alpha_exp) / max(alpha_exp, 0.01)
            if rel_err_a > 0.05:
                logger.warning(
                    f"[integrity] {cond}: alpha_hill={alpha_obs:.3f} "
                    f"vs expected {alpha_exp:.3f} (rel_err={rel_err_a:.3f}) > 5% (continuing)"
                )
            else:
                logger.info(
                    f"[integrity] {cond}: alpha_hill = {alpha_obs:.3f} "
                    f"(expected {alpha_exp:.3f}, rel_err={rel_err_a:.4f}) OK"
                )
    return data


# ---------------------------------------------------------------------------
# Step 2: schema adapter — w_init reconstruction + Phase 2 §2.1/§2.2 schema
# ---------------------------------------------------------------------------

def reconstruct_w_init_aggregate(
    seed: int, N: int, B: int, wealth_mode: str,
    pareto_alpha: float = 1.5, pareto_xmin: int = 9,
    M: int = 5, S: int = 2,
) -> np.ndarray:
    """aggregate_sim.simulate_aggregate の RNG 消費順を replicate して w_init を抽出。

    aggregate_sim.py:62-73 のコード sequence (strategies → init_u100 → init_active
    → mu0 → [pareto: u_pareto]) を踏襲する。test_aggregate_parity で bit-一致が
    検証済の経路。
    """
    rng = np.random.default_rng(seed)
    K = 5 ** M
    _ = rng.choice([-1, 0, 1], size=(N, S, K)).astype(np.int8)
    init_u100 = rng.integers(0, 100, size=N)
    _ = rng.integers(0, S, size=N).astype(np.int64)
    _ = int(rng.integers(0, K))
    if wealth_mode == "uniform":
        w = (int(B) + init_u100).astype(np.int64)
    elif wealth_mode == "pareto":
        u_pareto = rng.uniform(0.0, 1.0, size=N)
        w_float = pareto_xmin * (u_pareto ** (-1.0 / pareto_alpha))
        w = w_float.astype(np.int64)
        w[w < int(B)] = int(B)
    else:
        raise ValueError(f"unknown wealth_mode={wealth_mode}")
    return w


def reconstruct_w_init_lob(
    seed: int, N_sg: int, B: int, wealth_mode: str,
    pareto_alpha: float = 1.5, pareto_xmin: float = 9.0,
    logger: Optional[logging.Logger] = None,
) -> Optional[np.ndarray]:
    """LOB SpeculationAgent.setup() RNG 消費を replicate (要 PAMS).

    PAMS の SequentialRunner は random.Random(seed) を simulator.prng とし、
    各 agent には simulator が prng を分配する。Pure-Python で agent.prng の
    state を bit-一致で再現するには PAMS の class_register / agent setup を
    通す必要があり、Windows env では PAMS が無いので None を返す。

    Mac 環境で実行する場合のみ pams を import して再現可能。本 v2 では
    Windows-only の S1 sanity check では LOB 側の corr(w_init, h) を skip。
    """
    try:
        import random  # noqa: F401
        # Lazy import — PAMS が無ければ ImportError
        from pams.runners import SequentialRunner  # noqa: F401, type: ignore
    except ImportError:
        if logger:
            logger.warning(
                "[w_init/lob] PAMS unavailable on this env — LOB w_init reconstruction skipped. "
                "Run on Mac or supplement Phase 2 sim with explicit w_init logging."
            )
        return None

    # Mac で動かす場合の参考実装スケッチ (本 v2 の Windows test では到達しない):
    #   sg_block の wealth_mode 分岐に合わせて simulator.prng から N_sg 個を draw
    #   ただし PAMS の internal prng split は black-box なので、確実なのは
    #   SequentialRunner を空で 1 回だけ実行して setup() 完了直後の sg_wealth を抽出する方法。
    #   実装は YH006_1 Phase 2 で SG agent に w_init logging を追加することで本問題を回避する。
    if logger:
        logger.warning(
            "[w_init/lob] LOB w_init replay is not implemented in v2 (Mac-side TODO)."
        )
    return None


def adapt_to_phase2_schemas(
    cond: str, pkl_data: Dict[str, Any], logger: logging.Logger,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Phase 1 pkl dict を Phase 2 §2.1 (RT 単位) + §2.2 (agent 単位) DataFrame へ変換。"""
    rt = pkl_data["round_trips"]
    params = PHASE1_PARAMS[cond]

    # ---- §2.1 RT 単位 ----
    rt_df = pd.DataFrame({
        "agent_id": np.asarray(rt["agent_idx"], dtype=np.int64),
        "t_open": np.asarray(rt["open_t"], dtype=np.int64),
        "t_close": np.asarray(rt["close_t"], dtype=np.int64),
        "horizon": (np.asarray(rt["close_t"], dtype=np.int64) -
                    np.asarray(rt["open_t"], dtype=np.int64)),
        "direction": np.asarray(rt["entry_action"], dtype=np.int8),
        "q": np.asarray(rt["entry_quantity"], dtype=np.int64),
        "delta_g": np.asarray(rt["delta_G"], dtype=np.float64),
    })
    rt_df = rt_df.sort_values(["agent_id", "t_open"], kind="stable").reset_index(drop=True)
    rt_df["rt_idx"] = rt_df.groupby("agent_id").cumcount()

    # ---- w_init: agent-level 生涯初期 wealth ----
    if params["world"] == "agg":
        w_init = reconstruct_w_init_aggregate(
            seed=params["seed"], N=params["N"], B=params["B"],
            wealth_mode=params["wealth_mode"],
            pareto_alpha=params.get("pareto_alpha", 1.5),
            pareto_xmin=params.get("pareto_xmin", 9),
            M=params["M"], S=params["S"],
        )
        N_total = params["N"]
    else:
        w_init = reconstruct_w_init_lob(
            seed=params["seed"], N_sg=params["N_sg"], B=params["B"],
            wealth_mode=params["wealth_mode"],
            pareto_alpha=params.get("pareto_alpha", 1.5),
            pareto_xmin=params.get("pareto_xmin", 9.0),
            logger=logger,
        )
        N_total = params["N_sg"]

    # ---- w_open / w_close per RT (post-hoc 累積再構成) ----
    # bankruptcy substitute を考慮しない単純累積。Phase 1 の substitute_events が
    # pkl に乗っていない (yh006_to_yh005_adapter は load しない) ため、
    # substitute 跨ぎの正確な再構成は不可。S1 sanity check の範囲では許容、
    # parquet には書き出すが S1 主指標としては使わない。
    rt_df["delta_w"] = rt_df["delta_g"] * rt_df["q"].astype(np.float64)
    rt_df["cum_dw"] = rt_df.groupby("agent_id")["delta_w"].cumsum()
    if w_init is not None:
        w_init_map = pd.Series(
            data=np.asarray(w_init, dtype=np.float64),
            index=np.arange(N_total),
            name="w_init",
        )
        rt_df = rt_df.merge(
            w_init_map.rename("w_init"),
            how="left",
            left_on="agent_id",
            right_index=True,
        )
        rt_df["w_close"] = rt_df["w_init"] + rt_df["cum_dw"]
        rt_df["w_open"] = rt_df["w_close"] - rt_df["delta_w"]
    else:
        rt_df["w_init"] = np.nan
        rt_df["w_open"] = np.nan
        rt_df["w_close"] = np.nan
    rt_df.drop(columns=["delta_w", "cum_dw"], inplace=True)

    rt_df["cond"] = cond
    rt_df["seed"] = params["seed"]

    # ---- §2.2 agent 単位 ----
    final_wealth = np.asarray(pkl_data.get("final_wealth", np.full(N_total, np.nan)),
                              dtype=np.float64)
    if final_wealth.size != N_total:
        logger.warning(
            f"[adapter] {cond}: final_wealth size ({final_wealth.size}) ≠ N_total ({N_total})"
        )
        # Pad/truncate
        fw_padded = np.full(N_total, np.nan, dtype=np.float64)
        copy_n = min(final_wealth.size, N_total)
        fw_padded[:copy_n] = final_wealth[:copy_n]
        final_wealth = fw_padded

    n_rt_per_agent = rt_df.groupby("agent_id").size().reindex(
        np.arange(N_total), fill_value=0
    ).to_numpy()

    # Phase 1 は per-agent birth/retire を記録していないので近似:
    # birth=0、retire=T (全員 sim 終了まで生存と仮定、wealth<B substitute は
    # 1 つの agent_id 内で発生して同じ agent_id で続く)
    if params["world"] == "agg":
        T_total = params["T"]
    else:
        T_total = params["T_main"]

    agents_df = pd.DataFrame({
        "agent_id": np.arange(N_total, dtype=np.int64),
        "birth_step": np.zeros(N_total, dtype=np.int64),
        "retire_step": np.full(N_total, T_total, dtype=np.int64),
        "lifetime": np.full(N_total, T_total, dtype=np.int64),
        "w_init": (np.asarray(w_init, dtype=np.float64)
                   if w_init is not None else np.full(N_total, np.nan)),
        "w_final": final_wealth,
        "forced_retired": np.zeros(N_total, dtype=bool),  # Phase 1 未記録
        "lifetime_capped": np.zeros(N_total, dtype=bool),  # Phase 2 only
        "n_round_trips": n_rt_per_agent.astype(np.int64),
        "cond": cond,
        "seed": params["seed"],
    })

    return rt_df, agents_df


# ---------------------------------------------------------------------------
# Step 3 + 4: indicators + timescale
# ---------------------------------------------------------------------------

def compute_indicators(rt_df: pd.DataFrame, agents_df: pd.DataFrame) -> Dict[str, float]:
    """5 main + plan B preemptive を計算して dict で返す。"""
    h = rt_df["horizon"].to_numpy(dtype=np.float64)
    dG = rt_df["delta_g"].to_numpy(dtype=np.float64)
    abs_dG = np.abs(dG)
    return {
        "n_rt": int(len(rt_df)),
        "rho_pearson": corr_pearson(h, abs_dG),
        "rho_spearman": corr_spearman(h, abs_dG),
        "tau_kendall": corr_kendall(h, abs_dG),
        "bin_var_slope": bin_variance_slope(h, dG, K=15),
        "qreg_slope_diff": quantile_slope_diff(h, dG),
        "corr_winit_h": corr_winit_h_spearman(rt_df, agents_df),
        "skew_high_low_diff": skewness_high_low_diff(h, dG),
        "hill_alpha_dG": hill_estimator(dG, n_tail_frac=0.10),
    }


def compute_timescale_indicators(
    rt_df: pd.DataFrame,
) -> Dict[str, Dict[str, float]]:
    """RT count median split (S1 plan v2 §0.2) で前半/後半の 5 主指標を計算。"""
    sorted_df = rt_df.sort_values("t_open", kind="stable").reset_index(drop=True)
    n = len(sorted_df)
    n_half = n // 2
    halves = {
        "first_half": sorted_df.iloc[:n_half],
        "second_half": sorted_df.iloc[n_half:],
    }
    out: Dict[str, Dict[str, float]] = {}
    for name, sub in halves.items():
        if len(sub) < 2:
            out[name] = {k: float("nan") for k in MAIN_INDICATORS}
            out[name]["n_rt"] = int(len(sub))
            continue
        h = sub["horizon"].to_numpy(dtype=np.float64)
        dG = sub["delta_g"].to_numpy(dtype=np.float64)
        abs_dG = np.abs(dG)
        out[name] = {
            "n_rt": int(len(sub)),
            "rho_pearson": corr_pearson(h, abs_dG),
            "rho_spearman": corr_spearman(h, abs_dG),
            "tau_kendall": corr_kendall(h, abs_dG),
            "bin_var_slope": bin_variance_slope(h, dG, K=15),
            "qreg_slope_diff": quantile_slope_diff(h, dG),
        }
    return out


# ---------------------------------------------------------------------------
# Step 5: interaction
# ---------------------------------------------------------------------------

def compute_interaction(metrics_by_cond: Dict[str, Dict[str, float]],
                        indicator: str) -> float:
    """[ρ(C3) − ρ(C2)] − [ρ(C0p) − ρ(C0u)] for a given indicator."""
    try:
        v_C3 = metrics_by_cond["C3"][indicator]
        v_C2 = metrics_by_cond["C2"][indicator]
        v_C0p = metrics_by_cond["C0p"][indicator]
        v_C0u = metrics_by_cond["C0u"][indicator]
    except KeyError:
        return float("nan")
    if any(not np.isfinite(v) for v in (v_C3, v_C2, v_C0p, v_C0u)):
        return float("nan")
    return float((v_C3 - v_C2) - (v_C0p - v_C0u))


# ---------------------------------------------------------------------------
# Step 6: outputs (csv + figure + README)
# ---------------------------------------------------------------------------

def make_summary_table(
    metrics: Dict[str, Dict[str, float]],
    timescale: Dict[str, Dict[str, Dict[str, float]]],
    interactions: Dict[str, float],
) -> pd.DataFrame:
    rows = []
    for cond, m in metrics.items():
        row: Dict[str, Any] = {"cond": cond, **m}
        if cond in timescale:
            for half_name, hm in timescale[cond].items():
                for k, v in hm.items():
                    row[f"{k}_{half_name}"] = v
        rows.append(row)
    if interactions:
        inter_row: Dict[str, Any] = {"cond": "interaction"}
        for k, v in interactions.items():
            inter_row[k] = v
        rows.append(inter_row)
    return pd.DataFrame(rows)


def plot_indicator_comparison(
    metrics: Dict[str, Dict[str, float]],
    interactions: Dict[str, float],
    out_path: Path,
    logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(12, 8),
                             gridspec_kw={"height_ratios": [3, 1]})
    ax_main = axes[0]
    indicator_labels = {
        "rho_pearson": "Pearson ρ",
        "rho_spearman": "Spearman ρ",
        "tau_kendall": "Kendall τ",
        "bin_var_slope": "bin Var slope",
        "qreg_slope_diff": "Qreg slope diff (q90-q10)",
    }
    indicators = list(indicator_labels.keys())
    cond_order = [c for c in CONDITIONS if c in metrics]
    n_cond = len(cond_order)
    n_ind = len(indicators)
    width = 0.8 / max(n_cond, 1)
    x = np.arange(n_ind)
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641",
               "C2": "#d95f02", "C3": "#a63603"}
    for i, cond in enumerate(cond_order):
        vals = [metrics[cond].get(ind, np.nan) for ind in indicators]
        ax_main.bar(x + i * width - 0.4 + width / 2, vals, width,
                    label=cond, color=palette.get(cond, "gray"))
    ax_main.set_xticks(x)
    ax_main.set_xticklabels([indicator_labels[i] for i in indicators], rotation=15)
    ax_main.axhline(0, color="black", linewidth=0.5)
    ax_main.set_ylabel("indicator value")
    ax_main.set_title(
        "S1 (tentative) — 5 main indicators × conditions  "
        "(point estimates; CI is S1-secondary scope)"
    )
    ax_main.legend(loc="best", fontsize=9)

    ax_inter = axes[1]
    i_vals = [interactions.get(ind, np.nan) for ind in indicators]
    bars = ax_inter.bar(x, i_vals, color=["#444"] * n_ind, edgecolor="black")
    for bar, v in zip(bars, i_vals):
        if np.isfinite(v):
            ax_inter.text(bar.get_x() + bar.get_width() / 2, v,
                          f"{v:+.3f}", ha="center",
                          va="bottom" if v >= 0 else "top", fontsize=9)
    ax_inter.set_xticks(x)
    ax_inter.set_xticklabels([indicator_labels[i] for i in indicators], rotation=15)
    ax_inter.axhline(0, color="black", linewidth=0.5)
    ax_inter.set_ylabel("interaction\n(C3-C2)-(C0p-C0u)")
    ax_inter.set_title(
        "Interaction = (C3 − C2) − (C0p − C0u)  "
        "(point estimates; CI is S1-secondary scope)"
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    import matplotlib.pyplot as _plt
    _plt.close(fig)
    logger.info(f"[output] saved figure: {out_path}")


def write_readme(
    loaded_conds: List[str],
    metrics: Dict[str, Dict[str, float]],
    interactions: Dict[str, float],
    timescale: Dict[str, Dict[str, Dict[str, float]]],
    out_path: Path,
) -> None:
    n_loaded = len(loaded_conds)
    lines: List[str] = []
    lines.append("# YH006_1 — Phase 2 結果サマリ")
    lines.append("")
    lines.append("## Stage S1 (tentative) — Phase 1 データ再分析")
    lines.append("")
    lines.append(
        f"**実行範囲**: {n_loaded} / 4 条件で完走 ("
        + ", ".join(loaded_conds) + ")"
    )
    lines.append("")
    lines.append("### 5 主指標 (点推定、CI は S1-secondary で取る)")
    lines.append("")
    lines.append("| cond | n_rt | Pearson | Spearman | Kendall | binVar slope | qreg slope diff |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for cond in CONDITIONS:
        if cond not in metrics:
            lines.append(f"| {cond} | — | — | — | — | — | — |")
            continue
        m = metrics[cond]
        lines.append(
            f"| {cond} | {m['n_rt']:,} | {m['rho_pearson']:.4f} | "
            f"{m['rho_spearman']:.4f} | {m['tau_kendall']:.4f} | "
            f"{m['bin_var_slope']:.4f} | {m['qreg_slope_diff']:.4f} |"
        )
    lines.append("")
    lines.append("### Interaction = (C3 − C2) − (C0p − C0u)")
    lines.append("")
    lines.append("| indicator | full | first half | second half |")
    lines.append("|---|---:|---:|---:|")
    for ind in MAIN_INDICATORS:
        v = interactions.get(ind, float("nan"))
        v1 = interactions.get(f"{ind}_first_half", float("nan"))
        v2 = interactions.get(f"{ind}_second_half", float("nan"))
        lines.append(f"| {ind} | {v:+.4f} | {v1:+.4f} | {v2:+.4f} |")
    lines.append("")
    lines.append("### Plan B 先取り指標")
    lines.append("")
    lines.append("| cond | corr(w_init, h) | skew(high − low) | Hill α (|ΔG|) |")
    lines.append("|---|---:|---:|---:|")
    for cond in CONDITIONS:
        if cond not in metrics:
            lines.append(f"| {cond} | — | — | — |")
            continue
        m = metrics[cond]
        lines.append(
            f"| {cond} | {m['corr_winit_h']:.4f} | "
            f"{m['skew_high_low_diff']:.4f} | {m['hill_alpha_dG']:.4f} |"
        )
    lines.append("")
    lines.append("### S1 (tentative) の役割と判定")
    lines.append("")
    lines.append(
        "本 Stage は (a) 5 指標実装 sanity check / (b) Phase 1 → Phase 2 schema "
        "アダプタ確定 / (c) 桁感の事前確認、の 3 点に scope 限定。**plan A/B 分岐"
        "判定は出さない**。最終確定は S3 完了後の S1-secondary (100 trial bootstrap "
        "CI) で行う。S2/S3 は本 S1 結果に関わらず実行される。"
    )
    lines.append("")
    lines.append("### Layer 2 timescale concern (Phase 2 scope 外)")
    lines.append("")
    lines.append(
        "Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を"
        "超える長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + "
        "proposal Limitations 節に明記する。"
    )
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)
    OUT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("Stage S1 (tentative) — Phase 1 reanalysis")
    logger.info("=" * 70)

    # ---- Step 1: integrity check + load ----
    # 最終実装 (plan v2 §1 注意点 1): 4 条件揃った前提、不在は raise。
    logger.info("--- Step 1: pkl integrity check + load ---")
    loaded: Dict[str, Dict[str, Any]] = {}
    for cond in CONDITIONS:
        pkl_path = DATA_DIR / PKL_FILENAMES[cond]
        loaded[cond] = integrity_check(cond, pkl_path, logger)
    assert len(loaded) == 4, (
        f"expected all 4 conditions loaded, got {len(loaded)}: "
        f"{list(loaded.keys())}"
    )

    # ---- Step 2: schema adapter ----
    logger.info("--- Step 2: Phase 1 → Phase 2 schema adapter ---")
    rt_dfs: List[pd.DataFrame] = []
    agents_dfs: List[pd.DataFrame] = []
    for cond, data in loaded.items():
        rt_df, agents_df = adapt_to_phase2_schemas(cond, data, logger)
        rt_dfs.append(rt_df)
        agents_dfs.append(agents_df)
        logger.info(
            f"  {cond}: {len(rt_df):,} RTs, {len(agents_df)} agents adapted; "
            f"w_init available = {not agents_df['w_init'].isna().all()}"
        )
    rt_all = pd.concat(rt_dfs, ignore_index=True)
    agents_all = pd.concat(agents_dfs, ignore_index=True)

    rt_pq = OUT_DATA_DIR / "phase1_reanalysis_round_trips.parquet"
    ag_pq = OUT_DATA_DIR / "phase1_reanalysis_agents.parquet"
    rt_all.to_parquet(rt_pq, index=False)
    agents_all.to_parquet(ag_pq, index=False)
    logger.info(f"[output] saved parquet: {rt_pq} ({rt_pq.stat().st_size/1e6:.2f} MB)")
    logger.info(f"[output] saved parquet: {ag_pq} ({ag_pq.stat().st_size/1e3:.1f} KB)")

    # ---- Step 3: indicators ----
    logger.info("--- Step 3: 5 main + plan B preemptive indicators ---")
    metrics: Dict[str, Dict[str, float]] = {}
    for cond in loaded.keys():
        sub_rt = rt_all[rt_all["cond"] == cond]
        sub_ag = agents_all[agents_all["cond"] == cond]
        m = compute_indicators(sub_rt, sub_ag)
        metrics[cond] = m
        logger.info(
            f"  {cond}: n_rt={m['n_rt']:,}  "
            f"P={m['rho_pearson']:+.4f}  S={m['rho_spearman']:+.4f}  "
            f"K={m['tau_kendall']:+.4f}  binV={m['bin_var_slope']:+.4f}  "
            f"qreg={m['qreg_slope_diff']:+.4f}"
        )
        logger.info(
            f"          plan-B: corr(w_init,h)={m['corr_winit_h']:+.4f}  "
            f"skew_diff={m['skew_high_low_diff']:+.4f}  Hill_α={m['hill_alpha_dG']:.4f}"
        )

    # ---- Step 4: timescale (RT count median split) ----
    logger.info("--- Step 4: timescale half-time (RT count median split) ---")
    timescale: Dict[str, Dict[str, Dict[str, float]]] = {}
    for cond in loaded.keys():
        sub_rt = rt_all[rt_all["cond"] == cond]
        ts = compute_timescale_indicators(sub_rt)
        timescale[cond] = ts
        for half, vals in ts.items():
            logger.info(
                f"  {cond} {half} (n={vals['n_rt']:,}): "
                f"P={vals['rho_pearson']:+.4f}  S={vals['rho_spearman']:+.4f}  "
                f"K={vals['tau_kendall']:+.4f}  binV={vals['bin_var_slope']:+.4f}  "
                f"qreg={vals['qreg_slope_diff']:+.4f}"
            )

    # ---- Step 5: interaction (4 条件揃った前提) ----
    logger.info("--- Step 5: interaction calculation ---")
    interactions: Dict[str, float] = {}
    for ind in MAIN_INDICATORS:
        interactions[ind] = compute_interaction(metrics, ind)
    for half in ("first_half", "second_half"):
        ts_metrics = {c: timescale[c][half] for c in CONDITIONS}
        for ind in MAIN_INDICATORS:
            interactions[f"{ind}_{half}"] = compute_interaction(ts_metrics, ind)
    for k, v in interactions.items():
        logger.info(f"  interaction[{k}] = {v:+.4f}")

    # ---- Step 6: outputs (csv + figure + README) ----
    logger.info("--- Step 6: outputs ---")
    df_table = make_summary_table(metrics, timescale, interactions)
    csv_path = OUTPUTS_DIR / "tables" / "tab_S1_phase1_reanalysis.csv"
    df_table.to_csv(csv_path, index=False)
    logger.info(f"[output] saved csv: {csv_path}")

    fig_path = OUTPUTS_DIR / "figures" / "fig_S1_indicator_comparison.png"
    plot_indicator_comparison(metrics, interactions, fig_path, logger)

    readme_path = YH006_1 / "README.md"
    write_readme(list(loaded.keys()), metrics, interactions, timescale, readme_path)
    logger.info(f"[output] saved readme: {readme_path}")

    logger.info("=" * 70)
    logger.info(
        f"S1 (tentative) complete. Loaded {len(loaded)}/4 conditions. "
        f"Full interaction available: {len(loaded) == 4}."
    )
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
