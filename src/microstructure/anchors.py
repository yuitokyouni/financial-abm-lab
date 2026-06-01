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


def _expected_net_snipe(lambda_jump: float, jump_size: float, dt: float,
                        half_spread: float, batch_interval: int) -> float:
    """バッチ1回あたりの期待 sniping 額 E[(|S_N|*? - h)+]（committed-quote モデル）。

    バッチ N ステップで各ステップ確率 q=lambda*dt で ±J ジャンプ。net 変位の
    ジャンプ数 K~Binom(N,q)、上方ジャンプ u~Binom(K,1/2)、net=(2u-K)*J。
    arbitrageur は clear で stale quote の net 変位を 1 回 picking-off:
      E[(|net| - h)+] = sum_K P(K) sum_u C(K,u) 0.5^K max(|2u-K|*J - h, 0)
    厳密（有限和）。N=1 で q*(J-h)+ に帰着＝連続の per-step snipe。
    """
    q = lambda_jump * dt
    N, J, h = batch_interval, jump_size, half_spread
    total = 0.0
    for K in range(N + 1):
        pK = math.comb(N, K) * (q ** K) * ((1.0 - q) ** (N - K))
        if pK == 0.0:
            continue
        inner = 0.0
        for u in range(K + 1):
            net = abs(2 * u - K) * J
            payoff = net - h
            if payoff > 0.0:
                inner += math.comb(K, u) * (0.5 ** K) * payoff
        total += pK * inner
    return total


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


def kyle_lambda(jump_size: float, alpha: float | None = None) -> float:
    """price impact 係数（model-consistent）。

    informed(arbitrageur)の取引後、MM は真値を学習し mid が J だけ動く。
    **informed 取引1回あたりの price impact = J**（jump model では alpha は頻度に効くが
    1取引あたり impact には効かない）。検証はこのスケーリング（∝ J、informed で ~J）を
    sim の `informed_impact` と照合（SC-005, impact 層）。`alpha` は API 互換のため任意。
    """
    return jump_size
