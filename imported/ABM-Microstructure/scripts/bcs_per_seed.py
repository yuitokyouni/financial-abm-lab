"""US4 較正セル cont-committed / cont-revisable の per-seed markup（決定論再計算）。

finding 0002 の方向主張を分布仮定ゼロの正確検定（完全分離の Mann-Whitney exact）で
固定するための per-seed 永続化。BCS run と同一 config・同一 seed → bit 同一（D-B12）。
同一 master seed は条件横断で同一の子ストリーム（price/arrival/noise）を spawn する
ため対応あり構造でもある——paired 統計も併記する。charge は robustness tier。

実行: python scripts/bcs_per_seed.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microstructure.calibrations import get_calibration  # noqa: E402
from microstructure.designmap import (BudgetLedger, cell_id, run_one_seed,  # noqa: E402
                                      _planned_periods)


def main() -> int:
    base = get_calibration("bcs-es-spy").to_config()
    led = BudgetLedger("results/budget.json")
    vals: dict[str, list[float]] = {"committed": [], "revisable": []}
    rows = []
    for stal in ("committed", "revisable"):
        cfg = base.replace(mechanism="continuous", batch_interval=1, staleness=stal)
        for s in range(5):
            planned = _planned_periods(cfg)
            led.charge("robustness", planned)
            m, _, actual, rt = run_one_seed(cfg, s)
            led.refund("robustness", planned - actual)
            vals[stal].append(m.markup)
            rows.append({"cell": cell_id(cfg), "staleness": stal, "seed": s,
                         "markup": m.markup})
            print(f"{stal} seed={s} markup={m.markup:.4f} ({rt:.0f}s)", flush=True)
    with open("results/bcs_cont_seeds.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cell", "staleness", "seed", "markup"])
        w.writeheader()
        w.writerows(rows)
    c, v = vals["committed"], vals["revisable"]
    sep = max(c) < min(v)
    diffs = [b - a for a, b in zip(c, v)]
    print(f"complete separation: {sep}  (exact Mann-Whitney two-sided p = 2/252 ≈ 0.0079)")
    print(f"paired diffs (same master seed → same spawned streams): {['%.3f' % d for d in diffs]}")
    print(f"all paired diffs positive: {all(d > 0 for d in diffs)}"
          f"  (sign test exact two-sided p = {2 / 2**5:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
