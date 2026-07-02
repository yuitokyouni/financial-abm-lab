"""taxonomy — single source of truth for the atlas's classification vocabulary.

Previously spread across coverage.py (fact list, family taxonomy, deny-lists)
and gap_finder.py (a duplicated CANONICAL_FACTS). Consolidating here so:

  1. Adding / removing a fact or a mechanism family means editing ONE file,
     not chasing 4 copies.
  2. New callers (dashboard, propose, idea_judge) can import taxonomy
     directly instead of reaching into coverage internals.

The four public parts:

  CANONICAL_FACTS       — the return-observable stylized facts we track.
                           Anchor: Cont 2001. Return-only observability
                           is the inclusion criterion — herding lives in
                           mechanism_tags, not here.
  canonical_fact()      — normalise a fact string ('Fat Tails' → 'fat-tails')
  method_family()       — bucket a mechanism_tag into ABM / stat / ml / other
  FACT_TERMS_NOT_MECHANISMS  — mechanism_tag deny-list: fact terms leaked in
  TOO_GENERIC_MECHANISMS     — mechanism_tag deny-list: 'agent-based-model' etc
  GENERIC_OA_CONCEPTS        — fall-through concept deny-list from OpenAlex

Coverage builder and gap_finder both re-export the public names below via
their existing module paths, so external code (tests, callers) keeps working.
"""
from __future__ import annotations


def canonical_fact(s: str) -> str:
    """Normalise a fact label so 'fat tails' / 'fat-tails' / 'Fat Tails' all
    collapse to the same slug."""
    return s.strip().lower().replace(" ", "-")


# ---------------------------------------------------------------------------
# Stylized-fact vocabulary
# ---------------------------------------------------------------------------

#: Return-observable stylized facts, anchored on Cont 2001 "Empirical
#: properties of asset returns" (Quant. Finance 1:223-236). We include the
#: eight from Cont that are measurable from a return series alone, plus
#: regime-switching which is inferrable from returns via HMM/MRS estimation.
#: `herding` is intentionally NOT here — it is a mechanism whose observable
#: signature is a composite of vol-clustering / fat-tails / volume-vol-corr,
#: not a first-order return property.
CANONICAL_FACTS: list[str] = [
    # Cont 2001 canonical (return-observable)
    "fat-tails", "vol-clustering", "leverage", "long-memory",
    "aggregational-gaussianity", "absence-of-autocorr",
    "gain-loss-asymmetry", "volume-volatility-corr",
    # Return-measurable ABM-specific target
    "regime-switching",
    # catch-all — anything the LLM can't map cleanly
    "other",
]


# ---------------------------------------------------------------------------
# Mechanism-tag deny-lists
# ---------------------------------------------------------------------------

#: Stylized-fact terms that must never appear as a mechanism row — they
#: belong on the fact column only. The extraction prompt occasionally leaks
#: fact names into mechanism_tags; skip them here when picking the row's
#: primary tag. The paper still lands on the right column via
#: stylized_facts_targeted.
FACT_TERMS_NOT_MECHANISMS: frozenset[str] = frozenset({
    "leverage", "long-memory", "fat-tails", "vol-clustering",
    "absence-of-autocorr", "gain-loss-asymmetry",
    "aggregational-gaussianity", "volume-volatility-corr",
    "volatility",  # too broad — real methods are GARCH / stoch-vol / etc
    # NOTE: 'multifractal' was here but is legitimately ambiguous
    # (Multifractal Random Walk IS a real modelling family from Bacry-
    # Muzy-Delour). Keeping it as a stat mechanism is the less-lossy
    # call; papers using multifractal analysis of returns as a fact
    # get 'other' as fact instead.
})

#: Mechanism-tag terms that ARE modelling flags but are so generic they don't
#: inform the coverage matrix. Every paper in this corpus is an ABM by
#: construction; tagging one 'agent-based-model' as its primary keyword says
#: nothing. Skip these; the next, more specific tag gets promoted.
TOO_GENERIC_MECHANISMS: frozenset[str] = frozenset({
    "agent-based", "agent-based-model", "agent-based-modeling",
    "agent-based-simulation", "abm", "multi-agent", "multi-agent-model",
    "agent-model", "simulation", "computational-model",
    "framework", "model",
})

#: OpenAlex top-level fields-of-study that are too generic to serve as a
#: mechanism label — they pollute the coverage matrix with empty rows.
GENERIC_OA_CONCEPTS: frozenset[str] = frozenset({
    "Computer science", "Economics", "Business", "Mathematics",
    "Physics", "Engineering", "Psychology", "Finance",
    "Futures contract", "Algorithmic trading", "Artificial intelligence",
    "Machine learning", "Deep learning", "Optimization",
    "Mathematical economics", "Microeconomics", "Macro",
    "Industrial organization", "Financial economics",
    "Stylized fact",  # too generic AS A MECHANISM (it IS a target column)
})


# ---------------------------------------------------------------------------
# Method families
# ---------------------------------------------------------------------------

#: Method-family taxonomy. The corpus contains legitimate financial-modelling
#: work across multiple families — pure ABM, econometric / statistical models,
#: machine learning — and forcing them onto a single "ABM mechanism" axis
#: loses information. We tag every row with a family badge so the reader can
#: see the split.
#:
#: Membership is by lowercase exact match against the primary_tag with
#: substring heuristics for tag variants that slipped through. Unknown tags
#: default to 'other'.
ABM_MECHANISM_TAGS: frozenset[str] = frozenset({
    "minority-game", "order-book", "llm-agent", "chartist-fundamentalist",
    "kirman-ant", "speculation-game", "adaptive-control",
    "heterogeneous-agents", "heterogeneous-beliefs", "heterogeneous-expectations",
    "prospect-theory", "behavioral-finance", "microstructure",
    "market-microstructure", "market-making", "herding",
    "opinion-dynamics", "asymmetric-trading", "rational-expectations",
    "chartist", "fundamentalist", "microsimulation", "interacting-agents",
    "adaptive-expectations", "el-farol",
})

STAT_MODEL_TAGS: frozenset[str] = frozenset({
    "regime-switching", "hmm", "hidden-markov", "markov-switching",
    "mrs-garch", "garch", "arch", "e-garch", "egarch",
    "stochastic-volatility", "tar", "setar", "tacarr",
    "hawkes-process", "hawkes",
    "fractional-brownian-motion", "fractional-integration",
    "multifractal", "volterra", "log-periodogram", "semiparametric",
    "score-driven", "gas", "gas-model", "power-law",
    "levy-walk", "levy-flight", "levy",
    "cointegration", "copulas",
    "generative-model",
    "diffusion-model",  # SDE-flavoured, not agent-based
    "queue-reactive",   # Huang-Lehalle-Rosenbaum stochastic LOB model
})

ML_MODEL_TAGS: frozenset[str] = frozenset({
    "lstm", "transformer", "attention-mechanism", "attention",
    "siamese-architecture", "contrastive-learning",
    "variational-autoencoder", "vae", "generative-adversarial", "gan",
    "graph-gaussian-process", "ppo", "actor-critic", "dqn",
    "reinforcement-learning", "deep-learning", "neural-network",
    "neural-networks", "machine-learning", "gradient-boosting",
})


def method_family(tag: str) -> str:
    """Return the family bucket for a mechanism tag.

    Returns one of: 'ABM' | 'stat' | 'ml' | 'other'. Case-insensitive
    exact match against the three frozensets above, then a few substring
    heuristics to catch model-variant tags we haven't enumerated.
    """
    t = (tag or "").strip().lower().replace(" ", "-")
    if not t:
        return "other"
    if t in ABM_MECHANISM_TAGS:
        return "ABM"
    if t in STAT_MODEL_TAGS:
        return "stat"
    if t in ML_MODEL_TAGS:
        return "ml"
    # Substring heuristics for tag variants that slipped through.
    if any(k in t for k in ("garch", "markov", "hmm", "hawkes",
                              "levy", "volterra", "brownian",
                              "multifractal", "score-driven")):
        return "stat"
    if any(k in t for k in ("lstm", "transformer", "attention",
                              "neural", "-learning", "deep-",
                              "reinforcement")):
        return "ml"
    if any(k in t for k in ("agent", "-game", "microstruct",
                              "chartist", "fundamentalist",
                              "prospect", "behavioral", "herd",
                              "opinion", "rational-expectat")):
        return "ABM"
    return "other"


#: Display order for the row bands in the coverage matrix.
FAMILY_ORDER: tuple[str, ...] = ("ABM", "stat", "ml", "other")


#: Alias map: normalised tag variant → canonical mechanism slug. Applied
#: after canonical_fact() normalisation (lowercase + hyphens), so keys
#: here must be in that form. Catches the LLM's synonym drift — the same
#: mechanism appearing as 'limit-order-book' vs 'order-book' split into
#: two matrix rows in Yo's post-retag heatmap.
TAG_ALIASES: dict[str, str] = {
    "limit-order-book": "order-book",
    "lob": "order-book",
    "order-book-model": "order-book",
    "market-maker": "market-making",
    "minority-games": "minority-game",
    "hawkes": "hawkes-process",
    "hidden-markov": "hmm",
    "hidden-markov-model": "hmm",
    "markov-switching": "regime-switching",
    "reinforcement": "reinforcement-learning",
    "rl": "reinforcement-learning",
    "marl": "multi-agent-reinforcement-learning",
    "llm-agents": "llm-agent",
    "large-language-model-agent": "llm-agent",
}


def normalise_mechanism_tag(tag: str) -> str:
    """Lowercase-slug a mechanism tag and resolve known aliases.

    'Minority-Game' → 'minority-game';  'limit-order-book' → 'order-book'.
    This is what coverage/_primary_tag should emit so case variants and
    synonyms collapse into one matrix row.
    """
    slug = canonical_fact(tag)
    return TAG_ALIASES.get(slug, slug)
