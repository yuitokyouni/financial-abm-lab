"""provenance — L2 minimum の run メタデータ(prov.json、spec §13.1 / CLAUDE.md)。

各 run に対し git commit / resolved config の sha256 / seed(numpy・python・torch)/
env snapshot / 出力 sha256 / uuid7 を sidecar JSON に記録する。`reach_claim` は v0 では
`reported` 固定(validator が他を拒否)。

このモジュールは L2 の素材を *記録* するだけで、捕捉の sound 性は主張しない
(それは reach/validator の責務)。
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from uuid6 import uuid7

from provabm.reach import ReachClaim


def new_uuid7() -> str:
    """時刻順 sort 可能な UUID v7(出力命名・run 同定に使う)。"""
    return str(uuid7())


def utc_now_iso() -> str:
    """UTC ISO 8601 タイムスタンプ。"""
    return datetime.now(UTC).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_hash(config_yaml: str) -> str:
    """resolved config(YAML 文字列)の sha256。"""
    return sha256_hex(config_yaml.encode("utf-8"))


def output_sha256(path: Path | str) -> str:
    """出力ファイルの sha256(bit 再現の照合用)。"""
    return sha256_hex(Path(path).read_bytes())


def git_commit(repo: Path | str | None = None) -> str:
    """実装コードの git commit hash。repo 外/git 不在では 'unknown'。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo) if repo is not None else None,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"
    return result.stdout.strip()


def pip_freeze_sha256() -> str:
    """インストール済み dist の `name==version` をソートして sha256(env 同定)。"""
    seen: set[str] = set()
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name is None:
            continue
        seen.add(f"{name.lower()}=={dist.version}")
    joined = "\n".join(sorted(seen))
    return sha256_hex(joined.encode("utf-8"))


def env_snapshot() -> dict[str, str]:
    """Python version / platform / pip freeze digest。"""
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pip_freeze_sha256": pip_freeze_sha256(),
    }


def seed_dict(numpy: int, python: int, torch: int | None = None) -> dict[str, int | None]:
    """seed 三点(numpy / python / torch)を記録形式に。"""
    return {"numpy": numpy, "python": python, "torch": torch}


def output_basename(config_hash_hex: str, seed: int, uuid: str) -> str:
    """CLAUDE.md 命名規約: `{config_hash[:12]}_{seed}_{uuid7}`。"""
    return f"{config_hash_hex[:12]}_{seed}_{uuid}"


def prov_path_for(output_path: Path | str) -> Path:
    """出力に対する sidecar provenance のパス: `{output_basename}.prov.json`。"""
    p = Path(output_path)
    return p.with_name(f"{p.name}.prov.json")


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """1 run の provenance メタデータ(spec §13.1)。"""

    uuid: str
    git_commit: str
    config_hash: str
    config_yaml: str
    seed: dict[str, int | None]
    env: dict[str, str]
    started_at_utc: str
    completed_at_utc: str
    output_sha256: str
    ctx_log_path: str
    reach_claim: str = ReachClaim.REPORTED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path | str) -> Path:
        """prov.json を書き出す。"""
        out = Path(path)
        out.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return out


@dataclass
class ProvenanceRecorder:
    """run 開始時に不変メタを確定し、終了時に出力 digest 等を埋めて `RunProvenance` を生む。

    使い方:
        rec = ProvenanceRecorder(config_yaml=cfg, seed=seed_dict(...), repo=repo_root)
        ...  # run
        prov = rec.complete(output_path=out, ctx_log_path=log)
        prov.write(prov_path_for(out))
    """

    config_yaml: str
    seed: dict[str, int | None]
    repo: Path | str | None = None
    uuid: str = field(default_factory=new_uuid7)

    def __post_init__(self) -> None:
        self._git_commit = git_commit(self.repo)
        self._config_hash = config_hash(self.config_yaml)
        self._env = env_snapshot()
        self._started_at = utc_now_iso()

    @property
    def config_hash_hex(self) -> str:
        return self._config_hash

    def complete(
        self,
        *,
        output_path: Path | str,
        ctx_log_path: Path | str,
        reach_claim: ReachClaim = ReachClaim.REPORTED,
    ) -> RunProvenance:
        return RunProvenance(
            uuid=self.uuid,
            git_commit=self._git_commit,
            config_hash=self._config_hash,
            config_yaml=self.config_yaml,
            seed=self.seed,
            env=self._env,
            started_at_utc=self._started_at,
            completed_at_utc=utc_now_iso(),
            output_sha256=output_sha256(output_path),
            ctx_log_path=str(ctx_log_path),
            reach_claim=reach_claim.value,
        )


def write_ctx_log_parquet(records: Iterable[dict[str, Any]], path: Path | str) -> Path:
    """ctx イベント records を parquet に書く(CaptureSink.to_records() の出力を受ける)。"""
    import pandas as pd

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # meta は dict 列なので JSON 文字列化して parquet 互換にする。
    rows = [{**r, "meta": json.dumps(r.get("meta", {}), ensure_ascii=False)} for r in records]
    frame = pd.DataFrame(rows, columns=["agent_id", "step", "kind", "key", "meta"])
    frame.to_parquet(out, index=False)
    return out
