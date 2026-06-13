"""test_classifiers — SF/IR classifier の検出力を合成データで pin(spec §6, §9)。

「分離可能 → 高 accuracy」「同一分布 → chance(~50%)」を test に焼く。Null-1 が
50% を返すべき根拠(分類器が同一分布を分けないこと)をここで保証する。
"""

from __future__ import annotations

import numpy as np
import pytest
from toy.classifiers import (
    ir_classifier_cv_accuracy,
    sf_cnn_cv_accuracy,
    sf_summary_cv_accuracy,
)


def _two_gaussians(n: int, dim: int, sep: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    a = rng.normal(0.0, 1.0, size=(n, dim))
    b = rng.normal(sep, 1.0, size=(n, dim))
    x = np.vstack([a, b])
    y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
    return x, y


def test_summary_separable_high_accuracy() -> None:
    x, y = _two_gaussians(80, 4, sep=3.0, seed=1)
    assert sf_summary_cv_accuracy(x, y, seed=0) > 0.9


def test_summary_identical_is_chance() -> None:
    # 同一分布に任意 label → 分離情報ゼロ → ~50%(Null-1 の根拠)。
    rng = np.random.default_rng(2)
    x = rng.normal(size=(160, 4))
    y = np.array([0, 1] * 80)
    acc = sf_summary_cv_accuracy(x, y, seed=0)
    assert 0.35 <= acc <= 0.65


def test_ir_separable_high_accuracy() -> None:
    x, y = _two_gaussians(80, 12, sep=2.5, seed=3)
    assert ir_classifier_cv_accuracy(x, y, seed=0) > 0.85


def test_ir_identical_is_chance() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(size=(160, 12))
    y = np.array([0, 1] * 80)
    assert 0.35 <= ir_classifier_cv_accuracy(x, y, seed=0) <= 0.65


@pytest.mark.slow
def test_cnn_separable_high_accuracy() -> None:
    # 異なる AR(1) 係数の系列 → CNN が分離できる。
    rng = np.random.default_rng(5)
    n, t = 40, 200

    def ar1(phi: float) -> np.ndarray:
        s = np.zeros((n, t))
        for i in range(n):
            e = rng.normal(size=t)
            for k in range(1, t):
                s[i, k] = phi * s[i, k - 1] + e[k]
        return s

    x = np.vstack([ar1(0.0), ar1(0.7)]).astype(np.float64)
    y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
    assert sf_cnn_cv_accuracy(x, y, seed=0, epochs=15) > 0.75
