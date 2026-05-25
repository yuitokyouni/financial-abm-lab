"""LaTeX-compatible figure and table generation for publication.

Produces:
  1. render_latex_heatmap() — publication-quality heatmap with LaTeX text
  2. export_latex_table() — standalone LaTeX tabular for paper inclusion
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Patch

from prism.pipeline import TensorOutput
from prism.scoring.eligibility import EligibilityVerdict
from prism.types import MatchVerdict


VERDICT_COLORS = {
    MatchVerdict.MATCH: "#2ecc71",
    MatchVerdict.MISMATCH: "#e74c3c",
    MatchVerdict.INCONCLUSIVE: "#95a5a6",
}

FACT_LATEX_LABELS: dict[str, str] = {
    "volatility_clustering": r"Vol.\ Clust.\ ($\alpha+\beta$)",
    "leverage_effect": r"Leverage ($\rho_{r,\sigma^2}$)",
    "gain_loss_asymmetry": r"Skewness",
    "fat_tails": r"Kurtosis ($\kappa$)",
    "abs_autocorrelation": r"$\mathrm{ACF}(|r|)$",
    "squared_return_acf": r"$\mathrm{ACF}(r^2)$",
}

ADAPTER_LATEX_LABELS: dict[str, str] = {
    "sg": "SG",
    "ci": "CI",
    "zi": "ZI-C",
    "lm": "LM",
}

VERDICT_SYMBOLS: dict[MatchVerdict, str] = {
    MatchVerdict.MATCH: r"\checkmark",
    MatchVerdict.MISMATCH: r"\times",
    MatchVerdict.INCONCLUSIVE: "?",
}


def _try_latex_backend() -> bool:
    """Enable LaTeX rendering if available, otherwise use mathtext."""
    try:
        plt.rcParams.update({
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Computer Modern Roman"],
            "font.size": 10,
        })
        fig_test = plt.figure(figsize=(1, 1))
        fig_test.text(0.5, 0.5, r"$\alpha$")
        fig_test.savefig("/dev/null", format="png")
        plt.close(fig_test)
        return True
    except Exception:
        plt.rcParams.update({
            "text.usetex": False,
            "font.family": "serif",
            "font.size": 10,
        })
        return False


def render_latex_heatmap(
    tensor: TensorOutput,
    output_path: str | Path | None = None,
    figsize: tuple[float, float] | None = None,
    use_latex: bool = True,
) -> matplotlib.figure.Figure:
    """Render publication-quality heatmap with optional LaTeX text.

    Falls back to mathtext rendering if LaTeX is not installed.
    Outputs PDF or PGF for direct LaTeX inclusion.
    """
    if use_latex:
        _try_latex_backend()

    n_ners = len(tensor.ner_ids)
    n_adapters = len(tensor.adapter_ids)
    n_facts = len(tensor.fact_ids)

    if figsize is None:
        figsize = (max(4.5, n_facts * 1.8 * n_ners), max(2.5, n_adapters * 1.0 + 1.0))

    fig, axes = plt.subplots(1, n_ners, figsize=figsize, squeeze=False)

    for ner_idx, ner_id in enumerate(tensor.ner_ids):
        ax = axes[0, ner_idx]
        ax.set_title(
            _ner_label(ner_id),
            fontsize=9, fontweight="bold", pad=8,
        )

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
                alpha = 0.45 if is_ineligible else 0.8

                rect = FancyBboxPatch(
                    (fi + 0.05, ai + 0.05), 0.9, 0.9,
                    boxstyle="round,pad=0.03",
                    facecolor=color,
                    edgecolor="white",
                    linewidth=1.5,
                    alpha=alpha,
                )
                ax.add_patch(rect)

                if is_ineligible:
                    for offset in np.linspace(0.15, 0.85, 4):
                        ax.plot(
                            [fi + offset - 0.04, fi + offset + 0.04],
                            [ai + 0.15, ai + 0.85],
                            color="black", alpha=0.25, linewidth=0.6,
                        )

                wm = next(
                    (w for w in cell.weighted_matches if w.fact_id == fact_id),
                    None,
                )
                conf_val = wm.confidence_weighted if wm else match.confidence
                mdl_w = wm.mdl_weight if wm else None

                ax.text(
                    fi + 0.5, ai + 0.42, f"{conf_val:.2f}",
                    ha="center", va="center",
                    fontsize=9, fontweight="bold", color="white",
                )
                if mdl_w is not None:
                    ax.text(
                        fi + 0.5, ai + 0.72,
                        f"$w={mdl_w:.2f}$",
                        ha="center", va="center",
                        fontsize=6, color="white", alpha=0.85,
                    )

        ax.set_xlim(0, n_facts)
        ax.set_ylim(0, n_adapters)
        ax.set_xticks([i + 0.5 for i in range(n_facts)])
        ax.set_xticklabels(
            [FACT_LATEX_LABELS.get(f, f) for f in tensor.fact_ids],
            fontsize=7, rotation=35, ha="right",
        )
        ax.set_yticks([i + 0.5 for i in range(n_adapters)])
        ax.set_yticklabels(
            [ADAPTER_LATEX_LABELS.get(a, a) for a in tensor.adapter_ids],
            fontsize=8,
        )
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    legend_elements = [
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.MATCH], label="Match"),
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.MISMATCH], label="Mismatch"),
        Patch(facecolor=VERDICT_COLORS[MatchVerdict.INCONCLUSIVE], label="Inconclusive"),
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=3,
        fontsize=7,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )

    fig.tight_layout(rect=[0, 0.03, 1, 0.97])

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=300, bbox_inches="tight")

    return fig


def export_latex_table(
    tensor: TensorOutput,
    output_path: str | Path | None = None,
) -> str:
    r"""Export the tensor results as a LaTeX tabular.

    Returns a string containing a standalone \begin{table}...\end{table}
    environment ready for inclusion in a LaTeX document.
    """
    adapters = tensor.adapter_ids
    ner_ids = tensor.ner_ids
    facts = tensor.fact_ids
    n_facts = len(facts)

    lines: list[str] = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(
        r"\caption{PRISM Phase-Diagram Tensor: Sign consistency and "
        r"MDL-weighted confidence scores.}"
    )
    lines.append(r"\label{tab:prism-tensor}")

    col_spec = "ll" + "c" * n_facts
    lines.append(r"\begin{tabular}{" + col_spec + "}")
    lines.append(r"\toprule")

    header_facts = " & ".join(
        FACT_LATEX_LABELS.get(f, f.replace("_", r"\_")) for f in facts
    )
    lines.append(r"NER & Model & " + header_facts + r" \\")
    lines.append(r"\midrule")

    for ner_id in ner_ids:
        ner_cells = [c for c in tensor.cells if c.ner_id == ner_id]
        ner_label = _ner_label(ner_id).replace("_", r"\_")

        for ai, adapter_id in enumerate(adapters):
            cell = next((c for c in ner_cells if c.adapter_id == adapter_id), None)
            if cell is None:
                continue

            adapter_label = ADAPTER_LATEX_LABELS.get(adapter_id, adapter_id)

            is_ineligible = (
                cell.eligibility is not None
                and cell.eligibility.verdict == EligibilityVerdict.INELIGIBLE
            )

            ner_col = ner_label if ai == 0 else ""
            parts = [ner_col, adapter_label]

            for fact_id in facts:
                match = next(
                    (m for m in cell.matches if m.fact_id == fact_id), None
                )
                if match is None:
                    parts.append("---")
                    continue

                wm = next(
                    (w for w in cell.weighted_matches if w.fact_id == fact_id),
                    None,
                )
                conf = wm.confidence_weighted if wm else match.confidence
                symbol = VERDICT_SYMBOLS.get(match.sign_match, "?")

                cell_text = f"${symbol}$ {conf:.2f}"
                if is_ineligible:
                    cell_text = r"\textcolor{gray}{" + cell_text + "}"

                parts.append(cell_text)

            lines.append(" & ".join(parts) + r" \\")

        if ner_id != ner_ids[-1]:
            lines.append(r"\addlinespace")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(
        r"\par\vspace{2pt}\footnotesize "
        r"$\checkmark$ = sign match, $\times$ = sign mismatch, "
        r"? = inconclusive. Values show MDL-weighted confidence "
        r"($w_{\mathrm{MDL}} \cdot w_{\mathrm{causal}} \cdot c_{\mathrm{raw}}$). "
        r"Gray = ineligible (baseline outside empirical range)."
    )
    lines.append(r"\end{table}")

    result = "\n".join(lines)

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            f.write(result)

    return result


def _ner_label(ner_id: str) -> str:
    labels: dict[str, str] = {
        "tspp_2016_us_equity": "TSPP 2016",
        "french_ftt_2012_eu": "FTT 2012",
        "mifid2_2018_eu_tick": "MiFID II 2018",
    }
    return labels.get(ner_id, ner_id)
