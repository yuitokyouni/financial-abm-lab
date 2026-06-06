"""validator: claim↔reach 払い戻し表と provenance reach_claim 強制(§5.3 / §13.1)。"""

from __future__ import annotations

import pytest
from provabm.reach import ReachClaim
from provabm.validator import (
    ClaimType,
    ValidationError,
    assert_claim_supported,
    validate_provenance,
)


def _valid_prov(reach_claim: str = "reported") -> dict[str, object]:
    return {
        "uuid": "0190a000-0000-7000-8000-000000000000",
        "git_commit": "abc123",
        "config_hash": "deadbeef",
        "config_yaml": "x: 1",
        "seed": {"numpy": 0, "python": 0, "torch": None},
        "env": {"python_version": "3.13.1"},
        "started_at_utc": "2026-06-05T00:00:00+00:00",
        "completed_at_utc": "2026-06-05T00:00:01+00:00",
        "output_sha256": "0" * 64,
        "ctx_log_path": "runs/x.parquet",
        "reach_claim": reach_claim,
    }


def test_reported_provenance_accepted() -> None:
    validate_provenance(_valid_prov("reported"))  # 例外が出なければ pass


@pytest.mark.parametrize("claim", ["may", "must", "exact"])
def test_non_reported_reach_rejected(claim: str) -> None:
    with pytest.raises(ValidationError, match="v0 では受理しない"):
        validate_provenance(_valid_prov(claim))


def test_unknown_reach_claim_rejected() -> None:
    with pytest.raises(ValidationError, match="未知"):
        validate_provenance(_valid_prov("totally-bogus"))


def test_missing_field_rejected() -> None:
    prov = _valid_prov()
    del prov["output_sha256"]
    with pytest.raises(ValidationError, match="必須フィールド欠落"):
        validate_provenance(prov)


# --- 払い戻し表(§5.3)---------------------------------------------------
def test_reproducibility_from_reported_ok() -> None:
    assert_claim_supported(ClaimType.REPRODUCIBILITY, ReachClaim.REPORTED)


@pytest.mark.parametrize(
    "claim",
    [ClaimType.INVARIANCE, ClaimType.COUNTERFACTUAL, ClaimType.EXACT_ATTRIBUTION],
)
def test_causal_claims_from_reported_rejected(claim: ClaimType) -> None:
    # reported は両方向に外れる → 因果主張ゼロ(§5.2)。
    with pytest.raises(ValidationError):
        assert_claim_supported(claim, ReachClaim.REPORTED)


def test_invariance_needs_may_not_must() -> None:
    assert_claim_supported(ClaimType.INVARIANCE, ReachClaim.MAY)
    assert_claim_supported(ClaimType.INVARIANCE, ReachClaim.EXACT)
    with pytest.raises(ValidationError):
        assert_claim_supported(ClaimType.INVARIANCE, ReachClaim.MUST)


def test_counterfactual_needs_must_not_may() -> None:
    assert_claim_supported(ClaimType.COUNTERFACTUAL, ReachClaim.MUST)
    assert_claim_supported(ClaimType.COUNTERFACTUAL, ReachClaim.EXACT)
    with pytest.raises(ValidationError):
        assert_claim_supported(ClaimType.COUNTERFACTUAL, ReachClaim.MAY)


def test_exact_attribution_needs_exact() -> None:
    assert_claim_supported(ClaimType.EXACT_ATTRIBUTION, ReachClaim.EXACT)
    for insufficient in (ReachClaim.REPORTED, ReachClaim.MAY, ReachClaim.MUST):
        with pytest.raises(ValidationError):
            assert_claim_supported(ClaimType.EXACT_ATTRIBUTION, insufficient)
