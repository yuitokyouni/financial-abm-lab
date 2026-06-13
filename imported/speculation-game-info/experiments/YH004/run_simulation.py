"""YH004: Grand Canonical Minority Game — シミュレーション実行と可視化.

Usage:
    cd experiments/YH004
    python run_simulation.py [--seed 42]

論文 Figure 1 の再現を中心に、6 パネル構成で動作を検証する。
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import matplotlib.pyplot as plt

from model import simulate, binomial_theory


# --------------------------------------------------------------------------
# Panel 1/2: Figure 1 再現. ⟨N_active⟩ と σ[N_active] を r_min でスキャン.
# --------------------------------------------------------------------------


def panel12_figure1_scan(
    N: int = 101, M: int = 2, S: int = 2, T_win: int = 50,
    T_burn: int = 500, T_measure: int = 5000,
    n_trials: int = 5, n_points: int = 21, seed0: int = 42,
):
    r_min_grid = np.linspace(-T_win, T_win, n_points)
    mean_active = np.zeros(n_points)
    std_active = np.zeros(n_points)
    sd_of_mean = np.zeros(n_points)
    sd_of_std = np.zeros(n_points)

    for i, rm in enumerate(r_min_grid):
        trial_means = []
        trial_stds = []
        for trial in range(n_trials):
            res = simulate(
                N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_measure,
                r_min_static=float(rm), seed=seed0 + 997 * i + trial,
            )
            active = res["active"][T_burn:]
            trial_means.append(float(active.mean()))
            trial_stds.append(float(active.std()))
        mean_active[i] = np.mean(trial_means)
        sd_of_mean[i] = np.std(trial_means)
        std_active[i] = np.mean(trial_stds)
        sd_of_std[i] = np.std(trial_stds)
        print(f"  r_min={rm:+6.1f}  <N_active>={mean_active[i]:6.2f}  "
              f"σ={std_active[i]:5.2f}")
    return r_min_grid, mean_active, sd_of_mean, std_active, sd_of_std


# --------------------------------------------------------------------------
# Panel 3: N_active(t) 時系列 (2 r_min 値).
# --------------------------------------------------------------------------


def panel3_active_series(
    N: int = 101, M: int = 2, S: int = 2, T_win: int = 50,
    r_min_values=(-25.0, 0.0, 15.0), T_burn: int = 500, T_show: int = 800,
    seed: int = 43,
):
    series = {}
    for k, rm in enumerate(r_min_values):
        res = simulate(
            N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_show,
            r_min_static=float(rm), seed=seed + 17 * k,
        )
        series[rm] = res["active"][T_burn:T_burn + T_show]
    return series


# --------------------------------------------------------------------------
# Panel 4: attendance 分布 (MG 極限 vs GCMG 中間 r_min).
# --------------------------------------------------------------------------


def panel4_attendance_dist(
    N: int = 1001, M: int = 3, S: int = 2, T_win: int = 50,
    T_burn: int = 1000, T_measure: int = 20000, seed: int = 44,
):
    # MG 極限
    res_mg = simulate(
        N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_measure,
        r_min_static=-float(T_win + 1), seed=seed,
    )
    # GCMG 中間: T_win/2 くらいに設定 (厳しめ閾値)
    res_gc = simulate(
        N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_measure,
        r_min_static=float(T_win) * 0.3, seed=seed + 1,
    )
    excess_mg = 2.0 * res_mg["attendance"][T_burn:].astype(np.float64) - N
    excess_gc = 2.0 * res_gc["attendance"][T_burn:].astype(np.float64) - N
    return excess_mg, excess_gc


# --------------------------------------------------------------------------
# Panel 5: σ²/N vs α for MG vs GCMG(r_min=0).
# --------------------------------------------------------------------------


def panel5_sigma2_alpha(
    N: int = 101, S: int = 2, T_win: int = 50,
    M_values=range(1, 11), T_burn: int = 500, T_measure: int = 5000,
    seed0: int = 45, n_trials: int = 5,
):
    alphas = []
    mg_vals = []
    gcmg_vals = []
    for M in M_values:
        alpha = (1 << M) / N
        mg_trials = []
        gc_trials = []
        for trial in range(n_trials):
            # MG 極限
            res_mg = simulate(
                N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_measure,
                r_min_static=-float(T_win + 1), seed=seed0 + 11 * M + trial,
            )
            mg_trials.append(res_mg["excess"][T_burn:].var() / N)
            # GCMG (r_min = 0)
            res_gc = simulate(
                N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_measure,
                r_min_static=0.0, seed=seed0 + 11 * M + trial,
            )
            gc_trials.append(res_gc["excess"][T_burn:].var() / N)
        alphas.append(alpha)
        mg_vals.append(float(np.mean(mg_trials)))
        gcmg_vals.append(float(np.mean(gc_trials)))
        print(f"  M={M:2d}  α={alpha:6.3f}  σ²/N: MG={mg_vals[-1]:.3f}  "
              f"GCMG(r_min=0)={gcmg_vals[-1]:.3f}")
    return np.array(alphas), np.array(mg_vals), np.array(gcmg_vals)


# --------------------------------------------------------------------------
# Panel 6: 動的 r_min. λ スイープで ⟨N_active⟩ を見る.
# --------------------------------------------------------------------------


def panel6_dynamic_trace(
    N: int = 101, M: int = 2, S: int = 2, T_win: int = 50,
    lam_values=(0.5, 1.5, 3.0),
    T_burn: int = 500, T_show: int = 2000, seed0: int = 46,
):
    """動的 r_min の N_active(t) を 3 λ 値で重ねる. Figure 2 相当."""
    traces = {}
    for k, lam in enumerate(lam_values):
        res = simulate(
            N=N, M=M, S=S, T_win=T_win, T_total=T_burn + T_show,
            lam=float(lam), seed=seed0 + 137 * k,
        )
        traces[lam] = res["active"][T_burn:T_burn + T_show]
        print(f"  λ={lam:4.1f}  <N_active>={traces[lam].mean():6.2f}  "
              f"σ={traces[lam].std():5.2f}")
    return traces


# --------------------------------------------------------------------------
# 検証チェック
# --------------------------------------------------------------------------


def run_checks(seed: int = 42):
    print("\n[Check] 検証チェック")
    # 1. Seed 再現性
    a = simulate(N=101, M=2, S=2, T_win=50, T_total=500,
                 r_min_static=0.0, seed=seed)
    b = simulate(N=101, M=2, S=2, T_win=50, T_total=500,
                 r_min_static=0.0, seed=seed)
    assert np.array_equal(a["active"], b["active"]), "seed 再現性 NG"
    print("  ✓ seed 再現性: 同一 seed で active 完全一致")

    # 2. MG 極限: r_min = -(T_win+1) なら全員参加
    res = simulate(N=101, M=3, S=2, T_win=50, T_total=500,
                   r_min_static=-51.0, seed=seed)
    assert (res["active"] == 101).all(), "MG 極限で active != 101"
    print("  ✓ MG 極限: r_min=-T-1 で常時 active=101")

    # 3. 完全抑制: r_min = T_win なら (ほぼ) 全員非参加
    res = simulate(N=101, M=3, S=2, T_win=50, T_total=500,
                   r_min_static=50.0, seed=seed)
    print(f"  ✓ 完全抑制: r_min=+T で mean active = {res['active'].mean():.2f} "
          "(期待 ~0)")

    # 4. YH003 σ²/N 近似一致 (T_win=T_total で rolling が無効化された場合)
    res = simulate(N=101, M=6, S=2, T_win=2000, T_total=2000,
                   r_min_static=-2001.0, seed=seed)
    v = res["excess"][500:].var() / 101
    print(f"  ✓ YH003 MG 同値: σ²/N = {v:.3f} "
          "(YH003 reported 0.268 for M=6, N=101, S=2)")


# --------------------------------------------------------------------------
# 6 パネル描画
# --------------------------------------------------------------------------


def build_figure(seed: int, out_path: str):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        "Jefferies et al. (2001) Grand-Canonical Minority Game — YH004",
        fontsize=14, fontweight="bold",
    )

    # --- Panel 1 & 2: Figure 1 reproduction ---
    print("\n[Panel 1&2] Figure 1 scan (N=101, M=2, S=2, T=50)")
    t0 = time.time()
    rm_grid, mean_a, sdm_a, std_a, sds_a = panel12_figure1_scan(
        N=101, M=2, S=2, T_win=50,
        T_burn=500, T_measure=5000, n_trials=5, n_points=21, seed0=seed,
    )
    print(f"  Panel 1&2 done in {time.time() - t0:.1f}s")
    th_grid = np.linspace(-50, 50, 201)
    th_mean, th_std = binomial_theory(N=101, S=2, T_win=50, r_min_grid=th_grid)

    ax = axes[0, 0]
    ax.errorbar(rm_grid, mean_a, yerr=sdm_a, fmt="o", color="navy",
                markersize=5, capsize=3, label="simulation (5-trial mean)")
    ax.plot(th_grid, th_mean, "r--", linewidth=1.2,
            label=r"binomial theory (p.5)")
    ax.set_xlabel(r"$r_{\min}$ (signed score, $[-T, T]$)")
    ax.set_ylabel(r"$\langle N_{\mathrm{active}} \rangle$")
    ax.set_title(r"(1) $\langle N_{\mathrm{active}} \rangle$ vs $r_{\min}$  "
                 r"(N=101, m=2, s=2, T=50)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.errorbar(rm_grid, std_a, yerr=sds_a, fmt="o", color="darkgreen",
                markersize=5, capsize=3, label="simulation")
    ax.plot(th_grid, th_std, "r--", linewidth=1.2, label="binomial theory")
    ax.set_xlabel(r"$r_{\min}$")
    ax.set_ylabel(r"$\sigma[N_{\mathrm{active}}]$")
    ax.set_title(r"(2) $\sigma[N_{\mathrm{active}}]$ vs $r_{\min}$  "
                 r"(Fig. 1 bottom)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Panel 3: N_active(t) time series ---
    print("\n[Panel 3] N_active(t) traces")
    t0 = time.time()
    traces = panel3_active_series(
        N=101, M=2, S=2, T_win=50,
        r_min_values=(-25.0, 0.0, 15.0),
        T_burn=500, T_show=800, seed=seed + 50,
    )
    print(f"  Panel 3 done in {time.time() - t0:.1f}s")
    ax = axes[0, 2]
    colors = {-25.0: "tab:blue", 0.0: "tab:orange", 15.0: "tab:red"}
    for rm, ser in traces.items():
        ax.plot(ser, linewidth=0.5, color=colors[rm], alpha=0.85,
                label=f"r_min={rm:+.0f}")
    ax.set_xlabel("t (after burn-in)")
    ax.set_ylabel(r"$N_{\mathrm{active}}(t)$")
    ax.set_title(r"(3) $N_{\mathrm{active}}(t)$ traces, 3 $r_{\min}$ values")
    ax.legend(fontsize=9)

    # --- Panel 4: excess distribution (MG vs GCMG) ---
    print("\n[Panel 4] Excess distribution (MG vs GCMG intermediate)")
    t0 = time.time()
    excess_mg, excess_gc = panel4_attendance_dist(
        N=1001, M=3, S=2, T_win=50, T_burn=1000, T_measure=20000,
        seed=seed + 100,
    )
    print(f"  Panel 4 done in {time.time() - t0:.1f}s")
    print(f"  MG: std={excess_mg.std():.2f}, kurt={_excess_kurt(excess_mg):.2f}")
    print(f"  GCMG(r_min=0.3T): std={excess_gc.std():.2f}, "
          f"kurt={_excess_kurt(excess_gc):.2f}")
    ax = axes[1, 0]
    bins = np.linspace(-max(abs(excess_mg).max(), abs(excess_gc).max()),
                       max(abs(excess_mg).max(), abs(excess_gc).max()), 80)
    ax.hist(excess_mg, bins=bins, density=True, alpha=0.55, color="tab:blue",
            label=f"MG (r_min=−T−1), kurt={_excess_kurt(excess_mg):+.2f}")
    ax.hist(excess_gc, bins=bins, density=True, alpha=0.55, color="tab:red",
            label=f"GCMG (r_min=0.3T), kurt={_excess_kurt(excess_gc):+.2f}")
    ax.set_yscale("log")
    ax.set_xlabel("excess = 2A − N")
    ax.set_ylabel("density (log)")
    ax.set_title(r"(4) Excess distribution: MG vs GCMG  (N=1001, m=3, s=2, T=50)")
    ax.legend(fontsize=9)

    # --- Panel 5: σ²/N vs α, MG vs GCMG ---
    print("\n[Panel 5] σ²/N vs α  (MG vs GCMG(r_min=0))")
    t0 = time.time()
    alphas, mg_vals, gc_vals = panel5_sigma2_alpha(
        N=101, S=2, T_win=50, M_values=range(1, 11),
        T_burn=500, T_measure=5000, seed0=seed + 200, n_trials=5,
    )
    print(f"  Panel 5 done in {time.time() - t0:.1f}s")
    ax = axes[1, 1]
    ax.loglog(alphas, mg_vals, "o-", color="tab:blue",
              markersize=6, label="MG (r_min=−T−1)")
    ax.loglog(alphas, gc_vals, "s-", color="tab:red",
              markersize=6, label="GCMG (r_min=0)")
    ax.axhline(1.0, color="gray", linestyle=":", alpha=0.5,
               label="random (σ²/N=1)")
    ax.set_xlabel(r"$\alpha = 2^M / N$")
    ax.set_ylabel(r"$\sigma^2 / N$")
    ax.set_title(r"(5) $\sigma^2/N$ vs $\alpha$: MG vs GCMG  (N=101, s=2, T=50)")
    ax.legend(fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    # --- Panel 6: Dynamic r_min, time traces ---
    print("\n[Panel 6] Dynamic r_min N_active(t) trace, 3 λ values")
    t0 = time.time()
    dyn_traces = panel6_dynamic_trace(
        N=101, M=2, S=2, T_win=50, lam_values=(0.5, 1.5, 3.0),
        T_burn=500, T_show=2000, seed0=seed + 300,
    )
    print(f"  Panel 6 done in {time.time() - t0:.1f}s")
    ax = axes[1, 2]
    colors6 = {0.5: "tab:blue", 1.5: "tab:orange", 3.0: "tab:red"}
    for lam, trace in dyn_traces.items():
        ax.plot(trace, linewidth=0.5, color=colors6[lam], alpha=0.85,
                label=f"λ={lam:.1f}  ⟨·⟩={trace.mean():.1f}")
    ax.set_xlabel("t (after burn-in)")
    ax.set_ylabel(r"$N_{\mathrm{active}}(t)$")
    ax.set_title(r"(6) Dynamic $r_{\min} = \max(0, \lambda\sigma(r_i) - r_i)$  "
                 r"(N=101, m=2, s=2, T=50)")
    ax.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    print(f"\nFigure saved to {out_path}")
    plt.close()


def _excess_kurt(x: np.ndarray) -> float:
    from scipy.stats import kurtosis
    return float(kurtosis(x, fisher=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-checks", action="store_true")
    args = ap.parse_args()

    print("=" * 64)
    print("Jefferies et al. (2001) Grand-Canonical Minority Game — YH004")
    print("=" * 64)
    print(f"seed = {args.seed}")

    if not args.skip_checks:
        run_checks(seed=args.seed)

    build_figure(seed=args.seed, out_path="results.png")


if __name__ == "__main__":
    main()
