"""Scoring profiles (spec 002 §8) + contract conformance (§5/§6)."""

from __future__ import annotations

from atlas import profiles as P
from atlas.contract import ConformanceLevel, ContractModel, check_determinism


# --- claim admissibility: validator rule (prov_abm_design_notes §5.3) ---
def test_reported_rejects_causal_claims() -> None:
    ca = P.claim_admissibility("reported", ("invariance", "counterfactual"))
    assert ca.score == 0.0
    assert set(ca.rejected) == {"invariance", "counterfactual"}


def test_reported_admits_noncausal() -> None:
    ca = P.claim_admissibility("reported", ("reproducibility", "genealogy"))
    assert ca.score == 1.0


def test_no_claims_is_trivially_admissible() -> None:
    assert P.claim_admissibility("reported", ()).score == 1.0


def test_may_admits_invariance() -> None:
    ca = P.claim_admissibility("may", ("invariance",))
    assert ca.score == 1.0


# --- intervention coverage: C0 channel-less models score 0 honestly ---
def test_coverage_zero_without_channels() -> None:
    assert P.intervention_coverage(0).score == 0.0


def test_coverage_positive_with_channel() -> None:
    assert P.intervention_coverage(1).score > 0.0


# --- mechanism separability is pending until C1 ---
def test_separability_pending() -> None:
    ms = P.mechanism_separability_pending(("price_returns",))
    assert ms.status == "pending_c1"


# --- failure transparency: structured vs dumping ground (spec 002 §9) ---
def test_unstructured_failure_scores_zero() -> None:
    ft = P.failure_transparency(has_failure=True, taxonomy=None, reproducible=False, contract_ok=True)
    assert ft.score == 0.0 and not ft.structured


def test_structured_failure_scores_one() -> None:
    ft = P.failure_transparency(
        has_failure=True, taxonomy="battery_non_applicable", reproducible=True, contract_ok=True
    )
    assert ft.score == 1.0 and ft.structured


# --- audit completeness: may/must gap is a component, not the whole ---
def test_audit_gap_is_none_at_l2() -> None:
    prov = {f: "x" for f in ("uuid", "model", "config_hash", "seed", "output_sha256", "reach_claim")}
    ac = P.audit_completeness(prov, determinism_verified=True)
    assert ac.may_must_gap is None
    assert ac.score == 1.0


# --- contract: a fake model is C0/C2 and deterministic ---
class _FakeModel:
    name = "fake"

    def run(self, *, seed: int) -> dict:
        import numpy as np

        rng = np.random.default_rng(seed)
        return {"returns": rng.normal(size=64)}


def test_contract_c0_determinism_and_emit() -> None:
    assert check_determinism(_FakeModel(), seed=7)
    cm = ContractModel(_FakeModel(), config={"a": 1})
    cm.reset(7)
    assert "returns" in cm.emit()
    prov = cm.emit_prov()
    assert prov["reach_claim"] == "reported"
    assert prov["seed"] == 7
    assert cm.channels == ()


def test_radar_separability_none_for_c0() -> None:
    profile = P.ScoringProfile(
        claim_admissibility=P.claim_admissibility("reported", ("reported",)),
        audit_completeness=P.audit_completeness({"uuid": "x"}, determinism_verified=True),
        intervention_coverage=P.intervention_coverage(0),
        mechanism_separability=P.mechanism_separability_pending(()),
        replication_stability=P.ReplicationStability(5, {"std": 0.1}, 0.9),
        failure_transparency=P.failure_transparency(
            has_failure=False, taxonomy=None, reproducible=True, contract_ok=True
        ),
    )
    radar = profile.radar()
    assert radar["mechanism_separability"] is None
    assert set(radar) == set(P.PROFILE_AXES)
    assert ConformanceLevel.C2 > ConformanceLevel.C0
