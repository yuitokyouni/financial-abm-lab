"""YH005 baseline — core を import する薄いラッパー (spec 001 O1/O2 の実証)。

旧 imported/speculation-game-info/experiments/YH005/baseline.py は model/simulate/
analysis を experiment 内にベタ書きしていた。本版はそれらを再実装せず
`abm_models` と `stylized_facts` の正準 core から import するだけ。findings は
core 移植後も parity を保つ (tests/test_sg_parity.py)。

実行:
    uv run python -m experiments.speculation_game.baseline --seed 777
"""

from __future__ import annotations

import argparse

from abm_models.sg import BASELINE_PARAMS, SpeculationGame
from stylized_facts import log_returns_from_prices, stylized_facts_summary


def run_baseline(seed: int = 777) -> dict:
    model = SpeculationGame(**BASELINE_PARAMS, backend="vectorized")
    res = model.run(seed=seed)
    returns = log_returns_from_prices(res["prices"])
    summary = stylized_facts_summary(
        returns, acf_lags=(1, 14, 50, 200, 500), kurt_windows=(1, 16, 64, 256, 640)
    )
    print(f"[YH005 baseline] seed={seed} num_substitutions={res['num_substitutions']}")
    print(f"  std(r)   = {summary['std']:.4e}")
    print("  vol_acf  = " + ", ".join(f"τ={lag}:{summary['vol_acf'][lag]:+.4f}" for lag in summary["vol_acf"]))
    print("  kurt     = " + ", ".join(f"w={w}:{summary['kurt'][w]:+.2f}" for w in summary["kurt"]))
    print(f"  Hill α   = {summary['hill_alpha']:.3f}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()
    run_baseline(seed=args.seed)
