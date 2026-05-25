"""Integration test for the end-to-end pipeline."""

import numpy as np

from prism.pipeline import run_cell
from prism.types import MatchVerdict


class TestEndToEnd:
    def test_single_cell_runs(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "sg"
        assert result.ner_id == "tspp_2016_us_equity"
        assert len(result.matches) == 3

    def test_reproducibility(self):
        r1 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "gain_loss_asymmetry"],
            seed=99,
            n_paths=5,
        )
        r2 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "gain_loss_asymmetry"],
            seed=99,
            n_paths=5,
        )
        for m1, m2 in zip(r1.matches, r2.matches):
            assert m1.delta_model == m2.delta_model
            assert m1.sign_match == m2.sign_match

    def test_provenance_present(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        prov = result.provenance
        assert "run_id" in prov
        assert "data_hashes" in prov
        assert "rng_seeds" in prov
        assert prov["rng_seeds"]["simulation"] == 42
        assert "sim_pre" in prov["data_hashes"]
        assert "sim_post" in prov["data_hashes"]

    def test_to_dict(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["adapter_id"] == "sg"
        assert len(d["matches"]) == 1
        assert d["matches"][0]["sign_match"] in ["match", "mismatch", "inconclusive"]

    def test_different_seeds_different_results(self):
        r1 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=1,
            n_paths=5,
        )
        r2 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=2,
            n_paths=5,
        )
        assert r1.matches[0].delta_model != r2.matches[0].delta_model
