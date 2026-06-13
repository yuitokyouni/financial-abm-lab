"""Unit tests for pipeline module — CellOutput, TensorOutput, run_cell logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from prism.pipeline import (
    ADAPTER_REGISTRY,
    CellOutput,
    MethodComparisonOutput,
    MethodComparisonRow,
    TensorOutput,
    _compute_per_path_facts,
    compare_causal_methods,
    run_cell,
    run_tensor,
)
from prism.scoring.eligibility import (
    EligibilityResult,
    EligibilityVerdict,
    FactEligibility,
)
from prism.scoring.mdl import WeightedMatchResult
from prism.types import (
    CalibrationArtifact,
    CanonicalIntervention,
    ComplexitySpec,
    GroundTruthDelta,
    MarketData,
    MatchResult,
    MatchVerdict,
    NaturalExperimentRecord,
    SimulatedMarketData,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_match(
    fact_id: str = "leverage_effect",
    delta_model: float = -0.05,
    delta_empirical: float = -0.04,
    sign_match: MatchVerdict = MatchVerdict.MATCH,
    magnitude_within_ci: bool | None = True,
    confidence: float = 1.0,
) -> MatchResult:
    return MatchResult(
        fact_id=fact_id,
        delta_model=delta_model,
        delta_empirical=delta_empirical,
        sign_match=sign_match,
        magnitude_within_ci=magnitude_within_ci,
        confidence=confidence,
    )


def _make_weighted(
    fact_id: str = "leverage_effect",
    sign_match: MatchVerdict = MatchVerdict.MATCH,
    magnitude_within_ci: bool | None = True,
    confidence_raw: float = 1.0,
    mdl_weight: float = 0.3,
    causal_weight: float = 0.9,
) -> WeightedMatchResult:
    return WeightedMatchResult(
        fact_id=fact_id,
        delta_model=-0.05,
        delta_empirical=-0.04,
        sign_match=sign_match,
        magnitude_within_ci=magnitude_within_ci,
        confidence_raw=confidence_raw,
        mdl_weight=mdl_weight,
        causal_weight=causal_weight,
        confidence_weighted=confidence_raw * mdl_weight * causal_weight,
    )


def _make_eligibility(
    verdict: EligibilityVerdict = EligibilityVerdict.ELIGIBLE,
) -> EligibilityResult:
    checks = [
        FactEligibility(
            fact_id="volatility_clustering",
            value=0.85,
            expected_range=(0.5, 0.999),
            in_range=True,
        ),
        FactEligibility(
            fact_id="leverage_effect",
            value=-0.2,
            expected_range=(-0.5, 0.0),
            in_range=True,
        ),
    ]
    return EligibilityResult(model_id="test", verdict=verdict, checks=checks, n_pass=2, n_fail=0)


def _make_cell(
    adapter_id: str = "sg",
    ner_id: str = "tspp_2016_us_equity",
    with_weighted: bool = True,
    with_eligibility: bool = True,
) -> CellOutput:
    matches = [
        _make_match("leverage_effect", sign_match=MatchVerdict.MATCH),
        _make_match(
            "volatility_clustering",
            delta_model=0.1,
            delta_empirical=0.08,
            sign_match=MatchVerdict.MATCH,
            magnitude_within_ci=False,
            confidence=0.5,
        ),
        _make_match(
            "gain_loss_asymmetry",
            delta_model=0.01,
            delta_empirical=-0.03,
            sign_match=MatchVerdict.MISMATCH,
            magnitude_within_ci=None,
            confidence=0.0,
        ),
    ]
    weighted = (
        [
            _make_weighted("leverage_effect"),
            _make_weighted(
                "volatility_clustering",
                magnitude_within_ci=False,
                confidence_raw=0.5,
            ),
            _make_weighted(
                "gain_loss_asymmetry",
                sign_match=MatchVerdict.MISMATCH,
                magnitude_within_ci=None,
                confidence_raw=0.0,
            ),
        ]
        if with_weighted
        else []
    )
    eligibility = _make_eligibility() if with_eligibility else None

    return CellOutput(
        adapter_id=adapter_id,
        ner_id=ner_id,
        matches=matches,
        provenance={"run_id": "test-run-001", "parameters": {}},
        weighted_matches=weighted,
        eligibility=eligibility,
    )


# ---------------------------------------------------------------------------
# CellOutput tests
# ---------------------------------------------------------------------------


class TestCellOutputSummary:
    def test_summary_contains_adapter_and_ner(self):
        cell = _make_cell()
        s = cell.summary()
        assert "sg" in s
        assert "tspp_2016_us_equity" in s
        assert "PRISM Cell" in s

    def test_summary_shows_eligibility(self):
        cell = _make_cell(with_eligibility=True)
        s = cell.summary()
        assert "Eligibility: eligible" in s
        assert "PASS" in s

    def test_summary_without_eligibility(self):
        cell = _make_cell(with_eligibility=False)
        s = cell.summary()
        assert "Eligibility" not in s

    def test_summary_shows_weighted_matches(self):
        cell = _make_cell(with_weighted=True)
        s = cell.summary()
        assert "mdl_w=" in s
        assert "conf_weighted=" in s

    def test_summary_shows_unweighted_matches(self):
        cell = _make_cell(with_weighted=False)
        s = cell.summary()
        assert "confidence=" in s
        assert "mdl_w=" not in s

    def test_summary_sign_consistency(self):
        cell = _make_cell()
        s = cell.summary()
        assert "Sign consistency: 2/3" in s

    def test_summary_run_id(self):
        cell = _make_cell()
        s = cell.summary()
        assert "test-run-001" in s

    def test_summary_magnitude_rendering(self):
        cell = _make_cell(with_weighted=True)
        s = cell.summary()
        assert "yes" in s
        assert "no" in s
        assert "n/a" in s

    def test_summary_ineligible(self):
        cell = _make_cell()
        cell.eligibility = _make_eligibility(EligibilityVerdict.INELIGIBLE)
        s = cell.summary()
        assert "ineligible" in s


class TestCellOutputToDict:
    def test_basic_fields(self):
        cell = _make_cell()
        d = cell.to_dict()
        assert d["adapter_id"] == "sg"
        assert d["ner_id"] == "tspp_2016_us_equity"
        assert len(d["matches"]) == 3

    def test_match_structure(self):
        cell = _make_cell()
        d = cell.to_dict()
        m = d["matches"][0]
        assert "fact_id" in m
        assert "delta_model" in m
        assert "sign_match" in m
        assert m["sign_match"] in ("match", "mismatch", "inconclusive")

    def test_weighted_matches_present(self):
        cell = _make_cell(with_weighted=True)
        d = cell.to_dict()
        assert "weighted_matches" in d
        assert len(d["weighted_matches"]) == 3
        wm = d["weighted_matches"][0]
        assert "mdl_weight" in wm
        assert "confidence_weighted" in wm

    def test_no_weighted_matches(self):
        cell = _make_cell(with_weighted=False)
        d = cell.to_dict()
        assert "weighted_matches" not in d

    def test_eligibility_present(self):
        cell = _make_cell(with_eligibility=True)
        d = cell.to_dict()
        assert "eligibility" in d
        assert d["eligibility"]["verdict"] == "eligible"
        assert d["eligibility"]["n_pass"] == 2
        assert len(d["eligibility"]["checks"]) == 2

    def test_no_eligibility(self):
        cell = _make_cell(with_eligibility=False)
        d = cell.to_dict()
        assert "eligibility" not in d


# ---------------------------------------------------------------------------
# TensorOutput tests
# ---------------------------------------------------------------------------


class TestTensorOutputSummary:
    def test_summary_header(self):
        tensor = TensorOutput(
            cells=[_make_cell("sg"), _make_cell("ci", ner_id="french_ftt_2012_eu")],
            adapter_ids=["sg", "ci"],
            ner_ids=["tspp_2016_us_equity", "french_ftt_2012_eu"],
            fact_ids=["leverage_effect", "volatility_clustering"],
        )
        s = tensor.summary()
        assert "PRISM Phase-Diagram Tensor" in s
        assert "Divergence Analysis" in s

    def test_summary_shows_ineligible(self):
        cell = _make_cell("zi")
        cell.eligibility = _make_eligibility(EligibilityVerdict.INELIGIBLE)
        tensor = TensorOutput(
            cells=[cell],
            adapter_ids=["zi"],
            ner_ids=["tspp_2016_us_equity"],
            fact_ids=["leverage_effect"],
        )
        s = tensor.summary()
        assert "Ineligible" in s
        assert "zi" in s

    def test_summary_divergence_detected(self):
        cell_a = _make_cell("sg")
        cell_b = _make_cell("ci")
        cell_b.matches = [
            _make_match("leverage_effect", sign_match=MatchVerdict.MISMATCH),
            _make_match("volatility_clustering", sign_match=MatchVerdict.MATCH),
            _make_match("gain_loss_asymmetry", sign_match=MatchVerdict.MATCH),
        ]
        tensor = TensorOutput(
            cells=[cell_a, cell_b],
            adapter_ids=["sg", "ci"],
            ner_ids=["tspp_2016_us_equity"],
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
        )
        s = tensor.summary()
        assert "DIVERGENCE" in s


class TestTensorOutputToDict:
    def test_structure(self):
        tensor = TensorOutput(
            cells=[_make_cell()],
            adapter_ids=["sg"],
            ner_ids=["tspp_2016_us_equity"],
            fact_ids=["leverage_effect"],
        )
        d = tensor.to_dict()
        assert "adapter_ids" in d
        assert "ner_ids" in d
        assert "fact_ids" in d
        assert "cells" in d
        assert len(d["cells"]) == 1


# ---------------------------------------------------------------------------
# MethodComparisonOutput tests
# ---------------------------------------------------------------------------


class TestMethodComparisonOutput:
    def test_summary(self):
        rows = [
            MethodComparisonRow("rct", 1.0, "leverage_effect", 0.8, 0.3, 0.24),
            MethodComparisonRow("ols", 0.5, "leverage_effect", 0.8, 0.3, 0.12),
        ]
        mco = MethodComparisonOutput(
            adapter_id="sg",
            ner_id="test_ner",
            methods=["rct", "ols"],
            rows=rows,
        )
        s = mco.summary()
        assert "Causal Method Comparison" in s
        assert "rct" in s
        assert "ols" in s

    def test_to_dict(self):
        rows = [
            MethodComparisonRow("rct", 1.0, "leverage_effect", 0.8, 0.3, 0.24),
        ]
        mco = MethodComparisonOutput(
            adapter_id="sg",
            ner_id="test_ner",
            methods=["rct"],
            rows=rows,
        )
        d = mco.to_dict()
        assert d["adapter_id"] == "sg"
        assert d["ner_id"] == "test_ner"
        assert d["methods"] == ["rct"]
        assert len(d["rows"]) == 1
        assert d["rows"][0]["causal_method"] == "rct"
        assert d["rows"][0]["causal_weight"] == 1.0


# ---------------------------------------------------------------------------
# run_cell tests (mocked adapters)
# ---------------------------------------------------------------------------


def _make_mock_adapter():
    adapter = MagicMock()
    adapter.calibrate_baseline.return_value = CalibrationArtifact(
        model_id="mock",
        calibrated_params={},
        pre_data_hash="abc123",
        seed=42,
    )
    adapter.apply_intervention.return_value = adapter
    adapter.simulate.return_value = SimulatedMarketData(
        returns=np.random.default_rng(42).normal(0, 0.02, (500, 1)),
        seed=42,
        n_paths=1,
        model_id="mock",
    )
    adapter.describe_complexity.return_value = ComplexitySpec(
        n_free_params=5,
        structural_description="mock model",
    )
    return adapter


def _make_mock_ner():
    return NaturalExperimentRecord(
        ner_id="test_ner",
        intervention=CanonicalIntervention(
            intervention_class="tick_size_increase",
            canonical_params={"factor": 5.0},
        ),
        ground_truth_deltas=[
            GroundTruthDelta(
                fact_id="leverage_effect",
                delta_hat=-0.05,
                ci95=(-0.1, 0.0),
                causal_method="did_firm_fe",
            ),
        ],
        venue="US_equity",
        date_effective="2016-10-03",
    )


class TestRunCellUnit:
    def test_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            run_cell(
                adapter_name="nonexistent",
                ner_path="data/ner/jpx_2014_jp_tick.yaml",
                fact_ids=["leverage_effect"],
            )

    @patch("prism.pipeline.load_ner")
    @patch.dict(ADAPTER_REGISTRY, {"mock": MagicMock})
    def test_run_cell_with_mock(self, mock_load_ner: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        adapter = _make_mock_adapter()
        ADAPTER_REGISTRY["mock"] = lambda: adapter

        result = run_cell(
            adapter_name="mock",
            ner_path="fake_path.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        assert result.adapter_id == "mock"
        assert result.ner_id == "test_ner"
        assert len(result.matches) == 1
        assert result.eligibility is not None
        assert result.provenance["rng_seeds"]["simulation"] == 42

    @patch("prism.pipeline.load_ner")
    @patch.dict(ADAPTER_REGISTRY, {"mock": MagicMock})
    def test_run_cell_per_path(self, mock_load_ner: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        adapter = _make_mock_adapter()
        ADAPTER_REGISTRY["mock"] = lambda: adapter

        result = run_cell(
            adapter_name="mock",
            ner_path="fake_path.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
            per_path_facts=True,
        )
        assert result.adapter_id == "mock"
        assert result.provenance["parameters"]["per_path_facts"] is True

    @patch("prism.pipeline.load_ner")
    @patch.dict(ADAPTER_REGISTRY, {"mock": MagicMock})
    def test_run_cell_with_pre_data(self, mock_load_ner: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        adapter = _make_mock_adapter()
        ADAPTER_REGISTRY["mock"] = lambda: adapter

        pre = MarketData(returns=np.random.default_rng(0).normal(0, 0.02, (500, 1)))
        result = run_cell(
            adapter_name="mock",
            ner_path="fake_path.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
            pre_data=pre,
        )
        assert result.provenance["parameters"]["pre_data_source"] == "real"


# ---------------------------------------------------------------------------
# _compute_per_path_facts tests
# ---------------------------------------------------------------------------


class TestComputePerPathFacts:
    def test_basic(self):
        adapter = _make_mock_adapter()
        facts, sim = _compute_per_path_facts(
            adapter,
            ["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        assert "leverage_effect" in facts
        assert facts["leverage_effect"].metadata.get("aggregation") == "per_path_median"
        assert facts["leverage_effect"].metadata.get("n_paths") == 3
        assert sim is not None

    def test_all_nan_path(self):
        adapter = MagicMock()
        nan_returns = np.full((500, 1), np.nan)
        adapter.simulate.return_value = SimulatedMarketData(
            returns=nan_returns,
            seed=42,
            n_paths=1,
            model_id="nan_mock",
        )
        facts, _ = _compute_per_path_facts(adapter, ["leverage_effect"], seed=0, n_paths=2)
        assert "leverage_effect" in facts


# ---------------------------------------------------------------------------
# run_tensor unit tests
# ---------------------------------------------------------------------------


class TestRunTensorUnit:
    @patch("prism.pipeline.run_cell")
    @patch("prism.pipeline.load_ner")
    def test_run_tensor_calls_run_cell(self, mock_load_ner: MagicMock, mock_run_cell: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        mock_run_cell.return_value = _make_cell()

        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["ner1.yaml", "ner2.yaml"],
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        assert len(result.cells) == 4
        assert mock_run_cell.call_count == 4


# ---------------------------------------------------------------------------
# compare_causal_methods unit tests
# ---------------------------------------------------------------------------


class TestCompareCausalMethodsUnit:
    @patch("prism.pipeline.run_cell")
    @patch("prism.pipeline.load_ner")
    def test_compare_returns_all_methods(self, mock_load_ner: MagicMock, mock_run_cell: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        cell = _make_cell()
        cell.matches = [_make_match("leverage_effect")]
        mock_run_cell.return_value = cell

        result = compare_causal_methods(
            adapter_name="sg",
            ner_path="fake.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        assert len(result.methods) == 6
        assert len(result.rows) == 6

    @patch("prism.pipeline.run_cell")
    @patch("prism.pipeline.load_ner")
    def test_compare_specific_methods(self, mock_load_ner: MagicMock, mock_run_cell: MagicMock):
        mock_load_ner.return_value = _make_mock_ner()
        cell = _make_cell()
        cell.matches = [_make_match("leverage_effect")]
        mock_run_cell.return_value = cell

        result = compare_causal_methods(
            adapter_name="sg",
            ner_path="fake.yaml",
            fact_ids=["leverage_effect"],
            methods=["rct", "ols"],
            seed=42,
            n_paths=3,
        )
        assert result.methods == ["rct", "ols"]
        assert len(result.rows) == 2


# ---------------------------------------------------------------------------
# ADAPTER_REGISTRY tests
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_all_adapters_present(self):
        assert set(ADAPTER_REGISTRY.keys()) == {"sg", "ci", "zi", "lm", "fw"}

    def test_all_adapters_instantiate(self):
        for name, cls in ADAPTER_REGISTRY.items():
            adapter = cls()
            assert hasattr(adapter, "calibrate_baseline")
            assert hasattr(adapter, "simulate")
            assert hasattr(adapter, "describe_complexity")
