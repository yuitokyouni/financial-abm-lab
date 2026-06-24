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
    """流動性役 ZI-naïve 10 + 戦略役 ZI-matched_ar1 10 構成で、戦略役のみの agg を測る。"""
    kwargs = dict(common)
    n_strategy = kwargs.pop("n_strategy")
    n_zi_liq = kwargs.pop("n_zi_liq")
    m = SelfOrganizedBookMarket(
        **kwargs,
        n_zi=n_zi_liq, zi_mode="naive",
        n_kronos=0,
        n_zi_strategy=n_strategy,
        zi_strategy_mode="matched_ar1",
        zi_strategy_phi_ar1=0.418,
        zi_strategy_sigma_ar1_abs=6e-3,
        zi_strategy_mu_ar1=0.0,
        zi_strategy_margin_min=mm,
        zi_strategy_margin_max=mx,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    # 戦略役のみ agg を計算 (ZI-matched_ar1 のもの)
    strategy_agents = [a for a in res["zi_agents"] if getattr(a, "zi_mode", "") == "matched_ar1"]
    n_sub = sum(sum(1 for _, side, p, _ in a.action_log if side != 0 and p is not None)
                for a in strategy_agents)
    n_exec = sum(len(a.executed_log) for a in strategy_agents)
    return {
        "mm": mm, "mx": mx, "seed": seed, "dt": time.time() - t0,
        "agg": n_exec / max(n_sub, 1),
        "n_sub": n_sub, "n_exec": n_exec,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=800)
    p.add_argument("--n-strategy", type=int, default=10)
    p.add_argument("--n-zi-liq", type=int, default=10)
    p.add_argument("--n-seeds", type=int, default=3)
    p.add_argument("--target-agg", type=float, default=0.106,
                   help="CI×Kronos P2 実測 agg")
    args = p.parse_args()

    # ZI-matched 側 margin を 5 段階で振る。CI×Kronos は (3e-5, 1e-4)。
    # ZI-matched は agg が小さい傾向 (側選択の構造) なので、margin を狭くする方向を試す。
    # 2-group 構成での 2nd round: 流動性役 ZI が板を埋めるので戦略役 agg が約 2x
    # → 1st round の "0.18 @ (2e-5,8e-5)" から margin を広げる方向
    grids = [
        (2.0e-5, 1.0e-4),
        (2.5e-5, 1.2e-4),
        (3.0e-5, 1.2e-4),
        (3.5e-5, 1.2e-4),
        (3.0e-5, 1.5e-4),
    ]
    common_base = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        bar_size=10, order_ttl=15,
        # 流動性役 ZI-naïve のパラメータ
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    print(f"target agg = {args.target_agg:.4f}  (CI×Kronos P2 実測)")
    print(f"{'margin_min':>11} {'margin_max':>11}  {'agg_mean':>10}  {'agg_std':>10}  "
          f"{'n_sub_mean':>11}  {'n_exec_mean':>11}")
    rows = []
    for mm, mx in grids:
        aggs, subs, execs = [], [], []
        for seed in range(args.n_seeds):
            common = {**common_base, "n_strategy": args.n_strategy,
                      "n_zi_liq": args.n_zi_liq}
            r = _agg_one(seed, mm=mm, mx=mx, common=common)
            aggs.append(r["agg"]); subs.append(r["n_sub"]); execs.append(r["n_exec"])
        rows.append((mm, mx, np.mean(aggs), np.std(aggs, ddof=1) if len(aggs)>1 else 0))
        print(f"{mm:>11.1e} {mx:>11.1e}  {np.mean(aggs):>10.4f}  "
              f"{(np.std(aggs, ddof=1) if len(aggs)>1 else 0):>10.4f}  "
              f"{np.mean(subs):>11.1f}  {np.mean(execs):>11.1f}")

    print(f"\n→ target {args.target_agg:.4f} に最も近い行を P3 の --zi-margin-* に渡す")


if __name__ == "__main__":
    main()
