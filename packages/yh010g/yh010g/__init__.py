"""yh010g — 議決権行使個別開示のデータパイプライン (ワークストリームA)。

パイロット対象 3 社 (docs/2026-07-23-YH010g-disclosure-inventory.md の推奨構成):
  - 三菱UFJ信託銀行 (mufg_trust): 全期間 xlsx
  - アモーヴァAM 旧日興 (amova): robots 明示許可
  - ニッセイAM (nissay): 全議案に理由テキスト
"""

from yh010g.schema import VOTE_MAP, UnifiedRecord, normalize_date, proposal_col_id

__all__ = ["VOTE_MAP", "UnifiedRecord", "normalize_date", "proposal_col_id"]
