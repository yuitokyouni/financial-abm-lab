"""FactorModel — a_ij = mu_j + sum_k lambda_ik f_jk + eps_ij の推定 (YH010_HANDOFF §7-2)。

ルートA: 列平均補完 + 低ランク分解の EM 型反復 (Bubb & Catan 2022 の欠測対応 PCA。
  原典手続きは docs/2026-07-23-YH010g-method-notes-bolton-bubbcatan.md 参照:
  Kiers 1997; Ilin & Raiko 2010; Josse & Husson 2012)。
  1. 欠測を列平均で補完
  2. 補完済み行列を中心化して SVD、上位 k 次元を保持
  3. 欠測セルを mu + Z A' で再補完
  4. 収束まで 2-3 を反復
ルートB (IRT/理想点): Task 5 で実装 (fit_irt はスタブ)。

回転規約: SVD の主軸をそのまま使う (分散最大・直交)。成分の符号のみ不定であり、
符号の固定・因子の命名は外部照合 (ID-g1 推奨分裂等) でのみ行う — 推定器は関知しない。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from agora_engine.decision_matrix import DecisionMatrix


@dataclass
class FactorFit:
    scores: np.ndarray        # Z: (N, k) 主体スコア (= ideal points / 地図への追随度 lambda)
    loadings: np.ndarray      # A: (P, k) インスタンス側ローディング (= 地図因子 f)
    col_means: np.ndarray     # mu_j: (P,) 列平均 (議案の共通ファンダメンタルズの第一近似)
    k: int
    n_iter: int
    converged: bool
    sse_observed: float       # 観測セル上の残差二乗和
    sst_centered: float       # 観測セル上の (x_ij - mu_j)^2 の和

    def reconstruct(self) -> np.ndarray:
        return self.col_means[None, :] + self.scores @ self.loadings.T

    @property
    def explained_share(self) -> float:
        """観測セル・mu 条件付け後の分散のうち因子が説明するシェア。
        モノカルチャー指標の実体 (monoculture.py が唯一の公開窓口)。"""
        if self.sst_centered <= 0:
            return 0.0
        return 1.0 - self.sse_observed / self.sst_centered


def fit_pca_em(
    dm: DecisionMatrix | np.ndarray,
    k: int,
    max_iter: int = 200,
    tol: float = 1e-6,
    seed: int | None = None,
) -> FactorFit:
    """欠測対応 PCA (ルートA)。dm は DecisionMatrix か NaN 入り 2D 配列。

    seed は将来のランダム初期化用に予約 (現行は決定論的な列平均初期化のみ)。
    """
    X = dm.values if isinstance(dm, DecisionMatrix) else np.asarray(dm, dtype=float)
    if X.ndim != 2:
        raise ValueError("expected 2D matrix")
    n, p = X.shape
    if k < 1 or k > min(n, p):
        raise ValueError(f"k={k} out of range for shape {X.shape}")
    obs = ~np.isnan(X)
    if obs.sum() == 0:
        raise ValueError("no observed cells")

    # 1. 列平均補完 (全欠測列は 0)
    col_means = np.zeros(p)
    for j in range(p):
        col = X[obs[:, j], j]
        col_means[j] = col.mean() if len(col) else 0.0
    Xc = np.where(obs, X, col_means[None, :])

    prev_imputed = Xc[~obs].copy()
    n_iter = 0
    converged = False
    Z = np.zeros((n, k))
    A = np.zeros((p, k))
    for n_iter in range(1, max_iter + 1):
        # 2. 中心化して truncated SVD
        mu = Xc.mean(axis=0)
        U, s, Vt = np.linalg.svd(Xc - mu[None, :], full_matrices=False)
        Z = U[:, :k] * s[:k][None, :]
        A = Vt[:k, :].T
        recon = mu[None, :] + Z @ A.T
        # 3. 欠測セルのみ再補完
        Xc = np.where(obs, X, recon)
        imputed = Xc[~obs]
        if len(imputed) == 0:
            converged = True
            col_means = mu
            break
        delta = float(np.max(np.abs(imputed - prev_imputed))) if len(imputed) else 0.0
        prev_imputed = imputed.copy()
        col_means = mu
        if delta < tol:
            converged = True
            break

    resid = X - (col_means[None, :] + Z @ A.T)
    sse = float(np.nansum(np.where(obs, resid, 0.0) ** 2))
    centered = np.where(obs, X - col_means[None, :], 0.0)
    sst = float((centered ** 2).sum())
    return FactorFit(
        scores=Z, loadings=A, col_means=col_means, k=k,
        n_iter=n_iter, converged=converged,
        sse_observed=sse, sst_centered=sst,
    )


@dataclass
class IrtFit:
    theta: np.ndarray      # (N,) 主体の理想点 (平均0・分散1に標準化)
    slope: np.ndarray      # (P,) 識別力 a_j
    intercept: np.ndarray  # (P,) 切片 d_j (P(+1)=sigmoid(a_j*theta_i + d_j))
    n_iter: int
    converged: bool


def fit_irt(
    dm: DecisionMatrix | np.ndarray,
    max_iter: int = 100,
    tol: float = 1e-4,
    l2: float = 1.0,
    inner_newton: int = 3,
) -> IrtFit:
    """ルートB: 1次元 2パラメータ・ロジスティック IRT (交互 MAP 推定)。

    ±1 の二値投票を y=(x+1)/2 に変換し P(y=1)=sigmoid(a_j*theta + d_j) を推定。
    識別制約 (docstring 冒頭の回転規約に対応):
      - 尺度: theta を各反復で平均0・分散1に標準化
      - 符号: sum(a_j) >= 0 に固定 (因子の命名・向きの解釈は外部照合でのみ行う)
    事前分布は L2 正則化として実装 (theta, a, d ~ N(0, 1/l2))。
    多次元版・完全ベイズ版は将来 feature。
    """
    X = dm.values if isinstance(dm, DecisionMatrix) else np.asarray(dm, dtype=float)
    obs = ~np.isnan(X)
    if obs.sum() == 0:
        raise ValueError("no observed cells")
    Y = np.where(obs, (X + 1.0) / 2.0, 0.0)  # 欠測セルは重み0で無視
    n, p = X.shape
    rng_free_start = np.where(obs, X, 0.0).mean(axis=1)
    theta = (rng_free_start - rng_free_start.mean())
    sd = theta.std()
    theta = theta / sd if sd > 0 else np.zeros(n)
    a = np.ones(p)
    d = np.zeros(p)

    def sigmoid(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    converged = False
    n_iter = 0
    for n_iter in range(1, max_iter + 1):
        theta_prev = theta.copy()
        # item step: 各 j について (a_j, d_j) を Newton 法で更新 (ベクトル化)
        for _ in range(inner_newton):
            Z = theta[:, None] * a[None, :] + d[None, :]
            P1 = sigmoid(Z)
            W = np.where(obs, P1 * (1 - P1), 0.0)
            R = np.where(obs, Y - P1, 0.0)
            g_a = (R * theta[:, None]).sum(axis=0) - l2 * a
            g_d = R.sum(axis=0) - l2 * d
            h_aa = (W * theta[:, None] ** 2).sum(axis=0) + l2
            h_dd = W.sum(axis=0) + l2
            h_ad = (W * theta[:, None]).sum(axis=0)
            det = h_aa * h_dd - h_ad ** 2
            det = np.where(det < 1e-10, 1e-10, det)
            a = a + (h_dd * g_a - h_ad * g_d) / det
            d = d + (h_aa * g_d - h_ad * g_a) / det
        # person step: 各 i について theta_i を Newton 法で更新 (ベクトル化)
        for _ in range(inner_newton):
            Z = theta[:, None] * a[None, :] + d[None, :]
            P1 = sigmoid(Z)
            W = np.where(obs, P1 * (1 - P1), 0.0)
            R = np.where(obs, Y - P1, 0.0)
            g = (R * a[None, :]).sum(axis=1) - l2 * theta
            h = (W * a[None, :] ** 2).sum(axis=1) + l2
            theta = theta + g / h
        # 識別制約: 標準化 + 符号固定 (a を尺度に合わせて逆スケール)
        mu_t, sd_t = theta.mean(), theta.std()
        if sd_t > 0:
            theta = (theta - mu_t) / sd_t
            d = d + a * mu_t
            a = a * sd_t
        if a.sum() < 0:
            theta, a = -theta, -a
        if np.max(np.abs(theta - theta_prev)) < tol:
            converged = True
            break
    return IrtFit(theta=theta, slope=a, intercept=d, n_iter=n_iter, converged=converged)
