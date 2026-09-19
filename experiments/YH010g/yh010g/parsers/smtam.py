"""三井住友トラスト・アセットマネジメント 個別開示パーサ (CSV, cp932)。

形式 (2026-07-23 実査): ヘッダはセル内改行を含む引用フィールドあり (csv モジュールで処理):
  取引先フラッグ / コード / 社名 / 総会種類(定時) / 総会日程(YYYYMM ← 月精度!) /
  提案者 / 議案番号 / 候補者番号 / 議案分類 / 当社ガイドラインに基づく行使内容・賛否 /
  同・判断理由 / 他の行使内容
注意: 総会日は年月のみ開示 → meeting_date は 'YYYY-MM' (月精度) で返し、
build_matrix.resolve_month_only_dates が他社の日精度データと突き合わせて解決する。
"""

from __future__ import annotations

import csv
import unicodedata
import warnings

from yh010g.schema import (
    UnifiedRecord, map_proposer, map_vote, normalize_month, normalize_sec_code, normalize_sub_no,
)

MANAGER = "smtam"


def _norm(s) -> str:
    return unicodedata.normalize("NFKC", str(s)).replace("\n", "").strip()


def parse_smtam(path: str) -> list[UnifiedRecord]:
    with open(path, encoding="cp932", newline="") as f:
        reader = csv.reader(f)
        header_seen = False
        out: list[UnifiedRecord] = []
        unknown_votes: list[str] = []
        for row in reader:
            if not row:
                continue
            cells = [c if c is not None else "" for c in row]
            if len(cells) < 12:  # 末尾注記などの短行はパディング
                cells = cells + [""] * (12 - len(cells))
            if not header_seen:
                if len(cells) > 2 and _norm(cells[0]).startswith("取引先") and _norm(cells[1]) == "コード":
                    header_seen = True
                continue
            if _norm(cells[1]) == "":
                continue
            vote, known = map_vote(cells[9])
            if not known:
                unknown_votes.append(str(cells[9]))
            out.append(UnifiedRecord(
                manager=MANAGER,
                sec_code=normalize_sec_code(cells[1]),
                company_name=_norm(cells[2]),
                meeting_date=normalize_month(cells[4]),  # 月精度 'YYYY-MM'
                meeting_type=_norm(cells[3]),
                proposal_no=int(float(_norm(cells[6]))),
                sub_no=normalize_sub_no(cells[7]),
                proposer=map_proposer(cells[5]),
                category=_norm(cells[8]),
                vote=vote,
                vote_raw=_norm(cells[9]),
                reason=_norm(cells[10]) if len(cells) > 10 else "",
            ))
        if not header_seen:
            raise ValueError(f"{path}: header row not found")
        if not out:
            raise ValueError(f"{path}: no data rows parsed")
        if unknown_votes:
            warnings.warn(f"{path}: {len(unknown_votes)} unknown vote values, e.g. {unknown_votes[:5]}",
                          stacklevel=2)
        return out
