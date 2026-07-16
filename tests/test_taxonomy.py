"""Unit tests for the classification vocabulary in taxonomy.py.

These pin the contract that coverage.py, gap_finder.py, and future
callers rely on — if any of these fail, the atlas's axis semantics
have drifted and downstream displays will look wrong.
"""
from __future__ import annotations


def test_canonical_fact_normalises_spaces_and_case():
    from fingerprint_atlas.taxonomy import canonical_fact
    assert canonical_fact("Fat Tails") == "fat-tails"
    assert canonical_fact(" vol clustering ") == "vol-clustering"
    assert canonical_fact("Long-Memory") == "long-memory"


def test_canonical_facts_matches_cont_2001_plus_regime_switching():
    """Herding must NOT be here — it's a mechanism, not a return-observable
    fact. Guards against a future re-add that would re-break the diagonal."""
    from fingerprint_atlas.taxonomy import CANONICAL_FACTS
    assert "herding" not in CANONICAL_FACTS
    for f in ("fat-tails", "vol-clustering", "leverage", "long-memory",
               "aggregational-gaussianity", "absence-of-autocorr",
               "gain-loss-asymmetry", "volume-volatility-corr",
               "regime-switching", "other"):
        assert f in CANONICAL_FACTS, f"{f} missing from CANONICAL_FACTS"


def test_method_family_classifies_known_mechanisms():
    from fingerprint_atlas.taxonomy import method_family
    # ABM
    assert method_family("minority-game") == "ABM"
    assert method_family("LLM-agent") == "ABM"
    assert method_family("Kirman-ant") == "ABM"
    assert method_family("herding") == "ABM"
    # stat
    assert method_family("regime-switching") == "stat"
    assert method_family("HMM") == "stat"
    assert method_family("GARCH") == "stat"
    assert method_family("Hawkes-process") == "stat"
    # ml
    assert method_family("LSTM") == "ml"
    assert method_family("transformer") == "ml"
    assert method_family("reinforcement-learning") == "ml"


def test_method_family_uses_substring_fallback_for_variants():
    from fingerprint_atlas.taxonomy import method_family
    # Variants not enumerated but caught by substring heuristics
    assert method_family("MRS-GARCH") == "stat"
    assert method_family("time-varying-GARCH") == "stat"
    assert method_family("deep-lstm-model") == "ml"
    assert method_family("attention-transformer-hybrid") == "ml"
    assert method_family("multi-agent-simulation") == "ABM"


def test_method_family_defaults_to_other_for_unknown():
    from fingerprint_atlas.taxonomy import method_family
    assert method_family("network-analysis") == "other"
    assert method_family("") == "other"
    assert method_family(None) == "other"


def test_deny_lists_do_not_overlap_with_family_taxonomy_absurdly():
    """A term shouldn't be flagged as 'don't count as a mechanism' AND
    listed in one of the family sets. Regression guard."""
    from fingerprint_atlas.taxonomy import (
        FACT_TERMS_NOT_MECHANISMS, TOO_GENERIC_MECHANISMS,
        ABM_MECHANISM_TAGS, STAT_MODEL_TAGS, ML_MODEL_TAGS,
    )
    fam = ABM_MECHANISM_TAGS | STAT_MODEL_TAGS | ML_MODEL_TAGS
    for t in FACT_TERMS_NOT_MECHANISMS:
        assert t not in fam, f"{t!r} is both a fact-term and a family member"
    for t in TOO_GENERIC_MECHANISMS:
        assert t not in fam, f"{t!r} is both too-generic and a family member"


def test_coverage_reexports_stay_backward_compatible():
    """coverage.py used to expose these as underscore-prefixed names.
    External code and older tests may still import them from there;
    keep the shims working."""
    from fingerprint_atlas import coverage
    from fingerprint_atlas import taxonomy
    assert coverage._CANONICAL_FACTS is taxonomy.CANONICAL_FACTS
    assert coverage._FACT_TERMS_NOT_MECHANISMS is taxonomy.FACT_TERMS_NOT_MECHANISMS
    assert coverage._TOO_GENERIC_MECHANISMS is taxonomy.TOO_GENERIC_MECHANISMS
    assert coverage._GENERIC_OA_CONCEPTS is taxonomy.GENERIC_OA_CONCEPTS
    assert coverage._canonical_fact is taxonomy.canonical_fact


def test_gap_finder_canonical_facts_is_same_object_as_taxonomy():
    """gap_finder.CANONICAL_FACTS used to be a duplicated list. Now
    it must be the same object as taxonomy.CANONICAL_FACTS — otherwise
    the two can drift and gap-mine ends up disagreeing with coverage."""
    from fingerprint_atlas import gap_finder, taxonomy
    assert gap_finder.CANONICAL_FACTS is taxonomy.CANONICAL_FACTS
