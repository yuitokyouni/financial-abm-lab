"""YH004: Grand Canonical Minority Game baseline using the shared canonical model."""
from __future__ import annotations

import argparse
import numpy as np
from abm_models import GrandCanonicalMG

def run_baseline(seed: int = 42) -> dict:
    N = 101
    res = GrandCanonicalMG(N=N, M=2, S=2, T_win=50, T_total=21000, r_min_static=0.0).run(seed=seed)
    active = np.asarray(res["active"], dtype=np.float64)
    return {"model": "gcmg", "mean_active": float(active[1000:].mean())}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(run_baseline(seed=args.seed))
