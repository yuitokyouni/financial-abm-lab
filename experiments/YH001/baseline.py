"""YH001: Cont–Bouchaud baseline using the shared canonical model."""
from __future__ import annotations

import argparse
from abm_models import ContBouchaud
from abm_models.base import returns_of
from stylized_facts import hill_mle_tail_index, kurtosis_windowed

def run_baseline(seed: int = 42) -> dict:
    res = ContBouchaud(N=10000, c=0.9, T=20000).run(seed=seed)
    r = returns_of(res)
    return {
        "model": "cont_bouchaud",
        "excess_kurtosis": kurtosis_windowed(r, 1),
        "hill_alpha": hill_mle_tail_index(r),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(run_baseline(seed=args.seed))
