"""S5.8 — LOB T=10000 延長 run の KM 延長 + H_frozen / H_transient 判定 (Windows).

S5.8 plan §2.3:
  - `data/{C2,C3}_T10k/lifetimes_*.parquet` (6 seed) から KM S(τ)、τ ∈ [1, 10000]
  - sanity (§3.2): 同 seed の T=1500 run (data/C2, data/C3) と前半 1500 step の
    lifetime 集合が exact 一致するか (sequential sim なので run 長は前半に影響しない)
  - agg 参照: C0u/C0p を T_window=10000 で re-censor して同 protocol で KM。
    さらに full window (T=50000) の agg hazard constancy を extinction まで確認
    (T=50000 外挿の妥当性の裏付け、P5)
  - KPI (plan v1.1 P2 — 閾値は Katahira T=50000 での gap 生存に anchor):
      延長区間 [1500,3000] / [3000,6000] / [6000,10000] の ΔΛ/Δτ を segment 別に見る
      (単一平均は slow leak を隠すため禁止)。
      H_frozen:      全区間 ≤ 2e-5 (S5.7 C2 late-window ~1e-5 オーダーの継続、
                     T=50000 外挿で gap 残存) → S6 進行 GO
      H_transient:   いずれか ≥ 1e-3 (agg steady 3.0-3.2e-3 へ climb)
                     → rescope (T=1500 測定値としては真、freeze が解ける τ を報告)
      H_partial_freeze (dead zone 2e-5 - 1e-3、pre-registered):
                     slow leak。S6 GO だが A3 解釈を「partial freeze の解除」に限定、
                     headline を「T < X で凍結」に qualify (X = 外挿で gap が
                     半減する T)。6 seed では hazard 点推定の解像不足のため
                     値そのものは headline しない

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
HAZARD_EDGES_EXT = [0, 250, 1500, 3000, 6000, 9999]
EXT_SEGMENTS = [(1500, 3000), (3000, 6000), (6000, 9999)]
AGG_FULL_SEGMENTS = [(1500, 5000), (5000, 15000), (15000, 30000), (30000, 49999)]

# 閾値 (plan v1.1 P2): Katahira T=50000 での gap 生存に anchor。
#   h=1e-4 だと S(50000) ≈ S(1500)·exp(−1e-4×48500) で gap はほぼ消える (緩すぎ)。
#   h=2e-5 → exp(−0.97)≈0.38、C2 91%→~34% で agg (~0) との gap が残る。
#   anchor: S5.7 C2 late-window hazard (tab_S5.7_hazard_segments.csv、~1e-5 オーダー)
H_FROZEN_MAX = 2e-5
H_TRANSIENT_MIN = 1e-3  # agg steady 3.0-3.2e-3 と同 order へ climb
T_KATAHIRA = 50_000


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
    """plan v1.1 P2 の pre-registered 判定。

    P3 注意: H_transient は F1 の否定ではなく rescope (T=1500 ≒ Katahira/33 での
    測定値としては真のまま、「friction-induced transient freeze が τ~X で解ける」
    へ格上げ)。どちらに転んでも Layer-2-timescale 留保が測定済み result になる。
    """
    all_h = [seg["avg_hazard"] for segs in ext_hazards.values() for seg in segs]
    if all(h <= H_FROZEN_MAX for h in all_h):
        return ("H_frozen",
                f"全延長区間 hazard ≤ {H_FROZEN_MAX:.0e} (max={max(all_h):.2e}) — "
                f"S5.7 C2 late-window plateau の継続、T=50000 外挿でも gap 残存 "
                f"→ 凍結は定常。S6 進行 GO、Layer-2-timescale 留保が消える")
    if any(h >= H_TRANSIENT_MIN for h in all_h):
        return ("H_transient",
                f"延長区間に hazard ≥ {H_TRANSIENT_MIN:.0e} (max={max(all_h):.2e}) — "
                f"agg steady へ climb。F1 は T=1500 測定値として真のまま "
                f"『freeze が解ける τ』へ rescope (panic 不要)。S6 設計は要調整、"
                f"Yuito 議論")
    return ("H_partial_freeze",
            f"dead zone (max={max(all_h):.2e} ∈ [2e-5, 1e-3]) — slow leak。"
            f"pre-registered 処理: S6 GO だが A3 解釈を『partial freeze の解除』に"
            f"限定、headline は『T < X で凍結』に qualify。6 seed では hazard 値の"
            f"解像不足、値そのものは headline しない")


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

    # ----- P5: agg full-window (T=50000) hazard constancy (外挿妥当性の裏付け) -----
    agg_full_segments: Dict[str, List[Dict[str, float]]] = {}
    agg_S_50k: Dict[str, float] = {}
    for cond in AGG_CONDS:
        lt = load_lifetimes_window(cond, SEEDS_FULL, T_KATAHIRA, recensor=False)
        D, C = count_matrices(lt, SEEDS_FULL, T_KATAHIRA)
        S_full = km_from_counts(D.sum(axis=0), C.sum(axis=0))
        agg_S_50k[cond] = float(S_full[T_KATAHIRA - 1])
        segs = []
        for lo, hi in AGG_FULL_SEGMENTS:
            h = float((-np.log(max(S_full[hi], 1e-12))
                       + np.log(max(S_full[lo], 1e-12))) / (hi - lo))
            segs.append({"tau_lo": lo, "tau_hi": hi, "avg_hazard": h})
            logger.info(f"[agg-full] {cond} [{lo},{hi}]: {h:.2e}/step")
        agg_full_segments[cond] = segs
        hs = [s["avg_hazard"] for s in segs]
        logger.info(
            f"[agg-full] {cond} constancy: max/min = "
            f"{max(hs) / max(min(hs), 1e-12):.2f}x "
            f"(≈1 なら extinction まで一定 hazard、T=50000 外挿は妥当) | "
            f"S(49999) = {agg_S_50k[cond]:.2e}"
        )

    # ----- P2: T=50000 外挿 — gap が Katahira スケールで生き残るか -----
    extrap: Dict[str, Dict[str, float]] = {}
    for cond in LOB_CONDS:
        h_last = ext_hazards[cond][-1]["avg_hazard"]
        S_9999 = float(curves[cond][9999])
        S_50k = S_9999 * float(np.exp(-h_last * (T_KATAHIRA - 9999)))
        agg_ref = max(np.mean(list(agg_S_50k.values())), 1e-12)
        extrap[cond] = {
            "h_last_segment": h_last,
            "S_9999": S_9999,
            "S_50000_extrap": S_50k,
            "gap_vs_agg_50k": S_50k / agg_ref,
        }
        logger.info(
            f"[extrap] {cond}: h_last={h_last:.2e} S(9999)={S_9999:.3f} → "
            f"S(50000)≈{S_50k:.3f}, gap vs agg ≈ {S_50k / agg_ref:,.0f}x"
        )
        # slow-leak 判別: 区間 hazard の trend (→0 か const か)
        hs = [s["avg_hazard"] for s in ext_hazards[cond]]
        trend = ("decaying→0" if hs[-1] < 0.5 * max(hs[0], 1e-12)
                 else "constant (slow leak 注意)")
        extrap[cond]["segment_trend"] = trend
        logger.info(f"[extrap] {cond} segment trend: {hs} → {trend}")

    # ----- KPI 判定 -----
    verdict, verdict_msg = classify_extension(ext_hazards)
    logger.info(f"[verdict] {verdict} — {verdict_msg}")

    # ----- 出力 -----
    pd.DataFrame(rows).to_csv(
        OUTPUTS_DIR / "tables" / "tab_S5.8_survival_extension.csv", index=False)
    haz_rows = (
        [dict(cond=c, window="ext_T10k", **seg)
         for c, segs in ext_hazards.items() for seg in segs]
        + [dict(cond=c, window="agg_full_T50k", **seg)
           for c, segs in agg_full_segments.items() for seg in segs]
    )
    pd.DataFrame(haz_rows)[
        ["cond", "window", "tau_lo", "tau_hi", "avg_hazard"]].to_csv(
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
        "thresholds": {
            "H_frozen_max": H_FROZEN_MAX,
            "H_transient_min": H_TRANSIENT_MIN,
            "anchor": ("Katahira T=50000 での gap 生存 (h=2e-5 → exp(−0.97)≈0.38 で"
                       "gap 残存; 1e-4 だと消える) + S5.7 C2 late-window hazard"),
            "pre_registered_dead_zone": ("S6 GO だが A3 解釈を partial freeze 解除に"
                                         "限定、headline を『T < X で凍結』に qualify"),
        },
        "ext_hazards": ext_hazards,
        "agg_full_window_constancy": agg_full_segments,
        "agg_S_50k": agg_S_50k,
        "extrapolation_T50k": extrap,
        "S_at_grid": {c: {str(tau): float(curves[c][tau]) for tau in TAU_GRID_EXT}
                      for c in curves},
        "sanity_first_window": "PASS (exact match、stop trigger 非発火)",
        "headline_caution": ("延長 hazard の点推定は 6 seed で CI 広 — "
                             "値そのものは headline しない (verdict と外挿の結論のみ)"),
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
