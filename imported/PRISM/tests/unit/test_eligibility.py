"""Tests for static eligibility gate."""

from prism.scoring.eligibility import (
    EMPIRICAL_RANGES,
    EligibilityVerdict,
    FactRange,
    check_eligibility,
    check_fact_in_range,
)
from prism.types import FactResult


class TestCheckFactInRange:
    def test_in_range(self):
        fact = FactResult(fact_id="volatility_clustering", value=0.85)
        result = check_fact_in_range(fact)
        assert result is not None
        assert result.in_range is True

    def test_below_range(self):
        fact = FactResult(fact_id="volatility_clustering", value=0.1)
        result = check_fact_in_range(fact)
        assert result is not None
        assert result.in_range is False

    def test_above_range(self):
        fact = FactResult(fact_id="leverage_effect", value=0.5)
        result = check_fact_in_range(fact)
        assert result is not None
        assert result.in_range is False

    def test_nan_value_is_ineligible(self):
        fact = FactResult(fact_id="leverage_effect", value=float("nan"))
        result = check_fact_in_range(fact)
        assert result is not None
        assert result.in_range is False

    def test_unknown_fact_returns_none(self):
        fact = FactResult(fact_id="unknown_fact", value=0.5)
        result = check_fact_in_range(fact)
        assert result is None

    def test_boundary_lo(self):
        fact = FactResult(fact_id="volatility_clustering", value=0.5)
        result = check_fact_in_range(fact)
        assert result.in_range is True

    def test_boundary_hi(self):
        fact = FactResult(fact_id="volatility_clustering", value=0.999)
        result = check_fact_in_range(fact)
        assert result.in_range is True

    def test_custom_ranges(self):
        custom = {"test_fact": FactRange("test_fact", -1.0, 1.0)}
        fact = FactResult(fact_id="test_fact", value=0.5)
        result = check_fact_in_range(fact, custom)
        assert result is not None
        assert result.in_range is True


class TestCheckEligibility:
    def test_all_pass(self):
        facts = [
            FactResult(fact_id="volatility_clustering", value=0.85),
            FactResult(fact_id="leverage_effect", value=-0.1),
            FactResult(fact_id="gain_loss_asymmetry", value=-0.5),
        ]
        result = check_eligibility("test_model", facts)
        assert result.verdict == EligibilityVerdict.ELIGIBLE
        assert result.n_pass == 3
        assert result.n_fail == 0

    def test_one_fail(self):
        facts = [
            FactResult(fact_id="volatility_clustering", value=0.85),
            FactResult(fact_id="leverage_effect", value=0.5),  # out of range
        ]
        result = check_eligibility("test_model", facts)
        assert result.verdict == EligibilityVerdict.INELIGIBLE
        assert result.n_pass == 1
        assert result.n_fail == 1

    def test_all_fail(self):
        facts = [
            FactResult(fact_id="volatility_clustering", value=0.1),
            FactResult(fact_id="leverage_effect", value=0.5),
        ]
        result = check_eligibility("test_model", facts)
        assert result.verdict == EligibilityVerdict.INELIGIBLE
        assert result.n_fail == 2

    def test_empty_facts(self):
        result = check_eligibility("test_model", [])
        assert result.verdict == EligibilityVerdict.UNTESTED

    def test_unknown_facts_only(self):
        facts = [FactResult(fact_id="unknown_metric", value=0.5)]
        result = check_eligibility("test_model", facts)
        assert result.verdict == EligibilityVerdict.UNTESTED

    def test_summary_output(self):
        facts = [
            FactResult(fact_id="volatility_clustering", value=0.85),
            FactResult(fact_id="leverage_effect", value=-0.2),
        ]
        result = check_eligibility("sg_v0.1", facts)
        summary = result.summary()
        assert "sg_v0.1" in summary
        assert "eligible" in summary
        assert "PASS" in summary

    def test_model_id_preserved(self):
        facts = [FactResult(fact_id="volatility_clustering", value=0.85)]
        result = check_eligibility("my_model_v2", facts)
        assert result.model_id == "my_model_v2"


class TestEmpiricalRanges:
    def test_all_three_facts_have_ranges(self):
        assert "volatility_clustering" in EMPIRICAL_RANGES
        assert "leverage_effect" in EMPIRICAL_RANGES
        assert "gain_loss_asymmetry" in EMPIRICAL_RANGES

    def test_ranges_are_valid(self):
        for fid, r in EMPIRICAL_RANGES.items():
            assert r.lo < r.hi, f"{fid}: lo ({r.lo}) >= hi ({r.hi})"
