"""Tests for LaTeX-compatible figure and table generation."""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from prism.pipeline import CellOutput, TensorOutput
from prism.scoring.eligibility import (
    EligibilityResult,
    EligibilityVerdict,
    FactEligibility,
)
from prism.scoring.mdl import WeightedMatchResult
from prism.types import MatchResult, MatchVerdict
from prism.viz.latex import export_latex_table, render_latex_heatmap


def _make_tensor() -> TensorOutput:
    cells = []
    for adapter_id in ["sg", "ci", "lm"]:
        for ner_id in ["tspp_2016_us_equity", "french_ftt_2012_eu"]:
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
                    delta_model=0.01,
                    delta_empirical=0.02,
                    sign_match=MatchVerdict.MATCH,
                    confidence=0.8,
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
                    delta_model=0.01,
                    delta_empirical=0.02,
                    sign_match=MatchVerdict.MATCH,
                    magnitude_within_ci=None,
                    confidence_raw=0.8,
                    mdl_weight=0.26,
                    causal_weight=0.9,
                    confidence_weighted=0.187,
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
        adapter_ids=["sg", "ci", "lm"],
        ner_ids=["tspp_2016_us_equity", "french_ftt_2012_eu"],
        fact_ids=["leverage_effect", "volatility_clustering"],
    )


class TestRenderLatexHeatmap:
    def test_returns_figure(self):
        tensor = _make_tensor()
        fig = render_latex_heatmap(tensor, use_latex=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_saves_pdf(self, tmp_path):
        tensor = _make_tensor()
        out = tmp_path / "test_heatmap.pdf"
        fig = render_latex_heatmap(tensor, output_path=out, use_latex=False)
        assert out.exists()
        assert out.stat().st_size > 0
        plt.close(fig)

    def test_saves_png(self, tmp_path):
        tensor = _make_tensor()
        out = tmp_path / "test_heatmap.png"
        fig = render_latex_heatmap(tensor, output_path=out, use_latex=False)
        assert out.exists()
        plt.close(fig)

    def test_custom_figsize(self):
        tensor = _make_tensor()
        fig = render_latex_heatmap(tensor, figsize=(12, 4), use_latex=False)
        w, h = fig.get_size_inches()
        assert w == pytest.approx(12)
        assert h == pytest.approx(4)
        plt.close(fig)

    def test_with_ineligible(self):
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
        fig = render_latex_heatmap(tensor, use_latex=False)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestExportLatexTable:
    def test_returns_string(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert isinstance(result, str)

    def test_contains_tabular(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert r"\begin{tabular}" in result
        assert r"\end{tabular}" in result

    def test_contains_table_env(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert r"\begin{table}" in result
        assert r"\end{table}" in result

    def test_contains_adapters(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert "SG" in result
        assert "CI" in result
        assert "LM" in result

    def test_contains_ner_labels(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert "TSPP 2016" in result
        assert "FTT 2012" in result

    def test_contains_verdict_symbols(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert r"\checkmark" in result

    def test_saves_to_file(self, tmp_path):
        tensor = _make_tensor()
        out = tmp_path / "table.tex"
        export_latex_table(tensor, output_path=out)
        assert out.exists()
        content = out.read_text()
        assert r"\begin{table}" in content

    def test_with_ineligible_gray(self):
        tensor = _make_tensor()
        tensor.cells[0].eligibility = EligibilityResult(
            model_id="sg",
            verdict=EligibilityVerdict.INELIGIBLE,
            checks=[],
            n_pass=0,
            n_fail=1,
        )
        result = export_latex_table(tensor)
        assert r"\textcolor{gray}" in result

    def test_confidence_values(self):
        tensor = _make_tensor()
        result = export_latex_table(tensor)
        assert "0.23" in result
