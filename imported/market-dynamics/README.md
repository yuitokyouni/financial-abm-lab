# Market State Atlas

Multi-asset market state → causal latent embedding → free-energy landscape
**F(z) = -log ρ(z)** with 3D animated trajectory. See `SPEC.md` for the
full design and `DECISIONS.md` for every non-obvious choice.

## Status

Phases 0-7 + Phase 4.5 (universe-comparison meta-experiment) all landed,
61 tests green, `ruff` clean.

## Theory (one paragraph)

The over-damped Langevin equation has stationary density
`ρ(z) ∝ exp(-V(z)/T)`, so the learned free energy `F(z) = -log ρ(z)`
plays the role of an effective potential V. Minima of F are basins ≈
market regimes; saddle crossings are regime shifts. We project the
multi-asset state into a 2D latent **causally** (β-VAE, OOS-projectable),
estimate ρ via KDE, and detect basins by steepest-descent + topological
persistence merging. The pre-existing `market_dynamics.py` engine
(Kramers-Moyal drift/diffusion estimator + critical-slowdown EWS) is
reused on the latent `z(t)` rather than rewritten.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,data,viz,embed]" --extra-index-url https://download.pytorch.org/whl/cpu

pytest -q                                # 61 tests
atlas --help
atlas viz-demo --out artifacts\demo.html # synthetic double-well HTML, no network
atlas data                               # yfinance fetch + parquet cache
atlas features                           # build causal feature matrix
atlas embed                              # train β-VAE
atlas atlas --out artifacts\atlas.html   # full pipeline → 3D HTML
atlas experiment universe-comparison     # Phase 4.5 meta-experiment
atlas backtest --out artifacts\bt.txt    # Phase 7 honest report
```

## CLI commands

| command | phase | what it does |
|---|---|---|
| `atlas version` | 0 | print version |
| `atlas data` | 1 | yfinance → parquet cache (NaN-free, monotonic index) |
| `atlas features` | 2 | causal feature matrix (leakage-guarded) |
| `atlas embed` | 3 | β-VAE on the train window, report KL per dim |
| `atlas viz-demo` | 6 stub | synthetic 2D double-well 3D HTML |
| `atlas atlas` | 6 full | full pipeline → 3D HTML with z(t) animation |
| `atlas experiment universe-comparison` | 4.5 | run 4 universes, CSV + side-by-side HTML |
| `atlas backtest` | 7 | single-split ANOVA + permutation null, honest report |

## Architecture

```
state_atlas/
  config.py                # pydantic AtlasConfig + ExperimentsConfig
  data/                    # PriceSource + YFinanceSource + parquet cache
  features/                # contract.py (schema) + build.py (causal builder)
  embedding/               # β-VAE, KL per dim, OOS transform
  density/                 # KDE → F → steepest-descent basins + persistence merge
  dynamics/                # market_dynamics.py (existing) + latent_dynamics.py
  experiments/             # universe_comparison.py (Phase 4.5)
  viz/                     # plotly Surface + animated trajectory
  backtest/                # single-split walkforward.py with permutation null
  pipeline.py              # orchestrator used by `atlas atlas` and tests
  cli.py                   # typer entry points
```

## Known limits (the point of this project is to expose these)

- **Look-ahead is unforgiving.** A single accidental `.shift(-1)` invalidates
  the entire atlas. The `test_no_lookahead_under_future_corruption` test
  (Phase 2) is the canary — perturb the future, rebuild, the past must not
  move. If you add a feature, extend that test.
- **Posterior collapse is a measurement, not a bug.** When the β-VAE folds
  onto 1 effective dimension, that is the result "this universe lives on a
  single risk-on/risk-off axis." `atlas embed` reports KL per dim;
  `experiment universe-comparison` exposes `d_eff(τ)` across universes.
- **KDE noise creates fake basins.** Default `min_persistence=1.0` (in
  F-units, i.e. log-density) merges away wells whose separating saddle is
  less than one log-density unit above the basin minimum. Tune via
  `free_energy_with_basins(..., min_persistence=...)` if you have a
  reason; don't loosen it just to make a pretty plot.
- **EWS on real markets is noisy.** The pre-shift Kendall-τ test in
  `market_dynamics.early_warning` works cleanly on the synthetic ramp but
  routinely fires false positives on real data. It is provided as a
  diagnostic; do not turn it into a signal without backtesting.
- **The backtest is intentionally conservative.** A single chronological
  train/test split + ANOVA + permutation null. The default report is
  "no edge"; the bar to flip it is high. SPEC §2 forbids overclaiming.
- **No real-money trading code anywhere.** SPEC §2 #5. The IBKR hook
  (Phase 8) ships read-only or not at all.

## Where to look first

- `SPEC.md` — design rationale and the NON-NEGOTIABLE list (§2)
- `DECISIONS.md` — every "why we picked X over Y" with the date and the reason
- `tests/test_features.py::test_no_lookahead_under_future_corruption` — the
  leakage canary
- `state_atlas/density/free_energy.py` — persistence-based basin detection
- `state_atlas/experiments/universe_comparison.py` — the meta-experiment
  that turns universe choice into a measurement
