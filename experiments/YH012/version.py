"""lobcore の git コミットを ExperimentMeta.lobcore_version に載せる。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def default_lobcore_root() -> Path:
    env = os.environ.get("LOBCORE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # ユーザ環境の既定パス（指示どおり）
    home = Path("/home/yuito/dev/lobcore")
    if home.exists():
        return home.resolve()
    # Cloud / CI: 隣接または /workspace
    for candidate in (
        Path("/workspace"),
        Path(__file__).resolve().parents[4] / "lobcore",
        Path.cwd() / "lobcore",
    ):
        if (candidate / "python").is_dir() or (candidate / ".git").exists():
            return candidate.resolve()
    return home


def lobcore_git_hash(lobcore_root: Path | None = None) -> str:
    root = lobcore_root or default_lobcore_root()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"
