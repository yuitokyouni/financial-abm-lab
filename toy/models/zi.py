"""Zero-Intelligence Constrained (ZI-C) adapter — Gode & Sunder (1993).

A null baseline model where agents submit random limit orders with no
learning, no strategy switching, and no information processing.  Prices
emerge purely from random order flow against a budget constraint.

This model serves as a structural falsification benchmark: any ABM that
fails to outperform ZI-C on intervention-response scoring provides no
value beyond random noise.  Interventions enter ONLY as exogenous
structural constraints (tick_size grid width); effects on return-
distribution facts must emerge from the simulation dynamics alone.
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
class ZIParams:
    """Parameters for the Zero-Intelligence Constrained model."""

    n_agents: int = 100
    n_steps: int = 1000
    fundamental_value: float = 100.0

    noise_scale: float = 0.01
    tick_size: float = 0.01
    price_impact: float = 0.01


@dataclass
class ZIAdapter:
    """ModelAdapter implementation for the ZI-C null model.

    Interventions are purely structural: only tick_size changes, and any
    effect on return-distribution facts emerges from the price
    discretization dynamics.  No parameter besides tick_size is modified
    by apply_intervention.
    """

    params: ZIParams = field(default_factory=ZIParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        self.params.noise_scale = target_vol
        self.params.price_impact = 0.5
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="zi_v0.2",
            calibrated_params={
                "noise_scale": self.params.noise_scale,
                "price_impact": self.params.price_impact,
                "n_steps": self.params.n_steps,
                "tick_size": self.params.tick_size,
            },
            pre_data_hash=pre_data.content_hash(),
            seed=0,
            metadata={"target_vol": target_vol},
        )

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> ZIAdapter:
        new_params = ZIParams(
            n_agents=self.params.n_agents,
            n_steps=self.params.n_steps,
            fundamental_value=self.params.fundamental_value,
            noise_scale=self.params.noise_scale,
            tick_size=self.params.tick_size,
            price_impact=self.params.price_impact,
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

        return ZIAdapter(params=new_params)

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
            model_id="zi_v0.2",
            metadata={
                "n_agents": self.params.n_agents,
                "tick_size": self.params.tick_size,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=3,
            structural_description=(
                "Zero-Intelligence Constrained model with random limit orders "
                "and no learning or strategy switching (Gode & Sunder 1993). "
                "Interventions enter only through tick_size grid width."
            ),
            description_length=3.0,
        )

    def _simulate_one_path(self, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        p = self.params
        T = p.n_steps
        prices = np.full(T, p.fundamental_value)
        returns = np.zeros(T)

        for t in range(1, T):
            n_buyers = rng.binomial(p.n_agents, 0.5)
            n_sellers = p.n_agents - n_buyers

            buy_prices = prices[t - 1] + rng.normal(
                0, p.noise_scale * prices[t - 1], size=max(1, n_buyers)
            )
            sell_prices = prices[t - 1] + rng.normal(
                0, p.noise_scale * prices[t - 1], size=max(1, n_sellers)
            )

            avg_buy = float(np.mean(buy_prices))
            avg_sell = float(np.mean(sell_prices))

            excess_demand = (n_buyers - n_sellers) / p.n_agents
            mid = (avg_buy + avg_sell) / 2.0
            new_price = mid + p.price_impact * excess_demand * prices[t - 1]

            if p.tick_size > 0:
                new_price = round(new_price / p.tick_size) * p.tick_size
            new_price = max(new_price, p.tick_size)

            prices[t] = new_price
            returns[t] = (prices[t] - prices[t - 1]) / prices[t - 1]

        return returns
