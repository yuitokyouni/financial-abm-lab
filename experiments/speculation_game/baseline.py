"""Compatibility entry point; use experiments.YH005.baseline for new work."""
import argparse
from experiments.YH005.baseline import run_baseline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()
    run_baseline(seed=args.seed)
