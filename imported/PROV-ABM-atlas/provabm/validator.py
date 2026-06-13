"""validator — claim↔reach の最小強制(設計ノート §5.3 払い戻し表)。

標準を「正直」にする機構:**reach が支えられる主張しか出させない**。

| 主張 (ClaimType)        | sound に出せる reach |
|-------------------------|----------------------|
| invariance(到達しない) | may  (⊇ D*)          |
| counterfactual / 反実仮想 | must (⊆ D*)         |
| exact 因果帰属          | exact (may=must)     |
| reproducibility / 系譜  | reported(主張ゼロ)  |

→ `reported`/`must` からの invariance 発行、`reported` からの反実仮想発行は **REJECT**。
v0 は reach を `reported` しか生成できないので、結果として invariance/反実仮想/exact の主張は
すべて弾かれる(= honest)。再現性/系譜のみ通る。

provenance 側は `reach_claim` が `reported` 以外なら拒否する
(CLAUDE.md「v0 では reported のみ受け付ける」)。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from provabm.reach import SUPPORTED_REACH, ReachClaim


class ValidationError(Exception):
    """claim↔reach 不整合、または provenance の reach_claim 不正。"""


class ClaimType(StrEnum):
    """provenance/結果が添えうる主張の種類。"""

    REPRODUCIBILITY = "reproducibility"  # 系譜・再現性(因果主張ゼロ)
    INVARIANCE = "invariance"  # 「X は Y に到達しない」
    COUNTERFACTUAL = "counterfactual"  # 微細反実仮想 / response-read「X は Y に到達する」
    EXACT_ATTRIBUTION = "exact_attribution"  # 因果経路の厳密帰属


# 各 claim を sound に支える reach 集合(§5.3)。exact は may/must を包含する。
_SUPPORTING_REACH: dict[ClaimType, frozenset[ReachClaim]] = {
    ClaimType.REPRODUCIBILITY: frozenset(
        {ReachClaim.REPORTED, ReachClaim.MAY, ReachClaim.MUST, ReachClaim.EXACT}
    ),
    ClaimType.INVARIANCE: frozenset({ReachClaim.MAY, ReachClaim.EXACT}),
    ClaimType.COUNTERFACTUAL: frozenset({ReachClaim.MUST, ReachClaim.EXACT}),
    ClaimType.EXACT_ATTRIBUTION: frozenset({ReachClaim.EXACT}),
}

# §13.1 で prov.json に必須のフィールド。
_REQUIRED_PROV_FIELDS: frozenset[str] = frozenset(
    {
        "uuid",
        "git_commit",
        "config_hash",
        "seed",
        "env",
        "started_at_utc",
        "completed_at_utc",
        "output_sha256",
        "reach_claim",
    }
)


def assert_claim_supported(claim: ClaimType, reach: ReachClaim) -> None:
    """`claim` を `reach` で出してよいか検証。支えられなければ `ValidationError`。"""
    supporting = _SUPPORTING_REACH[claim]
    if reach not in supporting:
        allowed = ", ".join(sorted(r.value for r in supporting))
        raise ValidationError(
            f"claim '{claim.value}' は reach '{reach.value}' からは sound に出せない "
            f"(要: {allowed})。§5.3 払い戻し表を参照。"
        )


def validate_provenance(prov: Mapping[str, Any]) -> None:
    """prov.json(dict)を検証する。必須欠落・reach_claim 不正で `ValidationError`。

    v0 は `reach_claim == 'reported'` のみ受理する(CLAUDE.md provenance 要件)。
    """
    missing = _REQUIRED_PROV_FIELDS - prov.keys()
    if missing:
        raise ValidationError(f"prov.json に必須フィールド欠落: {sorted(missing)}")

    raw_claim = prov["reach_claim"]
    try:
        reach = ReachClaim(raw_claim)
    except ValueError as exc:
        valid = ", ".join(r.value for r in ReachClaim)
        raise ValidationError(f"reach_claim '{raw_claim}' は未知。許容: {valid}") from exc

    if reach not in SUPPORTED_REACH:
        raise ValidationError(
            f"reach_claim '{reach.value}' は v0 では受理しない。"
            f"v0 が出せるのは {sorted(r.value for r in SUPPORTED_REACH)} のみ "
            "(may/must/exact は L3+ 持ち越し)。"
        )
