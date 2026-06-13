"""YH005: 論文2 Fig. 11 再現スクリプト.

Baseline / Null A (exogenous history) / Null B (random decision) の 3 条件を
(N=1000, M=5, S=2, T=50000, B=9, C=3.0) で走らせ、r(t) 時系列と |r| ACF を比較する。

採用ルール:
  - Null A: history_mode='exogenous' — μ は毎ステップ uniform 再抽選、P は実 h で更新
  - Null B: decision_mode='random'   — position 非参照 (§4.5 literal 解釈),
                                        u<p で rec=±1 (0.5 ずつ)、else rec=0

期待結果:
  - baseline: |r| ACF at lag 50 > 0.10 (論文1 Fig. 6 の slow decay 領域、実測 ~0.12)
  - Null A/B: |ACF| < 0.05 (clustering 消失)

出力:
  experiments/YH005/results_null_tests.png
  experiments/YH005/outputs/null_tests_metrics.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from simulate import simulate
from analysis import (
    log_returns_from_prices,
    volatility_acf,
    stylized_facts_summary,
)


DEFAULT_PARAMS = dict(N=1000, M=5, S=2, T=50000, B=9, C=3.0, p0=100.0)
T_DISPLAY = 20000                # 時系列表示で先頭から使う step 数
VOL_ACF_MAX_LAG = 500


def _run_one(label: str, seed: int, **overrides) -> dict:
    params = {**DEFAULT_PARAMS, **overrides}
    print(f"[{label}] start (seed={seed}, params={ {k: v for k, v in params.items() if k != 'p0'} })")
    t0 = time.perf_counter()
    res = simulate(seed=seed, **params)
    t1 = time.perf_counter()
    print(f"[{label}] done in {t1-t0:.1f}s, num_substitutions={res['num_substitutions']}")
    return res


def _returns_from_sim(res: dict) -> np.ndarray:
    return log_returns_from_prices(res["prices"])


def run_null_tests(seed: int = 777, save_dir: Path | None = None) -> dict:
    if save_dir is None:
        save_dir = Path(__file__).resolve().parent
    outputs_dir = save_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    # --- シミュレーション ---
    baseline_res = _run_one("baseline", seed=seed)
    null_a_res = _run_one("Null A", seed=seed, history_mode="exogenous")
    null_b_res = _run_one("Null B", seed=seed, decision_mode="random")

    # --- stylized facts サマリ ---
    returns = {
        "baseline": _returns_from_sim(baseline_res),
        "null_a": _returns_from_sim(null_a_res),
        "null_b": _returns_from_sim(null_b_res),
    }
    metrics = {
        cond: stylized_facts_summary(r, acf_lags=(1, 14, 50, 200))
        for cond, r in returns.items()
    }

    # --- print: |r| ACF at lag 50 ---
    print("\n== |r| ACF at lag 50 ==")
    vol_acf_at_50 = {}
    for cond, r in returns.items():
        acf = volatility_acf(r, max_lag=VOL_ACF_MAX_LAG)
        vol_acf_at_50[cond] = float(acf[49])
        print(f"  {cond:<8}: {vol_acf_at_50[cond]:+.4f}")

    # acceptance check (§8.2)
    ok_baseline = vol_acf_at_50["baseline"] > 0.10
    ok_null_a = abs(vol_acf_at_50["null_a"]) < 0.05
    ok_null_b = abs(vol_acf_at_50["null_b"]) < 0.05
    print(
        f"\nAcceptance: baseline > 0.10? {ok_baseline} | "
        f"Null A |acf| < 0.05? {ok_null_a} | Null B |acf| < 0.05? {ok_null_b}"
    )

    # --- 3 パネル figure ---
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    panel_info = [
        ("baseline", "Baseline (endogenous history, strategy decisions)", axes[0]),
        ("null_a", "Null A (exogenous common history)", axes[1]),
        ("null_b", "Null B (random trading, p=0.5)", axes[2]),
    ]
    for cond, title, ax in panel_info:
        r = returns[cond][:T_DISPLAY]
        ax.plot(r, linewidth=0.5, color="tab:blue")
        annotation = (
            f"|r| ACF at lag 50 = {vol_acf_at_50[cond]:+.3f}    "
            f"kurt (window=1) = {metrics[cond]['kurt'][1]:+.1f}"
        )
        ax.set_title(f"{title}   —   {annotation}", fontsize=10)
        ax.set_ylabel("r(t) = Δ log p")
        ax.axhline(0, color="k", linewidth=0.3)
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel(f"t (first {T_DISPLAY} steps shown of T={DEFAULT_PARAMS['T']})")
    fig.suptitle(
        f"Fig. 11 reproduction: N={DEFAULT_PARAMS['N']}, M={DEFAULT_PARAMS['M']}, "
        f"S={DEFAULT_PARAMS['S']}, T={DEFAULT_PARAMS['T']}, seed={seed}",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    png_path = save_dir / "results_null_tests.png"
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"\nFigure saved: {png_path}")

    # --- JSON metrics ---
    json_path = outputs_dir / "null_tests_metrics.json"
    serializable = {
        "seed": seed,
        "params": DEFAULT_PARAMS,
        "vol_acf_at_lag_50": vol_acf_at_50,
        "acceptance": {
            "baseline_gt_0.10": ok_baseline,
            "null_a_lt_0.05": ok_null_a,
            "null_b_lt_0.05": ok_null_b,
        },
        "conditions": {cond: _to_json(m) for cond, m in metrics.items()},
    }
    with open(json_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"Metrics saved: {json_path}")

    return {
        "vol_acf_at_lag_50": vol_acf_at_50,
        "metrics": metrics,
        "png": str(png_path),
        "json": str(json_path),
    }


def _to_json(obj):
    """numpy 値を JSON シリアライズ可能に変換する再帰ヘルパ。"""
    if isinstance(obj, dict):
        return {str(k): _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()
    run_null_tests(seed=args.seed)
