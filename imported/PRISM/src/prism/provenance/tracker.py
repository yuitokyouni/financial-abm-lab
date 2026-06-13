"""Provenance Layer v0.1 — W3C PROV-O minimal implementation.

Records data hashes, code version, RNG seeds, and fact estimator versions
to ensure any result cell is fully reproducible.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import prism


@dataclass(frozen=True)
class ProvenanceRecord:
    """Immutable record of how a result was produced."""

    run_id: str
    timestamp: str
    code_version: str
    prism_version: str

    data_hashes: dict[str, str] = field(default_factory=dict)
    rng_seeds: dict[str, int] = field(default_factory=dict)
    estimator_versions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prov:type": "prism:EvaluationRun",
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "code_version": self.code_version,
            "prism_version": self.prism_version,
            "data_hashes": dict(self.data_hashes),
            "rng_seeds": dict(self.rng_seeds),
            "estimator_versions": dict(self.estimator_versions),
            "parameters": dict(self.parameters),
        }


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def make_run_id(prefix: str = "run") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    commit = get_git_commit()[:8]
    return f"{prefix}_{ts}_{commit}"


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


class ProvenanceTracker:
    """Accumulates provenance data during a run, then seals into a record."""

    def __init__(self, run_id: str | None = None):
        self._run_id = run_id or make_run_id()
        self._data_hashes: dict[str, str] = {}
        self._rng_seeds: dict[str, int] = {}
        self._estimator_versions: dict[str, str] = {}
        self._parameters: dict[str, Any] = {}

    def record_data_hash(self, label: str, data_hash: str) -> None:
        self._data_hashes[label] = data_hash

    def record_seed(self, label: str, seed: int) -> None:
        self._rng_seeds[label] = seed

    def record_estimator_version(self, fact_id: str, version: str) -> None:
        self._estimator_versions[fact_id] = version

    def record_parameter(self, key: str, value: Any) -> None:
        self._parameters[key] = value

    def seal(self) -> ProvenanceRecord:
        return ProvenanceRecord(
            run_id=self._run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            code_version=get_git_commit(),
            prism_version=prism.__version__,
            data_hashes=dict(self._data_hashes),
            rng_seeds=dict(self._rng_seeds),
            estimator_versions=dict(self._estimator_versions),
            parameters=dict(self._parameters),
        )
