"""MarketEnv — 実験B の逐次学習環境（research D-B3 の期構造）。

001 の vectorized engine とはコードパスを分離（plan Constraints: 検証済み資産を凍結）。
会計規約は 001 と同一: noise fill の MM PnL = h ∓ disp（committed。settle は stale quote、
評価は clear 時真値）、抽出 = arb 利得 = MM 損（ゼロサム）、fees = fee × noise fill 数。

期構造（学習 1 期 = 1 clearing サイクル。continuous は N=1 の特例として同一コード）:
  期初: belief m = 直近 clear の真値（staleness）→ 全 MM が half-spread を提示
  → N step の価格増分・noise 到着を蓄積 → 【revisable のみ: belief→v_clear に更新＝再気配】
  → arb 手番（確率 α、|v_clear − belief| > h_w なら勝者を 1 回 picking-off）
  → clear・reward → belief 更新。
  revisable では arb の利得機会が構造的に消える（|v−belief|=0 < h）ため抽出は恒等 0、
  noise は再気配 quote で settle し PnL = h ちょうど（∓disp 項は消える。期待値は不変）。

乱数は derive_rngs() が master seed から決定論的に導出（D-B12）。
"""
from __future__ import annotations

import math

import numpy as np

from .learnconfig import LearnConfig

_CHUNK = 8192  # N=1（continuous）用の事前抽選チャンク


def derive_rngs(cfg: LearnConfig) -> dict[str, object]:
    """master seed → 用途別の整数 seed（再構築可能・決定論、D-B12）。

    返り値の値は int（または int の list）。Generator は使う側が default_rng(int) で作る。
    同一 cfg.seed → 同一 seed 群。IR の factual/counterfactual のように「同一フローで
    2 回走らせる」用途のため、Generator でなく int を配る。
    """
    n = cfg.n_mm
    ints = np.random.default_rng(cfg.seed).integers(2 ** 62, size=3 + n + 3 + 3)
    return {
        "env": [int(x) for x in ints[0:3]],                  # price, arb, noise
        "agents": [int(x) for x in ints[3:3 + n]],           # 探索ストリーム
        "measure_env": [int(x) for x in ints[3 + n:6 + n]],
        "ir_env": [int(x) for x in ints[6 + n:9 + n]],
    }


class MarketEnv:
    def __init__(self, cfg: LearnConfig, env_seeds: list[int]) -> None:
        self.cfg = cfg
        self._rng_price = np.random.default_rng(env_seeds[0])
        self._rng_arb = np.random.default_rng(env_seeds[1])
        self._rng_noise = np.random.default_rng(env_seeds[2])
        self.grid = cfg.action_grid
        self.v = cfg.initial_price      # 真値
        self.m = cfg.initial_price      # belief（直近 clear の真値）
        self._tie_counter = 0
        self._buf_pos = _CHUNK          # N=1 チャンクバッファ
        self._buf: tuple[np.ndarray, ...] | None = None

    # ---- 内部: 1 期分のフロー抽選 ----------------------------------------

    def _draw_period_n1(self) -> tuple[float, float, bool, bool]:
        """N=1 用チャンク抽選: (価格増分, arb一様, noise到着, noise買い)。"""
        if self._buf_pos >= _CHUNK:
            cfg = self.cfg
            q = cfg.lambda_jump * cfg.dt
            jump = self._rng_price.random(_CHUNK) < q
            sign = np.where(self._rng_price.random(_CHUNK) < 0.5, 1.0, -1.0)
            inc = np.where(jump, sign * cfg.jump_size, 0.0)
            self._buf = (inc,
                         self._rng_arb.random(_CHUNK),
                         self._rng_noise.random(_CHUNK) < cfg.noise_rate * cfg.dt,
                         self._rng_noise.random(_CHUNK) < 0.5)
            self._buf_pos = 0
        i = self._buf_pos
        self._buf_pos += 1
        b = self._buf
        return float(b[0][i]), float(b[1][i]), bool(b[2][i]), bool(b[3][i])

    def _draw_period_batch(self, n_steps: int) -> tuple[float, float, int, int]:
        """batch 用: (net 変位, arb一様, noise買い数, noise売り数)。"""
        cfg = self.cfg
        q = cfg.lambda_jump * cfg.dt
        jump = self._rng_price.random(n_steps) < q
        sign = np.where(self._rng_price.random(n_steps) < 0.5, 1.0, -1.0)
        net = float(np.sum(np.where(jump, sign * cfg.jump_size, 0.0)))
        arrive = self._rng_noise.random(n_steps) < cfg.noise_rate * cfg.dt
        buy = self._rng_noise.random(n_steps) < 0.5
        n_buy = int(np.count_nonzero(arrive & buy))
        n_sell = int(np.count_nonzero(arrive & ~buy))
        return net, float(self._rng_arb.random()), n_buy, n_sell

    # ---- 1 学習期 ----------------------------------------------------------

    def step_core(self, actions: tuple[int, ...]):
        """1 学習期の中核（train の高速経路 — info dict を作らない）。step() と同一計算。

        returns (rewards: list[float], extraction, noise_pnl, fees, n_fills,
                 winner_a, h_w, disp)
        """
        cfg = self.cfg
        n_steps = cfg.period_steps
        if n_steps == 1:
            inc, arb_u, arrived, is_buy = self._draw_period_n1()
            v_final = self.v + inc
            n_buy = 1 if (arrived and is_buy) else 0
            n_sell = 1 if (arrived and not is_buy) else 0
        else:
            net, arb_u, n_buy, n_sell = self._draw_period_batch(n_steps)
            v_final = self.v + net

        winner_a = min(actions)
        winners = [i for i, a in enumerate(actions) if a == winner_a]
        h_w = self.grid[winner_a]
        disp = v_final - self.m  # 期内 net 変位（stale belief 基準）

        # noise（有限 R なら到着ごとに留保 r~U(0,R) で受諾判定, D-B11）
        if not math.isinf(cfg.noise_reserve):
            k = n_buy + n_sell
            if k:
                accept = self._rng_noise.random(k) * cfg.noise_reserve >= h_w
                acc_buy = int(np.count_nonzero(accept[:n_buy]))
                acc_sell = int(np.count_nonzero(accept[n_buy:]))
                n_buy, n_sell = acc_buy, acc_sell
        n_fills = n_buy + n_sell
        if cfg.staleness == "revisable":
            noise_pnl = n_fills * h_w                      # 再気配 quote で settle
            extraction = 0.0                               # 構造的に 0（docstring）
        else:
            noise_pnl = n_buy * (h_w - disp) + n_sell * (h_w + disp)
            extraction = 0.0
            if arb_u < cfg.alpha and abs(disp) > h_w:
                extraction = abs(disp) - h_w
        fees = cfg.fee * n_fills

        # reward（勝者総取り、tie は D-B8: 等分割 or 輪番）
        pool = noise_pnl + fees - extraction
        rewards = [0.0] * cfg.n_mm
        if cfg.tie_rule == "split" or len(winners) == 1:
            share = pool / len(winners)
            for i in winners:
                rewards[i] = share
        else:  # rotate
            rewards[winners[self._tie_counter % len(winners)]] = pool
            self._tie_counter += 1

        self.v = v_final
        self.m = v_final  # clear で学習（両 staleness 共通）
        return rewards, extraction, noise_pnl, fees, n_fills, winner_a, h_w, disp

    def step(self, actions: tuple[int, ...]) -> tuple[np.ndarray, dict]:
        (rewards, extraction, noise_pnl, fees, n_fills,
         winner_a, h_w, disp) = self.step_core(actions)
        info = {"extraction": extraction, "noise_pnl": noise_pnl, "fees": fees,
                "n_noise": n_fills, "winner_h": h_w, "winner_action": winner_a,
                "disp": disp}
        return np.asarray(rewards), info
