"""subfields — curated list of financial-ABM subfields for canon detection.

Each subfield gets:
  - key: short slug (file-safe, used in genealogy HTML filenames)
  - name: display name
  - category: foundational / stylized / microstructure / behavioral /
              network / crisis / learning
  - query: OpenAlex title_and_abstract phrase to feed find_canon_papers
  - seed_arxiv: optional arxiv_id of the canonical paper (when known) —
                lets genealogy bypass canon auto-selection and root at
                the actual foundational paper. Useful when the founder
                paper coined the term *after* publication so phrase
                search misses it (e.g. Challet-Zhang 1997 originally
                titled 'Emergence of cooperation…', not 'Minority game').

The 25-entry list aims to cover the consensus financial-ABM subfields:
foundational models, the 6 stylized facts, market microstructure,
behavioral, network/contagion, crisis, and learning. Extend by editing
this file — it's the single source of truth for canon-atlas.
"""
from __future__ import annotations

from typing import TypedDict


class Subfield(TypedDict, total=False):
    key: str
    name: str
    category: str
    query: str
    seed_arxiv: str | None


SUBFIELDS: list[Subfield] = [
    # ----- foundational models -----
    {"key": "minority_game", "name": "Minority Game", "category": "foundational",
     "query": "Minority game", "seed_arxiv": "adap-org/9708006"},
    {"key": "lux_marchesi", "name": "Lux-Marchesi chartist-fundamentalist",
     "category": "foundational", "query": "chartist fundamentalist",
     "seed_arxiv": "cond-mat/9810262"},
    {"key": "santa_fe_market", "name": "Santa Fe artificial stock market",
     "category": "foundational", "query": "Santa Fe artificial stock market",
     "seed_arxiv": None},
    {"key": "el_farol", "name": "El Farol bar problem",
     "category": "foundational", "query": "El Farol bar", "seed_arxiv": None},
    {"key": "kirman_ant", "name": "Kirman ant herding model",
     "category": "foundational", "query": "Kirman ant herding",
     "seed_arxiv": None},

    # ----- 6 stylized facts -----
    {"key": "heavy_tails", "name": "Heavy-tailed returns",
     "category": "stylized", "query": "heavy tail returns power law",
     "seed_arxiv": None},
    {"key": "vol_clustering", "name": "Volatility clustering",
     "category": "stylized", "query": "volatility clustering",
     "seed_arxiv": None},
    {"key": "leverage_effect", "name": "Leverage effect",
     "category": "stylized", "query": "leverage effect volatility",
     "seed_arxiv": None},
    {"key": "long_memory_vol", "name": "Long memory in volatility",
     "category": "stylized", "query": "long memory volatility",
     "seed_arxiv": None},
    {"key": "agg_gaussianity", "name": "Aggregational Gaussianity",
     "category": "stylized", "query": "aggregational Gaussianity returns",
     "seed_arxiv": None},

    # ----- market microstructure -----
    {"key": "limit_order_book", "name": "Limit order book models",
     "category": "microstructure", "query": "limit order book",
     "seed_arxiv": None},
    {"key": "market_impact", "name": "Market impact / price impact",
     "category": "microstructure", "query": "market impact price",
     "seed_arxiv": None},
    {"key": "bid_ask_spread", "name": "Bid-ask spread dynamics",
     "category": "microstructure", "query": "bid-ask spread",
     "seed_arxiv": None},
    {"key": "hft", "name": "High-frequency trading",
     "category": "microstructure", "query": "high frequency trading",
     "seed_arxiv": None},

    # ----- behavioral / heterogeneous agents -----
    {"key": "heterogeneous_beliefs", "name": "Heterogeneous beliefs (Brock-Hommes)",
     "category": "behavioral",
     "query": "heterogeneous beliefs asset pricing", "seed_arxiv": None},
    {"key": "bounded_rationality", "name": "Bounded rationality in markets",
     "category": "behavioral", "query": "bounded rationality market",
     "seed_arxiv": None},
    {"key": "prospect_theory", "name": "Prospect theory in trading",
     "category": "behavioral", "query": "prospect theory market",
     "seed_arxiv": None},

    # ----- network / contagion -----
    {"key": "financial_contagion", "name": "Financial contagion network",
     "category": "network", "query": "financial contagion network",
     "seed_arxiv": None},
    {"key": "systemic_risk", "name": "Systemic risk in networks",
     "category": "network", "query": "systemic risk network",
     "seed_arxiv": None},
    {"key": "interbank", "name": "Interbank network",
     "category": "network", "query": "interbank network",
     "seed_arxiv": None},
    {"key": "fire_sale", "name": "Fire sale / forced liquidation",
     "category": "network", "query": "fire sale dynamics",
     "seed_arxiv": None},

    # ----- crisis / regime -----
    {"key": "bubbles_crashes", "name": "Bubbles and crashes",
     "category": "crisis", "query": "bubbles crashes financial",
     "seed_arxiv": None},
    {"key": "log_periodic", "name": "Log-periodic crash precursors",
     "category": "crisis", "query": "log-periodic crash precursor",
     "seed_arxiv": None},
    {"key": "regime_switching", "name": "Regime switching",
     "category": "crisis", "query": "regime switching market",
     "seed_arxiv": None},

    # ----- learning -----
    {"key": "adaptive_expectations", "name": "Adaptive expectations / learning",
     "category": "learning", "query": "adaptive expectations learning market",
     "seed_arxiv": None},
]
