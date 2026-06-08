"""Lux-Marchesi (LM) adapter — herding-based heterogeneous agent model.

Based on Lux & Marchesi (1999, 2000).  Two agent populations —
fundamentalists and chartists — with endogenous switching driven by
herding dynamics.  Chartists are further split into optimists and
pessimists; opinion clusters drive price bubbles and crashes.

Key mechanism: social imitation (herding) creates endogenous regime
switching between calm (fundamentalist-dominated) and turbulent
(chartist-dominated) periods, reproducing volatility clustering,
fat tails, and the leverage effect.

The tick_size intervention affects the minimum price resolution,
changing the granularity of information available to agents and
dampening herding cascades via coarser price signals.
The transaction_tax intervention reduces speculative chartist
activity by increasing the cost of round-trip trades.
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
class LMParams:
    """Parameters for the Lux-Marchesi model."""

    n_fund: int = 200
    n_chart: int = 300
    n_steps: int = 1000
    fundamental_value: float = 100.0

    # Fundamentalist
    fund_speed: float = 0.05

    # Herding dynamics
    herd_strength: float = 1.5
    opinion_decay: float = 0.1

    # Chartist sensitivity
    chart_trend_weight: float = 0.8
    chart_lookback: int = 5

    # Noise
    noise_scale: float = 0.01

    # Market
    price_impact: float = 0.01
    tick_size: float = 0.01
    transaction_cost: float = 0.0


@dataclass
class LMAdapter:
    """ModelAdapter implementation for the Lux-Marchesi herding model."""

    params: LMParams = field(default_factory=LMParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        self.params.noise_scale = target_vol
        self.params.price_impact = 0.8
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="lm_v0.1",
            calibrated_params={
                "noise_scale": self.params.noise_scale,
                "price_impact": self.params.price_impact,
                "n_steps": self.params.n_steps,
                "herd_strength": self.params.herd_strength,
                "opinion_decay": self.params.opinion_decay,
                "chart_trend_weight": self.params.chart_trend_weight,
                "tick_size": self.params.tick_size,
                "transaction_cost": self.params.transaction_cost,
            },
            pre_data_hash=pre_data.content_hash(),
            seed=0,
            metadata={"target_vol": target_vol},
        )

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> LMAdapter:
        new_params = LMParams(
            n_fund=self.params.n_fund,
            n_chart=self.params.n_chart,
            n_steps=self.params.n_steps,
            fundamental_value=self.params.fundamental_value,
            fund_speed=self.params.fund_speed,
            herd_strength=self.params.herd_strength,
            opinion_decay=self.params.opinion_decay,
            chart_trend_weight=self.params.chart_trend_weight,
            chart_lookback=self.params.chart_lookback,
            noise_scale=self.params.noise_scale,
            price_impact=self.params.price_impact,
            tick_size=self.params.tick_size,
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

        return LMAdapter(params=new_params)

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
            model_id="lm_v0.1",
            metadata={
                "n_fund": self.params.n_fund,
                "n_chart": self.params.n_chart,
                "tick_size": self.params.tick_size,
                "herd_strength": self.params.herd_strength,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=8,
            structural_description=(
                "Herding-based heterogeneous agent model with endogenous "
                "opinion switching between fundamentalists and optimist/"
                "pessimist chartists (Lux & Marchesi 1999, 2000)"
            ),
            description_length=8.0,
        )

    def _simulate_one_path(self, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        p = self.params
        T = p.n_steps
        prices = np.full(T, p.fundamental_value)
        returns = np.zeros(T)

        n_total = p.n_fund + p.n_chart
        frac_fund = p.n_fund / n_total
        frac_chart = p.n_chart / n_total

        opinion = 0.0

        for t in range(1, T):
            # Fundamentalist demand: mean-revert toward fundamental
            mispricing = (p.fundamental_value - prices[t - 1]) / prices[t - 1]
            d_fund = p.fund_speed * mispricing * prices[t - 1]

            # Chartist opinion dynamics (herding)
            lag = min(p.chart_lookback, t)
            if lag > 0:
                trend = (prices[t - 1] - prices[max(0, t - 1 - lag)]) / (
                    lag * max(prices[t - 1], p.tick_size)
                )
            else:
                trend = 0.0

            opinion_pressure = p.herd_strength * opinion + p.chart_trend_weight * trend * 100
            opinion_noise = rng.normal(0, 0.5)
            opinion = (1 - p.opinion_decay) * opinion + p.opinion_decay * np.tanh(
                opinion_pressure + opinion_noise
            )

            d_chart = opinion * prices[t - 1] * 0.02

            # Noise
            d_noise = rng.normal(0, p.noise_scale * prices[t - 1])

            # Aggregate with transaction costs
            excess_demand = frac_fund * d_fund + frac_chart * d_chart + 0.1 * d_noise
            if p.transaction_cost > 0:
                cost_drag = p.transaction_cost * abs(excess_demand)
                excess_demand *= max(0.0, 1.0 - cost_drag / (abs(excess_demand) + 1e-10))

            dp = p.price_impact * excess_demand

            # Tick discretization
            if p.tick_size > 0:
                dp = round(dp / p.tick_size) * p.tick_size

            prices[t] = max(prices[t - 1] + dp, p.tick_size)
            returns[t] = (prices[t] - prices[t - 1]) / prices[t - 1]

        return returns
