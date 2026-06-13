"""S6 §3.3 — τ_max 較正 (Windows、~1 分、新規 sim なし).

GLOSSARY: τ_max = L_50 × 0.5。「L_50」の解釈 4 候補を C3 100 trial の
lifetimes parquet から計算して並記し、primary = (c) p25 ベースを確定値として
JSON に書き出す (S6 plan §3.3、選択理由は plan §2.3)。

Run:
  cd experiments/YH006_1
  python -m code.tau_max_calibration
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"

COND = "C3"


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("S6-tau")

    seeds = range(ENSEMBLE_SEED_BASE, ENSEMBLE_SEED_BASE + ENSEMBLE_N_TRIALS)
    parts = []
    trial_medians = []
    for seed in seeds:
        p = DATA_DIR / COND / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt = pd.read_parquet(p, columns=["lifetime", "censored"])
        parts.append(lt)
        trial_medians.append(float(lt["lifetime"].median()))
    pool = pd.concat(parts, ignore_index=True)
    life = pool["lifetime"].to_numpy(float)
    cens = pool["censored"].astype(bool).to_numpy()

    candidates = {
        # (a) trial-level lifetime median の trial 間 mean (T 張り付き、censoring artifact)
        "a_trial_level_median": float(np.mean(trial_medians)),
        # (b) uncensored 退場 agent のみの median (少数派の動態)
        "b_conditional_median": float(np.median(life[~cens])),
        # (c) 全 sample の p25 (生存分布全体の特性) — primary
        "c_p25": float(np.percentile(life, 25)),
        # (d) 全 sample の mean
        "d_lifetime_mean": float(life.mean()),
    }

    log.info(f"[L_50] candidates (C3, n_trial={len(parts)}, n_sample={len(pool):,}):")
    rows = {}
    for key, l50 in candidates.items():
        tau = int(math.ceil(l50 * 0.5))
        rows[key] = {"L_50": l50, "tau_max": tau}
        log.info(f"  ({key[0]}) {key[2:]:>22}: L_50={l50:8.1f} → tau_max={tau:4d}")

    # stop trigger (plan §5): 候補間 50x 以上の乖離 → L_50 解釈の根本見直し
    taus = [r["tau_max"] for r in rows.values()]
    spread = max(taus) / max(min(taus), 1)
    if spread >= 50:
        raise AssertionError(
            f"τ_max 候補間の乖離 {spread:.0f}x ≥ 50x — L_50 解釈の根本見直し、"
            f"停止して Yuito 相談 (plan §5)"
        )

    primary_key = "c_p25"
    tau_primary = rows[primary_key]["tau_max"]
    log.info(f"→ Primary: tau_max = {tau_primary} (基準: p25 × 0.5、plan §2.3 / "
             f"Yuito 承認 2026-06-07)")

    out = {
        "stage": "S6 §3.3",
        "cond": COND,
        "n_trials": len(parts),
        "n_samples": int(len(pool)),
        "censoring_rate": float(cens.mean()),
        "candidates": rows,
        "primary": primary_key,
        "tau_max": tau_primary,
        "rule": "tau_max = ceil(L_50 × 0.5), L_50 = pooled lifetime p25 (GLOSSARY A3)",
        "candidate_spread_x": spread,
        "timestamp": datetime.now().isoformat(),
    }
    out_path = LOGS_DIR / "S6_tau_max_calibration.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log.info(f"saved: {out_path}")


if __name__ == "__main__":
    main()
