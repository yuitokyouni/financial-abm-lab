"""channel_band — 観測チャネルの分離による機構識別(再設計 P1、Issue #11)。

介入応答で2モデルを識別するには、2モデルが観測データ上で区別不能(でなければ介入は不要)かつ
介入応答が異なる必要がある。我々の予備的実験では、同一方程式のパラメータ変種は介入応答が ~10⁻⁴ に
縮退して識別できず、機構を変えると介入前に CNN が生価格系列から約 0.9 で区別した。両要件を同時に
満たす例を本モジュールが構成する。

鍵(2026-06-13 実証): 単一資産の超過需要市場では return = λ·(order-flow)(相関 1.000)で、価格
チャネルと注文流チャネルは同一信号。よって価格を読むモデル A と注文流を読むモデル B は連続市場で
bit 同一の軌道を生み区別不能。batch auction(interval Nb 期ごとに一括清算、バッチ内は価格不変・
注文流のみ蓄積)では両チャネルが異なる情報を持ち、A はバッチ境界の価格変化にのみ反応、B は注文流に
毎期反応して、両者は異なる軌道を生む。連続データで区別不能なモデルを batch 改革が識別する。
介入は実在の市場設計政策(batch vs continuous、JPX/BoJ の論点、P2 と共通)。

実装は外部依存なし・ベクトル化(agent を配列化、window は prefix-sum で O(1)/agent)。
連続では simulate('A')==simulate('B') が bit 同一(test で固定)。batch では分岐。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, overload

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


def _mom(
    s: npt.NDArray[np.float64],
    s2: npt.NDArray[np.float64],
    t: int,
    lo: npt.NDArray[np.int64],
) -> npt.NDArray[np.float64]:
    """prefix-sum (s, s2) から窓 [lo, t) の正規化モメンタム mean/std を O(1)/agent で。"""
    w = np.maximum(t - lo, 1)
    mean = (s[t] - s[lo]) / w
    var = (s2[t] - s2[lo]) / w - mean**2
    out: npt.NDArray[np.float64] = mean / np.sqrt(np.maximum(var, 1e-12))
    return out


@overload
def simulate(
    model: str,
    batch_interval: int,
    seed: int,
    params: BandParams = ...,
    *,
    with_flow: Literal[False] = False,
) -> npt.NDArray[np.float64]: ...


@overload
def simulate(
    model: str,
    batch_interval: int,
    seed: int,
    params: BandParams = ...,
    *,
    with_flow: Literal[True],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]: ...


def simulate(
    model: str,  # "A"=price-reader / "B"=orderflow-reader / "adaptive"=学習(高|mom|チャネル)
    batch_interval: int,
    seed: int,
    params: BandParams = DEFAULT_PARAMS,
    *,
    with_flow: bool = False,
) -> npt.NDArray[np.float64] | tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """1 run。batch 境界ごとの log-return 系列(実際の価格変化)を返す。

    model="A": 価格 return チャネルを読む。"B": 注文流チャネル。"adaptive": 各 speculator が
    直近で |momentum| の大きいチャネルを選ぶ最小学習則(連続では両者同一なので A と一致、
    batch では情報のある注文流へ移行)。batch_interval=1 で連続市場(return=λ·flow → A=B bit 同一)。
    with_flow=True で (batch_returns, 毎期 order-flow 系列) を返す(microstructure facts 用、案3)。
    """
    p = params
    rng = np.random.default_rng(seed)
    u = rng.random(p.n_agents)
    spec = u < p.frac_spec
    n_fund = int(((u >= p.frac_spec) & (u < p.frac_spec + p.frac_fund)).sum())
    n_noise = int((u >= p.frac_spec + p.frac_fund).sum())
    hs = rng.integers(p.h_min, p.h_max + 1, size=int(spec.sum()))

    total = p.burn_in + p.steps
    # 価格 return と 注文流 の両チャネルの prefix sum を保持(model がどちらを読むか選ぶ)。
    p_s = np.zeros(total + 1)
    p_s2 = np.zeros(total + 1)
    f_s = np.zeros(total + 1)
    f_s2 = np.zeros(total + 1)
    price = p.p_star
    acc_ed = 0.0
    bret: list[float] = []
    flow_series: list[float] = []

    for t in range(total):
        if t > 0:
            lo = np.clip(t - hs, 0, t)
            pmom = _mom(p_s, p_s2, t, lo)  # 価格チャネルの momentum
            fmom = _mom(f_s, f_s2, t, lo)  # 注文流チャネルの momentum
            if model == "A":
                sig = pmom
            elif model == "B":
                sig = fmom
            else:  # adaptive: 各 agent が高|momentum|チャネルを選ぶ
                sig = np.where(np.abs(fmom) > np.abs(pmom), fmom, pmom)
            a_spec = np.where(np.abs(sig) > p.theta_chartist, np.sign(sig), 0.0)
            ed = float(a_spec.sum())
        else:
            ed = 0.0
        m = float(np.log(p.p_star / price))  # fundamentalist 錨
        if abs(m) > p.theta_fund:
            ed += n_fund * np.sign(m)
        ed += float(rng.integers(-1, 2, size=n_noise).sum())  # noise

        flow_t = ed / p.n_agents
        if t >= p.burn_in:
            flow_series.append(flow_t)
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

        p_s[t + 1] = p_s[t] + pret_t
        p_s2[t + 1] = p_s2[t] + pret_t * pret_t
        f_s[t + 1] = f_s[t] + flow_t
        f_s2[t + 1] = f_s2[t] + flow_t * flow_t

    rets = np.asarray(bret, dtype=np.float64)
    if with_flow:
        return rets, np.asarray(flow_series, dtype=np.float64)
    return rets
