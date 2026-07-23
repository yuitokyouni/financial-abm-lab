"""行列構築 — UnifiedRecord 群 → DecisionMatrix + サイドカー JSON (YH010g_HANDOFF §4)。

同一運用機関内の同一議案キー重複は、賛否が一致すれば一意化、矛盾すれば
duplicate_conflicts に記録して当該セルを NA に落とす (黙って上書きしない)。
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

from agora_engine import DecisionMatrix, build_matrix_sidecar
from yh010g.schema import UnifiedRecord, proposal_col_id


@dataclass
class BuildResult:
    dm: DecisionMatrix
    sidecar: dict
    n_meetings: int
    duplicate_conflicts: list[tuple[str, str]]  # (manager, col_id)


def build_decision_matrix(
    records: list[UnifiedRecord],
    matrix_id: str,
    sources: list[dict],
    created_by: str = "claude-code",
) -> BuildResult:
    cell: dict[tuple[str, str], float] = {}
    conflicts: set[tuple[str, str]] = set()
    meetings: set[tuple[str, str]] = set()
    for r in records:
        col = proposal_col_id(r.sec_code, r.meeting_date, r.proposal_no, r.sub_no)
        key = (r.manager, col)
        meetings.add((r.sec_code, r.meeting_date))
        if key in cell and cell[key] != r.vote:
            conflicts.add(key)
        else:
            cell.setdefault(key, r.vote)
    for key in conflicts:
        cell[key] = np.nan
    if conflicts:
        warnings.warn(f"{len(conflicts)} conflicting duplicate cells set to NA "
                      f"(e.g. {sorted(conflicts)[:3]})", stacklevel=2)

    dm = DecisionMatrix.from_long([(m, c, v) for (m, c), v in cell.items()])
    sidecar = build_matrix_sidecar(
        matrix_id=matrix_id,
        sources=sources,
        dm=dm,
        created_by=created_by,
        extra={
            "coverage": {"meetings": len(meetings)},
            "duplicate_conflicts": [list(k) for k in sorted(conflicts)],
        },
    )
    return BuildResult(dm=dm, sidecar=sidecar, n_meetings=len(meetings),
                       duplicate_conflicts=sorted(conflicts))


def records_to_rows(records: list[UnifiedRecord]) -> list[dict]:
    """長形式の dict 行 (parquet/csv 保存用)。"""
    return [vars(r) | {"col_id": proposal_col_id(r.sec_code, r.meeting_date, r.proposal_no, r.sub_no)}
            for r in records]
