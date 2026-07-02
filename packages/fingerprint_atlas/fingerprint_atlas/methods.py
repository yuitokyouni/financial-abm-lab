"""methods — the methodology-commentary store.

A row per *method / mechanism* (not per run): the 8 canonical ABMs, the 3
synthetic processes used as instrument probes, and any future LLM-based
agent designs or experiment-design patterns. Each row carries:

  - an objective, source-grounded mechanism description (seeded from papers)
  - four free-form text fields the user fills in over time:
      novelty_notes        — methodological-novelty assessment
      mechanism_strengths  — what this approach captures well
      mechanism_weaknesses — what's missing / weak / under-mechanised
      research_questions   — open questions arising from this method
  - free tags (comma-separated)

The objective layer (fingerprint atlas, stylized-facts search) stays
algorithmic. The judgment encoded here is the user's *research taste* at the
method level — the part that has to be a human, and the part that is
genuinely hard to copy because it accumulates one careful read at a time.

Storage: a single table `methods` in the same SQLite DB as `techniques` and
`runs`. The schema is additive; `ensure_methods_schema` is idempotent and
performs ALTER TABLE migrations for new columns if any.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any


METHODS_SCHEMA = """
CREATE TABLE IF NOT EXISTS methods (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL UNIQUE,    -- matches runs.model_name when applicable
    kind                 TEXT NOT NULL,           -- 'abm' | 'synthetic' | 'llm_method' | 'experiment_design'
    mechanism            TEXT NOT NULL,           -- 1-3 sentence objective description
    references_json      TEXT NOT NULL DEFAULT '[]',
    novelty_notes        TEXT NOT NULL DEFAULT '',
    mechanism_strengths  TEXT NOT NULL DEFAULT '',
    mechanism_weaknesses TEXT NOT NULL DEFAULT '',
    research_questions   TEXT NOT NULL DEFAULT '',
    tags                 TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
"""

_METHODS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_methods_kind ON methods(kind)",
]

#: Initial seed. Mechanism descriptions are sourced from the original papers
#: of each method; the four commentary columns start empty for the user.
SEED: list[dict[str, Any]] = [
    {
        "name": "speculation_game",
        "kind": "abm",
        "mechanism": (
            "N agents each carry S strategy tables of length 5^M mapping a recent "
            "quantised-return history μ to an action in {-1, 0, +1}. The aggregate "
            "excess demand drives a real price p while a cumulative quantised return "
            "drives a cognitive price P; agents swap to the strategy with the "
            "highest virtual P&L computed against P. Bankruptcy resets an agent's "
            "strategy bank."
        ),
        "references": ["arXiv:1906.01034", "Katahira & Chen 2019"],
    },
    {
        "name": "cont_bouchaud",
        "kind": "abm",
        "mechanism": (
            "Each step a random Erdős-Rényi graph over N agents (edge probability "
            "c/N) defines clusters of co-acting traders. Every cluster independently "
            "buys, sells, or holds with probabilities a, a, 1-2a; the price return "
            "is (sum of signed cluster sizes)/λ. Power-law cluster sizes near "
            "the percolation threshold produce fat-tailed returns."
        ),
        "references": ["Cont & Bouchaud 1997 (Macroeconomic Dynamics 4(2))"],
    },
    {
        "name": "lux_marchesi",
        "kind": "abm",
        "mechanism": (
            "Three populations — optimistic chartists (n+), pessimistic chartists "
            "(n-), and fundamentalists (n_f) — transition with rates set by recent "
            "price moves, opinion difference, and the fundamental gap p_f - p. "
            "Price moves up/down by a fixed tick with probability β·(ED + μ) where "
            "ED is the excess demand. Volatility clustering arises from rare crowd "
            "switches; tails come from large multinomial transitions."
        ),
        "references": ["Lux & Marchesi 2000 (IJTAF 3(4))"],
    },
    {
        "name": "minority_game",
        "kind": "abm",
        "mechanism": (
            "N agents each hold S binary strategies mapping the last M winning "
            "sides (history μ ∈ [0, 2^M)) to an action in {±1}. They pick the "
            "strategy with highest virtual capital. The side picked by the minority "
            "of agents wins; σ²/N (variance of attendance) traces a U-curve in "
            "α = 2^M/N showing a phase transition from random to inductive."
        ),
        "references": ["Challet & Zhang 1997 (Physica A 246)"],
    },
    {
        "name": "gcmg",
        "kind": "abm",
        "mechanism": (
            "Minority Game extended by giving each agent an extra 'abstain' option: "
            "an agent participates only if its best strategy's virtual capital "
            "exceeds an entry threshold r_min. Population size becomes endogenous; "
            "the resulting attendance time series shows fat tails (large kurtosis) "
            "absent from the canonical MG."
        ),
        "references": ["Jefferies, Hart, Hui, Johnson 2001 (Eur. Phys. J. B)"],
    },
    {
        "name": "chiarella_iori",
        "kind": "abm",
        "mechanism": (
            "Reduced-form price-impact model with three demand components — "
            "fundamentalists pulling price toward a fixed fair value, chartists "
            "extrapolating recent trends, and Gaussian noise. Net demand moves a "
            "scalar pseudo bid/ask via a deterministic linear price-impact function "
            "on a tick grid; there is NO limit-order book and NO order matching. "
            "Loosely inspired by Chiarella, Iori & Perelló (2009) but not a faithful "
            "continuous-double-auction implementation."
        ),
        "references": ["Chiarella, Iori & Perelló 2009 (loosely inspired, not faithful)"],
    },
    {
        "name": "zero_intelligence",
        "kind": "abm",
        "mechanism": (
            "Gode-Sunder null baseline: agents submit random limit orders subject "
            "only to a budget constraint, with no strategy switching and no use of "
            "information. Prices emerge purely from random order flow against the "
            "tick grid. Used as a structural falsification benchmark — any ABM "
            "claim should outperform ZI-C."
        ),
        "references": ["Gode & Sunder 1993 (J. Political Economy 101(1))"],
    },
    {
        "name": "franke_westerhoff",
        "kind": "abm",
        "mechanism": (
            "Reduced-form fundamentalist/chartist model. Population-weighted excess "
            "demand (fundamentalist mean-reversion + chartist extrapolation of the "
            "last return + Gaussian noise) drives a price-impact update. The chartist "
            "fraction evolves by an ad-hoc LINEAR switching rule (attraction ∝ "
            "|last return| and |mispricing|, offset by a constant and clipped) — NOT "
            "the discrete-choice / transition-probability mechanism of Franke & "
            "Westerhoff (2012); no herding term and no wealth. Loosely inspired, not "
            "faithful."
        ),
        "references": ["Franke & Westerhoff 2012 (loosely inspired, not faithful)"],
    },
    {
        "name": "garch11",
        "kind": "synthetic",
        "mechanism": (
            "Parametric conditional variance process: σ²_t = ω + α r²_{t-1} + "
            "β σ²_{t-1}, r_t = σ_t · z_t with z_t ~ N(0, 1). Volatility clustering "
            "via exponential decay of variance shocks; no agent-level mechanism, "
            "used as an objective probe against which the ABMs' clustering is "
            "compared (cf. instrument-validation atlas v3/v4)."
        ),
        "references": ["Bollerslev 1986 (J. Econometrics 31)"],
    },
    {
        "name": "levy_walk",
        "kind": "synthetic",
        "mechanism": (
            "α-stable returns r_t ~ S(α, β=0, c) generated by the Chambers-Mallows-"
            "Stuck algorithm. Fat tails are axiomatic (no clustering, no leverage, "
            "no autocorrelation by construction); used as a probe to check whether "
            "the fingerprint can isolate 'pure structural fat tails' from 'tails "
            "emerging via clustering'."
        ),
        "references": ["Chambers, Mallows & Stuck 1976 (JASA 71)"],
    },
    {
        "name": "regime_switch",
        "kind": "synthetic",
        "mechanism": (
            "Hidden Markov 2-state vol regime: a latent state s_t ∈ {low, high} "
            "evolves with fixed transition probabilities p_lo_hi, p_hi_lo. Within "
            "each state returns are i.i.d. Gaussian with state-specific volatility. "
            "Used as a Cont-outside probe for non-stationarity / regime structure."
        ),
        "references": ["Hamilton 1989 (Econometrica 57)"],
    },
]


@dataclass
class Method:
    id: int
    name: str
    kind: str
    mechanism: str
    references: list[str]
    novelty_notes: str
    mechanism_strengths: str
    mechanism_weaknesses: str
    research_questions: str
    tags: str
    created_at: str
    updated_at: str

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]


def _column_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def ensure_methods_schema(db_path: str) -> None:
    """Idempotent: create `methods` table + indexes; additive ALTER TABLE
    migrations for any new columns added in future versions."""
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(METHODS_SCHEMA)
        # Future column additions go here as ALTER TABLE ... IF NOT EXISTS
        for stmt in _METHODS_INDEXES:
            con.execute(stmt)
        con.commit()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def seed_methods(db_path: str, *, overwrite_mechanism: bool = False) -> dict:
    """Insert SEED rows for any methods not already in the table.

    overwrite_mechanism : if True, refresh the `mechanism` and `references_json`
                         columns for existing rows from SEED (keeps user
                         commentary columns intact). Use after updating SEED.
    """
    ensure_methods_schema(db_path)
    inserted, refreshed = 0, 0
    now = _now()
    with sqlite3.connect(db_path) as con:
        existing = {r[0]: r[1] for r in con.execute("SELECT name, id FROM methods").fetchall()}
        for s in SEED:
            if s["name"] not in existing:
                con.execute(
                    "INSERT INTO methods (name, kind, mechanism, references_json, "
                    "created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (s["name"], s["kind"], s["mechanism"],
                     json.dumps(s["references"]), now, now),
                )
                inserted += 1
            elif overwrite_mechanism:
                con.execute(
                    "UPDATE methods SET mechanism = ?, references_json = ?, "
                    "updated_at = ? WHERE name = ?",
                    (s["mechanism"], json.dumps(s["references"]), now, s["name"]),
                )
                refreshed += 1
        con.commit()
    return {"inserted": inserted, "refreshed": refreshed,
            "n_existing": len(existing), "n_seed": len(SEED)}


def list_methods(db_path: str, kind: str | None = None) -> list[Method]:
    sql = ("SELECT id, name, kind, mechanism, references_json, novelty_notes, "
           "mechanism_strengths, mechanism_weaknesses, research_questions, tags, "
           "created_at, updated_at FROM methods")
    args: tuple = ()
    if kind is not None:
        sql += " WHERE kind = ?"
        args = (kind,)
    sql += " ORDER BY kind, name"
    with sqlite3.connect(db_path) as con:
        rows = con.execute(sql, args).fetchall()
    out: list[Method] = []
    for r in rows:
        out.append(Method(
            id=r[0], name=r[1], kind=r[2], mechanism=r[3],
            references=json.loads(r[4] or "[]"),
            novelty_notes=r[5] or "", mechanism_strengths=r[6] or "",
            mechanism_weaknesses=r[7] or "", research_questions=r[8] or "",
            tags=r[9] or "", created_at=r[10], updated_at=r[11],
        ))
    return out


def get_method(db_path: str, name: str) -> Method | None:
    rs = list_methods(db_path)
    for m in rs:
        if m.name == name:
            return m
    return None


def update_method(db_path: str, name: str, *,
                  novelty_notes: str | None = None,
                  mechanism_strengths: str | None = None,
                  mechanism_weaknesses: str | None = None,
                  research_questions: str | None = None,
                  tags: str | None = None) -> None:
    """Patch any subset of the commentary columns. None means "don't touch"."""
    sets = []
    args: list[Any] = []
    for col, val in [
        ("novelty_notes", novelty_notes),
        ("mechanism_strengths", mechanism_strengths),
        ("mechanism_weaknesses", mechanism_weaknesses),
        ("research_questions", research_questions),
        ("tags", tags),
    ]:
        if val is not None:
            sets.append(f"{col} = ?")
            args.append(val)
    if not sets:
        return
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(name)
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            f"UPDATE methods SET {', '.join(sets)} WHERE name = ?",
            tuple(args),
        )
        if cur.rowcount == 0:
            raise KeyError(f"no method named {name!r}")
        con.commit()
