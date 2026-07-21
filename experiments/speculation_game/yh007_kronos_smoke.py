"""YH007 smoke — Kronos weights 取得 + CPU 推論レイテンシの再現可能計測。

spec 002 §6 のインフラ実測値 (HF API ✓, Kronos weights ✓, CPU 推論レイテンシ) を
誰でも追試できるようにする確認スクリプト。YH007-1 (aggregate) 実装の前段。

前提: Kronos リポ (shiyu-coder/Kronos, master) をローカルに展開し、`KRONOS_PATH`
で場所を指定する。pip-installable ではないので PYTHONPATH 経由で参照する。

実行:
    git clone https://github.com/shiyu-coder/Kronos.git /tmp/Kronos
    KRONOS_PATH=/tmp/Kronos uv run python -m experiments.speculation_game.yh007_kronos_smoke

合格基準:
    - Tokenizer + Kronos-small が HF からロード成功
    - CPU 推論 (pred_len=1, lookback=128, sample_count=1) が完了
    - latency 値を表示 (spec §7 地雷 4 の計算量見積もりに使う)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
import torch


def _ensure_kronos_on_path() -> None:
    path = os.environ.get("KRONOS_PATH")
    if not path:
        raise SystemExit(
            "KRONOS_PATH 未設定。`git clone https://github.com/shiyu-coder/Kronos.git <path>` "
            "してから `KRONOS_PATH=<path>` を渡して再実行。"
        )
    if not os.path.isdir(os.path.join(path, "model")):
        raise SystemExit(f"KRONOS_PATH={path} に model/ が無い。Kronos リポではない可能性。")
    sys.path.insert(0, path)


def _synthetic_ohlcva(n: int, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-06-01 09:00", periods=n, freq="min")
    close = 100.0 + np.cumsum(rng.normal(0, 0.05, n))
    high = close + rng.uniform(0, 0.2, n)
    low = close - rng.uniform(0, 0.2, n)
    op = close + rng.normal(0, 0.05, n)
    vol = rng.uniform(100, 1000, n)
    amt = vol * close
    df = pd.DataFrame({
        "open": op, "high": high, "low": low, "close": close,
        "volume": vol, "amount": amt,
    })
    return df, pd.Series(ts)


def run_smoke(lookback: int, sample_counts: list[int], threads: int) -> None:
    _ensure_kronos_on_path()
    torch.set_num_threads(threads)
    from model import Kronos, KronosPredictor, KronosTokenizer

    t0 = time.time()
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    t_tok = time.time() - t0
    t0 = time.time()
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    t_mod = time.time() - t0
    n_params = sum(p.numel() for p in model.parameters())
    dtype = next(model.parameters()).dtype
    print(f"[load] tokenizer={t_tok:.2f}s  model={t_mod:.2f}s  params={n_params/1e6:.2f}M  dtype={dtype}")

    predictor = KronosPredictor(model, tok, device="cpu", max_context=512)
    pred_len = 1

    df, ts = _synthetic_ohlcva(lookback + pred_len, seed=0)
    x_df = df.iloc[:lookback][["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
    x_ts = pd.Series(ts.iloc[:lookback].to_list())
    y_ts = pd.Series(ts.iloc[lookback:lookback + pred_len].to_list())

    _ = predictor.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                          pred_len=pred_len, T=1.0, top_p=0.9, sample_count=1, verbose=False)

    for sc in sample_counts:
        t0 = time.time()
        pred = predictor.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                                 pred_len=pred_len, T=1.0, top_p=0.9, sample_count=sc, verbose=False)
        dt = time.time() - t0
        print(f"[predict] threads={threads}  lookback={lookback}  pred_len={pred_len}  "
              f"sample_count={sc:>3}  dt={dt:.3f}s  pred.shape={tuple(pred.shape)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--lookback", type=int, default=128)
    p.add_argument("--sample-counts", type=int, nargs="+", default=[1, 4, 16])
    p.add_argument("--threads", type=int, default=4)
    args = p.parse_args()
    run_smoke(lookback=args.lookback, sample_counts=args.sample_counts, threads=args.threads)
