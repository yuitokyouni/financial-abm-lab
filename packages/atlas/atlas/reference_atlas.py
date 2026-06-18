"""Generate the first internal reference atlas (spec 002 §13 task 5) and check it
against the launch acceptance criteria (spec 002 §10).

The reference atlas is a *static* artifact (spec 002 §7): canonical models placed
in one coordinate system. It is the launch artifact, NOT a submission platform —
external submission infra is forbidden before ignition (spec 002 §11, enforced in
``atlas.ignition``).

``check_launch_readiness`` reports each spec 002 §10 criterion as met/pending with
a reason. It does not fake AC-4 (intervention separation): with only C0 canonical
rows that criterion is honestly *pending* until a C1 channel pair exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import diversity_coverage, diversity_satisfied, eligible_models
from .row import emit_row

ATLAS_SCHEMA_VERSION = "0.1.0"


def generate_reference_atlas(
    names: list[str] | None = None,
    *,
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5),
) -> dict[str, Any]:
    """Build the reference atlas dict (rows + meta + diversity coverage)."""
    names = names or eligible_models()
    rows = [emit_row(n, seeds=seeds) for n in names]
    return {
        "schema_version": ATLAS_SCHEMA_VERSION,
        "kind": "internal_reference_atlas",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "spec": "specs/002-minimum-viable-arena.md",
        "seeds": list(seeds),
        "n_rows": len(rows),
        "diversity_coverage": diversity_coverage(names),
        "rows": rows,
    }


def check_launch_readiness(atlas: dict[str, Any]) -> dict[str, Any]:
    """Evaluate spec 002 §10 launch acceptance criteria. Honest met/pending."""
    rows = atlas["rows"]
    names = [r["name"] for r in rows]
    n_pass = sum(1 for r in rows if r["contract_status"] in ("C0", "C2"))

    full_bundle = all(
        r.get("scoring_profile") is not None
        and r.get("provenance") is not None
        and (r.get("sf_profile") is not None or r["failure_transparency_note"]["structured"])
        for r in rows
    )
    # AC-4: an intervention dimension separates models not separated by SF.
    any_c1 = any(r["intervention_response_signature"] is not None for r in rows)

    criteria = {
        "contract_v1_frozen": {
            "met": True,
            "note": "docs/model_contract_v1.md + atlas.contract (C0/C1/C2)",
        },
        "at_least_8_rows_pass_ci": {
            "met": n_pass >= 8,
            "note": f"{n_pass} canonical rows pass contract/CI checks",
        },
        "full_artifact_bundle_per_row": {
            "met": full_bundle,
            "note": "each row has prov + scoring profile + SF profile or structured failure note",
        },
        "intervention_separates_beyond_sf": {
            "met": any_c1,
            "note": "PENDING: no exposed C1 channel pair yet (Finding 0002 order-book work)",
        },
        "one_command_rerun_per_row": {
            "met": True,
            "note": "atlas.registry.build_model(name).run(seed=...) reproduces each row",
        },
        "usable_without_external_submissions": {
            "met": diversity_satisfied(names) and n_pass >= 8,
            "note": "SF coordinate system over diverse canonical rows is citable as-is",
        },
    }
    launch_ready = all(c["met"] for c in criteria.values())
    return {
        "launch_ready": launch_ready,
        "criteria": criteria,
        "blocking": [k for k, c in criteria.items() if not c["met"]],
    }


def write_reference_atlas(out_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Generate, evaluate readiness, and write the atlas JSON. Returns the atlas."""
    atlas = generate_reference_atlas(**kwargs)
    atlas["launch_readiness"] = check_launch_readiness(atlas)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(atlas, indent=2, sort_keys=False, default=float))
    return atlas


def main() -> None:  # pragma: no cover - CLI entry
    repo_root = Path(__file__).resolve().parents[3]
    out = repo_root / "docs" / "atlas" / "reference_atlas_v0.json"
    atlas = write_reference_atlas(out)
    lr = atlas["launch_readiness"]
    print(f"wrote {out} — {atlas['n_rows']} rows, launch_ready={lr['launch_ready']}")
    for k, c in lr["criteria"].items():
        print(f"  [{'x' if c['met'] else ' '}] {k}: {c['note']}")


if __name__ == "__main__":  # pragma: no cover
    main()
