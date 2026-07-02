"""C-1 regression: bin_variance_slope のゼロ ΔG 汚染。

監査 (2026-07-02) C-1: ヘッドライン指標 bin_variance_slope が `np.maximum(|ΔG|,1e-9)`
で 0 を log(1e-9)=−20.7 に写像していたため、bin ごとの Var(log|ΔG|) が真の分散では
なく **ゼロ率の項** f(1−f)·(~22)² に支配され、指標が「ファネル」ではなく「ゼロ ΔG
頻度の horizon プロファイル」を測っていた。保存済み parquet で再計算すると符号が反転
(C0u: 実装 −0.41 → ゼロ除外 +0.99)。

修正: 既定で非ゼロ ΔG のみ使用 (exclude_zeros=True)。ゼロ率の horizon 依存は
bin_zero_rate_slope で分離報告する。

このテストは 2 つの信号を **逆方向** に埋め込んだ合成データで、修正版が真のファネル
(非ゼロ ΔG の散らばり) を、旧版がゼロ率を測っていたことを示す。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from analysis import bin_variance_slope, bin_zero_rate_slope  # noqa: E402


def _synthetic():
    """非ゼロ |ΔG| の散らばりは horizon とともに増加 (真のファネル ↑)、
    ゼロ率は horizon とともに減少 (逆方向) する合成 RT。"""
    rng = np.random.default_rng(0)
    N = 60_000
    h = rng.integers(1, 200, N).astype(float)
    sigma = 1.0 + 0.05 * h
    dG = np.round(rng.normal(0, sigma)).astype(float)
    dG[dG == 0] = 1.0  # 「信号」部分は非ゼロにしておく
    p_zero = np.clip(0.5 - 0.002 * h, 0.02, 0.6)  # ゼロ率は horizon で減少
    dG[rng.random(N) < p_zero] = 0.0
    return h, dG


def test_exclude_zeros_recovers_true_funnel():
    """exclude_zeros=True は真のファネル (正の slope) を回復する。"""
    h, dG = _synthetic()
    funnel = bin_variance_slope(h, dG, exclude_zeros=True)
    assert funnel > 0.8, f"真のファネル slope が正でない: {funnel:+.3f}"


def test_old_behavior_is_contaminated_by_zero_floor():
    """exclude_zeros=False (旧挙動) はゼロ率に汚染され、真のファネルと大きく乖離する。

    合成データではゼロ率を逆方向に埋めているので、旧指標は真のファネル (>0.8) から
    大きく下振れ (ここでは負近傍) する。"""
    h, dG = _synthetic()
    funnel = bin_variance_slope(h, dG, exclude_zeros=True)
    old = bin_variance_slope(h, dG, exclude_zeros=False)
    assert old < funnel - 0.5, (
        f"旧挙動が汚染されていない (old={old:+.3f}, funnel={funnel:+.3f})"
    )


def test_zero_rate_slope_isolates_zero_signal():
    """bin_zero_rate_slope は埋め込んだゼロ率の horizon 依存 (減少) を検出する。"""
    h, dG = _synthetic()
    zslope = bin_zero_rate_slope(h, dG)
    assert zslope < -0.5, f"ゼロ率 slope が減少を検出していない: {zslope:+.3f}"


def test_funnel_invariant_to_extra_zeros():
    """exclude_zeros=True の funnel slope は、ゼロ ΔG を追加しても不変 (ゼロは無視)。"""
    h, dG = _synthetic()
    base = bin_variance_slope(h, dG, exclude_zeros=True)
    # 大量のゼロ RT を全 horizon 帯に一様追加
    rng = np.random.default_rng(1)
    extra_h = rng.integers(1, 200, 40_000).astype(float)
    extra_dG = np.zeros(40_000)
    h2 = np.concatenate([h, extra_h])
    dG2 = np.concatenate([dG, extra_dG])
    after = bin_variance_slope(h2, dG2, exclude_zeros=True)
    assert abs(after - base) < 0.05, (
        f"ゼロ追加で funnel が変化した (base={base:+.3f}, after={after:+.3f})"
    )


if __name__ == "__main__":
    test_exclude_zeros_recovers_true_funnel()
    test_old_behavior_is_contaminated_by_zero_floor()
    test_zero_rate_slope_isolates_zero_signal()
    test_funnel_invariant_to_extra_zeros()
    print("[bin-variance-c1] ✓ pass")
