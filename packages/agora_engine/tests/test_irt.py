import numpy as np

from agora_engine import fit_pca_em
from agora_engine.factor_model import fit_irt


def _synthetic_2pl(n=60, p=300, missing=0.4, seed=0):
    rng = np.random.default_rng(seed)
    theta = rng.normal(size=n)
    a = rng.uniform(0.5, 2.0, size=p) * rng.choice([1, -1], size=p, p=[0.8, 0.2])
    d = rng.normal(scale=0.7, size=p)
    prob = 1 / (1 + np.exp(-(theta[:, None] * a[None, :] + d[None, :])))
    X = np.where(rng.random((n, p)) < prob, 1.0, -1.0)
    X[rng.random((n, p)) < missing] = np.nan
    return X, theta


def test_irt_recovers_planted_theta_with_missingness():
    X, theta_true = _synthetic_2pl()
    fit = fit_irt(X)
    assert fit.converged
    r = np.corrcoef(fit.theta, theta_true)[0, 1]
    assert abs(r) > 0.9
    # 識別制約: 標準化と符号固定
    assert abs(fit.theta.mean()) < 1e-6 and abs(fit.theta.std() - 1.0) < 1e-6
    assert fit.slope.sum() >= 0


def test_route_a_and_b_agree_on_same_data():
    """ルートA (PCA-EM) とルートB (IRT) のスコアが同一データで整合すること (頑健性比較の骨格)。"""
    X, _ = _synthetic_2pl(seed=3)
    za = fit_pca_em(X, k=1).scores[:, 0]
    zb = fit_irt(X).theta
    assert abs(np.corrcoef(za, zb)[0, 1]) > 0.85
