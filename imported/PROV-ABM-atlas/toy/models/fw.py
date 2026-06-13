"""Franke-Westerhoff (FW) adapter — structural stochastic model.

Based on Franke & Westerhoff (2012).  Two agent populations —
fundamentalists and chartists — with endogenous sentiment-driven
switching via transition probabilities.  The key mechanism is a
non-linear feedback between past price movements and the fraction
of chartists, producing volatility clustering, leverage, and fat tails.

The tick_size interventions affect the price discretization grid,
altering the resolution of trend signals available to chartists.
The transaction_tax intervention dampens speculative chartist demand
by increasing round-trip costs.
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
class FWParams:
    """Parameters for the Franke-Westerhoff model."""

    n_steps: int = 1000
    fundamental_value: float = 100.0

    # Fundamentalist
    phi: float = 0.12

    # Chartist
    chi: float = 1.5

    # Transition probabilities
    alpha_w: float = 1.8
    alpha_o: float = 0.05
    alpha_p: float = 0.2

    # Noise / market
    sigma_f: float = 0.01
    sigma_c: float = 0.02
    noise_scale: float = 0.01
    price_impact: float = 0.5
    tick_size: float = 0.01
    transaction_cost: float = 0.0


@dataclass
class FWAdapter:
    """ModelAdapter implementation for the Franke-Westerhoff model."""

    params: FWParams = field(default_factory=FWParams)

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact:
        target_vol = float(np.std(pre_data.returns))

        self.params.noise_scale = target_vol
        self.params.price_impact = 0.6
        self.params.n_steps = pre_data.n_days

        return CalibrationArtifact(
            model_id="fw_v0.1",
            calibrated_params={
                "noise_scale": self.params.noise_scale,
                "price_impact": self.params.price_impact,
                "n_steps": self.params.n_steps,
                "phi": self.params.phi,
                "chi": self.params.chi,
                "alpha_w": self.params.alpha_w,
                "tick_size": self.params.tick_size,
                "transaction_cost": self.params.transaction_cost,
            },
            pre_data_hash=pre_data.content_hash(),
            seed=0,
            metadata={"target_vol": target_vol},
        )

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> FWAdapter:
        new_params = FWParams(
            n_steps=self.params.n_steps,
            fundamental_value=self.params.fundamental_value,
            phi=self.params.phi,
            chi=self.params.chi,
            alpha_w=self.params.alpha_w,
            alpha_o=self.params.alpha_o,
            alpha_p=self.params.alpha_p,
            sigma_f=self.params.sigma_f,
            sigma_c=self.params.sigma_c,
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

        return FWAdapter(params=new_params)

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
            model_id="fw_v0.1",
            metadata={
                "phi": self.params.phi,
                "chi": self.params.chi,
                "alpha_w": self.params.alpha_w,
                "tick_size": self.params.tick_size,
            },
        )

    def describe_complexity(self) -> ComplexitySpec:
        return ComplexitySpec(
            n_free_params=6,
            structural_description=(
                "Structural stochastic model with sentiment-driven "
                "fundamentalist/chartist switching via transition probabilities "
                "(Franke & Westerhoff 2012)"
            ),
            description_length=6.0,
        )

    def _simulate_one_path(self, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        p = self.params
        T = p.n_steps
        prices = np.full(T, p.fundamental_value)
        returns = np.zeros(T)

        n_c = 0.5

        for t in range(1, T):
            n_f = 1.0 - n_c

            mispricing = (p.fundamental_value - prices[t - 1]) / prices[t - 1]
            d_fund = p.phi * mispricing * prices[t - 1]
            d_fund += rng.normal(0, p.sigma_f * prices[t - 1])

            if t > 1:
                past_return = returns[t - 1]
            else:
                past_return = 0.0
            d_chart = p.chi * past_return * prices[t - 1]
            d_chart += rng.normal(0, p.sigma_c * prices[t - 1])

            d_noise = rng.normal(0, p.noise_scale * prices[t - 1])

            excess_demand = n_f * d_fund + n_c * d_chart + 0.1 * d_noise

            if p.transaction_cost > 0:
                cost_drag = p.transaction_cost * abs(excess_demand)
                excess_demand *= max(0.0, 1.0 - cost_drag / (abs(excess_demand) + 1e-10))

            dp = p.price_impact * excess_demand

            if p.tick_size > 0:
                dp = round(dp / p.tick_size) * p.tick_size

            prices[t] = max(prices[t - 1] + dp, p.tick_size)
            returns[t] = (prices[t] - prices[t - 1]) / prices[t - 1]

            abs_mispr = abs(mispricing)
            p_to_chart = p.alpha_o + p.alpha_p * abs(returns[t]) * 100
            p_to_fund = p.alpha_o + p.alpha_w * abs_mispr

            p_to_chart = min(p_to_chart, 0.95)
            p_to_fund = min(p_to_fund, 0.95)

            switch_to_c = n_f * p_to_chart
            switch_to_f = n_c * p_to_fund

            n_c = n_c + switch_to_c - switch_to_f
            n_c = max(0.05, min(0.95, n_c))

        return returns
