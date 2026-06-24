"""YH007-8 P3 dose-matching pilot: ZI-matched (AR(1) φ=0.418, σ=6e-3) の margin を
CI×Kronos の P2 実測 agg=0.106 に揃える値を探す (margin grid search)。

これがないと P3 の SF 差が「Kronos 情報」でなく「aggression 量」由来になる
(裁定 §12 round3 の dose-matching parity 要件)。

実行:
    uv run python -m experiments.speculation_game.yh007_8_p3_agg_parity_pilot \\
      --warmup-steps 200 --main-steps 800 --n-agents 10 --n-seeds 3
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from abm_models.self_organized_book import SelfOrganizedBookMarket


def _agg_one(seed: int, *, mm: float, mx: float, common: dict) -> dict:
    kwargs = dict(common)
    n_agents = kwargs.pop("n_agents")
    m = SelfOrganizedBookMarket(
        **kwargs, n_zi=n_agents, n_kronos=0,
        zi_mode="matched_ar1", zi_phi_ar1=0.418, zi_sigma_ar1_abs=6e-3, zi_mu_ar1=0.0,
        margin_min=mm, margin_max=mx,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    return {
        "mm": mm, "mx": mx, "seed": seed, "dt": time.time() - t0,
        "agg": res["n_executed"] / max(res["n_submitted"], 1),
        "n_sub": res["n_submitted"], "n_exec": res["n_executed"],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=800)
    p.add_argument("--n-agents", type=int, default=10)
    p.add_argument("--n-seeds", type=int, default=3)
    p.add_argument("--target-agg", type=float, default=0.106,
                   help="CI×Kronos P2 実測 agg")
    args = p.parse_args()

    # ZI-matched 側 margin を 5 段階で振る。CI×Kronos は (3e-5, 1e-4)。
    # ZI-matched は agg が小さい傾向 (側選択の構造) なので、margin を狭くする方向を試す。
    # 第1 round: 0.80 / 0.59 / 0.26 / 0.011 / 0.001 → target 0.106 は 1.5e-5〜5e-5 と 3e-5〜1e-4 の間
    grids = [
        (1.5e-5, 4e-5),
        (1.5e-5, 5e-5),
        (1.5e-5, 6e-5),
        (2.0e-5, 6e-5),
        (2.0e-5, 8e-5),
    ]
    common_base = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        bar_size=10, order_ttl=15,
        sigma_eval=5e-5, tick_size=0.001, initial_market_price=300.0,
    )
    print(f"target agg = {args.target_agg:.4f}  (CI×Kronos P2 実測)")
    print(f"{'margin_min':>11} {'margin_max':>11}  {'agg_mean':>10}  {'agg_std':>10}  "
          f"{'n_sub_mean':>11}  {'n_exec_mean':>11}")
    rows = []
    for mm, mx in grids:
        aggs, subs, execs = [], [], []
        for seed in range(args.n_seeds):
            common = {**common_base, "n_agents": args.n_agents}
            r = _agg_one(seed, mm=mm, mx=mx, common=common)
            aggs.append(r["agg"]); subs.append(r["n_sub"]); execs.append(r["n_exec"])
        rows.append((mm, mx, np.mean(aggs), np.std(aggs, ddof=1) if len(aggs)>1 else 0))
        print(f"{mm:>11.1e} {mx:>11.1e}  {np.mean(aggs):>10.4f}  "
              f"{(np.std(aggs, ddof=1) if len(aggs)>1 else 0):>10.4f}  "
              f"{np.mean(subs):>11.1f}  {np.mean(execs):>11.1f}")

    print(f"\n→ target {args.target_agg:.4f} に最も近い行を P3 の --zi-margin-* に渡す")


if __name__ == "__main__":
    main()
