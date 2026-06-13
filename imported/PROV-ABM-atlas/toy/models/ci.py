"""Chiarella-Iori (CI) adapter — order-book-based heterogeneous agent model.

Based on Chiarella, Iori & Perelló (2009).  Agents submit limit orders
to a continuous double auction; price emerges from order matching rather
than from a single aggregate-demand clearing equation (as in SG).

The tick_size intervention widens the order-book grid, mechanically
increasing the bid-ask spread and reducing order-book depth.
The transaction_tax intervention adds a per-trade cost, deterring
marginal liquidity provision and amplifying volatility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from toy.models.types import (
    CalibrationArtifact,
    CanonicalIntervention,
    ComplexitySpec,
    MarketData,
    SimulatedMarketData,
)


@dataclass
class CIParams:
    """Parameters for the Chiarella-Iori model."""

    n_steps: int = 1000
    fundamental_value: float = 100.0

    # Strategy mixing
    alpha_fund: float = 0.4
    alpha_chart: float = 0.3
    alpha_noise: float = 0.3

    # Fundamentalist
    fund_speed: float = 0.05
    fund_confidence: float = 1.0

    # Chartist
    chart_lag: int = 10
    chart_strength: float = 0.8

    # Noise
    noise_scale: float = 0.01

    # Order book
    tick_size: float = 0.01
    spread_ticks: int = 3
    order_depth: int = 5

    # Market microstructure
    price_impact: float = 0.005
    transaction_cost: float = 0.0


@dataclass
class CIAdapter:
    """ModelAdapter implementation for the Chiarella-Iori order-book model."""

    params: CIParams = field(default_factory=CIParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        self.params.noise_scale = target_vol
        self.params.price_impact = 0.5
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="ci_v0.1",
            calibrated_params={
                "noise_scale": self.params.noise_scale,
                "price_impact": self.params.price_impact,
                "n_steps": self.params.n_steps,
                "tick_size": self.params.tick_size,
                "spread_ticks": self.params.spread_ticks,
                "transaction_cost": self.params.transaction_cost,
            },
            pre_data_hash=pre_data.content_hash(),
            seed=0,
            metadata={"target_vol": target_vol},
        )

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> CIAdapter:
        new_params = CIParams(
            n_steps=self.params.n_steps,
            fundamental_value=self.params.fundamental_value,
            alpha_fund=self.params.alpha_fund,
            alpha_chart=self.params.alpha_chart,
            alpha_noise=self.params.alpha_noise,
            fund_speed=self.params.fund_speed,
            fund_confidence=self.params.fund_confidence,
            chart_lag=self.params.chart_lag,
            chart_strength=self.params.chart_strength,
            noise_scale=self.params.noise_scale,
            tick_size=self.params.tick_size,
            spread_ticks=self.params.spread_ticks,
            order_depth=self.params.order_depth,
            price_impact=self.params.price_impact,
            transaction_cost=self.params.transaction_cost,
        )

        if intervention.intervention_class in ("tick_size_increase", "tick_size_decrease"):
            tick_from = intervention.canonical_params.get("min_tick_from", 1.0)
            tick_to = intervention.canonical_params.get("min_tick_to", tick_from)
            tick_ratio = tick_to / tick_from if tick_from != 0 else 1.0
            new_params.tick_size = self.params.tick_size * tick_ratio
        elif intervention.intervention_class == "transaction_tax":
            tax_rate = intervention.canonical_params.get("rate", 0.001)
            new_params.transaction_cost = tax_rate
        else:
            raise ValueError(f"Unknown intervention class: {intervention.intervention_class}")

        return CIAdapter(params=new_params)

    def simulate(self, seed: int, n_paths: int) -> SimulatedMarketData:
        all_returns = []

        for i in range(n_paths):
            rng_i = np.random.default_rng(seed + i)
            returns = self._simulate_one_path(rng_i)
            all_returns.append(returns)

        avg_returns = np.mean(all_returns, axis=0)

        return SimulatedMarketData(
            returns=avg_returns,
            seed=seed,
            n_paths=n_paths,
            model_id="ci_v0.1",
            metadata={
                "tick_size": self.params.tick_size,
                "transaction_cost": self.params.transaction_cost,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=9,
            structural_description=(
                "Continuous double-auction model with limit-order book, "
                "heterogeneous agents (fund/chart/noise), and order-matching "
                "price discovery (Chiarella, Iori & Perelló 2009)"
            ),
            description_length=9.0,
        )

    def _simulate_one_path(self, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        p = self.params
        T = p.n_steps
        prices = np.full(T, p.fundamental_value)
        returns = np.zeros(T)

        best_bid = p.fundamental_value - p.tick_size * p.spread_ticks
        best_ask = p.fundamental_value + p.tick_size * p.spread_ticks

        bid_depth = float(p.order_depth)
        ask_depth = float(p.order_depth)

        perf_fund = 0.0
        perf_chart = 0.0
        memory = 0.95

        a_fund = p.alpha_fund
        a_chart = p.alpha_chart
        a_noise = p.alpha_noise

        for t in range(1, T):
            mid = (best_bid + best_ask) / 2.0

            fund_fair = p.fundamental_value
            fund_order = p.fund_speed * (fund_fair - mid) * p.fund_confidence

            lag = min(p.chart_lag, t)
            if lag > 0:
                trend = (prices[t - 1] - prices[max(0, t - 1 - lag)]) / (
                    lag * max(prices[t - 1], p.tick_size)
                )
                chart_order = p.chart_strength * trend * mid
            else:
                chart_order = 0.0

            noise_order = rng.normal(0, p.noise_scale * mid)

            net_order = a_fund * fund_order + a_chart * chart_order + a_noise * noise_order

            cost = abs(net_order) * p.transaction_cost
            if abs(net_order) > 0:
                net_order *= max(0.0, 1.0 - cost / (abs(net_order) * mid + 1e-12))

            if net_order > 0:
                fill_price = best_ask + p.price_impact * net_order / (ask_depth + 1e-6)
                ask_depth = max(1.0, ask_depth - abs(net_order) * 0.1)
                bid_depth += abs(net_order) * 0.05
            elif net_order < 0:
                fill_price = best_bid + p.price_impact * net_order / (bid_depth + 1e-6)
                bid_depth = max(1.0, bid_depth - abs(net_order) * 0.1)
                ask_depth += abs(net_order) * 0.05
            else:
                fill_price = mid

            if p.tick_size > 0:
                fill_price = round(fill_price / p.tick_size) * p.tick_size
            fill_price = max(fill_price, p.tick_size)

            prices[t] = fill_price
            returns[t] = (prices[t] - prices[t - 1]) / prices[t - 1]

            spread = max(p.tick_size, p.tick_size * p.spread_ticks)
            best_bid = fill_price - spread / 2
            best_ask = fill_price + spread / 2

            bid_depth = bid_depth * 0.95 + p.order_depth * 0.05
            ask_depth = ask_depth * 0.95 + p.order_depth * 0.05

            perf_fund = memory * perf_fund + (1 - memory) * fund_order * returns[t]
            perf_chart = memory * perf_chart + (1 - memory) * chart_order * returns[t]

            total_perf = abs(perf_fund) + abs(perf_chart) + 1e-8
            w_fund = (abs(perf_fund) + 0.1) / (total_perf + 0.3)
            w_chart = (abs(perf_chart) + 0.1) / (total_perf + 0.3)
            w_noise = 1.0 - w_fund - w_chart
            w_noise = max(0.05, w_noise)

            s = w_fund + w_chart + w_noise
            a_fund = a_fund * 0.99 + (w_fund / s) * 0.01
            a_chart = a_chart * 0.99 + (w_chart / s) * 0.01
            a_noise = a_noise * 0.99 + (w_noise / s) * 0.01

        return returns
