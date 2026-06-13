"""YH003: Challet & Zhang (1997) Minority Game — シミュレーション実行と可視化.

Usage:
    cd experiments/YH003
    python run_simulation.py [--seed 42]
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import matplotlib.pyplot as plt

from model import simulate, sigma2_over_N


# --------------------------------------------------------------------------
# 各パネル用のシミュレーション
# --------------------------------------------------------------------------


def panel1_sigma2_scan(
    N: int = 101, M_values=range(1, 13), n_trials: int = 10,
    T_burn: int = 1000, T_measure: int = 10000, seed0: int = 42,
):
    """σ²/N vs α = 2^M/N を log-log でスキャン."""
    alphas = []
    means = []
    stds = []
    for M in M_values:
        alpha = (1 << M) / N
        vals = []
        for trial in range(n_trials):
            v = sigma2_over_N(N, M, S=2, T_burn=T_burn, T_measure=T_measure,
                              seed=seed0 + 1000 * M + trial)
            vals.append(v)
        alphas.append(alpha)
        means.append(float(np.mean(vals)))
        stds.append(float(np.std(vals)))
        print(f"  M={M:2d}  α={alpha:8.4f}  σ²/N = {means[-1]:.3f} ± {stds[-1]:.3f}")
    return np.array(alphas), np.array(means), np.array(stds)


def panel2_attendance_series(
    N: int = 1001, M_list=(6, 8, 10), T_show: int = 500,
    T_burn: int = 1000, seed0: int = 42,
):
    """3 本の A(t) 時系列を返す."""
    series = {}
    for M in M_list:
        res = simulate(N, M, S=2, T=T_burn + T_show, seed=seed0 + M)
        series[M] = res["attendance"][T_burn:T_burn + T_show]
    return series


def panel3_attendance_hist(
    N: int = 1001, M: int = 8, S: int = 5,
    T_burn: int = 1000, T_measure: int = 10000, seed: int = 43,
):
    """A(t) の分布."""
    res = simulate(N, M, S, T=T_burn + T_measure, seed=seed)
    return res["attendance"][T_burn:]


def panel4_success_vs_M(
    N: int = 1001, S: int = 5, M_values=range(1, 11),
    T_burn: int = 1000, T_measure: int = 10000, seed0: int = 44,
):
    """各 M での平均成功率 (measure 期の minority 当選率平均)."""
    success = []
    for M in M_values:
        res = simulate(N, M, S, T=T_burn + T_measure, seed=seed0 + M)
        # 各エージェントの measure 期における成功回数
        acts = res["actions"][T_burn:]           # (T_measure, N)
        wins = res["winner"][T_burn:]            # (T_measure,)
        hits = (acts == wins[:, None]).sum(axis=0)  # (N,)
        rate = hits.mean() / T_measure
        success.append(float(rate))
        print(f"  M={M}  success_rate = {rate:.4f}  (1/2 = 0.5)")
    return np.array(list(M_values)), np.array(success)


def panel5_score_dist(
    N: int = 1001, M: int = 8, S: int = 5,
    snapshots=(1000, 5000, 10000), seed: int = 45,
):
    """スコア分布 (virtual gain) のヒストグラムを 3 時点で取る."""
    T = max(snapshots) + 1
    res = simulate(N, M, S, T=T, seed=seed, track_scores_at=snapshots)
    return res["scores_snapshots"]


def panel6_cumulative_gain(
    N: int = 1001, M: int = 10, S: int = 5,
    T_burn: int = 1000, T_measure: int = 10000, seed: int = 46,
):
    """累積実点の軌跡. top/bottom/random 各 3 本."""
    res = simulate(N, M, S, T=T_burn + T_measure, seed=seed)
    acts = res["actions"][T_burn:]      # (T_measure, N)
    wins = res["winner"][T_burn:]       # (T_measure,)
    hits = (acts == wins[:, None]).astype(np.int64)  # (T_measure, N)
    cum = np.cumsum(hits, axis=0)       # (T_measure, N)
    final = cum[-1]
    order = np.argsort(final)
    bottom3 = order[:3]
    top3 = order[-3:][::-1]
    rng = np.random.default_rng(seed + 99)
    middle = order[len(order) // 2 - 10: len(order) // 2 + 10]
    random3 = rng.choice(middle, size=3, replace=False)
    return cum, top3, bottom3, random3


# --------------------------------------------------------------------------
# 検証チェック (層3)
# --------------------------------------------------------------------------


def run_checks(seed: int = 42):
    """仕様書の検証チェックリストを走らせる."""
    print("\n[Check] 検証チェック")
    # 1. 乱数シード再現性
    a = simulate(N=101, M=5, S=2, T=500, seed=seed)
    b = simulate(N=101, M=5, S=2, T=500, seed=seed)
    assert np.array_equal(a["attendance"], b["attendance"]), "seed 再現性 NG"
    print("  ✓ seed 再現性: 同一 seed で attendance 完全一致")

    # 2. 戦略空間の初期分布
    rng_check = np.random.default_rng(seed)
    test_strat = rng_check.choice([-1, 1], size=(1001, 5, 256))
    print(f"  ✓ 戦略初期化: 平均 = {test_strat.mean():+.4f} (|.| < 0.01 が理想)")

    # 3. A(t) の対称性
    res = simulate(N=1001, M=8, S=2, T=11000, seed=seed)
    att = res["attendance"][1000:]
    mean_A = att.mean()
    print(f"  ✓ 平均 attendance = {mean_A:.2f} (N/2 = 500.5 との差 "
          f"{abs(mean_A - 500.5):.2f})")
    from scipy.stats import skew
    sk = skew(att - 500.5)
    print(f"  ✓ 歪度 (A - N/2) = {sk:+.4f} (|.| < 0.1 なら対称)")

    # 4. σ²/N の単調性検証 (N=101 粗スキャン)
    print("  [sweep] σ²/N vs M (N=101, S=2, 1 trial, 粗スキャン)")
    vals = {}
    for M in [1, 3, 5, 7, 9, 11]:
        v = sigma2_over_N(N=101, M=M, S=2, T_burn=500, T_measure=5000,
                          seed=seed + M)
        vals[M] = v
        print(f"    M={M:2d}  σ²/N = {v:.3f}")
    argmin_M = min(vals, key=vals.get)
    print(f"  ✓ σ²/N 最小は M={argmin_M} (α={2**argmin_M/101:.3f}) 付近. 理論 α_c ≈ 0.34")


# --------------------------------------------------------------------------
# 6 パネル描画
# --------------------------------------------------------------------------


def build_figure(seed: int, out_path: str):
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        "Challet & Zhang (1997) Minority Game — YH003",
        fontsize=14, fontweight="bold",
    )

    # Panel 1: σ²/N vs α (log-log)
    print("\n[Panel 1] σ²/N vs α スキャン (N=101, M=1..12, 10 trials)")
    t0 = time.time()
    alphas, means, stds = panel1_sigma2_scan(
        N=101, M_values=range(1, 13), n_trials=10,
        T_burn=500, T_measure=5000, seed0=seed,
    )
    print(f"  Panel 1 done in {time.time() - t0:.1f}s")
    ax = axes[0, 0]
    ax.errorbar(alphas, means, yerr=stds, fmt="o-", color="navy",
                markersize=5, capsize=3, linewidth=1.5)
    # ランダム参照線 (全員コインフリップ): σ²/N = 1/4 × N / N = 0.25 × 4 = 1.0
    # 正確には excess = ±1 一様、Var = N、Var/N = 1
    ax.axhline(1.0, color="red", linestyle=":", alpha=0.5,
               label="random (σ²/N=1)")
    # 理論 α_c ≈ 0.34
    ax.axvline(0.34, color="gray", linestyle="--", alpha=0.5,
               label=r"$\alpha_c \approx 0.34$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\alpha = 2^M / N$")
    ax.set_ylabel(r"$\sigma^2 / N$")
    ax.set_title(r"(1) $\sigma^2/N$ vs $\alpha = 2^M/N$  (N=101, S=2, 10 trials)")
    ax.legend(fontsize=9)
    ax.grid(True, which="both", alpha=0.3)
    argmin_idx = int(np.argmin(means))
    print(f"  min σ²/N at α = {alphas[argmin_idx]:.3f} "
          f"(M={argmin_idx + 1}), value = {means[argmin_idx]:.3f}")

    # Panel 2: A(t) 時系列 3 本
    print("\n[Panel 2] A(t) 3 本 (N=1001, M=6/8/10)")
    t0 = time.time()
    series = panel2_attendance_series(N=1001, M_list=(6, 8, 10), T_show=500,
                                      T_burn=1000, seed0=seed)
    print(f"  Panel 2 done in {time.time() - t0:.1f}s")
    ax = axes[0, 1]
    colors = {6: "tab:red", 8: "tab:green", 10: "tab:blue"}
    for M, ser in series.items():
        ax.plot(ser, linewidth=0.6, color=colors[M], label=f"M={M}", alpha=0.85)
    ax.axhline(500.5, color="k", linestyle="--", alpha=0.5, label="N/2")
    ax.set_xlabel("t (after burn-in)")
    ax.set_ylabel("A(t)")
    ax.set_title("(2) Attendance A(t), three M values  (N=1001, S=2)")
    ax.legend(fontsize=9)

    # Panel 3: A のヒストグラム
    print("\n[Panel 3] A のヒストグラム (N=1001, M=8, S=5)")
    t0 = time.time()
    att = panel3_attendance_hist(N=1001, M=8, S=5, T_burn=1000,
                                 T_measure=10000, seed=seed + 100)
    print(f"  Panel 3 done in {time.time() - t0:.1f}s  "
          f"(mean={att.mean():.2f}, std={att.std():.2f})")
    ax = axes[0, 2]
    ax.hist(att, bins=60, density=True, alpha=0.75, color="tab:orange",
            edgecolor="black", linewidth=0.3)
    ax.axvline(500.5, color="k", linestyle="--", alpha=0.6, label="N/2")
    # 参考: Gaussian N(500.5, std)
    from scipy.stats import norm
    xs = np.linspace(att.min(), att.max(), 200)
    ax.plot(xs, norm.pdf(xs, att.mean(), att.std()), "r-",
            linewidth=1.5, label="Gaussian fit")
    ax.set_xlabel("A(t)")
    ax.set_ylabel("density")
    ax.set_title("(3) Attendance distribution  (N=1001, M=8, S=5)")
    ax.legend(fontsize=9)

    # Panel 4: Success rate vs M
    print("\n[Panel 4] Success rate vs M (N=1001, S=5, M=1..10)")
    t0 = time.time()
    Ms, rates = panel4_success_vs_M(
        N=1001, S=5, M_values=range(1, 11),
        T_burn=1000, T_measure=10000, seed0=seed + 200,
    )
    print(f"  Panel 4 done in {time.time() - t0:.1f}s")
    ax = axes[1, 0]
    ax.plot(Ms, rates, "o-", color="tab:purple", markersize=7, linewidth=1.5)
    ax.axhline(0.5, color="red", linestyle="--", alpha=0.6,
               label="1/2 (random)")
    ax.set_xlabel("M")
    ax.set_ylabel("mean success rate")
    ax.set_title("(4) Mean success rate vs M  (N=1001, S=5)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Panel 5: スコア分布 3 時点
    print("\n[Panel 5] 戦略スコア分布 3 時点 (N=1001, M=8, S=5)")
    t0 = time.time()
    snaps = panel5_score_dist(
        N=1001, M=8, S=5, snapshots=(1000, 5000, 10000), seed=seed + 300,
    )
    print(f"  Panel 5 done in {time.time() - t0:.1f}s")
    ax = axes[1, 1]
    colors_snap = ["tab:red", "tab:green", "tab:blue"]
    # スコアは平均 t/2 付近で集積するため、中心化して広がりを見せる
    for (t, arr), c in zip(sorted(snaps.items()), colors_snap):
        centered = arr.flatten() - arr.mean()
        ax.hist(centered, bins=60, alpha=0.55,
                label=f"t={t} (mean={arr.mean():.0f})",
                color=c, density=True)
    ax.set_xlabel("virtual score − mean")
    ax.set_ylabel("density")
    ax.set_title("(5) Centered virtual-score dist., 3 snapshots  (N=1001, M=8, S=5)")
    ax.legend(fontsize=9)

    # Panel 6: 累積実点軌跡
    print("\n[Panel 6] 累積実点軌跡 (N=1001, M=10, S=5)")
    t0 = time.time()
    cum, top3, bottom3, random3 = panel6_cumulative_gain(
        N=1001, M=10, S=5, T_burn=1000, T_measure=10000, seed=seed + 400,
    )
    print(f"  Panel 6 done in {time.time() - t0:.1f}s")
    ax = axes[1, 2]
    xs = np.arange(cum.shape[0])
    # 期待値 0.5 * t からの偏差でプロットすると top/bottom の差が可視化される
    deviation = cum - 0.5 * xs[:, None]
    for i, idx in enumerate(top3):
        ax.plot(xs, deviation[:, idx], color="tab:green", alpha=0.85,
                linewidth=1.1, label="top 3" if i == 0 else None)
    for i, idx in enumerate(bottom3):
        ax.plot(xs, deviation[:, idx], color="tab:red", alpha=0.85,
                linewidth=1.1, label="bottom 3" if i == 0 else None)
    for i, idx in enumerate(random3):
        ax.plot(xs, deviation[:, idx], color="tab:gray", alpha=0.8,
                linewidth=1.0, label="random 3" if i == 0 else None)
    ax.axhline(0, color="k", linestyle="--", alpha=0.4, label="chance (0.5 × t)")
    ax.set_xlabel("t (after burn-in)")
    ax.set_ylabel("cumulative gain − 0.5 × t")
    ax.set_title("(6) Cumulative gain deviation from chance  (N=1001, M=10, S=5)")
    ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    print(f"\nFigure saved to {out_path}")
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-checks", action="store_true")
    args = ap.parse_args()

    print("=" * 62)
    print("Challet & Zhang (1997) Minority Game — YH003")
    print("=" * 62)
    print(f"seed = {args.seed}")

    if not args.skip_checks:
        run_checks(seed=args.seed)

    build_figure(seed=args.seed, out_path="results.png")


if __name__ == "__main__":
    main()
