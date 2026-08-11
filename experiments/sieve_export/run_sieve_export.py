"""SOB (self_organized_book, spec 003 substrate) → sieve directory-of-runs export.

10 seeds を実行し、sieve (https://github.com/yuitokyouni/sieve) の
directory 形式 (manifest.yaml + runs/seed-XXX.csv, 列 = step,price,volume) に
書き出す。burn-in (= PAMS warmup session 長) は manifest 側で宣言し、
CSV には全 step を残す (sieve 側で drop させる — データを黙って加工しない)。

観測系列:
  - price  = market price (PAMS `get_market_prices`, 最終約定価格ベース)
  - volume = step ごとの約定数量 (PAMS `get_executed_volumes`)。
    kronos_lob/bar_aggregator の定数 proxy とは違い実測値。

実行: uv run python experiments/sieve_export/run_sieve_export.py
その後: sieve inspect experiments/sieve_export/dataset --out <run dir>
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import yaml

from pams.logs.market_step_loggers import MarketStepSaver
from pams.runners import SequentialRunner

from abm_models.self_organized_book.model import build_sob_config
from abm_models.self_organized_book.zi_agent import ZIAgent

# --- 実験パラメータ (spec 003 P0: ZI-only 内生流動性 CDA) ---
SEEDS = list(range(10))
WARMUP_STEPS = 200          # ZI warmup session (= burn-in として宣言)
MAIN_STEPS = 5000
N_ZI = 50
PARAMS = dict(
    warmup_steps=WARMUP_STEPS,
    main_steps=MAIN_STEPS,
    n_zi=N_ZI,
    bar_size=10,
    order_ttl=20,
    order_volume=1,
    sigma_eval=0.005,
    margin_min=0.001,
    margin_max=0.01,
    initial_market_price=300.0,
    tick_size=0.00001,
    zi_mode="naive",
)

OUT = Path(__file__).parent / "dataset"


def run_one(seed: int) -> tuple[np.ndarray, np.ndarray]:
    cfg = build_sob_config(**PARAMS)
    saver = MarketStepSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(seed), logger=saver)
    runner.class_register(ZIAgent)
    runner._setup()
    runner._run()
    market = runner.simulator.markets[0]
    end_step = market.get_time() + 1
    prices = np.asarray(market.get_market_prices(range(end_step)), dtype=float)
    volumes = np.asarray(market.get_executed_volumes(range(end_step)), dtype=float)
    return prices, volumes


def main() -> None:
    runs_dir = OUT / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for seed in SEEDS:
        prices, volumes = run_one(seed)
        fname = f"seed-{seed:03d}.csv"
        with open(runs_dir / fname, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["step", "price", "volume"])
            for step, (p, v) in enumerate(zip(prices, volumes)):
                w.writerow([step, f"{p:.6f}", f"{v:.0f}"])
        entries.append({"file": f"runs/{fname}", "run_id": f"seed-{seed:03d}",
                        "seed": seed})
        print(f"seed {seed}: {len(prices)} steps, "
              f"total volume {volumes.sum():.0f}", flush=True)

    manifest = {
        "model_id": "self_organized_book",
        "model_version": "spec003-P0-zi",
        "display_name": "Self-Organized Book (ZI-only, endogenous liquidity CDA)",
        "model_family": "lob-abm",
        "parameters": PARAMS,
        "geometry": "multi_run_ensemble",
        "derive_return": "log",
        # burn-in = ZI warmup session (spec 003 §3.4)。板を温める区間で、
        # 系列冒頭の transient を診断から除外する。
        "burn_in": {"steps": WARMUP_STEPS},
        "notes": (
            "PAMS CDA, all-LIMIT ZI agents, endogenous liquidity (no market "
            "maker; spec 003 YH007-8). price = market price (last executed), "
            "volume = executed volume per step. Rows 0..%d are the ZI warmup "
            "session, declared as burn_in." % (WARMUP_STEPS - 1)
        ),
    }
    with open(OUT / "manifest.yaml", "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)
    print(f"wrote {OUT / 'manifest.yaml'} + {len(entries)} run files")


if __name__ == "__main__":
    main()
