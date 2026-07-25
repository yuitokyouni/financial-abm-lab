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
    month_resolution: dict | None = None        # 月精度日付の解決統計


def drop_class_meetings(records: list[UnifiedRecord]) -> tuple[list[UnifiedRecord], int]:
    """種類株主総会の行を除外する。

    種類株主総会は普通株主総会と同日に開かれることがあり (例: 7150 2022-06-24)、
    総会キー (証券コード, 総会日) が普通総会と衝突する。開示しているのは一部の
    運用機関のみでクロス結合もできないため、除外して件数を記録する。
    """
    kept = [r for r in records if "種類" not in r.meeting_type]
    return kept, len(records) - len(kept)


def long_rows_to_matrix(
    rows: list[tuple[str, str, float]],
) -> tuple[DecisionMatrix, list[tuple[str, str]]]:
    """(manager, col_id, vote) の長形式から、矛盾重複を NA 化して行列を構築する。

    同一キーの賛否矛盾 (不統一行使の分割開示等) は単一の ±1 で表現できないため
    NA とし、キーのリストを返す (build_decision_matrix と同一の規約)。
    panel_analysis 等、parquet から部分行列を作る全ての場所でこれを使うこと。
    """
    cell: dict[tuple[str, str], float] = {}
    conflicts: set[tuple[str, str]] = set()
    for m, c, v in rows:
        key = (m, c)
        if key in cell and cell[key] != v:
            conflicts.add(key)
        else:
            cell.setdefault(key, v)
    for key in conflicts:
        cell[key] = np.nan
    dm = DecisionMatrix.from_long([(m, c, v) for (m, c), v in cell.items()])
    return dm, sorted(conflicts)


def resolve_month_only_dates(records: list[UnifiedRecord]) -> tuple[list[UnifiedRecord], dict]:
    """月精度 ('YYYY-MM') の meeting_date を、日精度レコードとの突き合わせで解決する。

    SMTAM は総会日を年月でしか開示しないため、(証券コード, 年月) に対して他社の
    日精度総会日が一意に存在する場合のみその日を割り当てる。複数候補 (同月複数総会) や
    候補なしのレコードは解決不能として除外し、統計を返す (黙って落とさない)。
    """
    full_dates: dict[tuple[str, str], set[str]] = {}
    for r in records:
        if len(r.meeting_date) == 10:
            full_dates.setdefault((r.sec_code, r.meeting_date[:7]), set()).add(r.meeting_date)
    resolved: list[UnifiedRecord] = []
    stats = {"month_only": 0, "resolved": 0, "ambiguous": 0, "no_candidate": 0}
    for r in records:
        if len(r.meeting_date) == 10:
            resolved.append(r)
            continue
        stats["month_only"] += 1
        cands = full_dates.get((r.sec_code, r.meeting_date), set())
        if len(cands) == 1:
            stats["resolved"] += 1
            resolved.append(UnifiedRecord(**{**vars(r), "meeting_date": next(iter(cands))}))
        elif len(cands) > 1:
            stats["ambiguous"] += 1
        else:
            stats["no_candidate"] += 1
    if stats["ambiguous"] or stats["no_candidate"]:
        warnings.warn(
            f"month-only dates dropped: ambiguous={stats['ambiguous']} "
            f"no_candidate={stats['no_candidate']} (resolved={stats['resolved']})",
            stacklevel=2)
    return resolved, stats


def build_decision_matrix(
    records: list[UnifiedRecord],
    matrix_id: str,
    sources: list[dict],
    created_by: str = "claude-code",
) -> BuildResult:
    records, month_stats = resolve_month_only_dates(records)
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
            "month_resolution": month_stats,
        },
    )
    return BuildResult(dm=dm, sidecar=sidecar, n_meetings=len(meetings),
                       duplicate_conflicts=sorted(conflicts), month_resolution=month_stats)


def records_to_rows(records: list[UnifiedRecord]) -> list[dict]:
    """長形式の dict 行 (parquet/csv 保存用)。"""
    return [vars(r) | {"col_id": proposal_col_id(r.sec_code, r.meeting_date, r.proposal_no, r.sub_no)}
            for r in records]
