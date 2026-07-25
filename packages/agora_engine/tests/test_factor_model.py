import numpy as np
import pytest

from agora_engine import DecisionMatrix, fit_pca_em, monoculture_index


def _planted_low_rank(n=60, p=200, k=2, noise=0.1, missing=0.4, seed=0):
    rng = np.random.default_rng(seed)
    Z = rng.normal(size=(n, k))
    A = rng.normal(size=(p, k))
    mu = rng.normal(scale=0.5, size=p)
    X = mu[None, :] + Z @ A.T + rng.normal(scale=noise, size=(n, p))
    mask = rng.random((n, p)) < missing
    Xm = X.copy()
    Xm[mask] = np.nan
    return Xm, X, mu


def test_recovers_planted_structure_with_missingness():
    Xm, X_true, _ = _planted_low_rank()
    fit = fit_pca_em(Xm, k=2)
    assert fit.converged
    # 観測+欠測の全セルで再構成が真値に近い (列平均ベースラインより大幅に良い)
    recon = fit.reconstruct()
    err = np.nanmean((recon - X_true) ** 2)
    baseline = np.nanmean((np.nanmean(Xm, axis=0)[None, :] - X_true) ** 2)
    assert err < 0.1 * baseline
    # 惑星構造 (k=2) は mu 条件付け後分散のほぼ全てを説明する
    assert fit.explained_share > 0.9


def test_monoculture_index_contrast():
    # 共有因子あり vs 独立ノイズのみ — 指標は前者で高く後者で低い
    Xm_shared, _, _ = _planted_low_rank(noise=0.1)
    rng = np.random.default_rng(1)
    X_noise = rng.normal(size=(60, 200))
    X_noise[rng.random((60, 200)) < 0.4] = np.nan
    idx_shared = monoculture_index(fit_pca_em(Xm_shared, k=2))
    idx_noise = monoculture_index(fit_pca_em(X_noise, k=2))
    assert idx_shared > 0.9
    assert idx_noise < 0.5
    assert idx_shared > idx_noise + 0.4


def test_accepts_decision_matrix_and_validates_k():
    dm = DecisionMatrix.from_long(
        [(f"m{i}", f"p{j}", float((-1) ** (i + j))) for i in range(6) for j in range(8)]
    )
    fit = fit_pca_em(dm, k=1)
    assert fit.scores.shape == (6, 1) and fit.loadings.shape == (8, 1)
    with pytest.raises(ValueError, match="out of range"):
        fit_pca_em(dm, k=7)
