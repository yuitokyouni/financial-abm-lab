"""emit_row + reference atlas generation (spec 002 tasks 3 & 5).

Uses a small, fast subset and few seeds so the suite stays quick. The full
8-model atlas is generated offline by ``atlas.reference_atlas.main`` and committed
to ``docs/atlas/reference_atlas_v0.json``.
"""

from __future__ import annotations

from atlas import diversity_satisfied
from atlas.reference_atlas import check_launch_readiness, generate_reference_atlas
from atlas.registry import diversity_coverage, eligible_models
from atlas.row import emit_row

_FAST_SEEDS = (1, 2)


def test_emit_row_returns_model_has_sf_profile() -> None:
    row = emit_row("zero_intelligence", seeds=_FAST_SEEDS)
    assert row["contract_status"] in ("C0", "C2")
    assert row["sf_profile"] is not None
    assert row["intervention_response_signature"] is None  # honest: C1 pending
    assert row["intervention_response_status"] == "pending_c1"
    assert row["radar"]["mechanism_separability"] is None
    assert row["provenance"]["reach_claim"] == "reported"


def test_priceless_model_gets_structured_failure() -> None:
    row = emit_row("minority_game", seeds=_FAST_SEEDS)
    assert row["sf_profile"] is None
    note = row["failure_transparency_note"]
    assert note["has_failure"] and note["structured"]
    assert note["taxonomy"] == "battery_non_applicable"


def test_full_registry_is_eligible_and_diverse() -> None:
    names = eligible_models()
    assert len(names) >= 8
    # spec 002 §7 diversity constraint: every required tag covered.
    assert diversity_satisfied(names), diversity_coverage(names)


def test_reference_atlas_subset_structure_and_readiness() -> None:
    atlas = generate_reference_atlas(
        names=["zero_intelligence", "cont_bouchaud"], seeds=_FAST_SEEDS
    )
    assert atlas["n_rows"] == 2
    lr = check_launch_readiness(atlas)
    # AC-4 must be honestly pending (no C1 channel pair).
    assert lr["criteria"]["intervention_separates_beyond_sf"]["met"] is False
    assert "intervention_separates_beyond_sf" in lr["blocking"]
    # contract_v1_frozen is met.
    assert lr["criteria"]["contract_v1_frozen"]["met"] is True
