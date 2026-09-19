"""Validate experiment ownership without importing models or installing dependencies.

Run from any working directory: python /path/to/repo/tools/check_layout.py
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys
import tomllib

COMPATIBILITY_DIRS = {"classical", "speculation_game", "_template", "__pycache__"}
KINDS = {"simulation", "empirical", "design", "archive", "workflow"}
ARCHIVES = {
    "speculation-game-info", "PRISM", "PROV-ABM-atlas", "market-dynamics",
    "ABM-Microstructure", "agent-based-modeling",
}


def local_path(base: Path, value: object) -> Path | None:
    """Reject absolute or escaping paths in the tracked manifest."""
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = (base / path).resolve()
    return resolved if resolved.is_relative_to(base.resolve()) else None


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    packages = {p.name for p in (root / "packages").iterdir() if p.is_dir()}
    ids: set[str] = set()
    for experiment in sorted((root / "experiments").iterdir()):
        if not experiment.is_dir() or experiment.name in COMPATIBILITY_DIRS or experiment.name.startswith("."):
            continue
        label = str(experiment.relative_to(root))
        if not (experiment / "README.md").is_file():
            errors.append(f"{label}: missing README.md")
        manifest = experiment / "experiment.toml"
        if not manifest.is_file():
            errors.append(f"{label}: missing experiment.toml")
            continue
        try:
            data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{label}: invalid manifest: {exc}")
            continue
        eid = data.get("id")
        if not isinstance(eid, str) or eid != experiment.name or eid in ids:
            errors.append(f"{label}: id must match directory and be unique")
        if isinstance(eid, str):
            ids.add(eid)
        if not isinstance(data.get("title"), str) or not data["title"].strip():
            errors.append(f"{label}: title required")
        if not isinstance(data.get("kind"), str) or data["kind"] not in KINDS:
            errors.append(f"{label}: unknown kind")
        for key in ("shared_packages", "paths", "commands", "archives"):
            values = data.get(key)
            if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                errors.append(f"{label}: {key} must be a list of strings")
                continue
            if key == "shared_packages":
                for package in values:
                    if package not in packages:
                        errors.append(f"{label}: unknown shared package {package}")
            elif key in {"paths", "archives"}:
                base = experiment if key == "paths" else root
                for value in values:
                    target = local_path(base, value)
                    if target is None or not target.exists():
                        errors.append(f"{label}: missing or invalid {key} entry {value}")
                    elif key == "archives" and not value.startswith("imported/"):
                        errors.append(f"{label}: archive must point into imported/: {value}")
    # An importable Python package can be experiment-specific; do not move it back.
    if (root / "packages/yh010g").exists():
        errors.append("yh010g must remain experiment-owned, not in packages/")
    alias = root / "unwind-tape"
    if not alias.is_symlink() or alias.resolve() != (root / "experiments/YH009").resolve():
        errors.append("unwind-tape must be the compatibility symlink to experiments/YH009")
    for archive in ARCHIVES:
        if not (root / "imported" / archive).is_dir():
            errors.append(f"missing preserved archive: {archive}")
    # This is an AST import check, not a claim of dynamic dependency analysis.
    for area in (root / "packages", root / "src"):
        for source in area.rglob("*.py"):
            if "tests" in source.relative_to(area).parts:
                continue
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except (OSError, SyntaxError) as exc:
                errors.append(f"{source.relative_to(root)}: {exc}")
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                if any(name == "experiments" or name.startswith("experiments.") for name in names):
                    errors.append(f"{source.relative_to(root)}:{node.lineno}: shared code imports an experiment")
    for path in (root / "docs").rglob("*"):
        if path.is_file() and path.suffix.lower() in {".csv", ".json", ".npz", ".npy", ".parquet"}:
            errors.append(f"{path.relative_to(root)}: put data/results in the owning experiment")
    return errors


def main() -> int:
    errors = validate(Path(__file__).resolve().parents[1])
    if errors:
        print("Repository layout errors:\n" + "\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("Repository layout OK: manifests, ownership, archive locations and compatibility link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
