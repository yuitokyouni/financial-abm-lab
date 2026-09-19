# unwind-tape ABM (research YH009)

A minimal, **self-contained** agent-based model of a single Japanese-equity name
undergoing a large **block sale of cross-shareholdings** (政策保有株の売出し / 大口
ブロック売り). It is the simulation counterpart to the empirical shortfall
decomposition in `../MEASUREMENT_SPEC.md` (s1/s2/s3), and it lets us ask
counterfactual questions the data can't answer directly (buyback size, market
backdrop, information dissemination).

> **Status: working model, first calibration.** The cost of the sale is now
> **emergent** — it comes out of anticipatory traders taking liquidity from
> market makers, not from an injected fundamental drop. A single coordinate-
> descent pass already lands s1/s2/σ in the right order of magnitude (§7).

Dependencies: **numpy + Python standard library only.** No imports from any
other repo code (`scripts/`, `packages/`, `src/fabm`), matching the unwind-tape
convention of self-contained subprojects.

---

## 1. The core idea: a closed loop, made of a maker and a taker

The whole model exists to keep one property true:

> **Agents react to the price their own orders produced, not to an exogenous
> path.** Nothing scripts s1 or s2. They emerge from two roles interacting in the
> book.

The market is a **Brunnermeier–Pedersen (2005) "predatory trading" mechanism**
ported to a limit-order book:

- **FCN agents are market makers (liquidity providers).** Every step, a maker
  reads the live mid, the recent-return MA, and its own inventory, forms a
  valuation `v_i = p·exp(r·τ)` with
  `r = g1·(log v − log p) + g2·MA(returns) + g3·ε`, and quotes **both sides**
  around an inventory-skewed reservation price. Two sign-checked feedback
  channels live in `r`:
  - **Fundamentalist** `g1·(log v − log p)`: price **down** → quote **up** →
    the maker **absorbs / stabilises** (mean reversion → rebound).
  - **Chartist** `g2·MA`: a **down**-move → quote **down** → the maker
    **withdraws support / chases the trend** (amplifying → drift-down).
  - **Inventory skew**: as it fills the bid into a falling market it gets long,
    skews its quotes down, and past `mm_max_inventory` stops quoting the bid
    entirely — so **liquidity thins exactly when a seller is hitting it** (the BP
    channel). It usually *provides*; on a strong signal it *takes* (crosses).
- **Predators are liquidity takers (anticipatory front-runners).** When a block
  sale is announced, they estimate its impact by **walking the observable book**
  (`estimate_sell_impact`), size an aggregate short as a fraction of the block,
  and **market-sell ahead of it** — creating the announcement gap and the drift.
  After the placement they **cover** (buy back) → price recovers. This is the
  textbook predatory pattern: race the distressed seller down, then reverse.

The cost is therefore *emergent*: predator selling vs maker g1/g2/inventory
decides how deep the gap is and whether price has recovered by the placement
(rebound) or is still sliding (drift-down). 1 step = 1 order event.

---

## 2. Files

| File | Role |
|------|------|
| `order_book.py` | Price-time-priority LOB. `add_limit` (crossing part walks the book, remainder rests), `market_order` (walk, no bound), `best_bid/ask/mid`, `cancel(agent_id)`, and `estimate_sell_impact(qty)` (**non-mutating** book-walk the predators use to size their front-run from real depth). Prices are integer ticks internally. |
| `agents.py` | `ZIAgent` (noise) and `FCNMarketMaker` (two-sided, inventory-skewed maker; may cross to take on a strong signal). An agent may return a **list** of actions (a maker quotes two sides). |
| `market.py` | Orchestrator. Central **inventory** tracking (needed by makers and predators). `warmup()` defines `V`; `run_event(...)` runs the treatment and returns the s1/s2/s3 metrics. The predators (aggregate) are driven here, on the event schedule, not in the random-agent pool. |
| `experiments.py` | Sweep drivers `exp1..exp4` (fix all, sweep one, average over seeds) + the log-log δ fit. |
| `calibrate.py` | Coordinate descent fitting s1/s2/σ to the empirical no-buyback moments. `python -m abm.calibrate`. |
| `run.py` | CLI. `python -m abm.run {smoke,exp1,exp2,exp3,exp4,all}` → `out/<exp>_{detail,summary}.csv`. |
| `config.py` | Baseline parameters (dataclass). All `TODO(calibration)` live here. |

---

## 3. The event and the s1/s2/s3 readout

`Market.run_event(Qover_V, W, announce_info, buyback_ratio, mkt_drift, seed)`:

1. **warmup** → steady state; mean per-step volume sets `V` (per execution
   window), so **`Q/V` is a participation rate**. `Q = Qover_V · V`.
2. `P_ref` = mid just before the news. A **buyback** (if any) posts a standing
   bid-support wall of `buyback_ratio·Q` here — later selling must exhaust it
   first, so a bigger buyback leaves a smaller drop.
3. **announce (s1)** — if `announce_info`, predators size an aggregate short `S`
   from a book-walk of the block (gated: small blocks don't clear it) and sell
   the **announce tranche continuously** across the window. Continuous pressure
   holds a **persistent gap** (a one-shot dump is just bought back). → **s1**.
4. **drift (s2)** — predators work the rest of `S`, ramped toward the placement;
   makers absorb/skew. Whether price keeps sliding or the makers claw it back is
   the g1/g2 balance → this is where the **s2 archetype dispersion** comes from.
5. **execution (s3)** —
   - *announced*: the placement is done **off the lit book** at the exogenous
     underwriter haircut `exec_discount` (empirical median ≈ −3.1%, size-flat).
     The lit-market cost was the anticipation (s1+s2), not a book walk.
   - *unannounced counterfactual* (exp1): the block instead **walks the lit book**
     over `W` slices → emergent, size-dependent s3 (the pure-execution size test).
6. **post** — predators cover → recovery (diagnostic `P_post`; **not** in s1/s2/s3).

Readout (matching `../MEASUREMENT_SPEC.md`, positive = cost to the seller):

```
s1 = ln(P_ref)      - ln(P_day0end)      announcement impact (predator gap)
s2 = ln(P_day0end)  - ln(P_exec_ref)     drift / front-running
s3 = ln(P_exec_ref) - ln(P_exec)         execution discount (exogenous / walk)
IS = s1 + s2 + s3 = ln(P_ref) - ln(P_exec)
```

Returned dict also includes `P_ref, P_day0end, P_exec_ref, P_exec, P_post,
predator_short, V, Q, seller_filled, sigma` (realized event vol, pre-recovery).

---

## 4. Experiments (fix all, sweep one; average over M seeds)

| Exp | Sweeps | Fixed | Reports |
|-----|--------|-------|---------|
| **exp1** size | `Q/V ∈ {0.5,1,2,5,10,20,50,100}` | buyback 0, μ 0, info off | mean IS per size; **δ, R²** from `IS ∝ (Q/V)^δ` (δ=0.5 = √-law) |
| **exp2** buyback | `buyback_ratio ∈ {0,0.1,0.22,0.4}` | Q/V=15, μ 0, info off | IS(β=0) − IS(β=0.22) |
| **exp3** backdrop | `mkt_drift ∈ {-0.06,…,0.06}` | Q/V=15, buyback 0, info off | how IS moves with μ |
| **exp4** information | `announce_info ∈ {False,True}` | Q/V=15, buyback 0, μ 0 | s1/s2 with vs without predators |

Only exp4 activates the predators; **exp1–3 run with the sale unannounced**, so
those sweeps isolate the pure execution / buyback / backdrop effects.

Reference behaviour (30–40 seeds, baseline): exp1 IS rises 0.7%→2.0% in Q/V
(monotone, δ≈0.25); exp2 IS falls 2.0%→0.9% as buyback 0→0.4; exp3 IS rises
1.1%→4.3% as μ +0.06→−0.06 (down market = more loss); exp4 turns s1≈0 into
**s1≈+1.6%** (announce gap) with s2≈0 — the empirical s1≫s2 structure.

---

## 5. How to run

```bash
cd unwind-tape
python3 -m abm.run smoke              # proof the loop runs
python3 -m abm.run exp1               # one experiment (default 60 seeds) -> abm/out/*.csv
python3 -m abm.run all --seeds 40
python3 -m abm.calibrate --seeds 80   # fit s1/s2/sigma -> abm/out/calibration.csv
```

Seeds are `range(N)`, all randomness flows from `numpy.random.default_rng(seed)`,
so runs are **reproducible**. `abm/out/` is git-ignored (regenerable).

---

## 6. Modelling choices worth knowing (and their caveats)

- **FCN = market maker, predator = taker.** The taker/maker split is what makes
  s1/s2 emerge. It replaced the old skeleton's *injected* fundamental drop (s1)
  and *scheduled* front-run flow (s2), which were the honest weakness of the
  first pass.
- **s1 must be held, not dumped.** Makers mean-revert hard, so a one-shot
  announce sell is fully bought back inside the window. Predators sell the
  announce tranche *continuously* to hold a persistent gap.
- **s3 is exogenous for an announced placement.** A public offering is placed
  off-market to institutions at the underwriter's discount; it does **not** walk
  the continuous book. So `exec_discount` sets s3 for announced events; the
  book-walk s3 is only the *unannounced counterfactual* (exp1) that isolates the
  size effect. s3 is **not** an ABM calibration target either way.
- **Thin seed book.** The starter ladder is deliberately shallow (`seed_depth`);
  the replenishing liquidity is the makers. The old deep seed was *why* the
  market was too liquid to move — the direct cause of the σ floor below.
- **Buyback = standing bid-support wall** posted at announce, absorbing later
  selling (a real buyback provides a bid).
- **`Q/V` is a participation rate** — and it is already **anchored to real ADV**:
  the empirical `Q/ADV` per leg is fed straight in as `Qover_V`, and because every
  readout is a log-price *ratio* the absolute `V` cancels. `abm/sensitivity.py`
  (`python -m abm.sensitivity`) stress-tests the *un-anchored* sim scale (window
  length, tick, seed depth) and reports what is robust: **σ is robust to every
  scale knob (2–23% span); s1/s2 *levels* and δ depend on the execution-window
  length (up to ~83%)**, so those must be pinned to the real execution timeline,
  not left to an arbitrary step count.

---

## 7. Calibration (first pass on the reworked model)

`abm/calibrate.py` fits the emergent s1/s2 channels (+ realised σ) to the
empirical **no-buyback** moments. **s3 is exogenous** and NOT calibrated.
Targets (cost basis, `announce_info=True`):

    s1_median ~ +3.8% ,  s2_std ~ 4.0% ,  sigma ~ 1.5%

Method: coordinate descent (one line-search per knob) over the empirical
Q/ADV distribution × seeds. Knobs → target:
`fcn_g1_mean`→s1 (weaker fundamentalist pin ⇒ deeper, more persistent gap),
`predator_block_frac`→s2 dispersion, `fcn_price_band`→σ.

**Result (light run: 1 pass, 40 seeds) vs the old injected-s1 skeleton:**

| moment | old skeleton | **reworked** | target | note |
|---|---|---|---|---|
| s1_median | +0.99% (injected) | **+2.78%** | +3.8% | now **emergent** (−27%) |
| s2_std | 1.8% (stuck) | **+5.30%** | 4.0% | dispersion now reachable (+32%) |
| **sigma** | **0.09% (hard floor)** | **+1.15%** | 1.5% | **floor broken** (−23%) |
| loss | 0.92 | **0.23** | | |

**What changed and what remains:**

1. **The σ floor is gone.** The old passive-FCN + deep-book market was too calm
   to exceed ~0.1% event vol at *any* parameter. Thin book + liquidity-taking
   predators put σ at ~1.1% — the same order as the ~1.5% target, from tuning.
2. **s1 is no longer injected.** It emerges from predators holding a gap against
   the makers; its size responds to `g1`/`band`, not to a scripted drop. It lands
   ~73% of target on a light pass (more selling / weaker pin closes it).
3. **The residual is a coupling, not a wall.** `g1` and `band` move all three
   moments together, so a 1-pass descent overshoots s2_std while undershooting
   s1/σ. A fuller fit (2 passes, 80 seeds, and decoupling s1 via
   `predator_announce_frac`) is the next tightening — but nothing here is
   structurally blocked, unlike the old σ floor.
4. **δ is still under-identified** (impact exponent, IS ∝ (Q/V)^δ): thin vs thick
   book bracket it at δ≈0.26–0.27 (R²≈0.69). The empirical size effect alone does
   not pin δ — it hinges on the (unobservable) book depth. Report δ as a range.

**Sequencing.** Real production runs (full seed counts, the whole Q/V grid,
final fits, and the `V`→ADV anchoring of §6) happen **after the N-gate**
(`measurable execution legs ≥ 30`, ≥2 sale routes ≥10 each — see
`../MEASUREMENT_SPEC.md`), once the moments the model must match are measured.
