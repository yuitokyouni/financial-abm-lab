"""YH003: Minority Game baseline using the shared canonical model."""
from __future__ import annotations

import argparse
import numpy as np
from abm_models import MinorityGame

def _sigma2_over_N(attendance: np.ndarray, N: int, burn: int) -> float:
    a = np.asarray(attendance[burn:], dtype=np.float64)
    return float(a.var() / N)

def run_baseline(seed: int = 42) -> dict:
    N, T, burn = 101, 10000, 2000
    res = MinorityGame(N=N, M=6, S=2, T=T).run(seed=seed)
    return {"model": "minority_game", "sigma2_over_N": _sigma2_over_N(res["attendance"], N, burn)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(run_baseline(seed=args.seed))
