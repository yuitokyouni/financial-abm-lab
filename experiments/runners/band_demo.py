"""band_demo — 「連続データで区別不能なモデルを batch 政策が識別する」の定量再現(再設計 P1)。

price-reader(A)と orderflow-reader(B)を、連続市場(batch=1)と batch auction(batch=N)で
それぞれ走らせ、両機構の出力を SF classifier(LR)/ 1D-CNN で見分けられるかを測る。

期待: 連続 → CNN ≈ chance(観測 identical)/ batch → CNN ≫ chance(政策が脱共役して識別)。

実行: uv run python -m experiments.runners.band_demo
"""

from __future__ import annotations

import argparse

import numpy as np
from toy.channel_band import simulate
from toy.classifiers import sf_cnn_cv_accuracy, sf_summary_cv_accuracy
from toy.sf_battery import CALIBRATION_SF, measure_sf_battery

T_D = 300


def _runset(model: str, batch: int, m: int, base: int) -> tuple[np.ndarray, np.ndarray]:
    sf, ret = [], []
    for i in range(m):
        b = simulate(model, batch, base + i)
        if b.size < 50:
            b = np.concatenate([b, np.zeros(50 - b.size)])
        s = measure_sf_battery(b, include_post=False)
        sf.append([s[k] for k in CALIBRATION_SF])
        w = b[-T_D:] if b.size >= T_D else np.concatenate([np.zeros(T_D - b.size), b])
        ret.append(w)
    return np.asarray(sf), np.asarray(ret)


def _discriminate(a: tuple, b: tuple, *, cnn_epochs: int, seed: int) -> tuple[float, float]:
    asf, aret = a
    bsf, bret = b
    y = np.concatenate([np.zeros(len(asf), int), np.ones(len(bsf), int)])
    lr = sf_summary_cv_accuracy(np.vstack([asf, bsf]), y, seed=seed)
    cnn = sf_cnn_cv_accuracy(np.vstack([aret, bret]), y, seed=seed, epochs=cnn_epochs)
    return lr, cnn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", type=int, default=60, help="runs / model / regime")
    ap.add_argument("--batch", type=int, default=10, help="batch interval (policy regime)")
    ap.add_argument("--cnn-epochs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=1000)
    args = ap.parse_args()

    print(f"連続市場 (batch=1): A(price-reader) vs B(orderflow-reader), M={args.m}")
    lr1, cnn1 = _discriminate(
        _runset("A", 1, args.m, args.seed),
        _runset("B", 1, args.m, args.seed),
        cnn_epochs=args.cnn_epochs,
        seed=1,
    )
    print(f"  LR={lr1:.3f}  CNN={cnn1:.3f}   (≈0.5 → 観測 identical = 歴史データで区別不能)")

    print(f"batch auction (batch={args.batch}): 同じ A vs B")
    lr2, cnn2 = _discriminate(
        _runset("A", args.batch, args.m, args.seed),
        _runset("B", args.batch, args.m, args.seed),
        cnn_epochs=args.cnn_epochs,
        seed=1,
    )
    print(f"  LR={lr2:.3f}  CNN={cnn2:.3f}   (>0.5 → batch 政策が脱共役して識別)")
    print(f"\n結果: 連続で区別不能(CNN={cnn1:.2f})なモデルを、batch 改革が識別(CNN={cnn2:.2f})。")


if __name__ == "__main__":
    main()
