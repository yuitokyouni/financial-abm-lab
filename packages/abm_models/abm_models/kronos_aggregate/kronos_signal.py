"""shiyu-coder/Kronos の KronosPredictor をラップした SignalProvider。

YH007-1 の閉ループ用。Kronos リポは pip-installable でないため、`KRONOS_PATH`
環境変数で github clone のパスを渡し、`sys.path` 経由で `model.kronos` を import する。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .model import KronosSignal, SignalProvider


def _ensure_kronos_on_path(kronos_path: Optional[str] = None) -> None:
    path = kronos_path or os.environ.get("KRONOS_PATH")
    if not path:
        raise RuntimeError(
            "KRONOS_PATH 未設定。`git clone https://github.com/shiyu-coder/Kronos.git <path>` "
            "してから `KRONOS_PATH=<path>` を渡して再実行。"
        )
    if not os.path.isdir(os.path.join(path, "model")):
        raise RuntimeError(f"KRONOS_PATH={path} に model/ が無い。Kronos リポではない可能性。")
    if path not in sys.path:
        sys.path.insert(0, path)


@dataclass
class KronosPredictorWrapper:
    """KronosPredictor を 1 回ロードして、毎 step 再利用するラッパー。

    `__call__(history)` で SignalProvider プロトコルを満たす。
    """
    lookback: int = 128
    sample_count: int = 4
    temperature: float = 1.0
    top_p: float = 0.9
    max_context: int = 512
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-base"
    model_name: str = "NeoQuasar/Kronos-small"
    device: str = "cpu"
    kronos_path: Optional[str] = None
    threads: int = 4

    def __post_init__(self) -> None:
        _ensure_kronos_on_path(self.kronos_path)
        import torch

        torch.set_num_threads(self.threads)
        from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore

        self._tok = KronosTokenizer.from_pretrained(self.tokenizer_name)
        self._model = Kronos.from_pretrained(self.model_name)
        self._predictor = KronosPredictor(
            self._model, self._tok, device=self.device, max_context=self.max_context
        )

    def __call__(self, history: pd.DataFrame) -> KronosSignal:
        if len(history) < self.lookback:
            raise ValueError(
                f"history が短すぎる: len={len(history)} < lookback={self.lookback}"
            )
        x_df = history.iloc[-self.lookback:][
            ["open", "high", "low", "close", "volume", "amount"]
        ].reset_index(drop=True)
        x_ts = pd.Series(history["timestamps"].iloc[-self.lookback:].to_list())
        # 次バー 1 本の timestamp を仮置き (履歴の周期から推定)
        last_ts = pd.Timestamp(history["timestamps"].iloc[-1])
        dt = last_ts - pd.Timestamp(history["timestamps"].iloc[-2])
        y_ts = pd.Series([last_ts + dt])

        # KronosPredictor.predict(sample_count=K) は K 個の予測 close の平均を返す。
        # YH007-1 では確信度 std は使わない (全員参加) ため、平均のみ取り、std=0 とする。
        # YH007-3 で参加ゲートに確信度を流す段階で sample 分散を取る方式に拡張する (TODO)。
        pred_df = self._predictor.predict(
            df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
            pred_len=1, T=self.temperature, top_p=self.top_p,
            sample_count=self.sample_count, verbose=False,
        )
        return KronosSignal(
            last_close=float(history["close"].iloc[-1]),
            pred_close_mean=float(pred_df["close"].iloc[0]),
            pred_close_std=0.0,
        )


def make_kronos_signal_provider(**kwargs) -> SignalProvider:
    """便利関数。`SignalProvider` として使える wrapper を返す。"""
    return KronosPredictorWrapper(**kwargs)
