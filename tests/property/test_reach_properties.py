"""reach 性質(property test)。

reported reach の素性:
- 出力の reach = その step で触れた入力キーの和(報告ベース)
- 入力を増やすと reach は単調に大きくなる(⊆)
- may/must/exact は v0 未実装(NotImplementedError)
"""

from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st
from provabm.capture import CtxEvent, CtxEventKind
from provabm.reach import exact_reach, may_reach, must_reach, reported_reach

_keys = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6)


def _obs(keys: set[str], step: int = 0) -> list[CtxEvent]:
    return [CtxEvent(1, step, CtxEventKind.OBSERVE, k) for k in keys]


def _orders(assets: set[str], step: int = 0) -> list[CtxEvent]:
    return [CtxEvent(1, step, CtxEventKind.SUBMIT_ORDER, a) for a in assets]


@given(inputs=st.sets(_keys, max_size=6), outputs=st.sets(_keys, min_size=1, max_size=3))
def test_reported_reach_is_union_of_step_inputs(inputs: set[str], outputs: set[str]) -> None:
    reach = reported_reach(_obs(inputs) + _orders(outputs))
    for out_key in outputs:
        assert reach[out_key] == frozenset(inputs)


@given(
    base=st.sets(_keys, max_size=4),
    extra=st.sets(_keys, max_size=4),
    output=_keys,
)
def test_reach_monotone_in_inputs(base: set[str], extra: set[str], output: str) -> None:
    r_small = reported_reach(_obs(base) + _orders({output}))
    r_big = reported_reach(_obs(base | extra) + _orders({output}))
    assert r_small[output] <= r_big[output]


def test_no_order_means_empty_reach() -> None:
    assert reported_reach(_obs({"price", "cash"})) == {}


def test_reach_groups_by_step() -> None:
    # 異 step は別グループ。同 asset が両 step に出れば和を取る。
    events = (
        _obs({"price"}, step=0)
        + _orders({"A"}, step=0)
        + _obs({"social"}, step=1)
        + _orders({"A"}, step=1)
    )
    assert reported_reach(events)["A"] == frozenset({"price", "social"})


@pytest.mark.parametrize("fn", [may_reach, must_reach, exact_reach])
def test_unimplemented_reach_flavors_raise(fn: object) -> None:
    with pytest.raises(NotImplementedError):
        fn()  # type: ignore[operator]
