"""Zero-Intelligence Constrained (ZI-C) adapter — Gode & Sunder (1993).

A null baseline model where agents submit random limit orders with no
learning, no strategy switching, and no information processing.  Prices
emerge purely from random order flow against a budget constraint.

This model serves as a structural falsification benchmark: any ABM that
fails to outperform ZI-C on intervention-response scoring provides no
value beyond random noise.  ZI-C is expected to:
  - Fail the eligibility gate (no volatility clustering, no leverage)
  - Produce INCONCLUSIVE or MISMATCH verdicts on intervention response
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from prism.types import (
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
    bid_ask_spread: float = 0.005


@dataclass
class ZIAdapter:
    """ModelAdapter implementation for the ZI-C null model."""

    params: ZIParams = field(default_factory=ZIParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        self.params.noise_scale = target_vol
        self.params.price_impact = 0.5
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="zi_v0.1",
            calibrated_params={
                "noise_scale": self.params.noise_scale,
                "price_impact": self.params.price_impact,
                "n_steps": self.params.n_steps,
                "tick_size": self.params.tick_size,
                "bid_ask_spread": self.params.bid_ask_spread,
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
            bid_ask_spread=self.params.bid_ask_spread,
        )

        if intervention.intervention_class == "tick_size_increase":
            new_tick = intervention.canonical_params.get("min_tick_to", 0.05)
            new_params.tick_size = new_tick
            tick_ratio = new_tick / self.params.tick_size
            new_params.bid_ask_spread *= tick_ratio
        elif intervention.intervention_class == "transaction_tax":
            tax_rate = intervention.canonical_params.get("rate", 0.001)
            new_params.bid_ask_spread *= (1 + tax_rate * 5)
        else:
            raise ValueError(
                f"Unknown intervention class: {intervention.intervention_class}"
            )

        return ZIAdapter(params=new_params)

    def simulate(self, seed: int, n_paths: int) -> SimulatedMarketData:
        rng = np.random.default_rng(seed)
        all_returns = []

        for _ in range(n_paths):
            returns = self._simulate_one_path(rng)
            all_returns.append(returns)

        avg_returns = np.mean(all_returns, axis=0)

        return SimulatedMarketData(
            returns=avg_returns,
            seed=seed,
            n_paths=n_paths,
            model_id="zi_v0.1",
            metadata={
                "n_agents": self.params.n_agents,
                "tick_size": self.params.tick_size,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=4,
            structural_description=(
                "Zero-Intelligence Constrained model with random limit orders "
                "and no learning or strategy switching (Gode & Sunder 1993)"
            ),
            description_length=4.0,
        )

    def _simulate_one_path(
        self, rng: np.random.Generator
    ) -> npt.NDArray[np.float64]:
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
