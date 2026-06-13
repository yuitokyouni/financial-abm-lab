"""band_analyses — ワーキングペーパー3案の数値を再現(再設計 P1)。

案1: batch interval dose-response(price-reader A vs orderflow-reader B)。
案2: 学習(adaptive)vs 固定(A)。
案3: microstructure(注文流)facts vs return-distribution facts。

すべて `toy/channel_band.py` 上。識別精度 = SF1-4 の LR / 生系列の 1D-CNN の 5-fold CV accuracy。

実行: uv run python -m experiments.runners.band_analyses
"""

from __future__ import annotations

import argparse

import numpy as np
from toy.channel_band import simulate
from toy.classifiers import sf_cnn_cv_accuracy, sf_summary_cv_accuracy
from toy.sf_battery import CALIBRATION_SF, _acf, measure_sf_battery

T_D = 300


def _sf_ret(b: np.ndarray) -> list[float]:
    if b.size < 50:
        b = np.concatenate([b, np.zeros(50 - b.size)])
    s = measure_sf_battery(b, include_post=False)
    return [s[k] for k in CALIBRATION_SF]


def _micro_facts(f: np.ndarray) -> list[float]:
    """注文流の microstructure facts: ボラ・ACF(lag1)・|flow|ACF・尖度。"""
    f = np.asarray(f, dtype=np.float64)
    return [
        float(f.std()),
        float(_acf(f, 1)),
        float(_acf(np.abs(f), 1)),
        float(((f - f.mean()) ** 4).mean() / (f.std() ** 4 + 1e-12) - 3.0),
    ]


def _window(b: np.ndarray) -> np.ndarray:
    return b[-T_D:] if b.size >= T_D else np.concatenate([np.zeros(T_D - b.size), b])


def _discriminate_returns(
    model_a: str, model_b: str, batch: int, m: int, base: int, cnn_epochs: int
) -> tuple[float, float]:
    """2 モデルの batch-return 系列を LR(SF1-4)/ CNN で識別。"""
    asf, aret, bsf, bret = [], [], [], []
    for i in range(m):
        ba = simulate(model_a, batch, base + i)
        bb = simulate(model_b, batch, base + i)
        asf.append(_sf_ret(ba))
        bsf.append(_sf_ret(bb))
        aret.append(_window(ba))
        bret.append(_window(bb))
    y = np.concatenate([np.zeros(m, int), np.ones(m, int)])
    lr = sf_summary_cv_accuracy(np.vstack([asf, bsf]), y, seed=1)
    cnn = sf_cnn_cv_accuracy(np.vstack([aret, bret]), y, seed=1, epochs=cnn_epochs)
    return lr, cnn


def _discriminate_factsets(batch: int, m: int, base: int) -> tuple[float, float]:
    """案3: A vs B を return facts と microstructure facts で別々に LR 識別。"""
    rfa, rfb, mfa, mfb = [], [], [], []
    for i in range(m):
        ba, fa = simulate("A", batch, base + i, with_flow=True)
        bb, fb = simulate("B", batch, base + i, with_flow=True)
        rfa.append(_sf_ret(ba))
        rfb.append(_sf_ret(bb))
        mfa.append(_micro_facts(fa))
        mfb.append(_micro_facts(fb))
    y = np.concatenate([np.zeros(m, int), np.ones(m, int)])
    lr_ret = sf_summary_cv_accuracy(np.vstack([rfa, rfb]), y, seed=1)
    lr_mic = sf_summary_cv_accuracy(np.vstack([mfa, mfb]), y, seed=1)
    return lr_ret, lr_mic


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", type=int, default=60)
    ap.add_argument("--cnn-epochs", type=int, default=15)
    args = ap.parse_args()

    print("=== 案1: batch dose-response (A=price vs B=orderflow) ===")
    print(f"{'N':>4} | {'LR':>6} {'CNN':>6}")
    for n in (1, 2, 5, 10, 20):
        lr, cnn = _discriminate_returns("A", "B", n, args.m, 1000, args.cnn_epochs)
        print(f"{n:>4} | {lr:>6.3f} {cnn:>6.3f}")

    print("\n=== 案2: 学習(adaptive) vs 固定(A) ===")
    print(f"{'N':>4} | {'LR':>6} {'CNN':>6}")
    for n in (1, 10, 20):
        lr, cnn = _discriminate_returns("A", "adaptive", n, args.m, 2000, args.cnn_epochs)
        print(f"{n:>4} | {lr:>6.3f} {cnn:>6.3f}")

    print("\n=== 案3: return facts vs microstructure facts (A vs B 分離、LR) ===")
    print(f"{'N':>4} | {'return':>8} {'micro':>8}")
    for n in (1, 2, 5, 10):
        rr, mm = _discriminate_factsets(n, args.m, 3000)
        print(f"{n:>4} | {rr:>8.3f} {mm:>8.3f}")


if __name__ == "__main__":
    main()
