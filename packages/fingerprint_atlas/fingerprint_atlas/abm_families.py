"""abm_families — reference cards for every ABM family in the registry.

The inverse-ABM distance heatmap is meaningless without knowing:
  - what each family was originally proposed for
  - how faithful our reimplementation is to the source paper
  - the family's *epistemic role* — esp. zero_intelligence, which was
    introduced as a NULL HYPOTHESIS, not as a model of behaviour. A
    real market matching ZI means 'price discovery is mostly mechanical
    here, not strategic', not 'these traders are stupid'.

Each entry:
  key              matches the heatmap column / REGISTRY key
  name             display label
  source_paper     primary citation (Author Year, Journal vol)
  arxiv_id         optional, for cross-link to literature_methods
  mechanism        1-2 sentences on what makes the model distinctive
  fidelity_notes   list of known deviations from the source paper
                   (so the distance numbers carry an honest caveat)
  epistemic_role   what conclusion to draw if a real period is close
                   to THIS family
"""
from __future__ import annotations

from typing import TypedDict


class ABMFamily(TypedDict, total=False):
    key: str
    name: str
    source_paper: str
    arxiv_id: str | None
    mechanism: str
    fidelity_notes: list[str]
    epistemic_role: str


ABM_FAMILIES: list[ABMFamily] = [
    {
        "key": "chiarella_iori",
        "name": "Chiarella–Iori",
        "source_paper": "Chiarella & Iori (2002), Quantitative Finance 2(5), 346-353",
        "arxiv_id": None,
        "mechanism": (
            "Three heterogeneous trader types (chartist / fundamentalist / "
            "noise) interacting through a continuous double auction LOB. "
            "Trader weights are sampled per agent at init."
        ),
        "fidelity_notes": [
            "3-trader-type formulation matches the original; per-agent weight "
            "distribution follows the QF paper.",
            "LOB matching uses simple price-time priority — no queue jumping "
            "or hidden orders.",
            "Tick size is normalised; absolute price-level effects from the "
            "original tick discretisation are not reproduced.",
        ],
        "epistemic_role": (
            "LOB-aware chartist/fundamentalist baseline. Match here = market "
            "behaviour explainable by three-type heterogeneity + explicit "
            "order arrival, without needing strategic learning."
        ),
    },
    {
        "key": "cont_bouchaud",
        "name": "Cont–Bouchaud",
        "source_paper": (
            "Cont & Bouchaud (2000), Macroeconomic Dynamics 4(2), 170-196"
        ),
        "arxiv_id": "cond-mat/9712318",
        "mechanism": (
            "Percolation-based herding: agents form random clusters on a "
            "graph and each cluster trades as one unit. Heavy-tailed returns "
            "emerge mechanically from the cluster-size power-law distribution."
        ),
        "fidelity_notes": [
            "Mean cluster connectivity a is the single tunable parameter; "
            "matches the paper exactly.",
            "Original model is static — our impl bolts on a discrete-time "
            "clearing loop so a time-series fingerprint can be measured.",
            "No order book; clearing is at a single equilibrium price each step.",
        ],
        "epistemic_role": (
            "Minimalist null for fat-tail provenance. Match here = heavy tails "
            "are coming from group-formation structure, not from individual-"
            "agent strategy."
        ),
    },
    {
        "key": "franke_westerhoff",
        "name": "Franke–Westerhoff",
        "source_paper": "Franke & Westerhoff (2012), JEDC 36(8), 1193-1211",
        "arxiv_id": None,
        "mechanism": (
            "Discrete-choice agents switching between chartist and "
            "fundamentalist strategies based on (a) relative recent profits "
            "and (b) herding pressure. Produces structural stochastic "
            "volatility from the switching dynamics alone."
        ),
        "fidelity_notes": [
            "Switching intensity β is the dominant tunable; we sweep it "
            "instead of fixing to the published JEDC estimate.",
            "Herding term weight is taken from the JEDC mean estimate; "
            "joint calibration of β + herding weight not yet done.",
        ],
        "epistemic_role": (
            "Discrete-choice extension of Lux-Marchesi with empirically-"
            "calibrated transitions. Match here = vol clustering is "
            "explainable by strategy-switching dynamics."
        ),
    },
    {
        "key": "gcmg",
        "name": "Grand-Canonical Minority Game",
        "source_paper": "Challet & Marsili (2003), Physical Review E 68(3)",
        "arxiv_id": "cond-mat/0210549",
        "mechanism": (
            "Minority Game with a variable agent population — agents enter "
            "the market when their best historical strategy looks profitable, "
            "exit otherwise. Captures crowd density effects pure MG misses."
        ),
        "fidelity_notes": [
            "Entry-threshold ε is our main parameter and matches the GCMG "
            "formulation.",
            "Phase transition (efficient vs herding) reproduces qualitatively; "
            "exact critical α_c may differ by ~5% from the paper.",
            "No price formation in the original — we map minority signal to a "
            "synthetic return for fingerprint comparability.",
        ],
        "epistemic_role": (
            "Population-dynamic extension of MG; bridge between MG abstraction "
            "and realistic markets. Match here = strategic learning + entry/"
            "exit dynamics together drive the observed signature."
        ),
    },
    {
        "key": "lux_marchesi",
        "name": "Lux–Marchesi",
        "source_paper": "Lux & Marchesi (1999), Nature 397(6719), 498-500",
        "arxiv_id": "cond-mat/9810262",
        "mechanism": (
            "Three populations (optimistic chartist / pessimistic chartist / "
            "fundamentalist) with continuous-time transitions governed by "
            "relative profits and opinion contagion. Generates fat tails and "
            "volatility clustering jointly."
        ),
        "fidelity_notes": [
            "Transition-rate parameters taken from the Nature supplement.",
            "Time-step discretisation slightly inflates the vol-clustering "
            "ACF tail vs the continuous-time original (~5% deviation).",
            "Fundamentalist anchor process modelled as Brownian motion; "
            "the original was unspecified.",
        ],
        "epistemic_role": (
            "Canonical chartist/fundamentalist with structural switching. "
            "Match here = market behaviour explained by population-level "
            "opinion dynamics."
        ),
    },
    {
        "key": "minority_game",
        "name": "Minority Game",
        "source_paper": "Challet & Zhang (1997), Physica A 246(3), 407-418",
        "arxiv_id": "adap-org/9708006",
        "mechanism": (
            "N agents pick ±1 each round; whoever is in the minority wins. "
            "Each agent holds S strategies indexed by memory-m history, "
            "selects the best-historic one each step."
        ),
        "fidelity_notes": [
            "Memory m and strategy pool S are swept; phase diagram matches "
            "the original (σ²/N vs α = 2^m / N) exactly.",
            "No price formation — minority signal is mapped to a synthetic "
            "return so the fingerprint can be measured.",
            "Strategy initialisation is identical across runs; re-seeding "
            "kills the phase structure (known limitation of MG).",
        ],
        "epistemic_role": (
            "Foundational El-Farol descendant. Match here = market signature "
            "is consistent with simple coordination-game phase transitions; "
            "interpret with care since MG has no price dimension."
        ),
    },
    {
        "key": "speculation_game",
        "name": "Speculation Game (SG)",
        "source_paper": (
            "Katahira et al. (2019), Physica A 524, 503-518; "
            "Katahira & Chen (2020), J. Syst. Sci. Complex. 35(1), 221-244"
        ),
        "arxiv_id": "1909.03185",
        "mechanism": (
            "3-layer cognitive ABM: (1) perception of market state, "
            "(2) round-trip trade execution, (3) wealth-dynamic entry/exit "
            "of agents on bankruptcy. Rule-based but reproduces 5 of 6 main "
            "stylized facts (everything except leverage effect + gain/loss "
            "asymmetry)."
        ),
        "fidelity_notes": [
            "Layer 1-2 implemented from the Physica A formulation; layer 3 "
            "bankruptcy/entry follows JSSC.",
            "YH006_1 found: under LOB friction, layer-2 round-trips fail to "
            "execute and the wealth-dynamic mechanism stalls (81% survival "
            "in LOB vs 99% bankruptcy in aggregate-supply baseline) — this "
            "is a structural limit of SG, not an impl bug.",
        ],
        "epistemic_role": (
            "Most cognitively-explicit rule-based ABM in this catalog and "
            "the primary research target of this lab's master's program. "
            "Match here = signature consistent with explicit cognition + "
            "round-trip + wealth-dynamic mechanisms acting jointly."
        ),
    },
    {
        "key": "zero_intelligence",
        "name": "Zero Intelligence (ZI)",
        "source_paper": (
            "Gode & Sunder (1993), Journal of Political Economy 101(1) "
            "[original]; Farmer, Patelli & Zovko (2005), PNAS 102(6), "
            "2254-2259 [LOB extension cited here]"
        ),
        "arxiv_id": "cond-mat/0309233",
        "mechanism": (
            "Agents submit random orders within budget constraints. No "
            "strategy, no learning, no memory. Order arrival is Poisson; "
            "order size and limit price are uniformly random within "
            "reservation bounds."
        ),
        "fidelity_notes": [
            "Order-arrival rate and reservation-price bounds calibrated to "
            "match real-market order-flow intensity, NOT to fit returns.",
            "Cancellation rate is set to a typical empirical value (Farmer et "
            "al.); not tuned per period.",
        ],
        "epistemic_role": (
            "NULL HYPOTHESIS. ZI was NOT introduced as a model of trader "
            "behaviour — it tests how much of observed market structure is "
            "produced by the matching engine + budget constraints alone, "
            "independent of strategy. A real-market period matching ZI is "
            "evidence that the observed dynamics in that period are mostly "
            "structural / mechanical, not strategic. Interpret with that "
            "framing — 'close to ZI' is not 'close to a model'; it's 'close "
            "to a baseline that says strategy doesn't matter here'."
        ),
    },
]


def find_family(key: str) -> ABMFamily | None:
    for f in ABM_FAMILIES:
        if f["key"] == key:
            return f
    return None
