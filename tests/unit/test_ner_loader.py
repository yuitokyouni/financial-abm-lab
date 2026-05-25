"""Tests for NER loader."""

from pathlib import Path

import pytest

from prism.data import load_ner
from prism.types import NaturalExperimentRecord


JPX_PATH = Path("data/ner/jpx_2014_jp_tick.yaml")

FTT_PATH = Path("data/ner/french_ftt_2012_eu.yaml")

# These NERs still contain external_claim references and must raise ValueError.
INVALID_NER_PATHS = [
    Path("data/ner/tspp_2016_us_equity.yaml"),
    Path("data/ner/mifid2_2018_eu_tick.yaml"),
]


class TestLoadJpxNer:
    def test_loads_successfully(self):
        ner = load_ner(JPX_PATH)
        assert isinstance(ner, NaturalExperimentRecord)

    def test_ner_id(self):
        ner = load_ner(JPX_PATH)
        assert ner.ner_id == "jpx_2014_jp_tick"

    def test_intervention_class(self):
        ner = load_ner(JPX_PATH)
        assert ner.intervention.intervention_class == "tick_size_decrease"

    def test_canonical_params(self):
        ner = load_ner(JPX_PATH)
        assert ner.intervention.canonical_params["min_tick_from"] == 1.0
        assert ner.intervention.canonical_params["min_tick_to"] == 0.1

    def test_ground_truth_count(self):
        ner = load_ner(JPX_PATH)
        assert len(ner.ground_truth_deltas) == 6

    def test_ground_truth_fact_ids(self):
        ner = load_ner(JPX_PATH)
        ids = {gt.fact_id for gt in ner.ground_truth_deltas}
        assert ids == {
            "volatility_clustering",
            "leverage_effect",
            "gain_loss_asymmetry",
            "fat_tails",
            "abs_autocorrelation",
            "squared_return_acf",
        }

    def test_assignment(self):
        ner = load_ner(JPX_PATH)
        assert ner.assignment == "regulatory_cutoff"

    def test_venue(self):
        ner = load_ner(JPX_PATH)
        assert ner.venue == "JP_equity_largecap"

    def test_date_effective(self):
        ner = load_ner(JPX_PATH)
        assert ner.date_effective == "2014-01-14"

    def test_empirically_derived_deltas_have_ci(self):
        ner = load_ner(JPX_PATH)
        for d in ner.ground_truth_deltas:
            assert d.ci95 is not None
            assert d.ci95[0] <= d.ci95[1]
            assert "empirical_prism_estimator" in d.references[0]


class TestLoadFttNer:
    def test_loads_successfully(self):
        ner = load_ner(FTT_PATH)
        assert isinstance(ner, NaturalExperimentRecord)
        assert ner.ner_id == "french_ftt_2012_eu"

    def test_intervention_class(self):
        ner = load_ner(FTT_PATH)
        assert ner.intervention.intervention_class == "transaction_tax"

    def test_ground_truth_count(self):
        ner = load_ner(FTT_PATH)
        assert len(ner.ground_truth_deltas) == 6

    def test_empirically_derived_deltas_have_ci(self):
        ner = load_ner(FTT_PATH)
        for d in ner.ground_truth_deltas:
            assert d.ci95 is not None
            assert d.ci95[0] <= d.ci95[1]
            assert "empirical_prism_estimator" in d.references[0]

    def test_significant_facts_have_nonzero_ci(self):
        ner = load_ner(FTT_PATH)
        sig_facts = {"leverage_effect", "squared_return_acf"}
        for d in ner.ground_truth_deltas:
            if d.fact_id in sig_facts:
                assert not (d.ci95[0] <= 0 <= d.ci95[1]), (
                    f"{d.fact_id} CI95 should not cross zero"
                )


class TestInvalidNersRejected:
    """NERs marked with external_claim references must be rejected at load time."""

    @pytest.mark.parametrize("path", INVALID_NER_PATHS)
    def test_external_claim_raises(self, path):
        with pytest.raises(ValueError, match="external_claim"):
            load_ner(path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_ner("nonexistent.yaml")
