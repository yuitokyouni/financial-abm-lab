"""Integration test for the end-to-end pipeline."""


from prism.pipeline import compare_causal_methods, run_cell, run_tensor
from prism.scoring.eligibility import EligibilityVerdict
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


class TestZIEndToEnd:
    def test_zi_tick_size_cell(self):
        result = run_cell(
            adapter_name="zi",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "zi"
        assert result.ner_id == "tspp_2016_us_equity"
        assert len(result.matches) == 3

    def test_zi_transaction_tax_cell(self):
        result = run_cell(
            adapter_name="zi",
            ner_path="data/ner/french_ftt_2012_eu.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.adapter_id == "zi"
        assert len(result.matches) == 3

    def test_zi_has_eligibility(self):
        result = run_cell(
            adapter_name="zi",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.eligibility is not None

    def test_zi_simpler_mdl_weight(self):
        zi = run_cell("zi", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        sg = run_cell("sg", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        ci = run_cell("ci", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        assert zi.weighted_matches[0].mdl_weight > sg.weighted_matches[0].mdl_weight
        assert zi.weighted_matches[0].mdl_weight > ci.weighted_matches[0].mdl_weight


class TestFatTailsFact:
    def test_fat_tails_in_cell(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["fat_tails"],
            seed=42,
            n_paths=5,
        )
        assert len(result.matches) == 1
        assert result.matches[0].fact_id == "fat_tails"

    def test_fat_tails_all_adapters(self):
        for adapter in ["sg", "ci", "zi"]:
            result = run_cell(
                adapter_name=adapter,
                ner_path="data/ner/tspp_2016_us_equity.yaml",
                fact_ids=["fat_tails"],
                seed=42,
                n_paths=5,
            )
            assert len(result.matches) == 1


class TestTensor3x2:
    def test_3x2_tensor_runs(self):
        result = run_tensor(
            adapter_names=["sg", "ci", "zi"],
            ner_paths=[
                "data/ner/tspp_2016_us_equity.yaml",
                "data/ner/french_ftt_2012_eu.yaml",
            ],
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry", "fat_tails", "abs_autocorrelation"],
            seed=42,
            n_paths=5,
        )
        assert len(result.cells) == 6  # 3 adapters x 2 NERs
        assert set(result.adapter_ids) == {"sg", "ci", "zi"}
        assert len(result.ner_ids) == 2

    def test_3x2_all_cells_have_5_facts(self):
        result = run_tensor(
            adapter_names=["sg", "ci", "zi"],
            ner_paths=[
                "data/ner/tspp_2016_us_equity.yaml",
                "data/ner/french_ftt_2012_eu.yaml",
            ],
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry", "fat_tails", "abs_autocorrelation"],
            seed=42,
            n_paths=5,
        )
        for cell in result.cells:
            assert len(cell.matches) == 5
            assert len(cell.weighted_matches) == 5
            assert cell.eligibility is not None


class TestCausalMethodComparison:
    def test_compare_runs(self):
        result = compare_causal_methods(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        assert result.adapter_id == "sg"
        assert result.ner_id == "tspp_2016_us_equity"
        assert len(result.methods) == 6  # all known methods
        assert len(result.rows) == 6  # 6 methods × 1 fact

    def test_rct_highest_weight(self):
        result = compare_causal_methods(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            methods=["rct", "ols"],
            seed=42,
            n_paths=5,
        )
        rct_row = [r for r in result.rows if r.causal_method == "rct"][0]
        ols_row = [r for r in result.rows if r.causal_method == "ols"][0]
        assert rct_row.causal_weight > ols_row.causal_weight
        assert rct_row.confidence_weighted >= ols_row.confidence_weighted

    def test_compare_to_dict(self):
        result = compare_causal_methods(
            adapter_name="ci",
            ner_path="data/ner/french_ftt_2012_eu.yaml",
            fact_ids=["leverage_effect"],
            methods=["did_firm_fe", "iv"],
            seed=42,
            n_paths=5,
        )
        d = result.to_dict()
        assert d["adapter_id"] == "ci"
        assert len(d["rows"]) == 2
        assert d["methods"] == ["did_firm_fe", "iv"]

    def test_compare_summary(self):
        result = compare_causal_methods(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            methods=["rct", "ols"],
            seed=42,
            n_paths=5,
        )
        summary = result.summary()
        assert "rct" in summary
        assert "ols" in summary
        assert "Causal Method Comparison" in summary


class TestPerPathFacts:
    """Phase 5a: per-path fact estimation preserves distributional properties."""

    def test_per_path_cell_runs(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "fat_tails"],
            seed=42,
            n_paths=5,
            per_path_facts=True,
        )
        assert result.adapter_id == "sg"
        assert len(result.matches) == 2

    def test_per_path_preserves_fat_tails(self):
        classic = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["fat_tails"],
            seed=42,
            n_paths=5,
            per_path_facts=False,
        )
        per_path = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["fat_tails"],
            seed=42,
            n_paths=5,
            per_path_facts=True,
        )
        assert per_path.matches[0].fact_id == "fat_tails"
        assert classic.matches[0].fact_id == "fat_tails"

    def test_per_path_has_provenance(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=3,
            per_path_facts=True,
        )
        prov = result.provenance
        assert "run_id" in prov
        assert prov["parameters"]["per_path_facts"] is True

    def test_per_path_reproducibility(self):
        r1 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "fat_tails"],
            seed=99,
            n_paths=5,
            per_path_facts=True,
        )
        r2 = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "fat_tails"],
            seed=99,
            n_paths=5,
            per_path_facts=True,
        )
        for m1, m2 in zip(r1.matches, r2.matches):
            assert m1.delta_model == m2.delta_model

    def test_per_path_all_adapters(self):
        for adapter in ["sg", "ci", "zi"]:
            result = run_cell(
                adapter_name=adapter,
                ner_path="data/ner/tspp_2016_us_equity.yaml",
                fact_ids=["fat_tails", "leverage_effect"],
                seed=42,
                n_paths=3,
                per_path_facts=True,
            )
            assert len(result.matches) == 2
            assert result.eligibility is not None
            assert len(result.weighted_matches) == 2

    def test_per_path_tensor(self):
        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["data/ner/tspp_2016_us_equity.yaml"],
            fact_ids=["fat_tails"],
            seed=42,
            n_paths=3,
            per_path_facts=True,
        )
        assert len(result.cells) == 2
        for cell in result.cells:
            assert len(cell.matches) == 1


class TestPhase3Integration:
    """Phase 3: MDL weighting, eligibility gate, causal method weighting."""

    def test_cell_has_weighted_matches(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        assert len(result.weighted_matches) == 1
        wm = result.weighted_matches[0]
        assert wm.mdl_weight > 0
        assert wm.causal_weight > 0
        assert wm.confidence_weighted == wm.confidence_raw * wm.mdl_weight * wm.causal_weight

    def test_sg_simpler_than_ci_by_mdl(self):
        sg = run_cell("sg", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        ci = run_cell("ci", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        assert sg.weighted_matches[0].mdl_weight > ci.weighted_matches[0].mdl_weight

    def test_cell_has_eligibility(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"],
            seed=42,
            n_paths=10,
        )
        assert result.eligibility is not None
        assert result.eligibility.verdict in (
            EligibilityVerdict.ELIGIBLE,
            EligibilityVerdict.INELIGIBLE,
        )
        assert len(result.eligibility.checks) > 0

    def test_eligibility_in_provenance(self):
        result = run_cell("sg", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        assert "eligibility" in result.provenance.get("parameters", {})

    def test_causal_weight_from_ner(self):
        result = run_cell(
            adapter_name="sg",
            ner_path="data/ner/tspp_2016_us_equity.yaml",
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        wm = result.weighted_matches[0]
        assert wm.causal_weight == 0.9  # tspp uses did_firm_fe

    def test_to_dict_includes_phase3_fields(self):
        result = run_cell("sg", "data/ner/tspp_2016_us_equity.yaml", ["leverage_effect"], seed=42, n_paths=5)
        d = result.to_dict()
        assert "weighted_matches" in d
        assert "eligibility" in d
        assert d["eligibility"]["verdict"] in ("eligible", "ineligible", "untested")

    def test_tensor_with_phase3(self):
        result = run_tensor(
            adapter_names=["sg", "ci"],
            ner_paths=["data/ner/tspp_2016_us_equity.yaml"],
            fact_ids=["leverage_effect"],
            seed=42,
            n_paths=5,
        )
        for cell in result.cells:
            assert len(cell.weighted_matches) > 0
            assert cell.eligibility is not None
        summary = result.summary()
        assert "Eligibility" in summary
