"""CLI entry point for `prism run`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prism.pipeline import compare_causal_methods, run_cell, run_tensor
from prism.viz import export_latex_table, render_heatmap, render_latex_heatmap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prism",
        description="PRISM — Provenance-backed Reproducible Intervention-response Scoring of Mechanisms",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run one cell of the phase-diagram tensor")
    run_parser.add_argument(
        "--adapter",
        required=True,
        help="Model adapter name (e.g., sg)",
    )
    run_parser.add_argument(
        "--ner",
        required=True,
        help="NER id or path to NER YAML file",
    )
    run_parser.add_argument(
        "--facts",
        required=True,
        help="Comma-separated fact IDs (e.g., leverage,volclust,gainloss)",
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default: 42)",
    )
    run_parser.add_argument(
        "--n-paths",
        type=int,
        default=10,
        help="Number of simulation paths to average (default: 10)",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: stdout summary)",
    )
    run_parser.add_argument(
        "--per-path-facts",
        action="store_true",
        default=False,
        help="Compute facts per simulation path (preserves kurtosis/skewness)",
    )
    run_parser.add_argument(
        "--real-data",
        action="store_true",
        default=False,
        help="Use real market data for calibration (requires yfinance + internet)",
    )

    tensor_parser = sub.add_parser(
        "tensor", help="Run the full phase-diagram tensor (adapters × NERs × facts)"
    )
    tensor_parser.add_argument(
        "--adapters",
        required=True,
        help="Comma-separated adapter names (e.g., sg,ci)",
    )
    tensor_parser.add_argument(
        "--ners",
        required=True,
        help="Comma-separated NER ids or paths",
    )
    tensor_parser.add_argument(
        "--facts",
        required=True,
        help="Comma-separated fact IDs (e.g., leverage,volclust,gainloss)",
    )
    tensor_parser.add_argument(
        "--seed", type=int, default=42, help="RNG seed (default: 42)"
    )
    tensor_parser.add_argument(
        "--n-paths", type=int, default=10, help="Simulation paths (default: 10)"
    )
    tensor_parser.add_argument(
        "--output", type=str, default=None, help="Output JSON file path"
    )
    tensor_parser.add_argument(
        "--per-path-facts", action="store_true", default=False,
        help="Compute facts per simulation path (preserves kurtosis/skewness)",
    )
    tensor_parser.add_argument(
        "--real-data", action="store_true", default=False,
        help="Use real market data for calibration (requires yfinance + internet)",
    )

    compare_parser = sub.add_parser(
        "compare", help="Compare causal method weightings for one cell"
    )
    compare_parser.add_argument(
        "--adapter", required=True, help="Model adapter name"
    )
    compare_parser.add_argument(
        "--ner", required=True, help="NER id or path"
    )
    compare_parser.add_argument(
        "--facts", required=True, help="Comma-separated fact IDs"
    )
    compare_parser.add_argument(
        "--methods", type=str, default=None,
        help="Comma-separated causal methods (default: all known methods)",
    )
    compare_parser.add_argument("--seed", type=int, default=42)
    compare_parser.add_argument("--n-paths", type=int, default=10)
    compare_parser.add_argument("--output", type=str, default=None)
    compare_parser.add_argument(
        "--per-path-facts", action="store_true", default=False,
        help="Compute facts per simulation path (preserves kurtosis/skewness)",
    )

    heatmap_parser = sub.add_parser(
        "heatmap", help="Run tensor and render phase-diagram heatmap"
    )
    heatmap_parser.add_argument(
        "--adapters", required=True, help="Comma-separated adapter names"
    )
    heatmap_parser.add_argument(
        "--ners", required=True, help="Comma-separated NER ids or paths"
    )
    heatmap_parser.add_argument(
        "--facts", required=True, help="Comma-separated fact IDs"
    )
    heatmap_parser.add_argument("--seed", type=int, default=42)
    heatmap_parser.add_argument("--n-paths", type=int, default=10)
    heatmap_parser.add_argument(
        "--per-path-facts", action="store_true", default=False,
        help="Compute facts per simulation path (preserves kurtosis/skewness)",
    )
    heatmap_parser.add_argument(
        "--output", type=str, default="heatmap.png",
        help="Output image file path (default: heatmap.png)",
    )

    latex_hm_parser = sub.add_parser(
        "latex-heatmap", help="Render publication-quality heatmap (PDF/PGF) for LaTeX"
    )
    latex_hm_parser.add_argument(
        "--adapters", required=True, help="Comma-separated adapter names"
    )
    latex_hm_parser.add_argument(
        "--ners", required=True, help="Comma-separated NER ids or paths"
    )
    latex_hm_parser.add_argument(
        "--facts", required=True, help="Comma-separated fact IDs"
    )
    latex_hm_parser.add_argument("--seed", type=int, default=42)
    latex_hm_parser.add_argument("--n-paths", type=int, default=10)
    latex_hm_parser.add_argument(
        "--per-path-facts", action="store_true", default=False,
    )
    latex_hm_parser.add_argument(
        "--output", type=str, default="heatmap.pdf",
        help="Output file path (default: heatmap.pdf)",
    )

    latex_tbl_parser = sub.add_parser(
        "latex-table", help="Export tensor results as LaTeX tabular"
    )
    latex_tbl_parser.add_argument(
        "--adapters", required=True, help="Comma-separated adapter names"
    )
    latex_tbl_parser.add_argument(
        "--ners", required=True, help="Comma-separated NER ids or paths"
    )
    latex_tbl_parser.add_argument(
        "--facts", required=True, help="Comma-separated fact IDs"
    )
    latex_tbl_parser.add_argument("--seed", type=int, default=42)
    latex_tbl_parser.add_argument("--n-paths", type=int, default=10)
    latex_tbl_parser.add_argument(
        "--per-path-facts", action="store_true", default=False,
    )
    latex_tbl_parser.add_argument(
        "--output", type=str, default="table.tex",
        help="Output .tex file path (default: table.tex)",
    )

    return parser


FACT_ALIASES = {
    "leverage": "leverage_effect",
    "volclust": "volatility_clustering",
    "gainloss": "gain_loss_asymmetry",
    "fattails": "fat_tails",
    "absacf": "abs_autocorrelation",
    "sqacf": "squared_return_acf",
}

NER_SEARCH_DIRS = [
    Path("data/ner"),
    Path("data"),
]


def resolve_ner_path(ner_arg: str) -> Path:
    p = Path(ner_arg)
    if p.exists():
        return p
    for d in NER_SEARCH_DIRS:
        candidate = d / f"{ner_arg}.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"NER not found: {ner_arg}. Searched: {ner_arg}, "
        + ", ".join(str(d / f'{ner_arg}.yaml') for d in NER_SEARCH_DIRS)
    )


def resolve_fact_ids(facts_str: str) -> list[str]:
    raw = [f.strip() for f in facts_str.split(",")]
    return [FACT_ALIASES.get(f, f) for f in raw]


def _write_json(output_arg: str | None, data: dict[str, object]) -> None:
    if output_arg:
        out_path = Path(output_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\nFull result written to: {out_path}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        ner_path = resolve_ner_path(args.ner)
        fact_ids = resolve_fact_ids(args.facts)

        cell_result = run_cell(
            adapter_name=args.adapter,
            ner_path=ner_path,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
            use_real_data=args.real_data,
        )

        print(cell_result.summary())
        _write_json(args.output, cell_result.to_dict())

    elif args.command == "tensor":
        adapter_names = [a.strip() for a in args.adapters.split(",")]
        ner_paths: list[str | Path] = [resolve_ner_path(n.strip()) for n in args.ners.split(",")]
        fact_ids = resolve_fact_ids(args.facts)

        tensor_result = run_tensor(
            adapter_names=adapter_names,
            ner_paths=ner_paths,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
            use_real_data=args.real_data,
        )

        print(tensor_result.summary())
        _write_json(args.output, tensor_result.to_dict())

    elif args.command == "compare":
        ner_path = resolve_ner_path(args.ner)
        fact_ids = resolve_fact_ids(args.facts)
        methods = [m.strip() for m in args.methods.split(",")] if args.methods else None

        cmp_result = compare_causal_methods(
            adapter_name=args.adapter,
            ner_path=ner_path,
            fact_ids=fact_ids,
            methods=methods,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
        )

        print(cmp_result.summary())
        _write_json(args.output, cmp_result.to_dict())

    elif args.command == "heatmap":
        adapter_names = [a.strip() for a in args.adapters.split(",")]
        hm_ner_paths: list[str | Path] = [resolve_ner_path(n.strip()) for n in args.ners.split(",")]
        fact_ids = resolve_fact_ids(args.facts)

        hm_result = run_tensor(
            adapter_names=adapter_names,
            ner_paths=hm_ner_paths,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
            use_real_data=getattr(args, "real_data", False),
        )

        print(hm_result.summary())

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import matplotlib
        matplotlib.use("Agg")
        render_heatmap(hm_result, output_path=out_path)
        print(f"\nHeatmap written to: {out_path}")

    elif args.command == "latex-heatmap":
        adapter_names = [a.strip() for a in args.adapters.split(",")]
        lh_ner_paths: list[str | Path] = [resolve_ner_path(n.strip()) for n in args.ners.split(",")]
        fact_ids = resolve_fact_ids(args.facts)

        lh_result = run_tensor(
            adapter_names=adapter_names,
            ner_paths=lh_ner_paths,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
        )

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import matplotlib
        matplotlib.use("Agg")
        render_latex_heatmap(lh_result, output_path=out_path)
        print(f"LaTeX heatmap written to: {out_path}")

    elif args.command == "latex-table":
        adapter_names = [a.strip() for a in args.adapters.split(",")]
        lt_ner_paths: list[str | Path] = [resolve_ner_path(n.strip()) for n in args.ners.split(",")]
        fact_ids = resolve_fact_ids(args.facts)

        lt_result = run_tensor(
            adapter_names=adapter_names,
            ner_paths=lt_ner_paths,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
            per_path_facts=args.per_path_facts,
        )

        out_path = Path(args.output)
        table_tex = export_latex_table(lt_result, output_path=out_path)
        print(table_tex)
        print(f"\nLaTeX table written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
