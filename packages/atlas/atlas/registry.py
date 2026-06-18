"""Frozen semantic registry — the labeling layer the CI gate does NOT decide.

spec 002 §6: operational dependence is not eliminated, it is *confined to the
semantic layer*. The CI submission gate (``contract.check_determinism`` etc.)
decides schema/determinism/prov; it does **not** decide "is this really LM?" or
"which mechanism label does this response belong under?". Those judgments live
here, in a frozen registry, versioned and changed deliberately (spec 002 §12).

``declared_channels`` is the mechanism's *intended* B2 observation surface (a
semantic claim about the model). It is distinct from the *exposed* channels the
contract currently offers, which are ``()`` for every canonical ``run(seed)``
model until the order-book channel work (Finding 0002) wires them. The Atlas
records both, so neither is overstated (spec 002 §4 / §11).

The launch row set satisfies the spec 002 §7 diversity constraint — see
``diversity_coverage()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from abm_models import REGISTRY as MODEL_REGISTRY


@dataclass(frozen=True, slots=True)
class SemanticLabel:
    """Frozen semantic metadata for one model family."""

    name: str
    family: str
    mechanism_label: str
    reference: str
    declared_channels: tuple[str, ...]
    atlas_eligible: bool = True
    #: diversity tags this row satisfies (spec 002 §7).
    diversity_tags: tuple[str, ...] = ()
    notes: str = ""
    #: small, fast config for reference-atlas generation (not the paper-grade run).
    atlas_config: dict[str, Any] = field(default_factory=dict)


# --- spec 002 §7 diversity constraint targets ---
NULL_CONTROL = "null_or_negative_control"
SF_ORIENTED = "stylized_facts_oriented"
LEARNING = "learning_or_feedback"
ORDER_BOOK = "order_book_or_microstructure"
KNOWN_FAILURE = "known_failure_or_non_separation"
P1_EXPERIMENT = "used_in_p1_intervention_experiment"

REQUIRED_DIVERSITY = (NULL_CONTROL, SF_ORIENTED, LEARNING, ORDER_BOOK, KNOWN_FAILURE, P1_EXPERIMENT)


FROZEN_REGISTRY: dict[str, SemanticLabel] = {
    "zero_intelligence": SemanticLabel(
        name="zero_intelligence",
        family="null/zero-intelligence",
        mechanism_label="ZI constrained (budget-constrained random orders)",
        reference="Gode & Sunder 1993; Farmer-Patelli-Zovko 2005",
        declared_channels=(),  # strategy-free, no observation channel → B2-null by design
        diversity_tags=(NULL_CONTROL,),
        notes="negative control; {CB, ZI} predicted response-equivalent (program_claims §2.2)",
        atlas_config={"n_agents": 100, "n_steps": 2000},
    ),
    "cont_bouchaud": SemanticLabel(
        name="cont_bouchaud",
        family="stylized-facts/percolation",
        mechanism_label="Cont-Bouchaud herding (exogenous cluster formation)",
        reference="Cont & Bouchaud 1997",
        declared_channels=(),  # clustering is exogenous → no B2 surface (classical form)
        diversity_tags=(SF_ORIENTED, NULL_CONTROL),
        notes="SF-oriented; channel-less classical form is the {CB,ZI} equivalence anchor",
        atlas_config={"N": 300, "c": 0.9, "a": 0.01, "T": 400, "report_every": 0},
    ),
    "lux_marchesi": SemanticLabel(
        name="lux_marchesi",
        family="learning/feedback",
        mechanism_label="Lux-Marchesi chartist/fundamentalist switching",
        reference="Lux & Marchesi 2000",
        declared_channels=("price_returns", "agg_action"),
        diversity_tags=(LEARNING,),
        notes="endogenous switching near criticality; B2 surface pending (Finding 0002)",
        atlas_config={"n_integer_steps": 2000, "steps_per_unit": 10, "n_c_init": 50},
    ),
    "franke_westerhoff": SemanticLabel(
        name="franke_westerhoff",
        family="learning/sentiment",
        mechanism_label="Franke-Westerhoff sentiment herding",
        reference="Franke & Westerhoff 2012",
        declared_channels=("price_returns", "agg_action"),
        diversity_tags=(LEARNING,),
        notes="sentiment-driven fundamentalist/chartist switch",
        atlas_config={"n_steps": 2000},
    ),
    "chiarella_iori": SemanticLabel(
        name="chiarella_iori",
        family="order-book/microstructure",
        mechanism_label="Chiarella-Iori order-book (fund/chart/noise on a CLOB)",
        reference="Chiarella, Iori & Perelló 2009",
        declared_channels=("price_returns", "fundamental"),
        diversity_tags=(ORDER_BOOK, P1_EXPERIMENT),
        notes="order-book mechanism; Model T母体 of the P1 intervention experiment",
        atlas_config={"n_steps": 2000},
    ),
    "speculation_game": SemanticLabel(
        name="speculation_game",
        family="learning/strategy",
        mechanism_label="Speculation Game (Katahira-Chen inductive speculation)",
        reference="Katahira & Chen 2019",
        declared_channels=("price_returns",),
        diversity_tags=(LEARNING,),
        notes="self-reference SG; auxiliary mechanism (program_claims §2.2)",
        atlas_config={"N": 200, "M": 5, "S": 2, "T": 2000, "backend": "vectorized"},
    ),
    "minority_game": SemanticLabel(
        name="minority_game",
        family="learning/inductive",
        mechanism_label="Challet-Zhang Minority Game (attendance, price-less)",
        reference="Challet & Zhang 1997",
        declared_channels=("history",),
        diversity_tags=(KNOWN_FAILURE,),
        notes="price-less: return SF battery non-applicable (structured failure note)",
        atlas_config={"N": 101, "M": 6, "S": 2, "T": 2000},
    ),
    "gcmg": SemanticLabel(
        name="gcmg",
        family="learning/grand-canonical",
        mechanism_label="Grand-Canonical Minority Game (attendance, price-less)",
        reference="Jefferies et al. 2001",
        declared_channels=("history",),
        diversity_tags=(KNOWN_FAILURE,),
        notes="price-less: return SF battery non-applicable (structured failure note)",
        atlas_config={"N": 101, "M": 2, "S": 2, "T_total": 3000, "T_win": 50},
    ),
}


def eligible_models() -> list[str]:
    """Names of registry models that are Atlas-eligible AND have an implementation."""
    return [n for n, lab in FROZEN_REGISTRY.items() if lab.atlas_eligible and n in MODEL_REGISTRY]


def build_model(name: str) -> Any:
    """Instantiate a canonical model with its frozen atlas_config (small/fast)."""
    if name not in MODEL_REGISTRY:
        raise KeyError(f"{name} not in abm_models.REGISTRY")
    cls = MODEL_REGISTRY[name]
    return cls(**FROZEN_REGISTRY[name].atlas_config)


def diversity_coverage(names: list[str] | None = None) -> dict[str, list[str]]:
    """Map each required diversity tag → the models covering it (spec 002 §7)."""
    names = names or eligible_models()
    cover: dict[str, list[str]] = {tag: [] for tag in REQUIRED_DIVERSITY}
    for n in names:
        for tag in FROZEN_REGISTRY[n].diversity_tags:
            if tag in cover:
                cover[tag].append(n)
    return cover


def diversity_satisfied(names: list[str] | None = None) -> bool:
    """True iff every required diversity tag has ≥1 covering model."""
    return all(v for v in diversity_coverage(names).values())
