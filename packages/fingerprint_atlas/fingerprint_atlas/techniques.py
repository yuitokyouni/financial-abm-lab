"""techniques — curated catalog of financial-ABM implementation techniques.

Parallel to subfields.py. Where subfields catalogs **what papers study**
(Minority Game, Leverage Effect, …), this catalogs **how implementations
do it** (Hill estimator, event-driven LOB scheduling, intensity-of-choice
softmax, stationary bootstrap, …).

Each entry:
  key            short slug (file-safe)
  name           display name
  category       tail-stats / sim-arch / decision-rule / validation /
                 calibration / learning-agent
  purpose        1-line: what this technique computes or constructs
  gotchas        list[str] of known pitfalls / parameter sensitivities
  ref_papers     list of arxiv_ids / DOIs / 'oa:Wxxx' that define or
                 canonically use this technique (matched against
                 literature_methods.arxiv_id when surfaced in dashboard)
  ref_repos      list of GitHub URL / pypi package strings that
                 implement this technique well
  your_impl      optional: relative path under the user's own
                 YH00x codebase for cross-link, or None

The 30-entry seed is intentionally coarse — abstract enough to actually
appear in multiple repos. Subdivide when an entry turns out to span
distinct implementations (e.g. 'event-driven LOB' will likely split
into matching-engine vs scheduling vs reporting later).
"""
from __future__ import annotations

from typing import TypedDict


class Technique(TypedDict, total=False):
    key: str
    name: str
    category: str
    purpose: str
    gotchas: list[str]
    ref_papers: list[str]
    ref_repos: list[str]
    your_impl: str | None


TECHNIQUES: list[Technique] = [
    # ===== tail-stats (4): power-law / extreme-value estimation =====
    {"key": "hill_estimator", "name": "Hill estimator (power-law tail index)",
     "category": "tail-stats",
     "purpose": "Estimate the tail exponent α of a heavy-tailed return distribution.",
     "gotchas": [
         "Highly sensitive to the order-statistic threshold k; report a Hill plot, not a point.",
         "Biased downward for moderate samples; pair with stationary-bootstrap CI.",
         "Assumes IID — apply only after de-clustering volatility.",
     ],
     "ref_papers": ["10.1214/aos/1176343247"],
     "ref_repos": ["https://github.com/jeffalstott/powerlaw"],
     "your_impl": "src/fingerprint/hill.py"},

    {"key": "pickands_estimator",
     "name": "Pickands estimator (alt. tail index)",
     "category": "tail-stats",
     "purpose": "Tail-index estimator that requires no positivity, complementary to Hill.",
     "gotchas": [
         "Higher variance than Hill but more robust to threshold misspecification.",
         "Use jointly with Hill — divergence between the two signals model misspec.",
     ],
     "ref_papers": ["10.1214/aos/1176343003"],
     "ref_repos": []},

    {"key": "powerlaw_fit_ks",
     "name": "Power-law fit with KS distance + likelihood-ratio vs lognormal",
     "category": "tail-stats",
     "purpose": "Calibrate xmin + α and test power-law against alternatives (lognormal, exp).",
     "gotchas": [
         "A small p-value rejects power-law; high p doesn't accept it (Clauset).",
         "Lognormal often wins on finance returns — don't claim power-law without LR test.",
     ],
     "ref_papers": ["0706.1062"],
     "ref_repos": ["https://github.com/jeffalstott/powerlaw"]},

    {"key": "stationary_bootstrap",
     "name": "Stationary bootstrap (Politis-Romano)",
     "category": "tail-stats",
     "purpose": "Block bootstrap with geometric block lengths — preserves serial dependence.",
     "gotchas": [
         "Mean block length is the only knob; rule of thumb b ≈ n^{1/3}.",
         "Underestimates variance if dependence is much longer than mean block length.",
     ],
     "ref_papers": ["10.1080/01621459.1994.10476870"],
     "ref_repos": ["https://github.com/bashtage/arch"]},

    # ===== sim-arch (5): how the market loop is built =====
    {"key": "event_driven_lob",
     "name": "Event-driven LOB matching engine",
     "category": "sim-arch",
     "purpose": "Process orders by event time; maintain bid/ask price-time priority queues.",
     "gotchas": [
         "Tie-breaking on identical timestamps changes price formation — fix policy upfront.",
         "Cancel/replace storms can dominate runtime; profile before scaling agents.",
         "Reporting / snapshot frequency is a separate concern from match speed.",
     ],
     "ref_papers": ["10.51094/jxiv.461"],  # PAMS
     "ref_repos": [
         "https://github.com/masanorihirano/pams",
         "https://github.com/jpmorganchase/abides-jpmc-public",
     ]},

    {"key": "call_auction",
     "name": "Call auction / batch clearing",
     "category": "sim-arch",
     "purpose": "Aggregate orders over a window, clear at a single equilibrium price.",
     "gotchas": [
         "Sensitive to tick size and order-cancellation rules at the auction boundary.",
         "Useful as a baseline against continuous LOB to isolate scheduling effects.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/masanorihirano/pams"]},

    {"key": "discrete_time_tick",
     "name": "Discrete-time tick simulation",
     "category": "sim-arch",
     "purpose": "Simplest aggregate-supply/demand loop; tractable for cognitive ABMs.",
     "gotchas": [
         "Cannot reproduce LOB-specific microstructure noise.",
         "Bankruptcy / entry rules behave qualitatively differently vs LOB (Speculation Game finding).",
     ],
     "ref_papers": ["1909.03185"],
     "ref_repos": []},

    {"key": "order_arrival_poisson",
     "name": "Poisson order arrival",
     "category": "sim-arch",
     "purpose": "Generate exogenous order arrival times as a Poisson (or Hawkes) process.",
     "gotchas": [
         "Hawkes self-excitation captures order clustering; pure Poisson misses it.",
         "Rate parameter should be calibrated per-side (bid vs ask) for asymmetric flow.",
     ],
     "ref_papers": ["1502.03003"],
     "ref_repos": ["https://github.com/X-DataInitiative/tick"]},

    {"key": "agent_message_bus",
     "name": "Asynchronous agent message bus",
     "category": "sim-arch",
     "purpose": "Decouple agent decisions from exchange replies via queued messages.",
     "gotchas": [
         "Latency model (deterministic vs jitter) materially changes HFT behaviour.",
         "Test against a synchronous baseline to isolate latency-induced phenomena.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/jpmorganchase/abides-jpmc-public"]},

    # ===== decision-rule (8): the agent's choose-action core =====
    {"key": "chartist_fundamentalist_mix",
     "name": "Chartist–fundamentalist mix (Lux-Marchesi)",
     "category": "decision-rule",
     "purpose": "Population partitioned into trend-followers and fundamental-value traders.",
     "gotchas": [
         "Transition rates (chartist↔fundamentalist) drive volatility clustering; calibrate them, don't fix.",
     ],
     "ref_papers": ["cond-mat/9810262"],
     "ref_repos": []},

    {"key": "mg_strategy_selection",
     "name": "Minority Game strategy selection",
     "category": "decision-rule",
     "purpose": "Each agent holds S strategies, picks the one with best historical score.",
     "gotchas": [
         "Memory length m and strategy pool S jointly control the phase transition (σ²/N vs α=2^m/N).",
         "Strategy distribution is rank-frozen at init — re-seeding kills the phase structure.",
     ],
     "ref_papers": ["adap-org/9708006"],
     "ref_repos": []},

    {"key": "sg_three_layer",
     "name": "Speculation Game 3-layer (cognition / round-trip / wealth)",
     "category": "decision-rule",
     "purpose": "Rule-based cognitive ABM separating perception, trade execution, wealth update.",
     "gotchas": [
         "Bankruptcy + entry rule is essential — disabling it kills wealth-distribution stylized facts.",
         "Round-trip layer assumes complete fills; under LOB friction, layer effectively stops (YH006_1).",
     ],
     "ref_papers": ["1909.03185"],
     "ref_repos": [],
     "your_impl": "src/sg/agents.py"},

    {"key": "brock_hommes_softmax",
     "name": "Brock-Hommes intensity-of-choice (softmax)",
     "category": "decision-rule",
     "purpose": "Multinomial logit over predictor strategies weighted by past fitness.",
     "gotchas": [
         "Intensity β → 0 = uniform mix; β → ∞ = always-best-only; sweep, don't fix.",
         "Adaptive belief switching produces routes-to-chaos; baseline against fixed-mix.",
     ],
     "ref_papers": [],  # Brock-Hommes 1998 is journal; insert oa:Wxxx after canon-ingest
     "ref_repos": []},

    {"key": "kirman_ant_switching",
     "name": "Kirman ant binary switching",
     "category": "decision-rule",
     "purpose": "Continuous-time switching between two opinions via pairwise meetings + self-conversion.",
     "gotchas": [
         "Self-conversion rate ε must be > 0 to break absorbing states.",
         "Generates herd dynamics — natural baseline for chartist-fundamentalist transitions.",
     ],
     "ref_papers": [],
     "ref_repos": []},

    {"key": "vwap_execution",
     "name": "VWAP / TWAP execution",
     "category": "decision-rule",
     "purpose": "Slice a parent order into children matching volume / time profile.",
     "gotchas": [
         "VWAP backtests leak future info if computed on the same window — use lagged profile.",
         "Compare against Almgren-Chriss optimal execution to isolate cost reduction.",
     ],
     "ref_papers": [],
     "ref_repos": []},

    {"key": "avellaneda_stoikov_mm",
     "name": "Avellaneda-Stoikov market making",
     "category": "decision-rule",
     "purpose": "Optimal bid/ask quotes given inventory aversion + volatility + arrival intensity.",
     "gotchas": [
         "Reservation-price formula assumes log-normal mid; under leverage effect, bias remains.",
         "Inventory limits dominate behaviour at high γ; test convergence to inventory targets.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/jpmorganchase/abides-jpmc-public"]},

    {"key": "prospect_asymmetric_sizing",
     "name": "Prospect-theoretic asymmetric position sizing",
     "category": "decision-rule",
     "purpose": "Loss-aversion λ ≈ 2.25 modulates order size by unrealized P&L regime.",
     "gotchas": [
         "Reference point (entry price vs running avg) materially changes asymmetry.",
         "Calibrate λ + α (probability weighting) jointly; orthogonalize against vol-targeting.",
     ],
     "ref_papers": [],  # Tversky-Kahneman 1992 journal; insert oa:Wxxx after canon-ingest
     "ref_repos": []},

    # ===== validation (6): does the simulator reproduce real markets? =====
    {"key": "stylized_facts_battery",
     "name": "Cont (2001) stylized-facts test battery",
     "category": "validation",
     "purpose": "11-fact suite: heavy tails, vol clustering, leverage, long memory, aggregational Gaussianity, etc.",
     "gotchas": [
         "Pass/fail thresholds are convention, not statistical tests — report effect sizes.",
         "Combine into a single fingerprint vector (this lab's 6-feature subset) for inverse-ABM matching.",
     ],
     "ref_papers": [],  # Cont 2001 QF; insert oa:Wxxx after canon-ingest
     "ref_repos": []},

    {"key": "fingerprint_pca",
     "name": "Fingerprint PCA (stylized-fact embedding)",
     "category": "validation",
     "purpose": "Standardize the 6-dim stylized-fact vector, PCA to 2D, layout model families.",
     "gotchas": [
         "PCA is sensitive to feature scale — z-score per dim before projecting.",
         "Mind PC loading interpretability; report top-2 loadings alongside the plot.",
     ],
     "ref_papers": [],
     "ref_repos": [],
     "your_impl": "src/fingerprint/atlas.py"},

    {"key": "garch_baseline_diff",
     "name": "GARCH(1,1) baseline difference",
     "category": "validation",
     "purpose": "Fit GARCH to observed returns; subtract its stylized-fact fingerprint as null.",
     "gotchas": [
         "GARCH already captures vol clustering — don't double-count.",
         "Compare ABM uplift vs GARCH on facts GARCH cannot fit (leverage, gain/loss asymmetry).",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/bashtage/arch"]},

    {"key": "ks_return_distribution",
     "name": "KS / Anderson-Darling on return distribution",
     "category": "validation",
     "purpose": "Distribution-level distance between simulated and observed returns.",
     "gotchas": [
         "KS is insensitive to tails; pair with AD or use the tail-restricted KS.",
         "p-values inflate under autocorrelation — use stationary bootstrap.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/scipy/scipy"]},

    {"key": "ljung_box_autocorr",
     "name": "Ljung-Box test for return / |return| autocorrelation",
     "category": "validation",
     "purpose": "Joint white-noise test up to lag L on returns (or squared returns).",
     "gotchas": [
         "Choose L to span the relevant horizon (~20-40 trading days for daily data).",
         "Always test |r| or r² too — returns can be white while |r| is highly autocorrelated.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/statsmodels/statsmodels"]},

    {"key": "leverage_cross_corr",
     "name": "Leverage cross-correlation at lag k",
     "category": "validation",
     "purpose": "Corr(r_t, r²_{t+k}) — negative values across k=1..20 = leverage effect.",
     "gotchas": [
         "Sign requires returns (not abs returns) at lag 0.",
         "Window length matters: 5-10 days picks up the operationally relevant scale.",
     ],
     "ref_papers": [],
     "ref_repos": []},

    # ===== calibration (4): fit ABM parameters to real data =====
    {"key": "grid_search_params",
     "name": "Grid search on ABM parameters",
     "category": "calibration",
     "purpose": "Brute-force evaluation over a parameter grid using a stylized-fact loss.",
     "gotchas": [
         "Grid density × params × ABM cost = combinatorial blowup; favour active search.",
         "Loss landscape often multimodal — local optima are common.",
     ],
     "ref_papers": [],
     "ref_repos": []},

    {"key": "fingerprint_nn",
     "name": "Fingerprint nearest-neighbour matching (inverse ABM)",
     "category": "calibration",
     "purpose": "Given observed fingerprint, find the closest ABM run in fingerprint space.",
     "gotchas": [
         "Distance metric (Euclidean vs Mahalanobis) changes the family ranking.",
         "Top-1 vs top-2 gap = confidence; report alongside the match.",
     ],
     "ref_papers": [],
     "ref_repos": [],
     "your_impl": "src/inverse_abm/match.py"},

    {"key": "abc_rejection",
     "name": "Approximate Bayesian Computation (ABC) for ABMs",
     "category": "calibration",
     "purpose": "Sample params from prior, simulate, accept if summary stats within ε of observed.",
     "gotchas": [
         "Acceptance rate collapses as ε shrinks; budget the sim count.",
         "Summary-statistic choice dominates result — use the same 6-feature fingerprint.",
     ],
     "ref_papers": ["1903.04279"],
     "ref_repos": ["https://github.com/elfi-dev/elfi"]},

    {"key": "pso_optimization",
     "name": "Particle-swarm optimisation on stylized-fact loss",
     "category": "calibration",
     "purpose": "Gradient-free swarm search; handles multimodal ABM loss landscapes.",
     "gotchas": [
         "Inertia + cognitive + social weights need tuning; rosenbrock-test before applying.",
         "Trapped local optima are common — restart with diverse seeds.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/ljvmiranda921/pyswarms"]},

    # ===== learning-agent (3): RL / interpretability for ABM =====
    {"key": "q_learning_agent",
     "name": "Q-learning agent in market simulator",
     "category": "learning-agent",
     "purpose": "Tabular Q-learning over discretised market state → action (buy/hold/sell).",
     "gotchas": [
         "State-space discretisation is everything — too fine = no convergence, too coarse = trivial policy.",
         "Reward shaping (P&L vs Sharpe vs drawdown-penalised) drives qualitatively different behaviour.",
     ],
     "ref_papers": [],
     "ref_repos": []},

    {"key": "deep_rl_market",
     "name": "Deep RL agent (PPO / SAC) trading in ABM",
     "category": "learning-agent",
     "purpose": "Neural-policy agent learned end-to-end against an ABM environment.",
     "gotchas": [
         "Environment non-stationarity (other agents adapt too) breaks single-agent convergence guarantees.",
         "Reproducibility weak unless seed + framework version pinned tightly.",
     ],
     "ref_papers": [],
     "ref_repos": [
         "https://github.com/AI4Finance-Foundation/FinRL",
         "https://github.com/jpmorganchase/abides-jpmc-public",
     ]},

    {"key": "sae_mechanistic_probe",
     "name": "Sparse autoencoder mechanistic probe of agent internals",
     "category": "learning-agent",
     "purpose": "Decompose learned agent activations into interpretable monosemantic features.",
     "gotchas": [
         "L1 penalty + dictionary size jointly control monosemanticity — sweep both.",
         "Use rule-based agent (Speculation Game) outputs as ground-truth labels for linear probes.",
     ],
     "ref_papers": [],
     "ref_repos": ["https://github.com/anthropic/sae"]},
]


def _looks_like_ref(ref: str) -> bool:
    r"""Does `ref` match one of the documented ref_papers formats?

    Accepts:
      - arxiv old-style   'cat/nnnnnnn' (with optional 'v\d+')
      - arxiv new-style   'YYMM.nnnnn'  (with optional 'v\d+')
      - DOI               '10.xxxx/…'
      - OpenAlex synthetic 'oa:Wxxxxx'
    """
    import re as _re
    if not isinstance(ref, str) or not ref:
        return False
    patterns = [
        r"^[a-z-]+/\d+(v\d+)?$",         # old-style arxiv
        r"^\d{4}\.\d{4,6}(v\d+)?$",      # new-style arxiv
        r"^10\.\d{4,}/",                   # DOI
        r"^oa:W\d+$",                       # OpenAlex synthetic id
    ]
    return any(_re.match(p, ref) for p in patterns)


def validate_techniques() -> dict:
    """Report coverage / format issues across the TECHNIQUES catalog.

    Returns {
        "total": int,
        "with_refs": int,
        "missing_refs": list[key],       # ref_papers == []
        "malformed_refs": list[(key, ref)],
    }
    """
    total = len(TECHNIQUES)
    with_refs = 0
    missing: list[str] = []
    malformed: list[tuple[str, str]] = []
    for t in TECHNIQUES:
        refs = t.get("ref_papers") or []
        if refs:
            with_refs += 1
            for r in refs:
                if not _looks_like_ref(r):
                    malformed.append((t["key"], r))
        else:
            missing.append(t["key"])
    return {
        "total": total,
        "with_refs": with_refs,
        "missing_refs": missing,
        "malformed_refs": malformed,
    }
