"""Speculation Game (SG) adapter — Katahira et al. (2019) variant.

A minimal heterogeneous-agent model with fundamentalists, chartists,
and noise traders. Agents switch strategies based on relative
performance, producing volatility clustering and leverage-like effects.

The tick_size intervention maps to the minimum price increment on
the simulated order book grid, affecting the cognitive threshold
for strategy switching.
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
class SGParams:
    """Parameters for the Speculation Game model."""

    n_steps: int = 1000
    fundamental_value: float = 100.0

    # Strategy switching
    beta: float = 1.5  # intensity of choice (switching sensitivity)
    memory: float = 0.95  # exponential decay for performance tracking

    # Agent types
    fundamentalist_speed: float = 0.05  # mean-reversion speed
    chartist_lag: int = 5  # lookback for trend following
    chartist_strength: float = 1.5  # trend extrapolation multiplier
    noise_scale: float = 0.01  # noise trader demand std

    # Market impact
    price_impact: float = 0.01  # price impact per unit excess demand
    tick_size: float = 0.01  # minimum price increment


@dataclass
class SGAdapter:
    """ModelAdapter implementation for the Speculation Game."""

    params: SGParams = field(default_factory=SGParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        # Scale noise so that typical price changes span many ticks.
        # noise demand ≈ N(0, noise_scale * P).  We want
        # price_impact * noise_scale * P ≈ target_vol * P  (in price space).
        # With price_impact fixed, set noise_scale = target_vol / price_impact.
        price_impact = 1.0  # unit price impact simplifies scaling
        noise_scale = target_vol  # so dp/P ≈ N(0, target_vol)

        self.params.noise_scale = noise_scale
        self.params.price_impact = price_impact
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="sg_v0.1",
            calibrated_params={
                "noise_scale": noise_scale,
                "price_impact": price_impact,
                "n_steps": self.params.n_steps,
                "beta": self.params.beta,
                "memory": self.params.memory,
                "tick_size": self.params.tick_size,
            },
            pre_data_hash=pre_data.content_hash(),
            seed=0,
            metadata={"target_vol": target_vol},
        )

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> SGAdapter:
        new_params = SGParams(
            n_steps=self.params.n_steps,
            fundamental_value=self.params.fundamental_value,
            beta=self.params.beta,
            memory=self.params.memory,
            fundamentalist_speed=self.params.fundamentalist_speed,
            chartist_lag=self.params.chartist_lag,
            chartist_strength=self.params.chartist_strength,
            noise_scale=self.params.noise_scale,
            price_impact=self.params.price_impact,
            tick_size=self.params.tick_size,
        )

        if intervention.intervention_class in ("tick_size_increase", "tick_size_decrease"):
            tick_from = intervention.canonical_params.get("min_tick_from", 1.0)
            tick_to = intervention.canonical_params.get("min_tick_to", tick_from)
            tick_ratio = tick_to / tick_from if tick_from != 0 else 1.0
            new_params.tick_size = self.params.tick_size * tick_ratio
        elif intervention.intervention_class == "transaction_tax":
            tax_rate = intervention.canonical_params.get("rate", 0.001)
            effective_cost = tax_rate * self.params.fundamental_value
            new_params.tick_size = max(self.params.tick_size, effective_cost)
        else:
            raise ValueError(f"Unknown intervention class: {intervention.intervention_class}")

        return SGAdapter(params=new_params)

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
            model_id="sg_v0.1",
            metadata={
                "tick_size": self.params.tick_size,
                "beta": self.params.beta,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=7,
            structural_description=(
                "Heterogeneous-agent model with fundamentalist/chartist/noise "
                "strategy switching via discrete choice (Katahira et al. 2019)"
            ),
            description_length=7.0,
        )

    def _simulate_one_path(self, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        p = self.params
        T = p.n_steps
        prices = np.full(T, p.fundamental_value)
        returns = np.zeros(T)

        # Agent state: fraction following each strategy
        w_fund = 0.5
        w_chart = 0.3
        w_noise = 0.2

        # Performance tracking
        perf_fund = 0.0
        perf_chart = 0.0

        for t in range(1, T):
            # Fundamentalist demand: mean-revert toward fundamental
            d_fund = p.fundamentalist_speed * (p.fundamental_value - prices[t - 1])

            # Chartist demand: follow recent trend
            lag = min(p.chartist_lag, t)
            if lag > 0:
                trend = (prices[t - 1] - prices[max(0, t - 1 - lag)]) / (lag * prices[t - 1])
                d_chart = p.chartist_strength * trend * prices[t - 1]
            else:
                d_chart = 0.0

            # Noise demand
            d_noise = rng.normal(0, p.noise_scale * prices[t - 1])

            # Aggregate demand and price update
            excess_demand = w_fund * d_fund + w_chart * d_chart + w_noise * d_noise
            dp = p.price_impact * excess_demand

            # Apply tick size discretization
            if p.tick_size > 0:
                dp = round(dp / p.tick_size) * p.tick_size

            prices[t] = max(prices[t - 1] + dp, p.tick_size)
            returns[t] = (prices[t] - prices[t - 1]) / prices[t - 1]

            # Update performance tracking
            perf_fund = p.memory * perf_fund + (1 - p.memory) * d_fund * returns[t]
            perf_chart = p.memory * perf_chart + (1 - p.memory) * d_chart * returns[t]

            # Strategy switching (discrete choice / softmax)
            exp_f = np.exp(p.beta * perf_fund)
            exp_c = np.exp(p.beta * perf_chart)
            denom = exp_f + exp_c + 1.0  # noise has baseline attractiveness of 1
            w_fund = exp_f / denom
            w_chart = exp_c / denom
            w_noise = 1.0 / denom

        return returns
