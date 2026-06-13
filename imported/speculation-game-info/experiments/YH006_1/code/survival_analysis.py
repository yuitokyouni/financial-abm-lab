"""S5.7 — agent lifetime survival function S(τ) の matched-window 比較 (KM 推定).

S5.7 plan §3.1-§3.2:
  - 4 condition (C0u/C0p/C2/C3) の lifetimes を pool、agg は T=1500 で
    re-censor (S5.5 §3.3 `recensor_lifetime_T1500` と同規約)
  - Kaplan-Meier (右側打ち切り対応) で S(τ)、τ ∈ [1, 1500]
  - trial-level bootstrap (seed 単位 resample × 10,000) で
    τ ∈ {100, 250, 500, 750, 1000, 1250, 1499} の 95% CI
  - 全域 Greenwood 95% CI band (figure 用、pooled iid 仮定)
  - cumulative hazard Λ(τ) ≡ −ln S_KM(τ) 併記 (Nelson-Aalen ではない)
  - 区間平均 hazard ΔΛ/Δτ (agg の早期 ramp → 安定 ~3e-3 の定量化)
  - S5.5 の censoring 率 / n と assertion で整合検算 (規約ズレ検出)

対象物の明示 (重要): 本 stage の S(τ) は **agent lifetime** (birth → 退場) の
survival であって round-trip horizon ではない。C0u の RT horizon median = 2 /
rt/agent/step = 0.209 は YH005_1 と完全一致 (cross-experiment 整合検算済、
2026-06-07)。agg lifetime median ≈ 390 と RT horizon median = 2 は別の対象の
統計量で、矛盾ではない。図表は常に "agent lifetime" を明記する。

Run (Windows、PAMS 不要):
  cd experiments/YH006_1
  python -m code.survival_analysis
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS  # noqa: E402

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

AGG_CONDS = ["C0u", "C0p"]
LOB_CONDS = ["C2", "C3"]
ALL_CONDS = AGG_CONDS + LOB_CONDS

T_WINDOW = 1500
TAU_GRID = [100, 250, 500, 750, 1000, 1250, 1499]
HAZARD_EDGES = [0, 100, 250, 500, 750, 1000, 1250, 1499]
N_BOOT = 10_000

# S5.5 (tab_S5.5_lifetime_subsample.csv) の matched 値 — 整合 assertion の基準。
# 乖離 > 0.5%pt は plan §5 stop trigger (re-censor 規約の解釈ズレ)。
S55_EXPECTED_CENSORING = {
    "C0u": 0.254, "C0p": 0.224, "C2": 0.910, "C3": 0.730,
}
CENSORING_TOL = 0.005


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.7")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.7_survival.log", encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Load + re-censor (S5.5 §3.3 と同規約)
# ---------------------------------------------------------------------------

def load_lifetimes_matched(
    cond: str, seeds: List[int],
) -> pd.DataFrame:
    """cond の lifetimes を pool。agg cond は T=1500 で re-censor。

    re-censor 規約 (subsample_aggregate.py::recensor_lifetime_T1500 と同一):
      - t_birth >= 1500: drop
      - t_end <= 1500: そのまま (元の censored 継承)
      - t_birth < 1500 < t_end: lifetime = 1500 − t_birth, censored=True

    Returns: 列 [seed, lifetime, censored] の DataFrame
    """
    parts: List[pd.DataFrame] = []
    for seed in seeds:
        p = DATA_DIR / cond / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt = pd.read_parquet(p, columns=["t_birth", "t_end", "lifetime",
                                         "censored", "seed"])
        if len(lt) == 0:
            continue
        if cond in AGG_CONDS:
            lt = lt[lt["t_birth"] < T_WINDOW].copy()
            clip = lt["t_end"] > T_WINDOW
            lt.loc[clip, "lifetime"] = T_WINDOW - lt.loc[clip, "t_birth"]
            lt["censored"] = lt["censored"].astype(bool) | clip
        parts.append(lt[["seed", "lifetime", "censored"]])
    out = pd.concat(parts, ignore_index=True)
    out["lifetime"] = out["lifetime"].astype(int)
    out["censored"] = out["censored"].astype(bool)
    return out


# ---------------------------------------------------------------------------
# KM 推定 (seed 別 count 行列 → bootstrap を行列演算で回す)
# ---------------------------------------------------------------------------

def seed_count_matrices(
    lt: pd.DataFrame, seeds: List[int], t_max: int = T_WINDOW,
) -> Tuple[np.ndarray, np.ndarray]:
    """seed 別の (event, censor) count 行列を返す。shape = (n_seed, t_max+1)。

    D[s, t] = seed s で lifetime==t の event (非 censored) 数
    C[s, t] = seed s で lifetime==t の censored 数
    """
    n_seed = len(seeds)
    seed_idx = {s: i for i, s in enumerate(seeds)}
    D = np.zeros((n_seed, t_max + 1), dtype=np.float64)
    C = np.zeros((n_seed, t_max + 1), dtype=np.float64)
    life = np.clip(lt["lifetime"].to_numpy(int), 0, t_max)
    cens = lt["censored"].to_numpy(bool)
    sidx = lt["seed"].map(seed_idx).to_numpy(int)
    np.add.at(D, (sidx[~cens], life[~cens]), 1.0)
    np.add.at(C, (sidx[cens], life[cens]), 1.0)
    return D, C


def km_from_counts(d: np.ndarray, c: np.ndarray) -> np.ndarray:
    """集計済 count から離散 KM curve を返す。

    d, c: shape (..., t_max+1)。time t の risk set は lifetime >= t の全 sample
    (同時刻の censored は event 後に離脱する標準規約)。
    Returns: S — shape (..., t_max+1)、S[..., t] = P(lifetime > t)。
    """
    total = d + c
    # n_at_risk[t] = Σ_{u >= t} total[u] — 逆向き cumsum
    n_at_risk = np.flip(np.cumsum(np.flip(total, axis=-1), axis=-1), axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(n_at_risk > 0, 1.0 - d / np.where(n_at_risk > 0,
                                                            n_at_risk, 1.0), 1.0)
    return np.cumprod(factor, axis=-1)


def greenwood_band(
    d: np.ndarray, c: np.ndarray, S: np.ndarray, z: float = 1.96,
) -> Tuple[np.ndarray, np.ndarray]:
    """全域 Greenwood 95% CI band: Var[S(t)] = S(t)² Σ_{u≤t} d_u / (n_u (n_u − d_u)).

    pooled sample の iid 仮定 (trial clustering 無視) — figure の band 用。
    grid 点の trial-level bootstrap CI と幅を比較して log に出す。
    """
    total = d + c
    n_at_risk = np.flip(np.cumsum(np.flip(total)), axis=-1)
    denom = n_at_risk * (n_at_risk - d)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(denom > 0, d / np.where(denom > 0, denom, 1.0), 0.0)
    var = S ** 2 * np.cumsum(term)
    half = z * np.sqrt(var)
    return np.clip(S - half, 0.0, 1.0), np.clip(S + half, 0.0, 1.0)


def hazard_segments(S: np.ndarray, edges: List[int]) -> List[Dict[str, float]]:
    """区間平均 hazard = ΔΛ/Δτ (Λ ≡ −ln S_KM)。agg の早期 ramp を定量化する。"""
    rows = []
    lam = -np.log(np.clip(S, 1e-12, None))
    for lo, hi in zip(edges[:-1], edges[1:]):
        rows.append({
            "tau_lo": lo, "tau_hi": hi,
            "avg_hazard": float((lam[hi] - lam[lo]) / (hi - lo)),
        })
    return rows


def bootstrap_km_ci(
    D: np.ndarray, C: np.ndarray, taus: List[int],
    n_boot: int = N_BOOT, ci: float = 0.95,
    rng: np.random.Generator | None = None,
    chunk: int = 500,
) -> Dict[int, Tuple[float, float]]:
    """seed 単位 resample の bootstrap で S(τ) の percentile CI。

    resample は multinomial 重み W (n_boot, n_seed) で表現し、
    重み付き count 和 W @ D / W @ C から chunk ごとに KM をベクトル計算。
    """
    if rng is None:
        rng = np.random.default_rng(0)
    n_seed = D.shape[0]
    boot_S = np.empty((n_boot, len(taus)), dtype=np.float64)
    tau_arr = np.asarray(taus, dtype=int)
    done = 0
    while done < n_boot:
        m = min(chunk, n_boot - done)
        W = rng.multinomial(n_seed, np.full(n_seed, 1.0 / n_seed),
                            size=m).astype(np.float64)
        S = km_from_counts(W @ D, W @ C)          # (m, t_max+1)
        boot_S[done:done + m] = S[:, tau_arr]
        done += m
    alpha = (1.0 - ci) / 2.0
    lo = np.quantile(boot_S, alpha, axis=0)
    hi = np.quantile(boot_S, 1.0 - alpha, axis=0)
    return {int(t): (float(lo[i]), float(hi[i])) for i, t in enumerate(taus)}


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def plot_survival(
    curves: Dict[str, np.ndarray],
    gw_bands: Dict[str, Tuple[np.ndarray, np.ndarray]],
    ci_bands: Dict[str, Dict[int, Tuple[float, float]]],
    out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641",
               "C2": "#d62728", "C3": "#a50f15"}
    labels = {"C0u": "C0u (agg uniform, T1500 re-censor)",
              "C0p": "C0p (agg pareto, T1500 re-censor)",
              "C2": "C2 (LOB uniform)", "C3": "C3 (LOB pareto)"}
    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(11, 9))

    t = np.arange(T_WINDOW + 1)
    for cond in ALL_CONDS:
        S = curves[cond]
        lo, hi = gw_bands[cond]
        ax_top.fill_between(t, np.clip(lo, 1e-4, None), hi,
                            color=palette[cond], alpha=0.18, linewidth=0)
        ax_top.plot(t, S, color=palette[cond], label=labels[cond], linewidth=1.6)
        band = ci_bands[cond]
        taus = sorted(band.keys())
        ax_top.errorbar(
            taus, [S[tau] for tau in taus],
            yerr=[[S[tau] - band[tau][0] for tau in taus],
                  [band[tau][1] - S[tau] for tau in taus]],
            fmt="none", ecolor=palette[cond], capsize=3, linewidth=1.0,
        )
    ax_top.set_yscale("log")
    ax_top.set_ylabel("S(τ) = P(agent lifetime > τ)   [log]")
    ax_top.set_title(
        "S5.7 KM agent-lifetime survival, matched window T=1500 "
        "(band = Greenwood 95%; markers = trial-level bootstrap 95% CI)"
    )
    ax_top.legend()
    ax_top.grid(alpha=0.3, which="both")

    for cond in ALL_CONDS:
        S = curves[cond]
        with np.errstate(divide="ignore"):
            lam = -np.log(np.clip(S, 1e-12, None))
        ax_bottom.plot(t, lam, color=palette[cond], label=labels[cond],
                       linewidth=1.6)
    ax_bottom.set_yscale("log")
    ax_bottom.set_xlabel("agent lifetime τ (steps)")
    ax_bottom.set_ylabel("Λ(τ) ≡ −ln S_KM(τ)   [log]")
    ax_bottom.set_title("Cumulative hazard — gap is hazard-driven, not run-length-driven")
    ax_bottom.legend()
    ax_bottom.grid(alpha=0.3, which="both")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    seeds = list(range(ENSEMBLE_SEED_BASE,
                       ENSEMBLE_SEED_BASE + ENSEMBLE_N_TRIALS))

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("S5.7 survival_analysis — KM S(τ) matched window T=1500")
    logger.info("=" * 70)

    curves: Dict[str, np.ndarray] = {}
    ci_bands: Dict[str, Dict[int, Tuple[float, float]]] = {}
    gw_bands: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    rows: List[Dict[str, float]] = []
    hazard_rows: List[Dict[str, float]] = []
    consistency: Dict[str, Dict[str, float]] = {}

    for cond in ALL_CONDS:
        lt = load_lifetimes_matched(cond, seeds)
        cens_rate = float(lt["censored"].mean())
        n_total = int(len(lt))
        consistency[cond] = {"n_total": n_total, "censoring_rate": cens_rate}
        logger.info(
            f"[load] {cond}: n={n_total:,} censoring={cens_rate:.1%} "
            f"(S5.5 期待値 {S55_EXPECTED_CENSORING[cond]:.1%})"
        )
        # §3.2 整合 assertion — 乖離 > 0.5%pt は stop trigger
        diff = abs(cens_rate - S55_EXPECTED_CENSORING[cond])
        if diff > CENSORING_TOL:
            raise AssertionError(
                f"S5.5 整合 fail: {cond} censoring {cens_rate:.3%} vs "
                f"期待 {S55_EXPECTED_CENSORING[cond]:.1%} (乖離 {diff:.3%} > 0.5%pt) "
                f"— re-censor 規約の解釈ズレ疑い、停止して Yuito 相談 (plan §5)"
            )

        D, C = seed_count_matrices(lt, seeds)
        d_pool, c_pool = D.sum(axis=0), C.sum(axis=0)
        S_pooled = km_from_counts(d_pool, c_pool)
        curves[cond] = S_pooled
        band = bootstrap_km_ci(D, C, TAU_GRID, rng=np.random.default_rng(0))
        ci_bands[cond] = band
        gw_lo, gw_hi = greenwood_band(d_pool, c_pool, S_pooled)
        gw_bands[cond] = (gw_lo, gw_hi)
        # Greenwood (iid 仮定) vs trial-level bootstrap の幅比較 (τ=1499)
        bw = band[1499][1] - band[1499][0]
        gw = gw_hi[1499] - gw_lo[1499]
        logger.info(
            f"[ci_width] {cond} τ=1499: bootstrap={bw:.4f} greenwood={gw:.4f} "
            f"(ratio {bw / max(gw, 1e-12):.2f}x — bootstrap は trial clustering 込み)"
        )
        # 区間平均 hazard ΔΛ/Δτ
        for seg in hazard_segments(S_pooled, HAZARD_EDGES):
            seg["cond"] = cond
            hazard_rows.append(seg)
            logger.info(
                f"[hazard] {cond} [{seg['tau_lo']:>4},{seg['tau_hi']:>4}]: "
                f"{seg['avg_hazard']:.2e}/step"
            )

        for tau in TAU_GRID:
            s = float(S_pooled[tau])
            lo, hi = band[tau]
            lam = float(-np.log(max(s, 1e-12)))
            rows.append({
                "cond": cond, "tau": tau,
                "S_km": s, "S_ci_lo": lo, "S_ci_hi": hi,
                "cum_hazard": lam,
                "n_total": n_total, "censoring_rate": cens_rate,
            })
            logger.info(
                f"[km] {cond} S({tau}) = {s:.4f} [{lo:.4f}, {hi:.4f}] "
                f"Λ={lam:.3f}"
            )

    table = pd.DataFrame(rows)
    table_path = OUTPUTS_DIR / "tables" / "tab_S5.7_survival_matched.csv"
    table.to_csv(table_path, index=False)
    logger.info(f"[output] saved: {table_path} ({len(table)} rows)")

    hazard_table = pd.DataFrame(hazard_rows)[
        ["cond", "tau_lo", "tau_hi", "avg_hazard"]]
    hazard_path = OUTPUTS_DIR / "tables" / "tab_S5.7_hazard_segments.csv"
    hazard_table.to_csv(hazard_path, index=False)
    logger.info(f"[output] saved: {hazard_path} ({len(hazard_table)} rows)")

    plot_survival(curves, gw_bands, ci_bands,
                  OUTPUTS_DIR / "figures" / "fig_S5.7_survival_curves.png",
                  logger)

    # headline 数値 (plan §1(d)): matched τ=1499 の S(τ)
    headline = {cond: float(curves[cond][1499]) for cond in ALL_CONDS}
    gap_u = headline["C2"] / max(headline["C0u"], 1e-12)
    gap_p = headline["C3"] / max(headline["C0p"], 1e-12)
    logger.info(
        f"[headline] matched S(1499): "
        + ", ".join(f"{c}={headline[c]:.4f}" for c in ALL_CONDS)
        + f" | gap uniform={gap_u:,.0f}x pareto={gap_p:,.0f}x"
    )

    summary = {
        "stage": "S5.7",
        "T_window": T_WINDOW,
        "tau_grid": TAU_GRID,
        "n_boot": N_BOOT,
        "estimand": "agent lifetime survival (round-trip horizon ではない)",
        "cum_hazard_definition": "Λ(τ) ≡ −ln S_KM(τ) (Nelson-Aalen ではない)",
        "recensor_protocol": "subsample_aggregate.recensor_lifetime_T1500 と同一",
        "consistency_vs_S5.5": consistency,
        "cross_experiment_check": {
            "C0u_rt_horizon_median": 2.0,
            "C0u_rt_per_agent_step": 0.209,
            "note": "YH005_1 (median=2, 0.21 rt/agent/step) と一致 — RT 定義 drift なし。"
                    "agg lifetime median ≈ 390 と RT horizon median = 2 は別対象の統計量",
        },
        "headline_S_matched_1499": headline,
        "headline_gap": {"uniform_C2_over_C0u": gap_u,
                         "pareto_C3_over_C0p": gap_p},
        "hazard_segments": hazard_rows,
        "table_path": str(table_path),
        "hazard_table_path": str(hazard_path),
        "note": ("raw headline 81.1% vs 0.9% は horizon 交絡のため retire。"
                 "headline は hazard 構造で張る: agg は早期 ramp 後 ~3e-3/step で"
                 "安定 (median lifetime ≈390)、LOB は初期 shake-out 後 hazard→0。"
                 "52x/58x は『matched 窓末 τ=1499 の survival ratio』と明示して"
                 "curve 添付で引用 (Yuito review 2026-06-07)"),
    }
    out_json = LOGS_DIR / "S5.7_summary_for_diff.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {out_json}")

    logger.info("=" * 70)
    logger.info("S5.7 complete.")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
