"""reach — 到達可能性の四分割(設計ノート §5)。

`may` / `must` / `exact` / `reported` の 4 つ。soundness 方向への写像:

- `may`   = 過大近似 = R ⊇ D*  → invariance(到達しない)の証明に使える
- `must`  = 過小近似 = R ⊆ D*  → 微細反実仮想(到達する)の証明に使える
- `exact` = may = must = D*     → 因果経路の厳密帰属
- `reported` = ctx ログ上の reach。関数内は過大・hidden channel は過小で **両方向に外れる**
  → 因果主張ゼロ、再現性/探索/系譜提示のみ(§5.2)。

**v0 は `reported` のみ実装**。`may` への昇格は hidden-channel gap を閉じた後
(AST whitelist 強制 = L3)にのみ起き、`must`/`exact` は taint/restricted DSL(L3.5-L4)が要る。
ここでは stub で明示拒否する。
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from provabm.capture import CtxEvent, CtxEventKind


class ReachClaim(StrEnum):
    """主張に添える reach フレーバー。validator が claim との整合を強制する。"""

    REPORTED = "reported"
    MAY = "may"
    MUST = "must"
    EXACT = "exact"

    @property
    def is_implemented(self) -> bool:
        # v0 で計算/受理できるのは reported のみ。
        return self is ReachClaim.REPORTED


# v0 で validator が受理する唯一の reach。
SUPPORTED_REACH: frozenset[ReachClaim] = frozenset({ReachClaim.REPORTED})

_INPUT_KINDS: frozenset[CtxEventKind] = frozenset(
    {CtxEventKind.OBSERVE, CtxEventKind.READ_OWN_STATE, CtxEventKind.RANDOM}
)


def reported_reach(events: Iterable[CtxEvent]) -> dict[str, frozenset[str]]:
    """ctx ログから reported reach を計算する。

    (agent_id, step) ごとに、その step で提出された各 order(出力 = asset key)に対し、
    同 step で触れた入力キー(observe/read_own_state/random)の和集合を割り当てる。

    これは over でも under でもなく **両方向に外れた** 量(§5.2)。因果主張には使えない。
    validator が reported からの invariance/反実仮想発行を拒否することで「正直」さを担保する。
    """
    # group key = (agent_id, step)
    inputs_by_group: dict[tuple[int, int], set[str]] = {}
    outputs_by_group: dict[tuple[int, int], set[str]] = {}
    for e in events:
        gk = (e.agent_id, e.step)
        if e.kind in _INPUT_KINDS:
            inputs_by_group.setdefault(gk, set()).add(e.key)
        elif e.kind is CtxEventKind.SUBMIT_ORDER:
            outputs_by_group.setdefault(gk, set()).add(e.key)

    reach: dict[str, frozenset[str]] = {}
    for gk, outputs in outputs_by_group.items():
        inputs = frozenset(inputs_by_group.get(gk, set()))
        for out_key in outputs:
            # 異 step で同 asset が出る場合は和を取る(報告ベースの粗い系譜)。
            reach[out_key] = reach.get(out_key, frozenset()) | inputs
    return reach


def may_reach(*_args: object, **_kwargs: object) -> dict[str, frozenset[str]]:
    """sound な `may`(R ⊇ D*)。hidden-channel を閉じる AST whitelist が前提。"""
    raise NotImplementedError(
        "reach.may: awaiting L3 — reported→sound-may は AST whitelist で "
        "hidden channel を閉じた後のみ"
    )


def must_reach(*_args: object, **_kwargs: object) -> dict[str, frozenset[str]]:
    """sound な `must`(R ⊆ D*)。関数内 data-dependence を下から確定する taint/DSL が前提。"""
    raise NotImplementedError("reach.must: awaiting L3.5-L4 — taint(部分) / restricted DSL(完全)")


def exact_reach(*_args: object, **_kwargs: object) -> dict[str, frozenset[str]]:
    """`exact`(may = must、宣言境界内)。完全性+精度を対 adversary で要する。"""
    raise NotImplementedError("reach.exact: awaiting L4 — restricted DSL / exact capture")
