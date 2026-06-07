"""S5.8 — LOB T=10000 延長 run の KM 延長 + H_frozen / H_transient 判定 (Windows).

S5.8 plan §2.3:
  - `data/{C2,C3}_T10k/lifetimes_*.parquet` (6 seed) から KM S(τ)、τ ∈ [1, 10000]
  - sanity (§3.2): 同 seed の T=1500 run (data/C2, data/C3) と前半 1500 step の
    lifetime 集合が exact 一致するか (sequential sim なので run 長は前半に影響しない)
  - agg 参照: C0u/C0p を T_window=10000 で re-censor して同 protocol で KM
  - KPI: 延長区間 [1500,3000] / [3000,5000] / [5000,10000] の ΔΛ/Δτ
      H_frozen 確定: 全区間 ≤ 1e-4 (両 cond) → S6 進行 GO
      H_transient:   いずれか ≥ 1e-3 → S6 再設計 + F1 refactor 議論
      ambiguous:     中間 → Yuito 議論

Run (Windows、Mac データ git pull 後):
  cd experiments/YH006_1
  python -m code.survival_extension
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

from survival_analysis import (  # noqa: E402
    km_from_counts, greenwood_band, hazard_segments, bootstrap_km_ci,
)

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

T_EXT = 10_000
T_MAIN = 1_500
SEEDS_EXT = list(range(1000, 1006))           # S5.8 plan §1.2
SEEDS_FULL = list(range(1000, 1100))          # agg 参照は 100 trial を流用
LOB_CONDS = ["C2", "C3"]
AGG_CONDS = ["C0u", "C0p"]

TAU_GRID_EXT = [1500, 2000, 3000, 5000, 7500, 9999]
HAZARD_EDGES_EXT = [0, 250, 1500, 3000, 5000, 9999]
EXT_SEGMENTS = [(1500, 3000), (3000, 5000), (5000, 9999)]

H_FROZEN_MAX = 1e-4     # plan §1.3 — agg ~3e-3 の 1/30 未満
H_TRANSIENT_MIN = 1e-3  # agg と同 order


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.8-win")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.8_survival_extension.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Load (window パラメタ化版 — survival_analysis.load_lifetimes_matched の一般化)
# ---------------------------------------------------------------------------

def load_lifetimes_window(
    data_subdir: str, seeds: List[int], t_window: int, recensor: bool,
) -> pd.DataFrame:
    """lifetimes を pool。recensor=True で T=t_window 打ち切り直し (agg 用)。

    LOB run は sim 自体が T=t_window で censoring 済なのでそのまま (recensor=False)。
    """
    parts: List[pd.DataFrame] = []
    for seed in seeds:
        p = DATA_DIR / data_subdir / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt = pd.read_parquet(p, columns=["t_birth", "t_end", "lifetime",
                                         "censored", "seed"])
        if len(lt) == 0:
            continue
        if recensor:
            lt = lt[lt["t_birth"] < t_window].copy()
            clip = lt["t_end"] > t_window
            lt.loc[clip, "lifetime"] = t_window - lt.loc[clip, "t_birth"]
            lt["censored"] = lt["censored"].astype(bool) | clip
        parts.append(lt[["seed", "lifetime", "censored"]])
    if not parts:
        raise FileNotFoundError(
            f"data/{data_subdir}: lifetimes parquet が見つからない "
            f"(Mac 側 S5.8 sim 完走 + git pull 済みか確認)"
        )
    out = pd.concat(parts, ignore_index=True)
    out["lifetime"] = out["lifetime"].astype(int)
    out["censored"] = out["censored"].astype(bool)
    return out


def count_matrices(
    lt: pd.DataFrame, seeds: List[int], t_max: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """seed 別 (event, censor) count 行列 (survival_analysis 版の t_max 一般化)。"""
    seed_idx = {s: i for i, s in enumerate(seeds)}
    D = np.zeros((len(seeds), t_max + 1), dtype=np.float64)
    C = np.zeros((len(seeds), t_max + 1), dtype=np.float64)
    life = np.clip(lt["lifetime"].to_numpy(int), 0, t_max)
    cens = lt["censored"].to_numpy(bool)
    sidx = lt["seed"].map(seed_idx).to_numpy(int)
    np.add.at(D, (sidx[~cens], life[~cens]), 1.0)
    np.add.at(C, (sidx[cens], life[cens]), 1.0)
    return D, C


# ---------------------------------------------------------------------------
# Sanity §3.2 — T10k run の前半 1500 step が T1500 run (S3) と exact 一致
# ---------------------------------------------------------------------------

def sanity_first_window(
    cond: str, seeds: List[int], logger: logging.Logger,
) -> bool:
    """sequential sim では run 長が前半に影響しないはず — exact 検算。

    検算対象: 各 seed で『t_end < T_MAIN の uncensored lifetime sample 集合
    (t_birth, t_end)』が data/{cond}/ (S3) と data/{cond}_T10k/ で一致。
    (S3 で censored だった agent は T10k では t_end >= T_MAIN で続行するため
    比較から除外する。)
    """
    ok = True
    for seed in seeds:
        a = pd.read_parquet(DATA_DIR / cond / f"lifetimes_{seed:04d}.parquet")
        b = pd.read_parquet(
            DATA_DIR / f"{cond}_T10k" / f"lifetimes_{seed:04d}.parquet")
        a_set = a[(~a["censored"].astype(bool)) & (a["t_end"] < T_MAIN)]
        b_set = b[(~b["censored"].astype(bool)) & (b["t_end"] < T_MAIN)]
        a_pairs = sorted(zip(a_set["t_birth"].astype(int),
                             a_set["t_end"].astype(int)))
        b_pairs = sorted(zip(b_set["t_birth"].astype(int),
                             b_set["t_end"].astype(int)))
        match = a_pairs == b_pairs
        ok = ok and match
        logger.info(
            f"[sanity] {cond} seed={seed}: 前半窓 uncensored sample "
            f"{len(a_pairs)} vs {len(b_pairs)} — {'MATCH' if match else 'MISMATCH'}"
        )
    return ok


# ---------------------------------------------------------------------------
# 判定 (plan §1.3)
# ---------------------------------------------------------------------------

def classify_extension(
    ext_hazards: Dict[str, List[Dict[str, float]]],
) -> Tuple[str, str]:
    all_h = [seg["avg_hazard"] for segs in ext_hazards.values() for seg in segs]
    if all(h <= H_FROZEN_MAX for h in all_h):
        return ("H_frozen",
                f"全延長区間の hazard ≤ {H_FROZEN_MAX:.0e} (max={max(all_h):.2e}) "
                f"→ plateau は bounded (定常凍結)。S6 進行 GO")
    if any(h >= H_TRANSIENT_MIN for h in all_h):
        return ("H_transient",
                f"延長区間に hazard ≥ {H_TRANSIENT_MIN:.0e} あり (max={max(all_h):.2e}) "
                f"→ T=1500 plateau は窓 artifact。S6 再設計 + F1 refactor を Yuito 議論")
    return ("ambiguous",
            f"中間 (max={max(all_h):.2e}) — 弱 transient、bound の言い方を Yuito 議論")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("S5.8 survival_extension — KM 延長 (T=10000) + H_frozen/H_transient 判定")
    logger.info("=" * 70)

    # ----- sanity §3.2 (stop trigger) -----
    for cond in LOB_CONDS:
        if not sanity_first_window(cond, SEEDS_EXT, logger):
            raise AssertionError(
                f"{cond}: T10k run の前半 1500 step が S3 run と不一致 — "
                f"main_steps override の副作用疑い、停止して Yuito 相談 (plan §4)"
            )

    curves: Dict[str, np.ndarray] = {}
    gw_bands: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    ci_bands: Dict[str, Dict[int, Tuple[float, float]]] = {}
    rows: List[Dict[str, float]] = []
    ext_hazards: Dict[str, List[Dict[str, float]]] = {}

    specs = (
        [(c, f"{c}_T10k", SEEDS_EXT, False) for c in LOB_CONDS]
        + [(c, c, SEEDS_FULL, True) for c in AGG_CONDS]   # agg 参照 (T=10000 re-censor)
    )
    for cond, subdir, seeds, recensor in specs:
        lt = load_lifetimes_window(subdir, seeds, T_EXT, recensor)
        logger.info(
            f"[load] {cond} ({subdir}): n={len(lt):,} "
            f"censoring={lt['censored'].mean():.1%} n_seed={lt['seed'].nunique()}"
        )
        D, C = count_matrices(lt, seeds, T_EXT)
        d_pool, c_pool = D.sum(axis=0), C.sum(axis=0)
        S = km_from_counts(d_pool, c_pool)
        curves[cond] = S
        gw_bands[cond] = greenwood_band(d_pool, c_pool, S)
        ci_bands[cond] = bootstrap_km_ci(D, C, TAU_GRID_EXT,
                                         rng=np.random.default_rng(0))
        for tau in TAU_GRID_EXT:
            lo, hi = ci_bands[cond][tau]
            rows.append({
                "cond": cond, "tau": tau, "S_km": float(S[tau]),
                "S_ci_lo": lo, "S_ci_hi": hi,
                "cum_hazard": float(-np.log(max(S[tau], 1e-12))),
            })
            logger.info(f"[km] {cond} S({tau}) = {S[tau]:.4f} [{lo:.4f}, {hi:.4f}]")
        segs = hazard_segments(S, [e for e in HAZARD_EDGES_EXT])
        for seg in segs:
            seg["cond"] = cond
        if cond in LOB_CONDS:
            ext_hazards[cond] = [
                {"tau_lo": lo, "tau_hi": hi,
                 "avg_hazard": float((-np.log(max(S[hi], 1e-12))
                                      + np.log(max(S[lo], 1e-12))) / (hi - lo))}
                for lo, hi in EXT_SEGMENTS
            ]
            for seg in ext_hazards[cond]:
                logger.info(
                    f"[hazard-ext] {cond} [{seg['tau_lo']},{seg['tau_hi']}]: "
                    f"{seg['avg_hazard']:.2e}/step"
                )

    # ----- KPI 判定 -----
    verdict, verdict_msg = classify_extension(ext_hazards)
    logger.info(f"[verdict] {verdict} — {verdict_msg}")

    # ----- 出力 -----
    pd.DataFrame(rows).to_csv(
        OUTPUTS_DIR / "tables" / "tab_S5.8_survival_extension.csv", index=False)
    haz_rows = [dict(cond=c, **seg) for c, segs in ext_hazards.items()
                for seg in segs]
    pd.DataFrame(haz_rows)[["cond", "tau_lo", "tau_hi", "avg_hazard"]].to_csv(
        OUTPUTS_DIR / "tables" / "tab_S5.8_hazard_extension.csv", index=False)

    import matplotlib.pyplot as plt
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641",
               "C2": "#d62728", "C3": "#a50f15"}
    fig, ax = plt.subplots(figsize=(11, 6))
    t = np.arange(T_EXT + 1)
    for cond in AGG_CONDS + LOB_CONDS:
        n_seed = len(SEEDS_EXT) if cond in LOB_CONDS else len(SEEDS_FULL)
        lo, hi = gw_bands[cond]
        ax.fill_between(t, np.clip(lo, 1e-5, None), hi,
                        color=palette[cond], alpha=0.15, linewidth=0)
        ax.plot(t, curves[cond], color=palette[cond],
                label=f"{cond} (T=10000 window, {n_seed} seeds)", linewidth=1.6)
    ax.axvline(T_MAIN, color="gray", linestyle="--", linewidth=1.0,
               label="T=1500 (S5.7 window)")
    ax.set_yscale("log")
    ax.set_xlabel("agent lifetime τ (steps)")
    ax.set_ylabel("S(τ) = P(agent lifetime > τ)   [log]")
    ax.set_title(
        f"S5.8 KM extension to T=10000 — verdict: {verdict} "
        f"(band = Greenwood 95%)"
    )
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig_path = OUTPUTS_DIR / "figures" / "fig_S5.8_survival_extension.png"
    fig.savefig(fig_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {fig_path}")

    summary = {
        "stage": "S5.8",
        "T_ext": T_EXT,
        "seeds_ext": SEEDS_EXT,
        "verdict": verdict,
        "verdict_message": verdict_msg,
        "thresholds": {"H_frozen_max": H_FROZEN_MAX,
                       "H_transient_min": H_TRANSIENT_MIN},
        "ext_hazards": ext_hazards,
        "S_at_grid": {c: {str(tau): float(curves[c][tau]) for tau in TAU_GRID_EXT}
                      for c in curves},
        "sanity_first_window": "PASS (exact match、stop trigger 非発火)",
        "timestamp": datetime.now().isoformat(),
    }
    with open(LOGS_DIR / "S5.8_summary_for_diff.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {LOGS_DIR / 'S5.8_summary_for_diff.json'}")

    logger.info("=" * 70)
    logger.info(f"S5.8 complete. Verdict: {verdict}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
