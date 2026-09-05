"""Archive exact write_log_file outputs, with bounded per-seed Git file sizes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from .run_ensemble import save_json, verified_pair


def archive(directory: Path, output: Path):
    plan = json.loads((directory / "plan.json").read_text())
    progress = json.loads((directory / "progress.json").read_text())
    if (
        progress["status"] != "COMPLETE: all prefixes byte equal"
        or sorted(progress["completed"]) != plan["seeds"]
    ):
        raise ValueError(
            "Incomplete or stopped ensemble; cannot archive as a completed study"
        )
    # Check all pairs before exporting even the first archive.
    for seed in plan["seeds"]:
        config = deepcopy(plan["config"])
        config["seed"] = seed
        verified_pair(directory / f"seed{seed:04d}", config, plan["lobcore_commit"])
    output.mkdir(parents=True, exist_ok=True)
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    manifest = {
        "format": "Per-seed deterministic tar.gz of original F/B binary files; no log regeneration.",
        "lobcore_commit": plan["lobcore_commit"],
        "seeds": [],
        "uncompressed_bytes": 0,
        "compressed_bytes": 0,
    }
    for seed in plan["seeds"]:
        name = f"seed{seed:04d}"
        members = {
            f"{name}/{filename}": (directory / name / filename).read_bytes()
            for filename in (
                "baseline.bin",
                "factual.bin",
                "config.yaml",
                "summary.json",
            )
        }
        path = logs / f"{name}.tar.gz"
        with path.open("wb") as stream:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=stream, mtime=0
            ) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as tar:
                    for filename, data in sorted(members.items()):
                        info = tarfile.TarInfo(filename)
                        info.size = len(data)
                        info.mode = 0o644
                        tar.addfile(info, io.BytesIO(data))
        # Compare every decompressed byte against the originals before recording.
        with tarfile.open(path, "r:gz") as tar:
            if sorted(tar.getnames()) != sorted(members):
                raise ValueError(f"Archive member mismatch: {path}")
            for filename, data in members.items():
                if tar.extractfile(filename).read() != data:
                    raise ValueError(f"Archive roundtrip mismatch: {path}:{filename}")
        manifest["seeds"].append(
            {
                "seed": seed,
                "path": str(path.relative_to(output)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "members": {
                    name: {
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                    for name, data in sorted(members.items())
                },
            }
        )
        manifest["uncompressed_bytes"] += sum(map(len, members.values()))
        manifest["compressed_bytes"] += path.stat().st_size
    for filename in ("plan.json", "progress.json"):
        (output / filename).write_bytes((directory / filename).read_bytes())
    save_json(output / "log_manifest.json", manifest)
    print(
        f"Archived {len(plan['seeds'])} verified pairs: {manifest['compressed_bytes']:,} bytes compressed"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    archive(args.run_dir, args.out_dir)


if __name__ == "__main__":
    main()
