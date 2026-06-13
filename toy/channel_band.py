"""channel_band — 観測チャネル脱共役による機構識別(再設計 P1 の核)。

**動機(Issue #11 / 二本の角)**: 異機構を SF-等価に似せて介入で分ける旧 toy(T/H)は構造的に
詰む —— パラメータ変種は介入応答が同じ(PRISM FATAL-3)、genuinely 異機構は観測で既に分かれる
(held-out CNN ~0.9)。介入弁別の価値は「観測等価 ∧ 介入分離」の細い帯にしか棲まない。

**鍵(2026-06-13 実証)**: 単一資産の超過需要市場では return = λ·(order-flow) で**価格チャネルと
注文流チャネルが厳密に同一信号**(corr=1)。だから:
- **価格を読むモデル A** と **注文流を読むモデル B** は、**連続市場では観測上 identical**
  (歴史データ・CNN で区別不能)。
- **batch auction**(interval Nb 期ごとに一括清算 → バッチ内は価格 flat だが注文流は蓄積)が
  両チャネルを**脱共役** → A は flat な価格を見て沈黙、B は注文流を見て活動 → 別挙動。

→ **「連続データで区別不能なモデルを、batch 政策改革が識別する」**。介入 = 実在の市場設計政策
(batch vs continuous、P2 の核・JPX/BoJ の政策論争)。これが帯に棲む構成的実例。

実装は self-contained・vectorized(agent を配列化、window は prefix-sum で O(1)/agent)。
連続では simulate('A')==simulate('B') が **bit 同一**(test で pin)。batch では分岐。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class BandParams:
    """市場 + 集団パラメータ(spec §3 系に対応、batch 拡張)。"""

    n_agents: int = 150
    steps: int = 1600
    burn_in: int = 300
    lam: float = 0.05
    p_star: float = 100.0
    frac_spec: float = 0.5  # speculator(チャネルを読む機構定義成分)
    frac_fund: float = 0.35  # fundamentalist(錨)
    h_min: int = 5
    h_max: int = 40
    theta_chartist: float = 0.7  # speculator 発火閾値(正規化モメンタム)
    theta_fund: float = 0.004  # fundamentalist 発火閾値(誤価格)


DEFAULT_PARAMS = BandParams()


def simulate(
    model: str,  # "A" = price-reader / "B" = orderflow-reader
    batch_interval: int,
    seed: int,
    params: BandParams = DEFAULT_PARAMS,
) -> npt.NDArray[np.float64]:
    """1 run。batch 境界ごとの log-return 系列(実際の価格変化)を返す。

    model="A": speculator は価格 return チャネルを読む。"B": 注文流チャネルを読む。
    batch_interval=1 で連続市場(return=λ·flow → A と B は bit 同一)。
    """
    p = params
    rng = np.random.default_rng(seed)
    u = rng.random(p.n_agents)
    spec = u < p.frac_spec
    n_fund = int(((u >= p.frac_spec) & (u < p.frac_spec + p.frac_fund)).sum())
    n_noise = int((u >= p.frac_spec + p.frac_fund).sum())
    hs = rng.integers(p.h_min, p.h_max + 1, size=int(spec.sum()))

    total = p.burn_in + p.steps
    sig_s = np.zeros(total + 1)  # signal 系列の prefix sum(model 依存)
    sig_s2 = np.zeros(total + 1)
    price = p.p_star
    acc_ed = 0.0
    bret: list[float] = []

    for t in range(total):
        # speculator: 自分の horizon 窓上の正規化モメンタム(prefix-sum で O(1)/agent)
        if t > 0:
            lo = np.clip(t - hs, 0, t)
            w = np.maximum(t - lo, 1)
            mean = (sig_s[t] - sig_s[lo]) / w
            var = (sig_s2[t] - sig_s2[lo]) / w - mean**2
            mom = mean / np.sqrt(np.maximum(var, 1e-12))
            a_spec = np.where(np.abs(mom) > p.theta_chartist, np.sign(mom), 0.0)
            ed = float(a_spec.sum())
        else:
            ed = 0.0
        # fundamentalist: 現在の誤価格(全員同質)
        m = float(np.log(p.p_star / price))
        if abs(m) > p.theta_fund:
            ed += n_fund * np.sign(m)
        # noise
        ed += float(rng.integers(-1, 2, size=n_noise).sum())

        flow_t = ed / p.n_agents
        acc_ed += ed
        if (t + 1) % batch_interval == 0:  # batch 境界で一括清算
            dlog = p.lam * acc_ed / (p.n_agents * batch_interval)
            price *= float(np.exp(dlog))
            acc_ed = 0.0
            pret_t = dlog
            if t >= p.burn_in:
                bret.append(dlog)
        else:  # バッチ内: 価格は動かない
            pret_t = 0.0

        sig = pret_t if model == "A" else flow_t  # A=価格 return / B=注文流
        sig_s[t + 1] = sig_s[t] + sig
        sig_s2[t + 1] = sig_s2[t] + sig * sig

    return np.asarray(bret, dtype=np.float64)
