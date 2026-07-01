"""coverage — (mechanism × stylized fact) heat-map over literature_methods.

Counts, per (mechanism tag, stylized fact), how many papers in the corpus
target that combination. Output:

  - markdown table (sorted by row total — biggest mechanism cluster on top)
  - matplotlib heatmap

The point is to surface research blind spots: a row dense in one column
but sparse in another suggests a literature gap worth proposing into.

The classification vocabulary (fact list, mechanism deny-lists, method
families) lives in taxonomy.py — the single source of truth for the whole
atlas. This module handles matrix construction and rendering.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from .taxonomy import (
    CANONICAL_FACTS,
    FACT_TERMS_NOT_MECHANISMS,
    FAMILY_ORDER,
    GENERIC_OA_CONCEPTS,
    TOO_GENERIC_MECHANISMS,
    canonical_fact,
    method_family,
)

# ---------------------------------------------------------------------------
# Backwards-compat re-exports. External code and tests may still import the
# underscore-prefixed names from coverage — keep the shims working.
# ---------------------------------------------------------------------------
_canonical_fact = canonical_fact
_CANONICAL_FACTS = CANONICAL_FACTS
_GENERIC_OA_CONCEPTS = GENERIC_OA_CONCEPTS
_FACT_TERMS_NOT_MECHANISMS = FACT_TERMS_NOT_MECHANISMS
_TOO_GENERIC_MECHANISMS = TOO_GENERIC_MECHANISMS
_FAMILY_ORDER = FAMILY_ORDER


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
    candidate_tags = [t for t, _ in tag_counts.most_common(top_rows * 3)]
    kept: list[str] = []
    for t in candidate_tags:
        if len(kept) >= top_rows:
            break
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
            kept.append(t)
    # Group rows by method family so ABM / stat / ml sit in contiguous
    # bands. Within a family, keep the by-count order from tag_counts.
    kept_by_family: dict[str, list[str]] = {f: [] for f in _FAMILY_ORDER}
    for t in kept:
        kept_by_family[method_family(t)].append(t)
    row_labels: list[str] = []
    for f in _FAMILY_ORDER:
        row_labels.extend(kept_by_family[f])
    row_families = [method_family(t) for t in row_labels]
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
        "row_families": row_families,
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
    if M.size == 0 or not row_labels:
        # Empty corpus — write a placeholder PNG so callers get a file.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "no data — ingest papers first",
                 ha="center", va="center", fontsize=14, color="#666",
                 transform=ax.transAxes)
        ax.set_axis_off()
        plt.tight_layout()
        plt.savefig(png_path, dpi=dpi)
        plt.close()
        return

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

    row_families = cov.get("row_families") or [""] * len(row_labels)
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    _y_colors = {"ABM": "#1f6feb", "stat": "#a15c07", "ml": "#7c3aed",
                  "other": "#666"}
    ax.set_yticklabels(
        [f"[{row_families[i] or 'other':>3s}] {r} ({cov['row_totals'][i]})"
          for i, r in enumerate(row_labels)],
        fontsize=9,
    )
    for i, fam in enumerate(row_families):
        ax.get_yticklabels()[i].set_color(_y_colors.get(fam, "#333"))
    # Horizontal separators between families so the reader sees the
    # groups jump — ABM / stat / ml bands.
    for i in range(1, len(row_families)):
        if row_families[i] != row_families[i - 1]:
            ax.axhline(i - 0.5, color="#444", linewidth=1.2)
    ax.set_xlabel("stylized fact targeted (paper extraction)")
    ax.set_ylabel("primary mechanism tag (grouped by method family)")
    n_by_family = Counter(row_families)
    fam_summary = " · ".join(f"[{f}] {n_by_family[f]}"
                              for f in _FAMILY_ORDER if n_by_family[f])
    # The figure is a corpus theme distribution — which mechanism family
    # targets which stylized fact. NOT a research-gap map: an empty cell
    # can be an under-explored gap, a hard-to-measure fact, or a
    # single-label extraction artifact. The 143/N split had the
    # denominator as "everything ever ingested" which was misleading
    # (only classified papers actually appear here). Drop it.
    ax.set_title(f"Corpus theme distribution — mechanism × stylized fact\n"
                  f"{cov['n_papers_classified']} classified papers  ·  "
                  f"{fam_summary} families")

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
    families = cov.get("row_families") or [""] * len(rows)
    lines = ["| family | mechanism (n) | " + " | ".join(cols) + " | total |"]
    lines.append("|" + " --- |" * (len(cols) + 3))
    for i, r in enumerate(rows):
        cells = ["_N/A_" if (i, j) in excluded
                  else (str(M[i, j]) if M[i, j] > 0 else "·")
                 for j in range(len(cols))]
        row_total = sum(int(M[i, j]) for j in range(len(cols))
                         if (i, j) not in excluded)
        lines.append(f"| **{families[i] or 'other'}** | "
                     f"**{r}** ({cov['row_totals'][i]}) | "
                     + " | ".join(cells) + f" | {row_total} |")
    # Column totals
    lines.append("| _total_ | "
                 + " | ".join(str(int(t)) for t in cov["col_totals"])
                 + f" | **{int(M.sum())}** |")
    return "\n".join(lines)
