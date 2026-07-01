"""gap_finder — detect under-explored cells in the research space.

The catalog of subfields, techniques, and ABM families is now broad
enough that the actionable next step is to flip the question: instead
of 'what HAS been done?' (canon-atlas) ask 'what HAS NOT been done that
is adjacent to high-density work?' (this module).

Three 2D views capture orthogonal kinds of gap:

  A. subfield × stylized_fact
     count of literature_methods rows whose mechanism_tags overlap
     a subfield's title_any tokens, broken down by which stylized
     facts each paper targets. An empty cell in an otherwise dense
     row = 'this subfield never asked about this fact.'

  B. abm_family × stylized_fact
     deviation of each family's median fingerprint value from real-
     market median, per dimension that maps to a stylized fact. A
     large deviation = 'this family fails to reproduce this fact at
     real-market scale' — a structural blind spot of the family.

  C. technique × subfield
     overlap between a technique's ref_papers and a subfield's
     matching papers. Zero overlap on a popular (technique × subfield)
     pair = 'no one has applied technique X in subfield Y.'

Salience score per cell = log(neighbour_density + 1) − log(this + 1),
weighted by view-specific multipliers. Top-N gaps surface as research
proposal candidates.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# Canonical 9-fact vocabulary (mirror of coverage._CANONICAL_FACTS but
# we duplicate to avoid coupling — coverage may change independently).
CANONICAL_FACTS = [
    "fat-tails", "vol-clustering", "leverage", "long-memory",
    "regime-switching", "aggregational-gaussianity",
    "absence-of-autocorr", "herding", "other",
]

# Which fingerprint dim(s) most directly probe each stylized fact.
# Used by view B to pick the right axis when measuring family deviation.
# A fact with no fingerprint mapping is skipped in view B (we can't
# measure it from runs).
FACT_TO_FINGERPRINT: dict[str, list[str]] = {
    "fat-tails": ["kurtosis", "hill_tail_index"],
    "vol-clustering": ["acf_absret_mean"],
    "leverage": ["leverage"],
    "long-memory": ["acf_absret_long", "acf_absret_decay"],
    "absence-of-autocorr": ["acf_ret_l1"],
    "aggregational-gaussianity": ["agg_kurt_decay"],
    # regime-switching / herding / other have no direct 1-feature probe
}


# ----- normalisation helpers ---------------------------------------------

def _norm_tag(s: str) -> str:
    return re.sub(r"\s+", "-", s.strip().lower())


def _split_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        items = raw
    else:
        items = (raw or "").split(",")
    return [_norm_tag(x) for x in items if str(x).strip()]


def _matches_subfield(paper_tags: list[str], subfield: dict) -> bool:
    """A paper matches a subfield iff any of its mechanism_tags or
    oa_concepts contains a subfield title_any token (case-insensitive
    substring)."""
    title_any = [t.lower() for t in (subfield.get("title_any") or [])]
    if not title_any:
        title_any = [subfield["name"].split()[0].lower()]
    haystack = " ".join(paper_tags).lower()
    return any(needle in haystack for needle in title_any)


# ----- views --------------------------------------------------------------

@dataclass
class GapView:
    name: str          # 'A' / 'B' / 'C'
    title: str         # human-readable
    row_labels: list[str]
    col_labels: list[str]
    matrix: np.ndarray   # shape (rows, cols), values >= 0
    salience: np.ndarray # same shape; higher = more interesting gap
    higher_is_gap: bool  # for view A & C: empty cells = gap (value=0)
                          # for view B: large deviation = gap
    description: str   # 1-2 line interpretation hint


def _build_view_a(rows: list[dict], subfields: list[dict]
                   ) -> GapView:
    """subfield × stylized_fact — paper count per cell."""
    facts = CANONICAL_FACTS
    M = np.zeros((len(subfields), len(facts)), dtype=int)
    for paper in rows:
        tags = _split_tags(paper.get("mechanism_tags"))
        concepts = _split_tags(paper.get("oa_concepts"))
        paper_facts = _split_tags(paper.get("stylized_facts_targeted"))
        if not paper_facts:
            continue
        haystack_tags = tags + concepts
        for i, sf in enumerate(subfields):
            if _matches_subfield(haystack_tags, sf):
                for f in paper_facts:
                    if f in facts:
                        M[i, facts.index(f)] += 1
    salience = _salience_empty_in_dense_row(M)
    return GapView(
        name="A",
        title="subfield × stylized-fact (paper count)",
        row_labels=[sf["name"] for sf in subfields],
        col_labels=facts,
        matrix=M,
        salience=salience,
        higher_is_gap=False,
        description=(
            "Empty cell in a dense row = this subfield has many papers "
            "in the corpus but none target this stylized fact. The most "
            "actionable view for proposing concrete experiments."
        ),
    )


def _build_view_b(runs_by_model: dict[str, list[dict]],
                   families: list[dict],
                   feature_names: list[str]) -> GapView:
    """abm_family × stylized_fact — |family_median − real_median| / real_std."""
    facts_with_fp = [f for f in CANONICAL_FACTS if f in FACT_TO_FINGERPRINT]
    fam_keys = [f["key"] for f in families
                 if f["key"] in runs_by_model]

    # Real-market baseline median + std, per fingerprint dim
    real_dims: dict[str, list[float]] = {fn: [] for fn in feature_names}
    for model, runs in runs_by_model.items():
        if not model.startswith("real_"):
            continue
        for r in runs:
            fp = r.get("_fp")
            if fp is None:
                continue
            if len(fp) != len(feature_names):
                # Skip runs whose fingerprint dim doesn't match current schema —
                # e.g. persisted from an older feature set. Silent because this
                # is expected during feature-set migrations.
                continue
            for j, fn in enumerate(feature_names):
                v = fp[j]
                if np.isfinite(v):
                    real_dims[fn].append(v)
    real_med = {fn: (np.median(v) if v else np.nan) for fn, v in real_dims.items()}
    real_std = {fn: (np.std(v) if len(v) > 1 else 1.0) for fn, v in real_dims.items()}

    M = np.zeros((len(fam_keys), len(facts_with_fp)), dtype=float)
    for i, k in enumerate(fam_keys):
        fam_dims: dict[str, list[float]] = {fn: [] for fn in feature_names}
        for r in runs_by_model.get(k, []):
            fp = r.get("_fp")
            if fp is None:
                continue
            if len(fp) != len(feature_names):
                continue
            for j, fn in enumerate(feature_names):
                v = fp[j]
                if np.isfinite(v):
                    fam_dims[fn].append(v)
        for c, fact in enumerate(facts_with_fp):
            dims = FACT_TO_FINGERPRINT[fact]
            devs = []
            for fn in dims:
                if not fam_dims[fn] or not np.isfinite(real_med[fn]):
                    continue
                fam_m = np.median(fam_dims[fn])
                if real_std[fn] > 1e-9:
                    devs.append(abs(fam_m - real_med[fn]) / real_std[fn])
            M[i, c] = float(np.mean(devs)) if devs else 0.0
    # Salience: just the matrix itself (large = blind spot), normalised
    sal = M / (M.max() + 1e-9) if M.size else M.copy()
    return GapView(
        name="B",
        title="abm_family × stylized-fact (z-distance from real-market median)",
        row_labels=fam_keys,
        col_labels=facts_with_fp,
        matrix=M,
        salience=sal,
        higher_is_gap=True,
        description=(
            "Large value = the family's median fingerprint on this fact is "
            "far (in real-market sigma units) from observed markets. "
            "Reading: 'this family does not reproduce this fact at real-"
            "market scale.' Structural blind spot worth a fix."
        ),
    )


def _build_view_c(rows: list[dict], techniques: list[dict],
                   subfields: list[dict]) -> GapView:
    """technique × subfield — count of papers in subfield S that reference
    technique T (via T.ref_papers ∩ S's matching papers).

    Key normalisation: arxiv ids stored in literature_methods may carry a
    version suffix ('cond-mat/9908480v3'); technique.ref_papers usually
    don't. Strip the suffix on BOTH sides when keying. Also accept the
    OpenAlex synthetic id ('oa:Wxxxx') and treat the W-id as a backup
    join key against techniques that cite an OA work directly.
    """
    by_key: dict[str, str] = {}  # normalised id → original arxiv_id
    for p in rows:
        aid = p.get("arxiv_id")
        if not aid:
            continue
        base = re.sub(r"v\d+$", "", aid.strip())
        by_key[base] = aid
        # Also index by full id (with version) so exact-match refs work
        if base != aid:
            by_key[aid] = aid
        # OpenAlex W-id indexed too (so a technique that cites 'W12345' or
        # 'oa:W12345' matches an OA-ingested row). Only from the actual OA
        # field — never from arxiv_id, which is a different namespace.
        oa = p.get("oa_paper_id") or ""
        m = re.search(r"(W\d+)", oa)
        if m:
            by_key[m.group(1)] = aid
            by_key[f"oa:{m.group(1)}"] = aid

    # For each subfield, find matching paper arxiv_ids in DB.
    subfield_papers: dict[str, set[str]] = {}
    for sf in subfields:
        keep = set()
        for p in rows:
            aid = p.get("arxiv_id")
            if not aid:
                continue
            tags = (_split_tags(p.get("mechanism_tags"))
                     + _split_tags(p.get("oa_concepts")))
            if _matches_subfield(tags, sf):
                keep.add(aid)
        subfield_papers[sf["key"]] = keep

    M = np.zeros((len(techniques), len(subfields)), dtype=int)
    for i, t in enumerate(techniques):
        t_papers = set()
        for ref in (t.get("ref_papers") or []):
            r = str(ref).strip()
            # Try in priority: raw, base (version-stripped), W-id
            for candidate in (r, re.sub(r"v\d+$", "", r)):
                if candidate in by_key:
                    t_papers.add(by_key[candidate])
                    break
        for j, sf in enumerate(subfields):
            M[i, j] = len(t_papers & subfield_papers[sf["key"]])
    salience = _salience_empty_in_dense_row(M)
    return GapView(
        name="C",
        title="technique × subfield (paper overlap)",
        row_labels=[t["name"] for t in techniques],
        col_labels=[sf["name"] for sf in subfields],
        matrix=M,
        salience=salience,
        higher_is_gap=False,
        description=(
            "Zero cell where both the technique AND the subfield are well-"
            "represented elsewhere = 'no one has applied this technique in "
            "this subfield.' Often the highest-novelty proposal slots."
        ),
    )


def _salience_empty_in_dense_row(M: np.ndarray) -> np.ndarray:
    """Salience for 'empty cell in dense row + column' style gaps.

    score(i, j) = log(row_total(i) + col_total(j) + 1) − log(M(i,j) + 1)

    High when row & column are dense but this specific cell is sparse.
    """
    if M.size == 0:
        return M.astype(float)
    row_tot = M.sum(axis=1, keepdims=True)
    col_tot = M.sum(axis=0, keepdims=True)
    sal = np.log(row_tot + col_tot + 1) - np.log(M + 1)
    return sal


# ----- top-level entry ----------------------------------------------------

@dataclass
class Gap:
    view: str
    row: str
    col: str
    value: float       # raw cell value (count or distance)
    salience: float
    row_total: float
    col_total: float
    why: str           # short human-readable reason


def _gap_why(view: GapView, i: int, j: int) -> str:
    row_tot = float(view.matrix[i].sum())
    col_tot = float(view.matrix[:, j].sum())
    val = float(view.matrix[i, j])
    if view.name == "A":
        return (f"subfield has {int(row_tot)} mechanism×fact entries total "
                f"but 0 targeting {view.col_labels[j]}.")
    if view.name == "B":
        return (f"family deviates {val:.2f}σ from real-market median on "
                f"{view.col_labels[j]} — likely structural failure to "
                f"reproduce this fact.")
    if view.name == "C":
        return (f"technique appears in {int(row_tot)} subfield linkages and "
                f"subfield in {int(col_tot)} technique linkages, but no paper "
                f"in the corpus combines them.")
    return ""


def build_views(rows: list[dict], runs: list[dict],
                subfields: list[dict], techniques: list[dict],
                families: list[dict],
                feature_names: list[str]) -> list[GapView]:
    # Pre-parse fingerprints for view B.
    runs_by_model: dict[str, list[dict]] = {}
    for r in runs:
        fp_raw = r.get("fingerprint_json")
        if fp_raw:
            try:
                fp = np.asarray(json.loads(fp_raw), dtype=float)
            except (ValueError, TypeError):
                fp = None
        else:
            fp = None
        r2 = dict(r)
        r2["_fp"] = fp
        runs_by_model.setdefault(r["model_name"], []).append(r2)

    views = [
        _build_view_a(rows, subfields),
        _build_view_b(runs_by_model, families, feature_names),
        _build_view_c(rows, techniques, subfields),
    ]
    return views


# Columns that are catch-all / meta and not meaningful as a 'gap' target.
# 'other' in the stylized-fact axis groups everything that didn't fit a
# canonical bucket, so an empty cell on the 'other' column tells us
# nothing.
_GAP_NOISE_COLS = frozenset({"other"})


def rank_top_gaps(views: list[GapView], *, top_n: int = 20,
                   view_weights: dict[str, float] | None = None,
                   min_row_total: int = 3, min_col_total: int = 1
                   ) -> list[Gap]:
    """Flatten all view cells, sort by (weighted salience), take top-N.

    Filters applied before ranking:
      - skip catch-all columns (`other`) — those are meta-buckets, not
        actual stylized facts to target
      - skip cells whose row OR column is too sparse to constitute a
        meaningful gap (row_total < min_row_total, col_total < min_col_total)
      - view A / C: skip cells with value > 0 (gap = empty)
      - view B: skip cells with deviation < 0.5σ (not really a gap)
    """
    weights = {"A": 1.0, "B": 1.3, "C": 1.0}
    if view_weights:
        weights.update(view_weights)
    all_gaps: list[Gap] = []
    for v in views:
        if v.matrix.size == 0:
            continue
        w = weights.get(v.name, 1.0)
        for i in range(v.matrix.shape[0]):
            for j in range(v.matrix.shape[1]):
                col_label = v.col_labels[j]
                if col_label in _GAP_NOISE_COLS:
                    continue
                val = float(v.matrix[i, j])
                row_tot = float(v.matrix[i].sum())
                col_tot = float(v.matrix[:, j].sum())
                if v.higher_is_gap:
                    # view B: keep only cells with non-trivial deviation
                    if val < 0.5:
                        continue
                else:
                    # view A / C: empty cell IS the gap, but row+col must
                    # be dense enough for the empty cell to be interesting
                    if val > 0:
                        continue
                    if row_tot < min_row_total or col_tot < min_col_total:
                        continue
                sal = float(v.salience[i, j]) * w
                all_gaps.append(Gap(
                    view=v.name,
                    row=v.row_labels[i],
                    col=col_label,
                    value=val,
                    salience=sal,
                    row_total=row_tot,
                    col_total=col_tot,
                    why=_gap_why(v, i, j),
                ))
    all_gaps.sort(key=lambda g: g.salience, reverse=True)
    return all_gaps[:top_n]


def find_gaps(rows: list[dict], runs: list[dict], *,
              feature_names: list[str] | None = None,
              top_n: int = 20) -> tuple[list[GapView], list[Gap]]:
    """One-call helper used by the CLI + dashboard. Pulls subfields /
    techniques / families from the curated modules."""
    from .subfields import SUBFIELDS
    from .techniques import TECHNIQUES
    from .abm_families import ABM_FAMILIES
    from .fingerprint import FEATURE_NAMES
    feats = feature_names or FEATURE_NAMES
    views = build_views(rows, runs, list(SUBFIELDS), list(TECHNIQUES),
                         list(ABM_FAMILIES), feats)
    top = rank_top_gaps(views, top_n=top_n)
    return views, top
