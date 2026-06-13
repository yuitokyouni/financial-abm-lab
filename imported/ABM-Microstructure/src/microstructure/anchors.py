"""解析アンカー（連続時間極限）。

**重要**: このモジュールは engine/metrics/agents/book を import しない。
sim と独立実装することで「検証の真値」が sim ロジックのバグを共有しないことを構造で担保する
(research D5 / A2)。LVR は無い（CLOB に pool 不在）。
"""
from __future__ import annotations

import math


def gm_break_even(lambda_jump: float, jump_size: float, alpha: float,
                  noise_rate: float) -> float:
    """Glosten-Milgrom 競争（zero-profit）half-spread h*。

    モデル（research D4）: MM は belief m 周りに ±h で両側気配。各ステップ
    確率 lambda*dt で ±J ジャンプ。jump 後、informed(arbitrageur, 確率 alpha)が
    stale quote を picking-off（J>h なら利益 J-h）。noise(強度 noise_rate)は無方向で
    half-spread h を MM に支払う。
    zero-profit: noise_rate * h = alpha * lambda * (J - h)
      => h* = alpha*lambda*J / (noise_rate + alpha*lambda)
    （dt は両辺で cancel ＝連続時間極限。常に h* < J）。
    """
    denom = noise_rate + alpha * lambda_jump
    if denom <= 0:
        return 0.0
    return alpha * lambda_jump * jump_size / denom


def _iter_net_displacement(n_steps: int, q: float, jump_size: float):
    """バッチ n_steps 内の net 変位 |S| の厳密分布を (確率, |S|) で列挙。

    各ステップ確率 q で ±J ジャンプ：ジャンプ数 K~Binom(n,q)、上方 u~Binom(K,1/2)、
    S=(2u-K)*J。有限和の厳密列挙。Budish rent（sniping 層）と kyle_lambda（impact 層）が
    共有する netting 機構。
    """
    for K in range(n_steps + 1):
        pK = math.comb(n_steps, K) * (q ** K) * ((1.0 - q) ** (n_steps - K))
        if pK == 0.0:
            continue
        for u in range(K + 1):
            yield pK * math.comb(K, u) * (0.5 ** K), abs(2 * u - K) * jump_size


def _expected_net_snipe(lambda_jump: float, jump_size: float, dt: float,
                        half_spread: float, batch_interval: int) -> float:
    """バッチ1回あたりの期待 sniping 額 E[(|S_N| - h)+]（committed-quote モデル）。

    arbitrageur は clear で stale quote の net 変位を 1 回 picking-off:
      E[(|S_N| - h)+] = Σ P(|S_N|=s) · max(s - h, 0)
    厳密（有限和）。N=1 で q*(J-h)+ に帰着＝連続の per-step snipe。
    """
    q = lambda_jump * dt
    return sum(p * (s - half_spread)
               for p, s in _iter_net_displacement(batch_interval, q, jump_size)
               if s > half_spread)


def budish_sniping_rent(lambda_jump: float, jump_size: float, alpha: float,
                        dt: float, half_spread: float,
                        batch_interval: int = 1) -> float:
    """単位時間あたり期待 sniping 抽出量（committed-quote モデルの厳密値）。

    rate = alpha * E[(|net 変位| - h)+] / (N * dt)。
    N=1 で alpha*q*(J-h)+/dt = alpha*lambda*(J-h)（連続）。
    N>1 では net 変位の凸性により、h≪J で減少・h~J で増加しうる（クロスオーバー）。
    この厳密アンカーが sim 抽出量と一致することで「クロスオーバーは coding artifact でなく
    モデルの抽出曲面の性質」であることを確定する（finding 0001 の検証）。
    """
    e = _expected_net_snipe(lambda_jump, jump_size, dt, half_spread, batch_interval)
    return alpha * e / (batch_interval * dt)


def kyle_lambda(lambda_jump: float, jump_size: float, alpha: float,
                noise_rate: float, dt: float, half_spread: float,
                batch_interval: int = 1) -> float:
    """identity-blind flow 回帰の price-impact 係数 λ（impact 層, SC-005 / research D5b v2）。

    sim 側 `metrics.price_impact`（取引主体を知らずに測る λ̂ = Σx·Δp/Σx²）の独立アンカー。
    flow 組成の混合期待値（pure-jump・committed-quote）:
      λ(N) = α·E[|S_N|·1{|S_N|>h}] / (α·P(|S_N|>h) + N·noise_rate·dt)
    分子＝informed flow が運ぶ価格情報（E[x·Δp] の informed 項。noise は方向独立で消える）、
    分母＝E[x²]＝informed 参加率 + noise 希釈（N ステップで線形蓄積）。
    N=1（h<J）で αλJ/(αλ+noise_rate) ＝ gm_break_even に厳密一致（GM の定理:
    competitive spread = adverse-selection impact。spread 層と impact 層の三角検証）。
    旧版 `=J` は sim の Bayesian 更新と circular で検出力ゼロだった（finding 0001 ③）。
    """
    q = lambda_jump * dt
    info = 0.0
    p_over = 0.0
    for p, s in _iter_net_displacement(batch_interval, q, jump_size):
        if s > half_spread:
            info += p * s
            p_over += p
    denom = alpha * p_over + batch_interval * noise_rate * dt
    if denom <= 0.0:
        return 0.0
    return alpha * info / denom
