# unwind-tape ABM skeleton (research YH009)

A minimal, **self-contained** agent-based model of a single Japanese-equity name
undergoing a large **block sale of cross-shareholdings** (政策保有株の売出し / 大口
ブロック売り). It is the simulation counterpart to the empirical shortfall
decomposition in `../MEASUREMENT_SPEC.md` (s1/s2/s3), and it lets us ask
counterfactual questions the data can't answer directly (buyback size, market
backdrop, information dissemination).

> **Status: working skeleton.** The point is a *closed loop that runs and moves
> in the right direction*, not a calibrated model. Every magnitude is
> provisional and flagged `TODO(calibration)` in `config.py`. Precise
> calibration is deferred until after the N-gate (see the bottom of this file).

Dependencies: **numpy + Python standard library only.** No imports from any
other repo code (`scripts/`, `packages/`, `src/fabm`), matching the unwind-tape
convention of self-contained subprojects.

---

## 1. The core idea: a closed loop

The whole model exists to keep one property true:

> **Agents react to the price their own orders produced, not to an exogenous
> path.** Every FCN order reads the *live* mid and the *live* recent-return
> moving average, decides, and posts. The next agent then sees the book those
> orders left behind.

This is what makes the sale's price impact *emergent* rather than assumed. Two
feedback channels are deliberately built in and sign-checked:

- **Fundamental term** `g1 * (log v - log p)`: when the seller pushes price
  **down**, this term grows **positive** → fundamentalists **buy** → absorbing /
  stabilising (mean reversion). Verified by smoke test 1.
- **Chartist term** `g2 * MA(recent returns)`: a **down**-move makes the moving
  average **negative** → chartists **sell** → amplifying (momentum).

`g1, g2, g3` and the horizon `τ` are drawn **per agent** from distributions, so
the population is heterogeneous.

1 simulation step = **1 order event** (one randomly chosen agent acts), per the
continuous-double-auction convention.

---

## 2. Files

| File | Role |
|------|------|
| `order_book.py` | Price-time-priority LOB. `add_limit` (crossing orders walk the book then rest the remainder), `market_order` (walk the book, no bound), `best_bid/ask/mid`, `cancel(agent_id)`. Prices are integer tick indices internally. |
| `agents.py` | `ZIAgent` (zero-intelligence: random limits/markets around the mid — liquidity + noise) and `FCNAgent` (fundamentalist + chartist + noise; **passive** quoting so restoration is gradual). Each returns an `Action` the market applies. |
| `market.py` | Orchestrator. `warmup()` (reach steady state, define `V`), `run_event(...)` (the treatment; returns the s1/s2/s3 metrics dict). Owns the book, the population and the fundamental `log_v`. |
| `experiments.py` | Sweep drivers `exp1..exp4` (fix everything, sweep one variable, average over seeds) + the log-log δ fit. |
| `run.py` | CLI. `python -m abm.run {smoke,exp1,exp2,exp3,exp4,all}`. Writes `out/<exp>_{detail,summary}.csv`. |
| `smoke_test.py` | Standalone `python -m abm.smoke_test` (thin wrapper over the two checks in `run.py`). |
| `config.py` | Baseline parameters as a dataclass. All `TODO(calibration)` live here. |

---

## 3. The event and the s1/s2/s3 readout

`Market.run_event(Qover_V, W, announce_info, buyback_ratio, mkt_drift, seed)`:

1. **warmup** (thousands of steps) → steady state. Mean traded volume per step is
   measured; `V` = that rate × one execution window's length, so **`Q/V` is a
   participation rate** (multiples of a window's worth of average volume). `Q = Qover_V · V`.
2. `P_ref` = mid just before the announcement.
3. **announce (t=0)** — if `announce_info`, the fundamental `v` takes a
   **permanent** downward step (the news that the stock is worth less). FCN
   reprice down toward it → the day-0 impact is **s1**.
4. **drift window** — front-runners who know the block is coming sell ahead of
   it. Modelled as a scheduled sell of `frontrun_fraction · Q` over the window,
   ramping toward execution. Pushes price below the new `v` → **s2**.
5. **execution [W slices]** — the seller sells `Q` via market orders (walk the
   book). A **buyback** posts aggressive bid support of `buyback_ratio · Q` just
   before each slice (so the seller's flow is absorbed at a supported price). The
   market drift `mkt_drift` is applied to `v` across the window. Seller fill VWAP
   is `P_exec` → **s3**.

Readout (matching `../MEASUREMENT_SPEC.md`, positive = cost to the seller):

```
s1 = ln(P_ref)      - ln(P_day0end)      announcement impact
s2 = ln(P_day0end)  - ln(P_exec_ref)     drift / front-running
s3 = ln(P_exec_ref) - ln(P_exec)         execution gap (seller VWAP)
IS = s1 + s2 + s3 = ln(P_ref) - ln(P_exec)
```

Returned dict also includes `P_ref, P_day0end, P_exec_ref, P_exec, V, Q,
seller_filled, sigma` (realized per-step vol over the event).

---

## 4. Experiments (fix all, sweep one; average over M seeds)

| Exp | Sweeps | Fixed | Reports |
|-----|--------|-------|---------|
| **exp1** size | `Q/V ∈ {0.5,1,2,5,10,20,50,100}` | buyback 0, μ 0, info off | mean IS per size; **δ, R²** from `IS ∝ (Q/V)^δ` (δ=0.5 = √-law) |
| **exp2** buyback | `buyback_ratio ∈ {0,0.1,0.22,0.4}` | Q/V=15, μ 0, info off | IS(β=0) − IS(β=0.22) |
| **exp3** backdrop | `mkt_drift ∈ {-0.06,…,0.06}` | Q/V=15, buyback 0, info off | how IS moves with μ |
| **exp4** information | `announce_info ∈ {False,True}` | Q/V=15, buyback 0, μ 0 | s2(on) − s2(off) = front-running premium |

Only exp4 activates the information channels; **exp1–3 run with the sale
unannounced**, so those sweeps are independent of the information machinery.

---

## 5. How to run

Run from the `unwind-tape/` directory (so `abm` resolves as a package):

```bash
cd unwind-tape

# mandatory smoke test (proof the skeleton runs)
python3 -m abm.run smoke

# one experiment (default 60 seeds); writes abm/out/*.csv
python3 -m abm.run exp1
python3 -m abm.run exp2 --seeds 100

# everything
python3 -m abm.run all --seeds 40
```

Seeds are `range(N)` and all randomness flows from `numpy.random.default_rng(seed)`,
so runs are **reproducible**. Output CSVs land in `abm/out/` (git-ignored — they
are regenerable artifacts).

### Smoke test output (reference numbers, seed-fixed)

```
[smoke 1] closed-loop continuity (one-off sell -> drop -> recovery)
  pre-shock mid P0=99.9250 ; post-shock P_after=99.7250 (drop -0.200%)
  settled mid P_settle=99.9250 -> recovered 100.0% of the drop (mean reversion present)

[smoke 2] light exp1: Q/V=[1,5,20], seeds=20
  IS_mean by Q/V: [0.00070, 0.00105, 0.00190]   (monotone increasing: True)
  delta_hat=0.334  R2=0.978
```

Full exp1 (Q/V 0.5→100, 40 seeds): IS rises 0.00058 → 0.00542, **δ≈0.42, R²≈0.96**
— close to the √-law without any calibration.

---

## 6. Modelling choices worth knowing (and their caveats)

These are pragmatic skeleton decisions, each revisitable:

- **Passive FCN quoting.** FCN provide graded, non-crossing liquidity. If they
  re-quoted aggressively across the touch, every execution slice would snap back
  to the same price and impact would saturate (no size effect). Passive quoting
  makes restoration *gradual*, which is what produces a monotone, near-√ size
  effect. Cost: price discovery is slow, so information effects have to be
  injected as flow rather than emerge from re-quoting (next point).
- **Information = permanent `v` drop (s1) + scheduled front-run flow (s2).**
  Because passive repricing is slow, we don't rely on it to transmit the news.
  s1 is a permanent fundamental step; s2 is an explicit front-run sell sized to
  the block. Provisional; the intended replacement is genuinely informed agents.
- **Buyback = aggressive bid support**, posted before each seller slice, so it
  directly absorbs the seller's flow (a real buyback provides a bid), rather than
  a market buy that would just walk the *other* side of the book.
- **`Q/V` is a participation rate** over a window of the execution window's
  length — not a fraction of literal daily volume. `TODO(calibration)`: map to
  real ADV.

---

## 7. Calibration TODO (after the N-gate)

Nothing here is fitted yet. The intended targets, from real tape moments
(`../MEASUREMENT_SPEC.md`, `../BENCHMARK_SPEC.md`):

- **`fcn_g1/g2/g3` distributions and `zi_fraction`** — set the stabilising vs
  amplifying balance and the stylised-facts profile (fat tails, vol clustering).
- **`announce_fundamental_drop`, `frontrun_fraction`** — fit to the s1 and to the
  **s2 dispersion in the no-buyback group** (the front-running premium).
- **`Qover_V` → real ADV mapping, `W`, warmup length** — fit s3 so the execution
  discount lands near the empirical **s3 ≈ −3%** on offerings, and so the impact
  exponent δ matches the residual-vs-√-law test (`implied_Y_s2`).
- **tick size / price grid / seed depth** — to a representative TSE name.

**Sequencing.** This is scaffolding. Real production runs (seed counts, the full
`Q/V` grid, parameter fits) happen **after the N-gate** (`measurable execution
legs ≥ 30`, ≥2 sale routes with ≥10 legs each — see `../MEASUREMENT_SPEC.md`),
once the empirical moments the model must match are actually measured.
