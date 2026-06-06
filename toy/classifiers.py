"""classifiers — SF classifier(LR + 1D-CNN)と IR classifier(XGBoost)(spec §6, §9)。

**scaffold のみ。** SF classifier は Week3、IR classifier は Week6。等価性検証(留保解決)に
依存するため、signature だけ置く。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def sf_classifier_cv_accuracy(
    features: npt.NDArray[np.float64], labels: npt.NDArray[np.int64]
) -> float:
    """SF feature(または生 return)で T-vs-H を 5-fold CV、accuracy を返す(Week3)。"""
    raise NotImplementedError("awaiting Week3: SF classifier(LR / 1D-CNN、spec §6)")


def ir_classifier_cv_accuracy(
    features: npt.NDArray[np.float64], labels: npt.NDArray[np.int64]
) -> float:
    """susceptibility curve feature で T-vs-H を 5-fold CV、accuracy を返す(Week6)。"""
    raise NotImplementedError("awaiting Week6: IR classifier(XGBoost / LR、spec §9)")
