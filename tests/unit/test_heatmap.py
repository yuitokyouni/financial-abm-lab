"""Tests for heatmap visualization."""

import matplotlib
matplotlib.use("Agg")

import pytest
import matplotlib.pyplot as plt

from prism.pipeline import CellOutput, TensorOutput
from prism.scoring.eligibility import (
    EligibilityResult,
    EligibilityVerdict,
    FactEligibility,
)
from prism.scoring.mdl import WeightedMatchResult
from prism.types import MatchResult, MatchVerdict
from prism.viz.heatmap import render_heatmap


def _make_tensor() -> TensorOutput:
    """Build a minimal 2×2 tensor for testing."""
    cells = []
    for adapter_id in ["sg", "ci"]:
        for ner_id in ["ner_a", "ner_b"]:
            matches = [
                MatchResult(
                    fact_id="leverage_effect",
                    delta_model=-0.05,
                    delta_empirical=-0.03,
                    sign_match=MatchVerdict.MATCH,
                    magnitude_within_ci=True,
                    confidence=1.0,
                ),
                MatchResult(
                    fact_id="volatility_clustering",
                    delta_model=0.0,
                    delta_empirical=0.02,
                    sign_match=MatchVerdict.INCONCLUSIVE,
                    confidence=0.0,
                ),
            ]
            weighted = [
                WeightedMatchResult(
                    fact_id="leverage_effect",
                    delta_model=-0.05,
                    delta_empirical=-0.03,
                    sign_match=MatchVerdict.MATCH,
                    magnitude_within_ci=True,
                    confidence_raw=1.0,
                    mdl_weight=0.26,
                    causal_weight=0.9,
                    confidence_weighted=0.234,
                ),
                WeightedMatchResult(
                    fact_id="volatility_clustering",
                    delta_model=0.0,
                    delta_empirical=0.02,
                    sign_match=MatchVerdict.INCONCLUSIVE,
                    magnitude_within_ci=None,
                    confidence_raw=0.0,
                    mdl_weight=0.26,
                    causal_weight=0.9,
                    confidence_weighted=0.0,
                ),
            ]
            eligibility = EligibilityResult(
                model_id=adapter_id,
                verdict=EligibilityVerdict.ELIGIBLE,
                checks=[
                    FactEligibility(
                        fact_id="leverage_effect",
                        value=-0.1,
                        expected_range=(-0.5, 0.0),
                        in_range=True,
                    )
                ],
                n_pass=1,
                n_fail=0,
            )
            cells.append(
                CellOutput(
                    adapter_id=adapter_id,
                    ner_id=ner_id,
                    matches=matches,
                    provenance={"run_id": "test"},
                    weighted_matches=weighted,
                    eligibility=eligibility,
                )
            )

    return TensorOutput(
        cells=cells,
        adapter_ids=["sg", "ci"],
        ner_ids=["ner_a", "ner_b"],
        fact_ids=["leverage_effect", "volatility_clustering"],
    )


class TestRenderHeatmap:
    def test_returns_figure(self):
        tensor = _make_tensor()
        fig = render_heatmap(tensor)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_saves_to_file(self, tmp_path):
        tensor = _make_tensor()
        out = tmp_path / "test_heatmap.png"
        fig = render_heatmap(tensor, output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0
        plt.close(fig)

    def test_custom_figsize(self):
        tensor = _make_tensor()
        fig = render_heatmap(tensor, figsize=(10, 5))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10)
        assert h == pytest.approx(5)
        plt.close(fig)

    def test_single_ner(self):
        tensor = _make_tensor()
        tensor.ner_ids = ["ner_a"]
        tensor.cells = [c for c in tensor.cells if c.ner_id == "ner_a"]
        fig = render_heatmap(tensor)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_with_ineligible_adapter(self):
        tensor = _make_tensor()
        tensor.cells[0].eligibility = EligibilityResult(
            model_id="sg",
            verdict=EligibilityVerdict.INELIGIBLE,
            checks=[
                FactEligibility(
                    fact_id="leverage_effect",
                    value=0.5,
                    expected_range=(-0.5, 0.0),
                    in_range=False,
                )
            ],
            n_pass=0,
            n_fail=1,
        )
        fig = render_heatmap(tensor)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)
