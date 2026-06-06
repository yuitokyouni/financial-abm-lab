"""ctx 不変条件(property test)。

固める核:
- 乱数は seed で再現可能(同 seed → 同 draw 列)
- ctx 呼び出しは捕捉ログに 1:1 で残る(L2)。L0/L1 では残らない
- submit_order は step 内 1 回まで、side→符号写像は固定
"""

from __future__ import annotations

import string

import numpy as np
import numpy.typing as npt
import pytest
from hypothesis import given
from hypothesis import strategies as st
from provabm.capture import CaptureLevel, CaptureSink, CtxEventKind
from provabm.ctx import Ctx

_keys = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6)


def _make_ctx(seed: int = 0, level: CaptureLevel = CaptureLevel.L2) -> tuple[Ctx, CaptureSink]:
    sink = CaptureSink(level)
    return Ctx(agent_id=1, rng=np.random.default_rng(seed), capture=sink), sink


@given(seed=st.integers(min_value=0, max_value=2**31 - 1), n=st.integers(min_value=0, max_value=20))
def test_random_reproducible_under_same_seed(seed: int, n: int) -> None:
    c1, _ = _make_ctx(seed)
    c2, _ = _make_ctx(seed)
    c1.bind_step(0, {}, {})
    c2.bind_step(0, {}, {})
    assert [c1.random() for _ in range(n)] == [c2.random() for _ in range(n)]


@given(seed=st.integers(min_value=0, max_value=2**31 - 1), n=st.integers(min_value=1, max_value=20))
def test_random_in_unit_interval(seed: int, n: int) -> None:
    c, _ = _make_ctx(seed)
    c.bind_step(0, {}, {})
    draws = [c.random("noise") for _ in range(n)]
    assert all(0.0 <= d < 1.0 for d in draws)


@given(obs_keys=st.sets(_keys, max_size=5), n_rand=st.integers(min_value=0, max_value=5))
def test_ctx_calls_are_captured_one_to_one(obs_keys: set[str], n_rand: int) -> None:
    c, sink = _make_ctx()
    observations: dict[str, npt.NDArray[np.float64]] = {
        k: np.zeros(3, dtype=np.float64) for k in obs_keys
    }
    c.bind_step(0, observations, {})
    for k in obs_keys:
        c.observe(k)
    for _ in range(n_rand):
        c.random()
    c.submit_order("hold")

    kinds = [e.kind for e in sink.events]
    assert kinds.count(CtxEventKind.OBSERVE) == len(obs_keys)
    assert kinds.count(CtxEventKind.RANDOM) == n_rand
    assert kinds.count(CtxEventKind.SUBMIT_ORDER) == 1
    assert len(sink) == len(obs_keys) + n_rand + 1


@given(level=st.sampled_from([CaptureLevel.L0, CaptureLevel.L1]))
def test_below_l2_captures_nothing(level: CaptureLevel) -> None:
    c, sink = _make_ctx(level=level)
    c.bind_step(0, {"p": np.ones(2)}, {"cash": 1.0})
    c.observe("p")
    c.read_own_state("cash")
    c.random()
    c.submit_order("buy")
    assert len(sink) == 0


def test_observe_returns_bound_value() -> None:
    c, _ = _make_ctx()
    arr = np.arange(4, dtype=np.float64)
    c.bind_step(0, {"price": arr}, {})
    assert np.array_equal(c.observe("price"), arr)


@pytest.mark.parametrize(("side", "expected"), [("buy", 1), ("sell", -1), ("hold", 0)])
def test_submit_order_sign_mapping(side: str, expected: int) -> None:
    c, _ = _make_ctx()
    c.bind_step(0, {}, {})
    assert c.submit_order(side) == expected
    assert c.submitted_order == expected


def test_submit_order_once_per_step() -> None:
    c, _ = _make_ctx()
    c.bind_step(0, {}, {})
    c.submit_order("buy")
    with pytest.raises(RuntimeError, match="more than once"):
        c.submit_order("sell")
    # 次 step では再び発注できる(rebind が order をリセット)。
    c.bind_step(1, {}, {})
    assert c.submit_order("sell") == -1


def test_unknown_side_rejected() -> None:
    c, _ = _make_ctx()
    c.bind_step(0, {}, {})
    with pytest.raises(ValueError, match="unknown side"):
        c.submit_order("yolo")
