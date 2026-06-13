"""Lux & Marchesi (2000) "Volatility clustering in financial markets: a
microsimulation of interacting agents" の再現実装 (Parameter Set I のみ).

Reference:
    Lux, T., & Marchesi, M. (2000). Volatility clustering in financial markets:
    a microsimulation of interacting agents.
    International Journal of Theoretical and Applied Finance, 3(4), 675-702.

数式は論文 §2 の式 (2.1)-(2.4) に厳密準拠。
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class Params:
    """Parameter Set I (論文 p.689) — aggregated form.

    Tc ≡ N·tc, Tf ≡ N·γ で個体レベル定数 tc, γ を吸収している。
    """

    N: int = 500
    nu1: float = 3.0
    nu2: float = 2.0
    beta: float = 6.0
    Tc: float = 10.0
    Tf: float = 5.0
    alpha1: float = 0.6
    alpha2: float = 0.2
    alpha3: float = 0.5
    pf: float = 10.0
    r: float = 0.004
    R: float = 0.0004
    s: float = 0.75
    sigma_mu: float = 0.05
    dt: float = 0.01
    dp: float = 0.01
    min_group: int = 4
    pdot_window: int = 20


def compute_zbar(p: Params) -> float:
    """(cond 1) a11 + a33 = 0 を満たす z を求める。

    論文 Appendix A の Jacobian (p.699) から、dp/dt = β·[x·z·Tc + (1−z)·(pf−p)·Tf]
    をミクロ時間スケールに合わせて用いると:
        a11 = 2·z·[ν1·(α1 − 1) + β·α2·z·Tc + β·(1 − z)·α3·Tc/pf]
        a33 = −β·(1 − z)·Tf
    (cond 1): a11 + a33 > 0 で不安定。= 0 となる z が臨界値 z̄。
    Parameter Set I で約 0.66 (論文 p.690 の 0.65 とほぼ一致)。
    """
    b = p.beta
    A = 2 * b * p.alpha2 * p.Tc - 2 * b * p.alpha3 * p.Tc / p.pf
    B = 2 * p.nu1 * (p.alpha1 - 1) + 2 * b * p.alpha3 * p.Tc / p.pf + b * p.Tf
    C = -b * p.Tf
    if abs(A) < 1e-12:
        return float(-C / B)
    disc = B * B - 4 * A * C
    if disc < 0:
        return float("nan")
    root1 = (-B + np.sqrt(disc)) / (2 * A)
    root2 = (-B - np.sqrt(disc)) / (2 * A)
    for r in (root1, root2):
        if 0.0 < r < 1.0:
            return float(r)
    return float(root1)


class LuxMarchesiMarket:
    """Lux-Marchesi (2000) の離散時間シミュレーション。

    State:
        n_plus, n_minus : 楽観/悲観 chartists の人数
        n_f             : fundamentalists の人数 (n_plus + n_minus + n_f = N)
        price           : 現在価格
        price_hist      : 直近 pdot_window+1 ステップの価格 (ring buffer)
    """

    def __init__(self, params: Params, seed: int = 42, n_c_init: int = 50):
        self.p = params
        self.rng = np.random.default_rng(seed)

        n_c = max(params.min_group * 2, n_c_init)
        n_plus = int(self.rng.integers(params.min_group, n_c - params.min_group + 1))
        n_minus = n_c - n_plus
        n_f = params.N - n_c
        self.n_plus = n_plus
        self.n_minus = n_minus
        self.n_f = n_f

        self.price = params.pf
        self.price_hist = np.full(params.pdot_window + 1, params.pf)
        self.hist_idx = 0

    @property
    def n_c(self) -> int:
        return self.n_plus + self.n_minus

    def _pdot(self) -> float:
        """直近 0.2 time unit (= 20 sim ステップ) の平均価格変化率."""
        oldest_idx = self.hist_idx
        newest_idx = (self.hist_idx - 1) % len(self.price_hist)
        newest = self.price_hist[newest_idx]
        oldest = self.price_hist[oldest_idx]
        return (newest - oldest) / (self.p.pdot_window * self.p.dt)

    def _multinomial_switches(self, n: int, p1: float, p2: float) -> tuple[int, int]:
        """n 人がそれぞれ独立に確率 p1, p2 で 2 種類の遷移のいずれかを起こす。

        p1 + p2 > 1 になるときは和を 1 に正規化する (稀)。
        """
        if n <= 0:
            return 0, 0
        if p1 < 0:
            p1 = 0.0
        if p2 < 0:
            p2 = 0.0
        total = p1 + p2
        if total > 1.0:
            p1 /= total
            p2 /= total
            total = 1.0
        draws = self.rng.multinomial(n, [p1, p2, 1.0 - total])
        return int(draws[0]), int(draws[1])

    def step(self) -> None:
        p = self.p
        N = p.N
        n_plus, n_minus, n_f = self.n_plus, self.n_minus, self.n_f
        n_c = n_plus + n_minus

        x = (n_plus - n_minus) / n_c if n_c > 0 else 0.0
        pdot = self._pdot()
        price = self.price

        # --- 式 (2.2): opinion switches 内 chartists ---
        U1 = p.alpha1 * x + p.alpha2 * (pdot / p.nu1)
        eU1 = np.exp(U1)
        base_op = p.nu1 * (n_c / N) * p.dt
        # pi_{+-} : pessimist → optimist の個体遷移確率
        pi_plus_from_minus = base_op * eU1
        pi_minus_from_plus = base_op / eU1

        # --- 式 (2.3): strategy switches chartist ↔ fundamentalist ---
        dev = (p.pf - price) / price
        absdev = abs(dev)
        profit_capital = (p.r + pdot / p.nu2) / price
        U2_1 = p.alpha3 * (profit_capital - p.R - p.s * absdev)
        U2_2 = p.alpha3 * (p.R - profit_capital - p.s * absdev)
        eU21 = np.exp(U2_1)
        eU22 = np.exp(U2_2)

        # f → + : 個体遷移確率 (meets optimist with prob n+/N)
        pi_plus_from_f = p.nu2 * (n_plus / N) * eU21 * p.dt
        # + → f : 個体遷移確率 (meets fundamentalist with prob nf/N)
        pi_f_from_plus = p.nu2 * (n_f / N) / eU21 * p.dt
        # f → -
        pi_minus_from_f = p.nu2 * (n_minus / N) * eU22 * p.dt
        # - → f
        pi_f_from_minus = p.nu2 * (n_f / N) / eU22 * p.dt

        # --- 吸収状態回避: メンバー数 < min_group の group から出ない ---
        # outflow from + : to minus (pi_minus_from_plus), to f (pi_f_from_plus)
        if n_plus >= p.min_group:
            out_plus_to_minus, out_plus_to_f = self._multinomial_switches(
                n_plus, pi_minus_from_plus, pi_f_from_plus
            )
        else:
            out_plus_to_minus = 0
            out_plus_to_f = 0

        if n_minus >= p.min_group:
            out_minus_to_plus, out_minus_to_f = self._multinomial_switches(
                n_minus, pi_plus_from_minus, pi_f_from_minus
            )
        else:
            out_minus_to_plus = 0
            out_minus_to_f = 0

        if n_f >= p.min_group:
            out_f_to_plus, out_f_to_minus = self._multinomial_switches(
                n_f, pi_plus_from_f, pi_minus_from_f
            )
        else:
            out_f_to_plus = 0
            out_f_to_minus = 0

        new_plus = (
            n_plus
            - out_plus_to_minus
            - out_plus_to_f
            + out_minus_to_plus
            + out_f_to_plus
        )
        new_minus = (
            n_minus
            - out_minus_to_plus
            - out_minus_to_f
            + out_plus_to_minus
            + out_f_to_minus
        )
        new_f = n_f - out_f_to_plus - out_f_to_minus + out_plus_to_f + out_minus_to_f

        self.n_plus = new_plus
        self.n_minus = new_minus
        self.n_f = new_f

        # --- 式 (2.4): 価格の ±0.01 離散ジャンプ ---
        # 論文 p.687 の footnote: 価格については「cents を elementary unit と
        # するため 1/100 スケーリング込み、追加調整不要」。すなわち
        # π_↑ = β·(ED+μ) がそのまま 1 ステップ確率。opinion/strategy は
        # Δt=1/100 を掛けるが、ここは掛けない。
        tc = p.Tc / N
        gamma = p.Tf / N
        ED = (new_plus - new_minus) * tc + new_f * gamma * (p.pf - price)
        mu = self.rng.normal(0.0, p.sigma_mu)
        signal = p.beta * (ED + mu)
        p_up = signal if signal > 0 else 0.0
        p_down = -signal if signal < 0 else 0.0
        if p_up > 1.0:
            p_up = 1.0
        if p_down > 1.0:
            p_down = 1.0

        u = self.rng.random()
        if p_up > 0 and u < p_up:
            self.price = price + p.dp
        elif p_down > 0 and u < p_down:
            self.price = price - p.dp
        if self.price < p.dp:
            self.price = p.dp

        # 価格履歴を更新
        self.price_hist[self.hist_idx] = self.price
        self.hist_idx = (self.hist_idx + 1) % len(self.price_hist)


def simulate(
    params: Params | None = None,
    n_integer_steps: int = 4000,
    steps_per_unit: int = 100,
    seed: int = 42,
    n_c_init: int = 50,
    verbose: bool = True,
) -> dict:
    """Parameter Set I で Lux-Marchesi (2000) を走らせる。

    Parameters
    ----------
    n_integer_steps : int
        記録対象とする integer time step 数 (論文 Fig.1 の時間軸 = 4000)
    steps_per_unit : int
        1 time unit あたりの simulation step 数 (Δt = 1/steps_per_unit = 0.01)
    """
    if params is None:
        params = Params()
    market = LuxMarchesiMarket(params, seed=seed, n_c_init=n_c_init)
    prices = np.empty(n_integer_steps + 1)
    x_series = np.empty(n_integer_steps + 1)
    z_series = np.empty(n_integer_steps + 1)

    prices[0] = market.price
    z_series[0] = market.n_c / params.N
    x_series[0] = (
        (market.n_plus - market.n_minus) / market.n_c if market.n_c > 0 else 0.0
    )

    log_every = max(1, n_integer_steps // 10)
    for t in range(1, n_integer_steps + 1):
        for _ in range(steps_per_unit):
            market.step()
        prices[t] = market.price
        z_series[t] = market.n_c / params.N
        x_series[t] = (
            (market.n_plus - market.n_minus) / market.n_c if market.n_c > 0 else 0.0
        )
        if verbose and t % log_every == 0:
            print(
                f"  step {t}/{n_integer_steps}  p={market.price:.3f}  "
                f"z={z_series[t]:.3f}  x={x_series[t]:+.3f}"
            )

    returns = np.diff(np.log(prices))
    return {
        "prices": prices,
        "returns": returns,
        "z": z_series,
        "x": x_series,
        "params": params,
        "zbar": compute_zbar(params),
    }
