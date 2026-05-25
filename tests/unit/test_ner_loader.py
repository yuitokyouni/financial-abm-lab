"""Tests for NER loader."""

from pathlib import Path

import pytest

from prism.data import load_ner
from prism.types import NaturalExperimentRecord


NER_PATH = Path("data/ner/tspp_2016_us_equity.yaml")
FTT_PATH = Path("data/ner/french_ftt_2012_eu.yaml")


class TestLoadNer:
    def test_loads_successfully(self):
        ner = load_ner(NER_PATH)
        assert isinstance(ner, NaturalExperimentRecord)

    def test_ner_id(self):
        ner = load_ner(NER_PATH)
        assert ner.ner_id == "tspp_2016_us_equity"

    def test_intervention_class(self):
        ner = load_ner(NER_PATH)
        assert ner.intervention.intervention_class == "tick_size_increase"

    def test_canonical_params(self):
        ner = load_ner(NER_PATH)
        assert ner.intervention.canonical_params["min_tick_to"] == 0.05

    def test_ground_truth_count(self):
        ner = load_ner(NER_PATH)
        assert len(ner.ground_truth_deltas) == 6

    def test_ground_truth_fact_ids(self):
        ner = load_ner(NER_PATH)
        ids = {gt.fact_id for gt in ner.ground_truth_deltas}
        assert ids == {"volatility_clustering", "leverage_effect", "gain_loss_asymmetry", "fat_tails", "abs_autocorrelation", "squared_return_acf"}

    def test_ci95_parsed(self):
        ner = load_ner(NER_PATH)
        for gt in ner.ground_truth_deltas:
            assert gt.ci95 is not None
            lo, hi = gt.ci95
            assert lo < hi

    def test_assignment(self):
        ner = load_ner(NER_PATH)
        assert ner.assignment == "randomized"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_ner("nonexistent.yaml")


class TestLoadFttNer:
    def test_loads_successfully(self):
        ner = load_ner(FTT_PATH)
        assert isinstance(ner, NaturalExperimentRecord)

    def test_ner_id(self):
        ner = load_ner(FTT_PATH)
        assert ner.ner_id == "french_ftt_2012_eu"

    def test_intervention_class(self):
        ner = load_ner(FTT_PATH)
        assert ner.intervention.intervention_class == "transaction_tax"

    def test_canonical_params(self):
        ner = load_ner(FTT_PATH)
        assert ner.intervention.canonical_params["rate"] == 0.002

    def test_ground_truth_count(self):
        ner = load_ner(FTT_PATH)
        assert len(ner.ground_truth_deltas) == 6

    def test_ground_truth_fact_ids(self):
        ner = load_ner(FTT_PATH)
        ids = {gt.fact_id for gt in ner.ground_truth_deltas}
        assert ids == {"volatility_clustering", "leverage_effect", "gain_loss_asymmetry", "fat_tails", "abs_autocorrelation", "squared_return_acf"}

    def test_assignment(self):
        ner = load_ner(FTT_PATH)
        assert ner.assignment == "regulatory_cutoff"
