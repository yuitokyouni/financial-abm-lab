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
    title_any: list[str]
    seed_arxiv: str | None


SUBFIELDS: list[Subfield] = [
    # ----- foundational models -----
    {"key": "minority_game", "name": "Minority Game", "category": "foundational",
     "query": "Minority game", "title_any": ["minority"],
     "seed_arxiv": "adap-org/9708006"},
    {"key": "lux_marchesi", "name": "Lux-Marchesi chartist-fundamentalist",
     "category": "foundational", "query": "chartist fundamentalist",
     "title_any": ["chartist", "fundamentalist"],
     "seed_arxiv": "cond-mat/9810262"},
    {"key": "santa_fe_market", "name": "Santa Fe artificial stock market",
     "category": "foundational", "query": "artificial stock market",
     "title_any": ["artificial stock", "artificial market"],
     "seed_arxiv": None},
    {"key": "el_farol", "name": "El Farol bar problem",
     "category": "foundational", "query": "El Farol",
     "title_any": ["el farol"], "seed_arxiv": None},
    {"key": "kirman_ant", "name": "Kirman ant herding model",
     "category": "foundational", "query": "Kirman herding",
     "title_any": ["kirman", "herding"],
     "seed_arxiv": None},

    # ----- 6 stylized facts -----
    {"key": "heavy_tails", "name": "Heavy-tailed returns",
     "category": "stylized", "query": "heavy-tailed returns",
     "title_any": ["heavy tail", "fat tail", "power law", "return"],
     "seed_arxiv": None},
    {"key": "vol_clustering", "name": "Volatility clustering",
     "category": "stylized", "query": "volatility clustering",
     "title_any": ["volatility"],
     "seed_arxiv": None},
    {"key": "leverage_effect", "name": "Leverage effect",
     "category": "stylized", "query": "leverage effect",
     "title_any": ["leverage", "volatility"],
     "seed_arxiv": None},
    {"key": "long_memory_vol", "name": "Long memory in volatility",
     "category": "stylized", "query": "long memory in volatility",
     "title_any": ["long memory", "volatility"],
     "seed_arxiv": None},
    {"key": "agg_gaussianity", "name": "Aggregational Gaussianity",
     "category": "stylized", "query": "aggregational Gaussianity",
     "title_any": ["gaussian", "aggregation", "return"],
     "seed_arxiv": None},

    # ----- market microstructure -----
    {"key": "limit_order_book", "name": "Limit order book models",
     "category": "microstructure", "query": "limit order book",
     "title_any": ["order book"],
     "seed_arxiv": None},
    {"key": "market_impact", "name": "Market impact / price impact",
     "category": "microstructure", "query": "price impact",
     "title_any": ["price impact", "market impact"],
     "seed_arxiv": None},
    {"key": "bid_ask_spread", "name": "Bid-ask spread dynamics",
     "category": "microstructure", "query": "bid-ask spread",
     "title_any": ["bid-ask", "bid ask", "spread"],
     "seed_arxiv": None},
    {"key": "hft", "name": "High-frequency trading",
     "category": "microstructure", "query": "high frequency trading",
     "title_any": ["high frequency", "high-frequency"],
     "seed_arxiv": None},

    # ----- behavioral / heterogeneous agents -----
    {"key": "heterogeneous_beliefs", "name": "Heterogeneous beliefs (Brock-Hommes)",
     "category": "behavioral",
     "query": "heterogeneous beliefs",
     "title_any": ["heterogeneous", "belief", "expectation"],
     "seed_arxiv": None},
    {"key": "bounded_rationality", "name": "Bounded rationality in markets",
     "category": "behavioral", "query": "bounded rationality market",
     "title_any": ["bounded rationality", "market"],
     "seed_arxiv": None},
    {"key": "prospect_theory", "name": "Prospect theory in trading",
     "category": "behavioral", "query": "prospect theory trading",
     "title_any": ["prospect theory", "trading", "investor"],
     "seed_arxiv": None},

    # ----- network / contagion -----
    {"key": "financial_contagion", "name": "Financial contagion network",
     "category": "network", "query": "financial contagion",
     "title_any": ["financial contagion", "contagion"],
     "seed_arxiv": None},
    {"key": "systemic_risk", "name": "Systemic risk in networks",
     "category": "network", "query": "systemic risk network",
     "title_any": ["systemic risk", "financial network"],
     "seed_arxiv": None},
    {"key": "interbank", "name": "Interbank network",
     "category": "network", "query": "interbank network",
     "title_any": ["interbank"],
     "seed_arxiv": None},
    {"key": "fire_sale", "name": "Fire sale / forced liquidation",
     "category": "network", "query": "fire sale",
     "title_any": ["fire sale", "firesale", "liquidation"],
     "seed_arxiv": None},

    # ----- crisis / regime -----
    {"key": "bubbles_crashes", "name": "Bubbles and crashes",
     "category": "crisis", "query": "financial bubbles",
     "title_any": ["bubble", "crash"],
     "seed_arxiv": None},
    {"key": "log_periodic", "name": "Log-periodic crash precursors",
     "category": "crisis", "query": "log-periodic crash",
     "title_any": ["log-periodic", "log periodic"],
     "seed_arxiv": None},
    {"key": "regime_switching", "name": "Regime switching",
     "category": "crisis", "query": "regime switching financial market",
     "title_any": ["regime", "switching"],
     "seed_arxiv": None},

    # ----- learning -----
    {"key": "adaptive_expectations", "name": "Adaptive expectations / learning",
     "category": "learning", "query": "adaptive expectations financial market",
     "title_any": ["adaptive expectation", "learning", "expectation"],
     "seed_arxiv": None},
]
