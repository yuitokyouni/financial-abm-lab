"""CLI entry point for `prism run`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prism.pipeline import run_cell


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
    return parser


FACT_ALIASES = {
    "leverage": "leverage_effect",
    "volclust": "volatility_clustering",
    "gainloss": "gain_loss_asymmetry",
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        ner_path = resolve_ner_path(args.ner)
        fact_ids = resolve_fact_ids(args.facts)

        result = run_cell(
            adapter_name=args.adapter,
            ner_path=ner_path,
            fact_ids=fact_ids,
            seed=args.seed,
            n_paths=args.n_paths,
        )

        print(result.summary())

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2, default=str)
            print(f"\nFull result written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
