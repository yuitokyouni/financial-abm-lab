"""preference — learn `feature_vector -> user preference` and propose next labels.

Three pieces, all NumPy-only:

  PreferenceModel   ridge regression (closed-form). Returns predicted preference
                    μ(x) and a crude uncertainty σ(x) (residual RMSE on the
                    training set, constant across x — adequate for cold start;
                    swap for a Gaussian-process regressor when label counts
                    justify it).

  novelty_score     Lehman & Stanley (2008) novelty: distance to the k-nearest
                    *already-labeled* point in standardised feature space.
                    Large => the point is in a region the user has not yet
                    expressed an opinion about.

  ucb_acquisition   the standard Upper Confidence Bound (Auer 2002, also used in
                    Bayesian optimisation, Srinivas et al. 2010):
                        a(x) = μ(x) + κ·σ(x) + λ·novelty(x)
                    `κ` trades exploration against exploitation of the
                    preference model; `λ` trades novelty against preference.

`propose_next_k` is the convenience driver: fit the model on the labeled set,
score every unlabeled candidate, return the top-k rows by acquisition value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .fingerprint import standardize


@dataclass
class PreferenceModel:
    """Ridge regression on the (standardised) feature vector.

    Stored state:
      mean_, std_  : feature-wise standardisation from the training data
      w_           : (d+1,) weights, last entry is the bias term
      residual_std_: scalar σ used as a constant uncertainty estimate
      lam_         : ridge regularisation strength
    """
    lam_: float = 1.0
    mean_: np.ndarray | None = field(default=None, repr=False)
    std_: np.ndarray | None = field(default=None, repr=False)
    w_: np.ndarray | None = field(default=None, repr=False)
    residual_std_: float | None = None
    n_train_: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PreferenceModel":
        """Closed-form ridge regression on standardised features."""
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2 or X.shape[0] != y.shape[0]:
            raise ValueError(f"shape mismatch: X={X.shape}, y={y.shape}")
        n, d = X.shape
        # 標準化 (feature-wise z-score). Fit-time mean/std are stored so predict()
        # applies the same transform.
        self.mean_ = X.mean(axis=0)
        std = X.std(axis=0)
        self.std_ = np.where(std > 0, std, 1.0)
        Xn = (X - self.mean_) / self.std_
        # Augment with bias term — the bias is NOT regularised (standard practice).
        Xa = np.hstack([Xn, np.ones((n, 1))])
        # (X^T X + λ diag(1,...,1,0)) w = X^T y
        A = Xa.T @ Xa
        reg = self.lam_ * np.eye(d + 1)
        reg[-1, -1] = 0.0
        self.w_ = np.linalg.solve(A + reg, Xa.T @ y)
        y_hat = Xa @ self.w_
        # 残差の標本標準偏差 — k(d+1) で自由度補正
        dof = max(1, n - (d + 1))
        self.residual_std_ = float(np.sqrt(((y - y_hat) ** 2).sum() / dof))
        self.n_train_ = int(n)
        return self

    def predict(self, X: np.ndarray, return_std: bool = False):
        """Predict μ(x), optionally with constant σ from training residuals."""
        if self.w_ is None:
            raise RuntimeError("fit() before predict()")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[None, :]
        Xn = (X - self.mean_) / self.std_
        Xa = np.hstack([Xn, np.ones((Xn.shape[0], 1))])
        mu = Xa @ self.w_
        if return_std:
            sigma = np.full(mu.shape, self.residual_std_ if self.residual_std_ else 0.0)
            return mu, sigma
        return mu


def novelty_score(X_query: np.ndarray, X_labeled: np.ndarray, k: int = 3) -> np.ndarray:
    """Mean distance from each query to its k-NN in the labeled set.

    Following Lehman & Stanley (2008): novelty(x) := mean distance to the k
    nearest neighbours in the already-explored archive. We use the existing
    `distance_matrix` so query and archive must share the same feature space
    (i.e. both standardised the same way before calling).

    If the labeled set is empty, novelty is +inf for every query (everything is
    new). If 0 < |labeled| < k, k is clipped to |labeled|.
    """
    X_query = np.asarray(X_query, dtype=float)
    X_labeled = np.asarray(X_labeled, dtype=float)
    if X_query.ndim == 1:
        X_query = X_query[None, :]
    if X_labeled.size == 0:
        return np.full(X_query.shape[0], np.inf)
    k = max(1, min(k, X_labeled.shape[0]))
    diff = X_query[:, None, :] - X_labeled[None, :, :]
    d = np.sqrt(np.nansum(diff ** 2, axis=-1))
    d_sorted = np.sort(d, axis=1)
    return d_sorted[:, :k].mean(axis=1)


def ucb_acquisition(mu: np.ndarray, sigma: np.ndarray, novelty: np.ndarray,
                    kappa: float = 1.0, lam: float = 1.0) -> np.ndarray:
    """Upper Confidence Bound acquisition.

    a(x) = μ(x) + κ·σ(x) + λ·novelty(x).
    κ=0, λ=0 collapses to pure greedy exploitation of the preference model;
    κ large biases toward points the model is uncertain about (in this simple
    ridge model, σ is constant so κ has no effect — kept for API compatibility
    with a future GP regressor).
    λ large biases toward unexplored regions of the feature space.
    """
    return mu + kappa * sigma + lam * novelty


@dataclass
class Proposal:
    row_id: int
    model_name: str
    mu: float
    sigma: float
    novelty: float
    acquisition: float


def propose_next_k(labeled_rows: Sequence[dict], unlabeled_rows: Sequence[dict],
                   k: int = 5, *, lam_ridge: float = 1.0, kappa: float = 1.0,
                   lam_novelty: float = 1.0, knn: int = 3) -> tuple[list[Proposal], PreferenceModel | None]:
    """Fit a preference model on `labeled_rows`, rank `unlabeled_rows`, return top k.

    With fewer than 2 labels we cannot fit a meaningful regressor, so we return
    the k *most novel* rows by Euclidean distance from the labeled point(s)
    (or random if no labels yet — pure exploration cold start).
    """
    # #10: NaN fingerprint 行を除外する。ラベル側に 1 つでも NaN があると
    # standardize → ridge が全 NaN 化し、score の argsort[::-1] で NaN スコア候補が
    # 最優先でラベリングに提示される。候補側の NaN 行も scoring 不能なので落とす。
    labeled_rows = [r for r in labeled_rows if np.all(np.isfinite(r["fingerprint"]))]
    unlabeled_rows = [r for r in unlabeled_rows if np.all(np.isfinite(r["fingerprint"]))]
    if not unlabeled_rows:
        return [], None

    X_lab = np.vstack([r["fingerprint"] for r in labeled_rows]) if labeled_rows else np.empty((0, 0))
    y_lab = np.array([r["preference_label"] for r in labeled_rows], dtype=float) if labeled_rows else np.array([])
    X_unl = np.vstack([r["fingerprint"] for r in unlabeled_rows])

    # standardise jointly so novelty distances live in the same space
    X_all = np.vstack([X_lab, X_unl]) if X_lab.size else X_unl
    X_std, mu_feat, sd_feat = standardize(X_all)
    n_lab = X_lab.shape[0]
    X_lab_std = X_std[:n_lab]
    X_unl_std = X_std[n_lab:]

    novelty = novelty_score(X_unl_std, X_lab_std, k=knn)

    if n_lab >= 2:
        model = PreferenceModel(lam_=lam_ridge).fit(X_lab_std, y_lab)
        mu_pred, sigma_pred = model.predict(X_unl_std, return_std=True)
        score = ucb_acquisition(mu_pred, sigma_pred, novelty, kappa=kappa, lam=lam_novelty)
    else:
        # Cold start: pure novelty.
        model = None
        mu_pred = np.zeros(len(unlabeled_rows))
        sigma_pred = np.zeros(len(unlabeled_rows))
        # Replace +inf with a large finite value so ranking still works
        nov_finite = np.where(np.isfinite(novelty), novelty, novelty[np.isfinite(novelty)].max() + 1.0
                              if np.any(np.isfinite(novelty)) else 1.0)
        score = nov_finite

    order = np.argsort(score)[::-1]
    proposals: list[Proposal] = []
    for idx in order[:k]:
        r = unlabeled_rows[idx]
        proposals.append(Proposal(
            row_id=int(r["id"]), model_name=str(r["model_name"]),
            mu=float(mu_pred[idx]), sigma=float(sigma_pred[idx]),
            novelty=float(novelty[idx]), acquisition=float(score[idx]),
        ))
    return proposals, model
