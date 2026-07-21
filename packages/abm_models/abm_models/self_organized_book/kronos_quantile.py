"""Kronos quantile sampling — `auto_regressive_inference` を fork して raw N サンプルを取り出す。

spec 003 §3.6: agent ごとに Kronos 分布の **別 quantile** を評価値とする。素の `KronosPredictor`
は `auto_regressive_inference` 内で `np.mean(preds, axis=1)` で sample_count 軸を強制平均
するため raw が取れない (ソース確認: shiyu-coder/Kronos master の model/kronos.py:472)。

本モジュールは mean しない版を実装し、`predict_quantile_closes(history, n_samples)` で
shape `(n_samples,)` の close 配列を返す (各要素 = sample_count 個のうち i 番目の独立サンプル)。
これを quantile_rank に sort して agent_id にひも付ける。

依存: `shiyu-coder/Kronos` リポを `KRONOS_PATH` 経由で sys.path に置くことを期待。
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd


def _ensure_kronos_on_path(kronos_path: Optional[str] = None) -> None:
    path = kronos_path or os.environ.get("KRONOS_PATH")
    if not path:
        raise RuntimeError(
            "KRONOS_PATH 未設定。`git clone https://github.com/shiyu-coder/Kronos.git <path>` "
            "してから `KRONOS_PATH=<path>` を渡して再実行。"
        )
    if not os.path.isdir(os.path.join(path, "model")):
        raise RuntimeError(f"KRONOS_PATH={path} に model/ が無い。")
    if path not in sys.path:
        sys.path.insert(0, path)


def _auto_regressive_inference_raw(
    tokenizer, model, x, x_stamp, y_stamp, max_context, pred_len,
    clip=5, T=1.0, top_k=0, top_p=0.99, sample_count=5,
):
    """`auto_regressive_inference` (shiyu-coder/Kronos master) の fork、mean せず raw を返す。

    Returns
    -------
    preds : np.ndarray, shape (sample_count, total_seq_len, n_features=6)
        x の長さ分の context + pred_len の予測列。呼び出し側で `[:, -pred_len:, :]` を取る。
    """
    import torch
    from model.kronos import sample_from_logits

    with torch.no_grad():
        x = torch.clip(x, -clip, clip)
        device = x.device
        x = x.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, x.size(1), x.size(2)).to(device)
        x_stamp = x_stamp.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, x_stamp.size(1), x_stamp.size(2)).to(device)
        y_stamp = y_stamp.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, y_stamp.size(1), y_stamp.size(2)).to(device)

        x_token = tokenizer.encode(x, half=True)
        initial_seq_len = x.size(1)
        batch_size = x_token[0].size(0)
        total_seq_len = initial_seq_len + pred_len
        full_stamp = torch.cat([x_stamp, y_stamp], dim=1)

        generated_pre = x_token[0].new_empty(batch_size, pred_len)
        generated_post = x_token[1].new_empty(batch_size, pred_len)
        pre_buffer = x_token[0].new_zeros(batch_size, max_context)
        post_buffer = x_token[1].new_zeros(batch_size, max_context)
        buffer_len = min(initial_seq_len, max_context)
        if buffer_len > 0:
            start_idx = max(0, initial_seq_len - max_context)
            pre_buffer[:, :buffer_len] = x_token[0][:, start_idx:start_idx + buffer_len]
            post_buffer[:, :buffer_len] = x_token[1][:, start_idx:start_idx + buffer_len]

        for i in range(pred_len):
            current_seq_len = initial_seq_len + i
            window_len = min(current_seq_len, max_context)
            context_end = current_seq_len
            context_start = max(0, context_end - max_context)
            if current_seq_len <= max_context:
                input_tokens = [
                    pre_buffer[:, :window_len],
                    post_buffer[:, :window_len],
                ]
            else:
                input_tokens = [pre_buffer, post_buffer]
            current_stamp = full_stamp[:, context_start:context_end, :].contiguous()

            s1_logits, context = model.decode_s1(input_tokens[0], input_tokens[1], current_stamp)
            s1_logits = s1_logits[:, -1, :]
            sample_pre = sample_from_logits(s1_logits, temperature=T, top_k=top_k, top_p=top_p, sample_logits=True)
            s2_logits = model.decode_s2(context, sample_pre)
            s2_logits = s2_logits[:, -1, :]
            sample_post = sample_from_logits(s2_logits, temperature=T, top_k=top_k, top_p=top_p, sample_logits=True)

            generated_pre[:, i] = sample_pre.squeeze(-1)
            generated_post[:, i] = sample_post.squeeze(-1)
            if current_seq_len < max_context:
                pre_buffer[:, current_seq_len] = sample_pre.squeeze(-1)
                post_buffer[:, current_seq_len] = sample_post.squeeze(-1)
            else:
                pre_buffer.copy_(torch.roll(pre_buffer, shifts=-1, dims=1))
                post_buffer.copy_(torch.roll(post_buffer, shifts=-1, dims=1))
                pre_buffer[:, -1] = sample_pre.squeeze(-1)
                post_buffer[:, -1] = sample_post.squeeze(-1)

        full_pre = torch.cat([x_token[0], generated_pre], dim=1)
        full_post = torch.cat([x_token[1], generated_post], dim=1)
        context_start = max(0, total_seq_len - max_context)
        input_tokens = [
            full_pre[:, context_start:total_seq_len].contiguous(),
            full_post[:, context_start:total_seq_len].contiguous(),
        ]
        z = tokenizer.decode(input_tokens, half=True)
        z = z.reshape(-1, sample_count, z.size(1), z.size(2))
        return z.cpu().numpy()  # shape (1, sample_count, total_seq_len, n_features)


@dataclass
class KronosQuantilePredictor:
    """1 回の autoregressive forward で N quantile close を取り出すラッパー。

    spec 003 §3.6 + §10-4 (バッチ化): agent ごとに別 quantile を渡すために、
    1 hub に共有して 1 回 predict すれば全 agent 分が揃う構造。
    """
    lookback: int = 64
    n_samples: int = 32
    temperature: float = 1.0
    top_p: float = 0.9
    max_context: int = 512
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-base"
    model_name: str = "NeoQuasar/Kronos-small"
    device: str = "cpu"
    kronos_path: Optional[str] = None
    threads: int = 4
    last_call_dt: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        _ensure_kronos_on_path(self.kronos_path)
        import torch
        torch.set_num_threads(self.threads)
        from model import Kronos, KronosTokenizer  # type: ignore
        self._tok = KronosTokenizer.from_pretrained(self.tokenizer_name)
        self._model = Kronos.from_pretrained(self.model_name)
        self._clip = 5
        # warmup (1 サンプル) — 初回の torch トレース・コンパイル分の遅延を払い切る
        self._warmup()

    def _warmup(self) -> None:
        n = self.lookback
        ts = pd.date_range("2026-06-01 09:00", periods=n + 1, freq="min")
        rng = np.random.default_rng(0)
        close = 100.0 + np.cumsum(rng.normal(0, 0.05, n + 1))
        df = pd.DataFrame({
            "open": close + 0.02, "high": close + 0.1, "low": close - 0.1,
            "close": close, "volume": np.full(n + 1, 100.0),
            "amount": np.full(n + 1, 100.0) * close,
        })
        _ = self.predict_quantile_closes(
            df.iloc[:n].reset_index(drop=True),
            pd.Series(ts[:n]), pd.Series(ts[n:n + 1]),
        )

    def predict_quantile_closes(
        self, history_df: pd.DataFrame,
        x_timestamp: pd.Series, y_timestamp: pd.Series,
    ) -> np.ndarray:
        """1 回の autoregressive forward で n_samples 個の close を取り出し、昇順 sort で返す。

        Returns
        -------
        closes_sorted : np.ndarray, shape (n_samples,)
            昇順 sort 済の close サンプル。`closes_sorted[k]` = quantile rank k/(n_samples-1) の close。
        """
        import torch
        from model.kronos import calc_time_stamps

        x = history_df[["open", "high", "low", "close", "volume", "amount"]].values.astype(np.float32)
        x_mean = np.mean(x, axis=0)
        x_std = np.std(x, axis=0)
        x_norm = np.clip((x - x_mean) / (x_std + 1e-5), -self._clip, self._clip)[np.newaxis, :]
        x_stamp = calc_time_stamps(x_timestamp).values.astype(np.float32)[np.newaxis, :]
        y_stamp = calc_time_stamps(y_timestamp).values.astype(np.float32)[np.newaxis, :]

        x_t = torch.from_numpy(x_norm).to(self.device)
        x_stamp_t = torch.from_numpy(x_stamp).to(self.device)
        y_stamp_t = torch.from_numpy(y_stamp).to(self.device)

        t0 = time.time()
        preds = _auto_regressive_inference_raw(
            self._tok, self._model, x_t, x_stamp_t, y_stamp_t,
            self.max_context, pred_len=1, clip=self._clip,
            T=self.temperature, top_k=0, top_p=self.top_p,
            sample_count=self.n_samples,
        )
        self.last_call_dt = time.time() - t0
        # preds shape: (1, n_samples, total_seq_len, 6) — 最後の time step の close 列
        preds_last = preds[0, :, -1, :] * (x_std + 1e-5) + x_mean  # (n_samples, 6)
        closes = preds_last[:, 3]
        return np.sort(closes)


def quantile_to_eval(closes_sorted: np.ndarray, agent_rank: float) -> float:
    """agent_rank ∈ [0, 1] を closes_sorted の対応 quantile に変換。

    線形補間で N サンプルから連続値を取り出す。
    """
    n = closes_sorted.size
    if n == 0:
        return float("nan")
    if n == 1:
        return float(closes_sorted[0])
    pos = float(np.clip(agent_rank, 0.0, 1.0)) * (n - 1)
    lo = int(np.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(closes_sorted[lo] * (1.0 - frac) + closes_sorted[hi] * frac)
