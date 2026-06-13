"""最小 zero-intelligence 指値板（Smith, Farmer, Gillespie & Krishnamurthy 2003 系）。

WP v2 §6 の order-book probe。channel_band の単一資産市場では return = λ·ED/N で
価格変化と注文流が同一信号（実測 corr 1.000、再パラメータ化）だった。板では成行注文は
最良気配の板厚を食い尽くすまで価格を動かさないので、価格変化チャネルと注文流チャネルが
脱共役しうる。本 probe はその脱共役（corr(Δmid, net-flow) < 1）を測る。これが、価格を読む
機構と注文流を読む機構が「同一モデルの再パラメータ化」でなく genuinely 異機構になりうる
ための前提条件。

設計（最小・正しさ優先、速度は後回し）:
- 価格はグリッド整数。bid_qty[p], ask_qty[p] が各価格の resting 数量。
- イベント: 指値(limit) / 成行(market) / 取消(cancel) を確率で抽選。
  - 指値買い: 価格 = best_ask − k（k~geometric、k≥1）。spread 内〜深部に置かれ板厚を作る。
  - 成行買い: best_ask の 1 単位を消費。板厚が尽きれば best_ask が上がる（価格が動く）。
  - 取消: 占有 level から数量重みで 1 単位除去。
- 政策 θ = tick: 指値価格を tick の倍数に丸める（JPX 2014 型の価格グリッド粗化）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LOBParams:
    grid: int = 512  # 価格 level 数
    p_limit: float = 0.55  # イベント確率: 指値
    p_market: float = 0.18  # イベント確率: 成行
    p_cancel: float = 0.27  # イベント確率: 取消（3つで和=1）
    offset_mean: float = 5.0  # 指値の最良反対気配からの平均 offset（tick）
    tick: int = 1  # 政策 θ: 価格グリッドの粗さ（1=最細）
    init_levels: int = 20  # 初期板の片側 level 数
    init_depth: int = 5  # 初期各 level の数量


DEFAULT_LOB = LOBParams()


@dataclass(frozen=True)
class LOBResult:
    mid: np.ndarray  # window ごとの mid 価格
    flow: np.ndarray  # window ごとの net 成行フロー（買い+ / 売り−）
    spread: np.ndarray  # window ごとの spread（best_ask − best_bid）
    depth: np.ndarray  # window ごとの最良気配の板厚（両側平均）


def _round_tick(price: int, tick: int) -> int:
    if tick <= 1:
        return price
    return int(round(price / tick) * tick)


def simulate_lob(
    n_windows: int,
    seed: int,
    params: LOBParams = DEFAULT_LOB,
    *,
    events_per_window: int = 25,
    warmup_windows: int = 200,
) -> LOBResult:
    """ZI 板を回し、window 単位で (mid, net-flow, spread, depth) を返す。

    各 window は ``events_per_window`` 個のイベント。window 内の net 成行フローと
    window 端での mid を記録する。
    """
    rng = np.random.default_rng(seed)
    g = params.grid
    tick = params.tick
    bid = np.zeros(g, dtype=np.int64)
    ask = np.zeros(g, dtype=np.int64)

    mid0 = g // 2
    for j in range(1, params.init_levels + 1):
        bp = _round_tick(mid0 - j, tick)
        ap = _round_tick(mid0 + j, tick)
        if 0 <= bp < g:
            bid[bp] += params.init_depth
        if 0 <= ap < g:
            ask[ap] += params.init_depth

    def best_bid() -> int:
        nz = np.nonzero(bid)[0]
        return int(nz[-1]) if nz.size else -1

    def best_ask() -> int:
        nz = np.nonzero(ask)[0]
        return int(nz[0]) if nz.size else -1

    probs = np.array([params.p_limit, params.p_market, params.p_cancel])
    probs = probs / probs.sum()

    total = warmup_windows + n_windows
    mids = np.empty(n_windows)
    flows = np.empty(n_windows)
    spreads = np.empty(n_windows)
    depths = np.empty(n_windows)

    for w in range(total):
        net_flow = 0
        for _ in range(events_per_window):
            bb = best_bid()
            ba = best_ask()
            # 板が片側枯渇したら再注入（最小限の市場メイク）
            if bb < 0 or ba < 0 or ba - bb >= params.offset_mean * 8:
                anchor = mid0 if (bb < 0 or ba < 0) else (bb + ba) // 2
                bp = _round_tick(anchor - 1, tick)
                ap = _round_tick(anchor + 1, tick)
                if 0 <= bp < g:
                    bid[bp] += params.init_depth
                if 0 <= ap < g:
                    ask[ap] += params.init_depth
                continue

            ev = rng.choice(3, p=probs)
            if ev == 0:  # 指値
                k = 1 + rng.geometric(1.0 / params.offset_mean)
                if rng.random() < 0.5:  # 買い指値
                    price = _round_tick(ba - k, tick)
                    if 0 <= price < g and price < ba:
                        bid[price] += 1
                else:  # 売り指値
                    price = _round_tick(bb + k, tick)
                    if 0 <= price < g and price > bb:
                        ask[price] += 1
            elif ev == 1:  # 成行
                if rng.random() < 0.5:  # 成行買い: best_ask を消費
                    ask[ba] -= 1
                    net_flow += 1
                else:  # 成行売り: best_bid を消費
                    bid[bb] -= 1
                    net_flow -= 1
            else:  # 取消
                if rng.random() < 0.5:
                    nz = np.nonzero(bid)[0]
                    if nz.size:
                        lvl = nz[rng.integers(nz.size)]
                        bid[lvl] -= 1
                else:
                    nz = np.nonzero(ask)[0]
                    if nz.size:
                        lvl = nz[rng.integers(nz.size)]
                        ask[lvl] -= 1

        bb = best_bid()
        ba = best_ask()
        if w >= warmup_windows:
            i = w - warmup_windows
            mids[i] = (bb + ba) / 2.0
            flows[i] = net_flow
            spreads[i] = ba - bb
            depths[i] = (bid[bb] + ask[ba]) / 2.0 if bb >= 0 and ba >= 0 else np.nan

    return LOBResult(mid=mids, flow=flows, spread=spreads, depth=depths)


def channel_correlation(res: LOBResult) -> float:
    """corr(Δmid, net-flow)。channel_band では 1.000。板では < 1 が脱共役の証拠。"""
    dmid = np.diff(res.mid)
    flow = res.flow[1:]
    if np.std(dmid) < 1e-12 or np.std(flow) < 1e-12:
        return float("nan")
    return float(np.corrcoef(dmid, flow)[0, 1])
