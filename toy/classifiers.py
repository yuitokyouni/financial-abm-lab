"""classifiers — SF classifier(LR + 1D-CNN)と IR classifier(GBDT)(spec §6, §9)。

SF 等価性の operational definition(§6 末尾): 両 SF classifier で T-vs-H の 5-fold CV
accuracy が 50-55%。本モジュールはその測定器。

**grouped CV について(severity review 2026-06-13)**: 入力は **1 run = 1 サンプル**
(SF feature は run ごとに 1 ベクトル、CNN は run ごとに 1 return 窓)。同一 run の窓が
fold を跨ぐ leakage は構造的に起きない(StratifiedKFold が run 単位で分割)。複数窓/run を
切る設計に拡張する場合は GroupKFold(group=run)へ切り替えること。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

Features = npt.NDArray[np.float64]
Labels = npt.NDArray[np.int64]


def sf_summary_cv_accuracy(
    features: Features, labels: Labels, *, n_splits: int = 5, seed: int = 0
) -> float:
    """SF1-4 feature ベクトルで T-vs-H を L2-LR、stratified 5-fold CV、平均 accuracy(§6.1)。

    fold ごとに StandardScaler を train で fit(leakage 防止)。各サンプル = 1 run。
    """
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    if x.ndim != 2:
        raise ValueError("features は (n_samples, n_features) の 2 次元であること")
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs: list[float] = []
    for tr, te in skf.split(x, y):
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=1000),  # 既定 L2 正則化(§6.1)
        )
        clf.fit(x[tr], y[tr])
        accs.append(float((clf.predict(x[te]) == y[te]).mean()))
    return float(np.mean(accs))


def sf_cnn_cv_accuracy(
    returns: Features,
    labels: Labels,
    *,
    n_splits: int = 5,
    seed: int = 0,
    epochs: int = 20,
    batch_size: int = 32,
    lr: float = 1e-3,
) -> float:
    """生 log-return 窓で T-vs-H を 1D-CNN、stratified 5-fold CV、平均 accuracy(§6.2)。

    入力 returns: (n_samples, T_d)。3 層 1D-CNN(kernel 5, channels [16,32,64])+ global
    average pooling + 2-class head(spec §6.2)。標準化は train の global mean/std で行い
    test に適用(窓間の volatility scale 差は識別情報なので per-window 標準化はしない)。
    決定的(torch.manual_seed を fold ごとに固定)。
    """
    import torch
    from torch import nn

    x = np.asarray(returns, dtype=np.float32)
    y = np.asarray(labels, dtype=np.int64)
    if x.ndim != 2:
        raise ValueError("returns は (n_samples, T_d) の 2 次元であること")

    def _build() -> nn.Module:
        return nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(64, 2),
        )

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs: list[float] = []
    for fold, (tr, te) in enumerate(skf.split(x, y)):
        torch.manual_seed(seed + fold)
        mu = float(x[tr].mean())
        sd = float(x[tr].std()) or 1.0
        xt = torch.from_numpy((x[tr] - mu) / sd).unsqueeze(1)
        xe = torch.from_numpy((x[te] - mu) / sd).unsqueeze(1)
        yt = torch.from_numpy(y[tr])
        ye = torch.from_numpy(y[te])

        model = _build()
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        loss_fn = nn.CrossEntropyLoss()
        gen = torch.Generator().manual_seed(seed + fold)
        n = xt.shape[0]
        best_state, best_val = None, -1.0
        for _ in range(epochs):
            model.train()
            perm = torch.randperm(n, generator=gen)
            for b in range(0, n, batch_size):
                idx = perm[b : b + batch_size]
                opt.zero_grad()
                loss = loss_fn(model(xt[idx]), yt[idx])
                loss.backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                val = float((model(xe).argmax(1) == ye).float().mean())
            if val > best_val:
                best_val, best_state = val, {k: v.clone() for k, v in model.state_dict().items()}
        if best_state is not None:
            model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            accs.append(float((model(xe).argmax(1) == ye).float().mean()))
    return float(np.mean(accs))


def ir_classifier_cv_accuracy(
    features: Features, labels: Labels, *, n_splits: int = 5, seed: int = 0
) -> float:
    """susceptibility curve feature で T-vs-H を GBDT、stratified 5-fold CV、平均 accuracy(§9)。

    各サンプル = 1 run の susceptibility 特徴ベクトル(spec §8.3 の f1-f4 × Y × 軸 × scheme)。
    """
    from xgboost import XGBClassifier

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    if x.ndim != 2:
        raise ValueError("features は (n_samples, n_features) の 2 次元であること")
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs: list[float] = []
    for fold, (tr, te) in enumerate(skf.split(x, y)):
        clf = XGBClassifier(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=seed + fold,
            eval_metric="logloss",
        )
        clf.fit(x[tr], y[tr])
        accs.append(float((clf.predict(x[te]) == y[te]).mean()))
    return float(np.mean(accs))


def sf_classifier_cv_accuracy(features: Features, labels: Labels) -> float:
    """後方互換 alias: SF summary(LR)classifier(§6.1)。"""
    return sf_summary_cv_accuracy(features, labels)
