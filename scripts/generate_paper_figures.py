#!/usr/bin/env python3
"""Batch generation of all figures and tables for the PRISM paper.

Produces:
  output/fig_heatmap_full.pdf      — 5x4 phase-diagram heatmap (all adapters x NERs)
  output/fig_heatmap_full.png      — PNG version for quick preview
  output/tab_full_tensor.tex       — LaTeX table (booktabs) of full tensor
  output/fig_heatmap_ticksize.pdf  — tick-size-only subset heatmap
  output/tab_ticksize.tex          — tick-size-only LaTeX table
  output/tensor_full.json          — raw JSON results for reproducibility
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prism.pipeline import run_tensor
from prism.viz import export_latex_table, render_heatmap, render_latex_heatmap

ALL_ADAPTERS = ["sg", "ci", "zi", "lm", "fw"]
ALL_NERS = [
    "data/ner/tspp_2016_us_equity.yaml",
    "data/ner/french_ftt_2012_eu.yaml",
    "data/ner/mifid2_2018_eu_tick.yaml",
    "data/ner/jpx_2014_jp_tick.yaml",
]
TICK_SIZE_NERS = [
    "data/ner/tspp_2016_us_equity.yaml",
    "data/ner/mifid2_2018_eu_tick.yaml",
    "data/ner/jpx_2014_jp_tick.yaml",
]
ALL_FACTS = [
    "volatility_clustering",
    "leverage_effect",
    "gain_loss_asymmetry",
    "fat_tails",
    "abs_autocorrelation",
    "squared_return_acf",
]

SEED = 42
N_PATHS = 20
OUTPUT_DIR = Path("output")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  PRISM Paper Figure Generator")
    print("=" * 60)

    # --- Full tensor ---
    print("\n[1/6] Running full tensor (5 adapters x 4 NERs x 6 facts = 120 cells)...")
    tensor_full = run_tensor(
        adapter_names=ALL_ADAPTERS,
        ner_paths=ALL_NERS,
        fact_ids=ALL_FACTS,
        seed=SEED,
        n_paths=N_PATHS,
        per_path_facts=True,
    )
    print(f"       {len(tensor_full.cells)} cells computed.")

    # Save raw JSON
    json_path = OUTPUT_DIR / "tensor_full.json"
    with open(json_path, "w") as f:
        json.dump(tensor_full.to_dict(), f, indent=2, default=str)
    print(f"       Raw results: {json_path}")

    # --- Full heatmap (PDF + PNG) ---
    print("\n[2/6] Rendering full heatmap (PDF)...")
    pdf_path = OUTPUT_DIR / "fig_heatmap_full.pdf"
    render_latex_heatmap(tensor_full, output_path=pdf_path)
    print(f"       {pdf_path}")

    print("\n[3/6] Rendering full heatmap (PNG)...")
    png_path = OUTPUT_DIR / "fig_heatmap_full.png"
    render_heatmap(tensor_full, output_path=png_path)
    print(f"       {png_path}")

    # --- Full LaTeX table ---
    print("\n[4/6] Exporting full LaTeX table...")
    tex_path = OUTPUT_DIR / "tab_full_tensor.tex"
    export_latex_table(tensor_full, output_path=tex_path)
    print(f"       {tex_path}")

    # --- Tick-size-only subset ---
    print("\n[5/6] Running tick-size subset tensor (5 x 3 x 6 = 90 cells)...")
    tensor_tick = run_tensor(
        adapter_names=ALL_ADAPTERS,
        ner_paths=TICK_SIZE_NERS,
        fact_ids=ALL_FACTS,
        seed=SEED,
        n_paths=N_PATHS,
        per_path_facts=True,
    )

    tick_pdf = OUTPUT_DIR / "fig_heatmap_ticksize.pdf"
    render_latex_heatmap(tensor_tick, output_path=tick_pdf)
    print(f"       {tick_pdf}")

    print("\n[6/6] Exporting tick-size LaTeX table...")
    tick_tex = OUTPUT_DIR / "tab_ticksize.tex"
    export_latex_table(tensor_tick, output_path=tick_tex)
    print(f"       {tick_tex}")

    print("\n" + "=" * 60)
    print("  All figures and tables generated in output/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
