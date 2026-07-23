"""三菱UFJ信託銀行 会社別議案別行使結果パーサ。

形式 (2026-07-23 実査、docs/2026-07-23-YH010g-disclosure-inventory.md):
  シート「議決権行使結果」、3行目がヘッダ:
  銘柄コード / 銘柄名称 / 総会日(YYYYMMDD) / 総会種類 / 議案番号 / 子議案番号 /
  提案者(会社|株主) / 議案分類 / 賛否 / 理由
  子議案番号: 2024年6月分以前は空欄、2024年7月以降ファイルは 0 が入る — どちらも 0 に正規化。
  賛否に「*」付き (顧客ガイドラインによる不統一行使の注記) がありうる → 記号は除去し
  unified には注記フラグを reason 側に残さず vote_raw で保持。
"""

from __future__ import annotations

import unicodedata
import warnings

import openpyxl

from yh010g.schema import (
    UnifiedRecord, map_proposer, map_vote, normalize_date, normalize_sec_code, normalize_sub_no,
)

SHEET = "議決権行使結果"
HEADER_PREFIX = ["銘柄コード", "銘柄名称", "総会日", "総会種類", "議案番号", "子議案番号", "提案者", "議案分類", "賛否"]
MANAGER = "mufg_trust"


def parse_mufg_trust(path: str) -> list[UnifiedRecord]:
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        if SHEET not in wb.sheetnames:
            raise ValueError(f"{path}: sheet {SHEET!r} not found (got {wb.sheetnames})")
        ws = wb[SHEET]
        rows = ws.iter_rows(values_only=True)
        header_seen = False
        out: list[UnifiedRecord] = []
        unknown_votes: list[str] = []
        skipped_footers: list[str] = []
        for row in rows:
            cells = [c if c is not None else "" for c in row]
            if not header_seen:
                head = [unicodedata.normalize("NFKC", str(c)).strip() for c in cells[:9]]
                if head == HEADER_PREFIX:
                    header_seen = True
                continue
            if str(cells[0]).strip() == "":
                continue
            try:
                sec_code = normalize_sec_code(cells[0])
            except ValueError:
                # データ末尾の注記行 (例: '（注）・撤回された議案を…') はスキップ
                skipped_footers.append(str(cells[0])[:20])
                continue
            vote, known = map_vote(cells[8])
            if not known:
                unknown_votes.append(str(cells[8]))
            out.append(UnifiedRecord(
                manager=MANAGER,
                sec_code=sec_code,
                company_name=str(cells[1]).strip(),
                meeting_date=normalize_date(cells[2]),
                meeting_type=str(cells[3]).strip(),
                proposal_no=int(float(str(cells[4]))),
                sub_no=normalize_sub_no(cells[5]),
                proposer=map_proposer(cells[6]),
                category=str(cells[7]).strip(),
                vote=vote,
                vote_raw=str(cells[8]).strip(),
                reason=str(cells[9]).strip() if len(cells) > 9 else "",
            ))
        if not header_seen:
            raise ValueError(f"{path}: header row not found in sheet {SHEET!r}")
        if not out:
            raise ValueError(f"{path}: no data rows parsed")
        if unknown_votes:
            warnings.warn(f"{path}: {len(unknown_votes)} unknown vote values, e.g. {unknown_votes[:5]}",
                          stacklevel=2)
        return out
    finally:
        wb.close()
