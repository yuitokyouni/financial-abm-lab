"""テープ/サイドカー JSON 規約 (YH010_HANDOFF §5, YH010g_HANDOFF §4)。

プロビナンス規約: 論文に載る全ての数値は run_id / matrix_id から再生成可能であること。
原本ファイルは加工せず保存し sha256 で固定。手動編集された成果物は verified: false。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agora_engine.decision_matrix import DecisionMatrix

SPEC_VERSION = "0.1"

_MATRIX_REQUIRED_KEYS = {"matrix_id", "spec_version", "sources", "coverage", "encoding", "provenance"}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(cwd: str | Path | None = None) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_matrix_sidecar(
    matrix_id: str,
    sources: list[dict],
    dm: DecisionMatrix,
    policy_reconstruction: dict | None = None,
    created_by: str = "claude-code",
    verified: bool = False,
    extra: dict | None = None,
) -> dict:
    """YH010g_HANDOFF §4 の行列スナップショット・サイドカー。

    sources の各要素: {manager, url, retrieved_at, format, parser, file_sha256}
    """
    cov = dm.coverage()
    side = {
        "matrix_id": matrix_id,
        "spec_version": SPEC_VERSION,
        "sources": sources,
        "coverage": {
            "managers": cov["rows"],
            "meetings": None,   # ビルダーが extra で上書き可
            "proposals": cov["cols"],
            "cells_observed": cov["cells_observed"],
            "cells_na": cov["cells_na"],
        },
        "encoding": dict(dm.encoding),
        "policy_reconstruction": policy_reconstruction
        or {"iss_policy_year": 0, "gl_policy_year": 0, "rules_ref": None},
        "provenance": {
            "code_sha": git_sha(),
            "created_by": created_by,
            "verified": bool(verified),
        },
    }
    if extra:
        for k, v in extra.items():
            if k == "coverage" and isinstance(v, dict):
                side["coverage"].update(v)
            else:
                side[k] = v
    return side


def write_sidecar(path: str | Path, sidecar: dict) -> None:
    missing = _MATRIX_REQUIRED_KEYS - sidecar.keys()
    if missing:
        raise ValueError(f"sidecar missing required keys: {sorted(missing)}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_sidecar(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        side = json.load(f)
    missing = _MATRIX_REQUIRED_KEYS - side.keys()
    if missing:
        raise ValueError(f"sidecar missing required keys: {sorted(missing)}")
    return side
