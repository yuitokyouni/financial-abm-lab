"""YH007-8 診断 (d): 現 fade が「chase 型 (= 現予想 vs 現価格)」かを実証。

spec 003 §3.2 round4 + §12 round5 の根因仮説の検証:
  仮説: KronosCI quantile-rank では Kronos 予測中心が mid から drift した瞬間、
        全 quantile が同符号 → 全 agent が同側 cross → 集合 over-shoot → ret_acf τ=1<0

測る量 (cheap, 既存 action_log + KronosQuantileHub.call_log から):
  (1) per-bar の **同側比率** = max(n_buy, n_sell) / n_active
      → 1.0 に近いほど全員同側 (= 集合 cross の頻度)
  (2) **trend/fade 構成比** = agent ごとに「v > mid (= trend)」「v < mid (= fade)」の bar 比率
      → 全 agent で同じ値なら現 fade が逆張りニッチを維持できていない
  (3) Kronos 分布中心 (= closes_sorted の median) と現 mid の差
      → mid から系統的に drift していれば集合 cross の機械的説明
  (4) (3) と (1) の相関 → drift が大きい bar で同側比率も大きい?

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.speculation_game.yh007_8_p3_diagnostic_d \\
      --seed 0 --warmup-steps 200 --main-steps 1000
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from abm_models.self_organized_book import SelfOrganizedBookMarket


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1000)
    p.add_argument("--n-strategy", type=int, default=10)
    p.add_argument("--n-zi-liq", type=int, default=10)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_d.json")
    args = p.parse_args()

    m = SelfOrganizedBookMarket(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_zi=args.n_zi_liq, zi_mode="naive",
        n_kronos=args.n_strategy,
        bar_size=args.bar_size, order_ttl=15,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
        kronos_margin_min=3.0e-5, kronos_margin_max=1.0e-4,
    )
    t0 = time.time()
    res = m.run(seed=args.seed)
    dt = time.time() - t0
    print(f"[diag-d] run dt={dt:.1f}s, kronos_agents={len(res['kronos_agents'])}, "
          f"warmup_bars={res['warmup_bars']}")

    kronos_agents = res["kronos_agents"]
    bar_size = res["bar_size"]
    n_strategy = len(kronos_agents)

    # ---- (1) per-bar の同側比率 ----
    # bar_index → {agent_id: side(±1, 0=abstain)}
    bar_to_sides: dict[int, dict[int, int]] = {}
    bar_to_v_minus_mid: dict[int, list[float]] = {}
    for a in kronos_agents:
        for t, side, price, payload in a.action_log:
            bi = t // bar_size
            bar_to_sides.setdefault(bi, {})
            # 同一 bar で複数 step あれば last が残る (= 最後の評価値が支配)
            bar_to_sides[bi][a.agent_id] = side
            if payload and "v" in payload and "mid" in payload:
                bar_to_v_minus_mid.setdefault(bi, []).append(
                    float(payload["v"]) - float(payload["mid"])
                )

    bars_sorted = sorted(bar_to_sides.keys())
    same_side_ratios = []
    side_bias_signed = []  # +1 = 全 buy, -1 = 全 sell
    for bi in bars_sorted:
        sides = list(bar_to_sides[bi].values())
        n_buy = sum(1 for s in sides if s > 0)
        n_sell = sum(1 for s in sides if s < 0)
        n_active = n_buy + n_sell
        if n_active < 2:
            same_side_ratios.append(float("nan"))
            side_bias_signed.append(float("nan"))
            continue
        r = max(n_buy, n_sell) / n_active
        same_side_ratios.append(r)
        side_bias_signed.append((n_buy - n_sell) / n_active)
    ss = np.array(same_side_ratios)
    ss_valid = ss[~np.isnan(ss)]
    print(f"\n=== (1) per-bar 同側比率 (n_active>=2 の bar のみ, n={ss_valid.size}) ===")
    print(f"  mean = {ss_valid.mean():.4f}  median = {np.median(ss_valid):.4f}")
    print(f"  P(=1.0 全員同側) = {(ss_valid == 1.0).mean():.4f}")
    print(f"  P(>=0.9) = {(ss_valid >= 0.9).mean():.4f}")
    print(f"  P(<=0.6 = 散らばり) = {(ss_valid <= 0.6).mean():.4f}")
    bias = np.array(side_bias_signed)
    bias_valid = bias[~np.isnan(bias)]
    print(f"  signed bias (n_buy-n_sell)/n_active: mean={bias_valid.mean():+.4f} "
          f"std={bias_valid.std():.4f}")

    # ---- (2) trend/fade 構成比 (agent ごとに v>mid の bar 比率) ----
    print(f"\n=== (2) trend/fade 構成比 (agent ごとの v>mid bar 比率) ===")
    per_agent_buy_ratio = []
    for a in kronos_agents:
        n_buy = sum(1 for t, side, price, payload in a.action_log if side > 0)
        n_active = sum(1 for t, side, price, payload in a.action_log if side != 0)
        ratio = n_buy / max(n_active, 1)
        per_agent_buy_ratio.append((a.agent_rank, ratio, n_active))
    per_agent_buy_ratio.sort()
    for rank, ratio, n_active in per_agent_buy_ratio:
        marker = "★" if 0.05 < ratio < 0.95 else "  "
        print(f"  rank={rank:.3f}  buy_ratio={ratio:.4f}  n_active={n_active}  {marker}")
    ratios = np.array([r for _, r, _ in per_agent_buy_ratio])
    print(f"  → buy_ratio std across agents = {ratios.std():.4f}")
    print(f"     (全 agent で同じ値 ≈ 0 = trend/fade ニッチ消滅 = 現 fade は逆張りでない)")

    # ---- (3) Kronos 分布中心 vs mid の差 ----
    print(f"\n=== (3) Kronos 分布中心 (= v median) と現 mid の差 (= predictor bias) ===")
    bar_to_median_v_mid: dict[int, float] = {}
    for bi, vs in bar_to_v_minus_mid.items():
        if vs:
            bar_to_median_v_mid[bi] = float(np.median(vs))
    diffs = np.array([bar_to_median_v_mid[bi] for bi in bars_sorted
                      if bi in bar_to_median_v_mid])
    if diffs.size:
        print(f"  bias (v_median − mid) mean = {diffs.mean():+.4e}")
        print(f"  bias std = {diffs.std():.4e}")
        print(f"  P(bias > 0) = {(diffs > 0).mean():.4f}  (= Kronos が mid 上を予想する頻度)")
        print(f"  |bias| > 1e-3 = {(np.abs(diffs) > 1e-3).mean():.4f}")

    # ---- (4) 同側比率と bias |·| の相関 ----
    print(f"\n=== (4) 同側比率 vs |bias| の関係 ===")
    if diffs.size == ss_valid.size and diffs.size >= 4:
        valid_idx = ~np.isnan(ss)
        b_arr = np.array([bar_to_median_v_mid.get(bi, float("nan")) for bi in bars_sorted])
        valid = valid_idx & ~np.isnan(b_arr)
        if valid.sum() >= 4:
            ss_v = ss[valid]
            ab_v = np.abs(b_arr[valid])
            corr = float(np.corrcoef(ss_v, ab_v)[0, 1])
            print(f"  corr(同側比率, |bias|) = {corr:+.4f}")
            print(f"  → +1 に近ければ仮説支持: bias が大きい bar で集合 cross 発生")

    # JSON 保存
    Path(args.out_json).write_text(json.dumps({
        "n_bars": int(ss_valid.size),
        "same_side_mean": float(ss_valid.mean()),
        "same_side_p1": float((ss_valid == 1.0).mean()),
        "same_side_p_geq_0_9": float((ss_valid >= 0.9).mean()),
        "signed_bias_mean": float(bias_valid.mean()),
        "buy_ratio_per_agent": per_agent_buy_ratio,
        "v_median_minus_mid_mean": float(diffs.mean()) if diffs.size else None,
        "v_median_minus_mid_std": float(diffs.std()) if diffs.size else None,
    }, default=str, indent=2))
    print(f"\nsaved: {args.out_json}")


if __name__ == "__main__":
    main()
