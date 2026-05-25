"""Phase-diagram heatmap — visualize the adapter × NER × fact tensor.

Produces a matplotlib figure with one subplot per NER, showing adapters
on the Y-axis and facts on the X-axis.  Cells are color-coded:
  green  = MATCH (sign correct)
  red    = MISMATCH (sign wrong)
  gray   = INCONCLUSIVE
  hatched = INELIGIBLE (failed static eligibility gate)

The cell text shows the MDL-weighted confidence when available.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

from prism.pipeline import TensorOutput
from prism.scoring.eligibility import EligibilityVerdict
from prism.types import MatchVerdict


VERDICT_COLORS = {
    MatchVerdict.MATCH: "#2ecc71",
    MatchVerdict.MISMATCH: "#e74c3c",
    MatchVerdict.INCONCLUSIVE: "#95a5a6",
}


def render_heatmap(
    tensor: TensorOutput,
    output_path: str | Path | None = None,
    figsize: tuple[float, float] | None = None,
) -> matplotlib.figure.Figure:
    """Render the phase-diagram tensor as a heatmap."""
    n_ners = len(tensor.ner_ids)
    n_adapters = len(tensor.adapter_ids)
    n_facts = len(tensor.fact_ids)

    if figsize is None:
        figsize = (max(6, n_facts * 2.5 * n_ners), max(3, n_adapters * 1.5))

    fig, axes = plt.subplots(
        1, n_ners, figsize=figsize, squeeze=False,
    )

    for ner_idx, ner_id in enumerate(tensor.ner_ids):
        ax = axes[0, ner_idx]
        ax.set_title(ner_id, fontsize=10, fontweight="bold", pad=10)

        ner_cells = [c for c in tensor.cells if c.ner_id == ner_id]

        for ai, adapter_id in enumerate(tensor.adapter_ids):
            cell = next((c for c in ner_cells if c.adapter_id == adapter_id), None)
            if cell is None:
                continue

            is_ineligible = (
                cell.eligibility is not None
                and cell.eligibility.verdict == EligibilityVerdict.INELIGIBLE
            )

            for fi, fact_id in enumerate(tensor.fact_ids):
                match = next(
                    (m for m in cell.matches if m.fact_id == fact_id), None
                )
                if match is None:
                    continue

                color = VERDICT_COLORS.get(match.sign_match, "#95a5a6")

                rect = FancyBboxPatch(
                    (fi, ai), 1, 1,
                    boxstyle="round,pad=0.05",
                    facecolor=color,
                    edgecolor="white",
                    linewidth=2,
                    alpha=0.6 if is_ineligible else 0.85,
                )
                ax.add_patch(rect)

                if is_ineligible:
                    for offset in np.linspace(0.1, 0.9, 5):
                        ax.plot(
                            [fi + offset - 0.05, fi + offset + 0.05],
                            [ai + 0.2, ai + 0.8],
                            color="black", alpha=0.3, linewidth=0.8,
                        )

                wm = next(
                    (w for w in cell.weighted_matches if w.fact_id == fact_id),
                    None,
                )
                if wm:
                    label = f"{wm.confidence_weighted:.2f}"
                    sub_label = f"(w={wm.mdl_weight:.2f})"
                else:
                    label = f"{match.confidence:.2f}"
                    sub_label = ""

                ax.text(
                    fi + 0.5, ai + 0.45, label,
                    ha="center", va="center",
                    fontsize=11, fontweight="bold", color="white",
                )
                if sub_label:
                    ax.text(
                        fi + 0.5, ai + 0.72, sub_label,
                        ha="center", va="center",
                        fontsize=7, color="white", alpha=0.8,
                    )

        ax.set_xlim(0, n_facts)
        ax.set_ylim(0, n_adapters)
        ax.set_xticks([i + 0.5 for i in range(n_facts)])
        ax.set_xticklabels(
            [_short_fact(f) for f in tensor.fact_ids],
            fontsize=8, rotation=30, ha="right",
        )
        ax.set_yticks([i + 0.5 for i in range(n_adapters)])
        ax.set_yticklabels(tensor.adapter_ids, fontsize=9)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        "PRISM Phase-Diagram Tensor",
        fontsize=13, fontweight="bold", y=1.02,
    )

    _add_legend(fig)

    fig.tight_layout()

    if output_path is not None:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")

    return fig


def _short_fact(fact_id: str) -> str:
    abbreviations = {
        "volatility_clustering": "vol_clust",
        "leverage_effect": "leverage",
        "gain_loss_asymmetry": "gain_loss",
    }
    return abbreviations.get(fact_id, fact_id[:12])


def _add_legend(fig: matplotlib.figure.Figure) -> None:
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.MATCH], label="MATCH"),
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.MISMATCH], label="MISMATCH"),
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.INCONCLUSIVE], label="INCONCLUSIVE"),
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=3,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, -0.05),
    )
