"""coverage — (mechanism × stylized fact) heat-map over literature_methods.

Counts, per (mechanism tag, stylized fact), how many papers in the corpus
target that combination. Output:

  - markdown table (sorted by row total — biggest mechanism cluster on top)
  - matplotlib heatmap

The point is to surface research blind spots: a row dense in one column
but sparse in another suggests a literature gap worth proposing into.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


def _canonical_fact(s: str) -> str:
    """Normalise a fact label so 'fat tails' / 'fat-tails' / 'Fat Tails' all
    collapse to the same column."""
    return s.strip().lower().replace(" ", "-")


# Canonical stylized-fact vocabulary the rest of the codebase uses
# (mirrored by extraction prompt in arxiv_ingest + CANONICAL_FACTS in
# gap_finder — keep them in sync).
#
# Anchor: Cont 2001 "Empirical properties of asset returns: stylized
# facts and statistical issues" (Quant. Finance 1:223-236). We adopt
# Cont's list plus two mechanism-flavoured facts that show up in
# financial-ABM lit (herding, regime-switching) since papers here
# routinely target those as reproducible signatures.
_CANONICAL_FACTS = [
    # Cont 2001 canonical
    "fat-tails", "vol-clustering", "leverage", "long-memory",
    "aggregational-gaussianity", "absence-of-autocorr",
    "gain-loss-asymmetry", "volume-volatility-corr",
    # ABM-specific stylized targets
    "regime-switching", "herding",
    # catch-all — anything the LLM can't map cleanly
    "other",
]


# OpenAlex top-level fields-of-study that are too generic to act as a
# 'mechanism' label — they pollute the coverage matrix with empty rows.
_GENERIC_OA_CONCEPTS = frozenset({
    "Computer science", "Economics", "Business", "Mathematics",
    "Physics", "Engineering", "Psychology", "Finance",
    "Futures contract", "Algorithmic trading", "Artificial intelligence",
    "Machine learning", "Deep learning", "Optimization",
    "Mathematical economics", "Microeconomics", "Macro",
    "Industrial organization", "Financial economics",
    "Stylized fact",  # too generic AS A MECHANISM (it IS a target column)
})


#: Stylized-fact terms that should NEVER appear as a mechanism row —
#: they belong on the fact column only. The extraction prompt still
#: sometimes leaks these into mechanism_tags (e.g., a paper about the
#: leverage effect gets tagged with 'leverage' as its primary
#: mechanism), which then duplicates the same concept on both axes and
#: creates spurious rows like `leverage (6)` or `long-memory (9)`. We
#: skip these when picking the row's primary tag; the paper still lands
#: on the right column via stylized_facts_targeted.
_FACT_TERMS_NOT_MECHANISMS = frozenset({
    "leverage", "long-memory", "fat-tails", "vol-clustering",
    "absence-of-autocorr", "gain-loss-asymmetry",
    "aggregational-gaussianity", "volume-volatility-corr",
    "multifractal",  # data property, not a modeling technique
    "volatility",     # too broad — real methods are GARCH / stoch-vol / etc
})

#: Mechanism-tag terms that ARE modelling flags but are so generic they
#: don't inform the coverage matrix. Every paper in this corpus is an
#: ABM by construction; a paper tagged 'agent-based-model' as its
#: primary keyword is basically saying nothing. Skip these when picking
#: the row label so the actual mechanism (further down mechanism_tags)
#: gets promoted instead. If ALL of a paper's tags are generic, it
#: falls through to oa_concepts / 'untagged' as before.
_TOO_GENERIC_MECHANISMS = frozenset({
    "agent-based", "agent-based-model", "agent-based-modeling",
    "agent-based-simulation", "abm", "multi-agent", "multi-agent-model",
    "agent-model", "simulation", "computational-model",
    "framework", "model",
})


def _primary_tag(row: dict) -> str:
    """Mirror of literature_map.primary_tag with three extra filters:
    generic OpenAlex top-level concepts (Computer science / Economics /
    Business / etc) don't count as a mechanism label; stylized-fact
    terms (leverage / long-memory / fat-tails / …) are skipped so they
    don't duplicate on both matrix axes; and too-generic ABM labels
    (agent-based-model / simulation / framework — the corpus is 100%
    ABMs, so tagging a paper 'agent-based-model' as its primary
    mechanism says nothing) are also skipped in favour of the next,
    more specific tag."""
    tags = row.get("mechanism_tags") or []
    for t in tags:
        norm = _canonical_fact(t)
        if not norm:
            continue
        if norm in _FACT_TERMS_NOT_MECHANISMS:
            continue
        if norm in _TOO_GENERIC_MECHANISMS:
            continue
        return t
    for concept in (row.get("oa_concepts") or "").split(","):
        c = concept.strip()
        if c and c not in _GENERIC_OA_CONCEPTS:
            return c
    return "untagged"


def build_coverage(rows: list[dict], *, top_rows: int = 15,
                    facts: list[str] | None = None
                    ) -> dict[str, Any]:
    """Return {row_labels, col_labels, matrix, row_totals, col_totals}.

    Rows: top-N mechanism tags by paper count.
    Cols: canonical stylized facts vocabulary (over-ridable).
    Cells: count of papers tagged with this fact in this mechanism."""
    cols = facts or _CANONICAL_FACTS

    tag_counts = Counter(_primary_tag(r) for r in rows)
    # Drop rows whose papers have zero targeted-fact intersections — they
    # contribute nothing to the heatmap and just create visual noise.
    candidate_tags = [t for t, _ in tag_counts.most_common(top_rows * 2)]
    row_labels: list[str] = []
    for t in candidate_tags:
        if len(row_labels) >= top_rows:
            break
        # quick relevance check: at least one paper with this tag has a
        # canonical fact in its stylized_facts_targeted.
        has_any = False
        for r in rows:
            if _primary_tag(r) != t:
                continue
            for raw in (r.get("stylized_facts_targeted") or []):
                if _canonical_fact(raw) in cols:
                    has_any = True
                    break
            if has_any:
                break
        if has_any:
            row_labels.append(t)
    col_idx = {c: j for j, c in enumerate(cols)}
    row_idx = {t: i for i, t in enumerate(row_labels)}

    M = np.zeros((len(row_labels), len(cols)), dtype=int)
    for r in rows:
        i = row_idx.get(_primary_tag(r))
        if i is None:
            continue
        for raw_fact in (r.get("stylized_facts_targeted") or []):
            j = col_idx.get(_canonical_fact(raw_fact))
            if j is not None:
                M[i, j] += 1

    # Mark tautological diagonal cells (row-name == column-name) as
    # excluded — e.g., 'regime-switching × regime-switching' or
    # 'herding × herding'. A paper whose mechanism IS regime-switching
    # producing the regime-switching stylized fact is trivially true and
    # doesn't inform coverage or gaps. Same for other future ABM-specific
    # facts (herding). We keep the count for the markdown table
    # (documentation) but flag which cells to grey out at render time.
    excluded_cells: set[tuple[int, int]] = set()
    for i, r_label in enumerate(row_labels):
        r_norm = _canonical_fact(r_label)
        j = col_idx.get(r_norm)
        if j is not None:
            excluded_cells.add((i, j))

    return {
        "row_labels": row_labels,
        "col_labels": cols,
        "matrix": M,
        "row_totals": M.sum(axis=1).tolist(),
        "col_totals": M.sum(axis=0).tolist(),
        "n_papers_total": len(rows),
        "n_papers_classified": sum(1 for r in rows
                                    if _primary_tag(r) in row_idx),
        "excluded_cells": excluded_cells,
    }


def render_heatmap(cov: dict, png_path: str, *, figsize=(12.0, 8.0),
                    dpi: int = 120) -> None:
    """Render the coverage matrix as an annotated heatmap. Empty cells are
    visually distinct (white) so research blind spots jump out."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    M = cov["matrix"]
    row_labels = cov["row_labels"]
    col_labels = cov["col_labels"]
    excluded = cov.get("excluded_cells") or set()

    # Prepare a display matrix where excluded cells are NaN so the
    # colour map treats them as "no data" instead of packing them into
    # the count scale (a tautological 7 was topping the whole matrix).
    M_display = M.astype(float).copy()
    for (i, j) in excluded:
        M_display[i, j] = np.nan

    fig, ax = plt.subplots(figsize=figsize)
    cmap = plt.cm.YlOrRd.with_extremes(under="white", bad="#e5e5e5")
    finite_max = np.nanmax(M_display) if np.isfinite(M_display).any() else 1.0
    vmax = max(int(finite_max), 2)  # >= 2 keeps vmin=0.5 < vmax non-singular
    im = ax.imshow(M_display, cmap=cmap, vmin=0.5, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels([f"{r} ({cov['row_totals'][i]})"
                          for i, r in enumerate(row_labels)], fontsize=9)
    ax.set_xlabel("stylized fact targeted (paper extraction)")
    ax.set_ylabel("primary mechanism tag")
    ax.set_title(f"Literature coverage — "
                  f"{cov['n_papers_classified']}/{cov['n_papers_total']} papers")

    # Cell annotations — count, '·' for empty, or 'N/A' for tautologies.
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if (i, j) in excluded:
                ax.text(j, i, "N/A", ha="center", va="center",
                         color="#888", fontsize=7, style="italic")
                continue
            v = M[i, j]
            ax.text(j, i, str(v) if v > 0 else "·",
                     ha="center", va="center",
                     color="black" if v < vmax * 0.6 else "white",
                     fontsize=8)
    fig.colorbar(im, ax=ax, label="paper count")
    plt.tight_layout()
    plt.savefig(png_path, dpi=dpi)
    plt.close()


def render_markdown(cov: dict) -> str:
    """Render the same matrix as a sortable markdown table."""
    cols = cov["col_labels"]
    rows = cov["row_labels"]
    M = cov["matrix"]
    excluded = cov.get("excluded_cells") or set()
    lines = ["| mechanism (n) | " + " | ".join(cols) + " | total |"]
    lines.append("|" + " --- |" * (len(cols) + 2))
    for i, r in enumerate(rows):
        cells = ["_N/A_" if (i, j) in excluded
                  else (str(M[i, j]) if M[i, j] > 0 else "·")
                 for j in range(len(cols))]
        # row total excludes tautological diagonal
        row_total = sum(int(M[i, j]) for j in range(len(cols))
                         if (i, j) not in excluded)
        lines.append(f"| **{r}** ({cov['row_totals'][i]}) | "
                     + " | ".join(cells) + f" | {row_total} |")
    # Column totals
    lines.append("| _total_ | "
                 + " | ".join(str(int(t)) for t in cov["col_totals"])
                 + f" | **{int(M.sum())}** |")
    return "\n".join(lines)
