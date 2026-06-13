"""離散時間 engine。連続 vs batch を同一の外生価格過程の上で回す。

真値 V は外生（取引に非依存）＝ジャンプ増分の累積。MM は belief m=直前の真値で
±h 気配を出し（1期 or 1バッチ staleness）、arbitrageur が stale quote を picking-off、
noise が無方向で約定する。全乱数は単一 default_rng(seed) 由来（決定論, D7）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace

import numpy as np

from .config import SimConfig
from .metrics import Metrics


@dataclass
class RunResult:
    config: SimConfig
    metrics: Metrics
    runtime_sec: float

    @property
    def extraction_rate(self) -> float:
        """単位時間あたり抽出量（Budish アンカーと比較）。"""
        return self.metrics.extraction / self.config.horizon


def _draw_increments(cfg: SimConfig, rng: np.random.Generator) -> np.ndarray:
    """各ステップの真値増分（jump ±J、確率 lambda*dt；diffusion 任意）。"""
    n = cfg.n_periods
    q = cfg.lambda_jump * cfg.dt
    jump = rng.random(n) < q
    direction = np.where(rng.random(n) < 0.5, 1.0, -1.0)
    inc = np.where(jump, direction * cfg.jump_size, 0.0)
    if cfg.sigma > 0:
        inc = inc + cfg.sigma * np.sqrt(cfg.dt) * rng.standard_normal(n)
    return inc


def _run_continuous(cfg: SimConfig, rng: np.random.Generator) -> Metrics:
    n = cfg.n_periods
    h, J = cfg.half_spread, cfg.jump_size
    pn = cfg.noise_rate * cfg.dt
    inc = _draw_increments(cfg, rng)
    v = cfg.initial_price + np.cumsum(inc)          # 各ステップ末の真値
    m = np.concatenate(([cfg.initial_price], v[:-1]))  # belief = 直前の真値（stale）
    disp = v - m                                    # = inc（このステップの移動）

    arb_present = rng.random(n) < cfg.alpha
    noise_present = rng.random(n) < pn
    noise_buy = rng.random(n) < 0.5

    # arbitrageur: stale quote が利益的（|disp|>h）なら picking-off。profit=|disp|-h。
    profitable = np.abs(disp) > h
    arb_trade = arb_present & profitable
    extraction = float(np.sum(np.abs(disp[arb_trade]) - h))
    n_arb = int(np.count_nonzero(arb_trade))
    informed_impact = float(np.mean(np.abs(disp[arb_trade]))) if n_arb else 0.0

    # noise: buy→MM は ask=m+h で売り PnL=h-disp、sell→bid=m-h で買い PnL=h+disp
    noise_pnl_each = np.where(noise_buy, h - disp, h + disp)
    noise_pnl = float(np.sum(noise_pnl_each[noise_present]))
    n_noise = int(np.count_nonzero(noise_present))

    # impact 層（D5b v2）: 主体を知らない符号付き flow x と価格変動 disp の原点回帰 λ̂。
    flow = (np.where(arb_trade, np.sign(disp), 0.0)
            + np.where(noise_present, np.where(noise_buy, 1.0, -1.0), 0.0))
    flow_sq = float(np.dot(flow, flow))
    price_impact = float(np.dot(flow, disp) / flow_sq) if flow_sq > 0 else 0.0

    return _assemble(cfg, extraction, noise_pnl, n_noise, n_arb,
                     informed_impact, price_impact)


def _run_batch(cfg: SimConfig, rng: np.random.Generator) -> Metrics:
    n, N = cfg.n_periods, cfg.batch_interval
    h = cfg.half_spread
    pn = cfg.noise_rate * cfg.dt
    inc = _draw_increments(cfg, rng)
    v = cfg.initial_price + np.cumsum(inc)
    noise_present = rng.random(n) < pn
    noise_buy = rng.random(n) < 0.5
    n_batches = (n + N - 1) // N
    arb_present = rng.random(n_batches) < cfg.alpha  # バッチごとに1回

    extraction = 0.0
    noise_pnl = 0.0
    n_noise = 0
    n_arb = 0
    informed_disp_sum = 0.0
    flow_dp = 0.0
    flow_sq = 0.0
    m0 = cfg.initial_price
    for b in range(n_batches):
        start = b * N
        end = min(start + N, n)
        v_final = v[end - 1]                 # clear 時の真値
        disp = v_final - m0                  # バッチ全体の net 変位（stale quote 基準）
        # arbitrageur: net 変位が利益的なら clear で 1 回だけ picking-off
        arb_sign = 0.0
        if arb_present[b] and abs(disp) > h:
            extraction += abs(disp) - h
            n_arb += 1
            informed_disp_sum += abs(disp)
            arb_sign = 1.0 if disp > 0 else -1.0
        # noise: バッチ内到着が clear 価格(stale quote)で settle、true=v_final
        idx = slice(start, end)
        nb = noise_present[idx]
        buys = int(np.count_nonzero(noise_buy[idx] & nb))
        sells = int(np.count_nonzero((~noise_buy[idx]) & nb))
        noise_pnl += buys * (h - disp) + sells * (h + disp)
        n_noise += buys + sells
        # impact 層（D5b v2）: バッチ単位の識別盲 flow x_b と net 変位の回帰和
        x = arb_sign + (buys - sells)
        flow_dp += x * disp
        flow_sq += x * x
        m0 = v_final                          # clear で学習
    informed_impact = informed_disp_sum / n_arb if n_arb else 0.0
    price_impact = flow_dp / flow_sq if flow_sq > 0 else 0.0
    return _assemble(cfg, extraction, noise_pnl, n_noise, n_arb,
                     informed_impact, price_impact)


def _assemble(cfg: SimConfig, extraction: float, noise_pnl: float,
              n_noise: int, n_arb: int, informed_impact: float,
              price_impact: float) -> Metrics:
    mm_trading_pnl = noise_pnl - extraction
    fees = cfg.fee * n_noise          # retail(noise) flow からの fee 収入（swap fee 同型）
    mm_net_pnl = mm_trading_pnl + fees  # 会計補助（spread 収入込み）
    # participation margin（spec/D9, AMM 同型）: fee 収入 − sniping 損(LVR) − 機会コスト。
    # spread 収入は含めない（固定提供下で fee が逆選択を補償できるか、の問い）。
    participation_margin = fees - extraction - cfg.opp_cost * cfg.horizon
    return Metrics(
        extraction=extraction,
        noise_pnl=noise_pnl,
        mm_trading_pnl=mm_trading_pnl,
        fees=fees,
        mm_net_pnl=mm_net_pnl,
        participation_margin=participation_margin,
        mm_exits=participation_margin < 0,
        effective_spread=2.0 * cfg.half_spread,
        informed_impact=informed_impact,
        price_impact=price_impact,
        n_noise=n_noise,
        n_arb=n_arb,
    )


def run(config: SimConfig) -> RunResult:
    """単一 run。同一 config（seed 含む）→ 同一 RunResult（SC-004）。"""
    t0 = time.perf_counter()
    rng = np.random.default_rng(config.seed)
    if config.mechanism == "continuous":
        metrics = _run_continuous(config, rng)
    elif config.mechanism == "batch":
        metrics = _run_batch(config, rng)
    else:
        raise ValueError(f"unknown mechanism: {config.mechanism}")
    return RunResult(config=config, metrics=metrics,
                     runtime_sec=time.perf_counter() - t0)


def measure_competitive_spread(config: SimConfig,
                               h_grid: np.ndarray | None = None) -> float:
    """MM trading PnL がゼロになる half-spread を scan して測る（GM の sim 側測定）。

    mm_trading_pnl は h について増加（noise 収入 ∝ h、sniping 損 ∝ (J-h)）。
    符号反転を線形補間して break-even h を返す。anchor (gm_break_even) と比較する量。
    """
    if h_grid is None:
        h_grid = np.linspace(0.01 * config.jump_size, 0.99 * config.jump_size, 25)
    pnls = []
    for h in h_grid:
        r = run(replace(config, half_spread=float(h)))
        pnls.append(r.metrics.mm_trading_pnl)
    pnls = np.asarray(pnls)
    sign = np.sign(pnls)
    cross = np.where(np.diff(sign) != 0)[0]
    if len(cross) == 0:
        # 反転が無い → grid 端で最小 |pnl|
        return float(h_grid[int(np.argmin(np.abs(pnls)))])
    i = cross[0]
    # 線形補間
    h0, h1 = h_grid[i], h_grid[i + 1]
    p0, p1 = pnls[i], pnls[i + 1]
    return float(h0 - p0 * (h1 - h0) / (p1 - p0))
