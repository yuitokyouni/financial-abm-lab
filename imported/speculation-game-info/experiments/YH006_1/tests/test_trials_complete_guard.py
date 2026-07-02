"""#34 regression: ensemble driver のエラー握り潰し防止。

監査 (2026-07-02) #34: worker 例外は結果 tuple の末尾に traceback 文字列で返るが、
多くのドライバが戻り値を捨てており失敗 trial が無言で n を縮め seed ペアリングも
ずらしていた。`assert_trials_complete` は失敗/欠落 trial を検出し strict で raise する。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from parallel import assert_trials_complete  # noqa: E402

_LOG = logging.getLogger("test")


def _result(seed, err=None):
    # (seed, runtime_sec, n_rt, n_sub, err)
    return (seed, 1.0, 100, 3, err)


def test_all_success_returns_no_errors():
    seeds = [1000, 1001, 1002]
    results = [_result(s) for s in seeds]
    errored = assert_trials_complete("C0u", seeds, results, _LOG, strict=True)
    assert errored == []


def test_errored_trial_raises_when_strict():
    seeds = [1000, 1001, 1002]
    results = [_result(1000), _result(1001, err="Traceback: boom"), _result(1002)]
    with pytest.raises(RuntimeError, match="1001"):
        assert_trials_complete("C0u", seeds, results, _LOG, strict=True)


def test_missing_trial_raises_when_strict():
    seeds = [1000, 1001, 1002]
    results = [_result(1000), _result(1002)]  # 1001 欠落
    with pytest.raises(RuntimeError, match="1001"):
        assert_trials_complete("C0u", seeds, results, _LOG, strict=True)


def test_non_strict_returns_failures_without_raising():
    seeds = [1000, 1001]
    results = [_result(1000, err="boom"), _result(1001)]
    errored = assert_trials_complete("C0u", seeds, results, _LOG, strict=False)
    assert errored == [1000]


if __name__ == "__main__":
    test_all_success_returns_no_errors()
    test_errored_trial_raises_when_strict()
    test_missing_trial_raises_when_strict()
    test_non_strict_returns_failures_without_raising()
    print("[trials-complete-guard] ✓ pass")
