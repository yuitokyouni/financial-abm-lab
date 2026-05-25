"""Integration test for the end-to-end pipeline."""

import numpy as np

from prism.pipeline import run_cell, run_tensor
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


class TestCIEndToEnd:
    def test_ci_tick_size_cell(self):
        result = run_cell(
            adapter_name="ci",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "ci"
        assert result.ner_id == "tspp_2016_us_equity"
        assert len(result.matches) == 3

    def test_ci_transaction_tax_cell(self):
        result = run_cell(
            adapter_name="ci",
            ner_path="data/ner/french_ftt_2012_eu.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "ci"
        assert result.ner_id == "french_ftt_2012_eu"
        assert len(result.matches) == 3

    def test_sg_transaction_tax_cell(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/french_ftt_2012_eu.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "sg"
        assert result.ner_id == "french_ftt_2012_eu"
        assert len(result.matches) == 3


class TestTensorPipeline:
    def test_2x2_tensor_runs(self):
        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=[
                "data/ner/tspp_2016_us_equity.yaml",
                "data/ner/french_ftt_2012_eu.yaml",
            ],
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=5,
        )
        assert len(result.cells) == 4  # 2 adapters × 2 NERs
        assert set(result.adapter_ids) == {"sg", "ci"}
        assert len(result.ner_ids) == 2

    def test_tensor_all_cells_have_matches(self):
        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=[
                "data/ner/tspp_2016_us_equity.yaml",
                "data/ner/french_ftt_2012_eu.yaml",
            ],
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=5,
        )
        for cell in result.cells:
            assert len(cell.matches) == 3
            for m in cell.matches:
                assert m.sign_match in (
                    MatchVerdict.MATCH,
                    MatchVerdict.MISMATCH,
                    MatchVerdict.INCONCLUSIVE,
                )

    def test_tensor_reproducibility(self):
        r1 = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["data/ner/tspp_2016_us_equity.yaml"],
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        r2 = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["data/ner/tspp_2016_us_equity.yaml"],
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        for c1, c2 in zip(r1.cells, r2.cells):
            for m1, m2 in zip(c1.matches, c2.matches):
                assert m1.delta_model == m2.delta_model

    def test_tensor_summary_and_dict(self):
        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["data/ner/tspp_2016_us_equity.yaml"],
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
        )
        summary = result.summary()
        assert "PRISM" in summary
        assert "sg" in summary
        assert "ci" in summary

        d = result.to_dict()
        assert len(d["cells"]) == 2
        assert "adapter_ids" in d
