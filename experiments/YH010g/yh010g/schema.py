"""統一スキーマと正規化規約 (YH010g_HANDOFF §4 A-1 の実装)。

名寄せ:
  - 発行体は証券コード (4桁文字列。REIT 等の 4 桁超もそのまま文字列で保持)
  - 総会 ID = (証券コード, 総会日)。総会種類はキーに含めない
    (ニッセイが種類を開示しないため。同一社・同日の複数総会は実務上例外的で、
     発生したら build_matrix の重複検出が顕在化させる)
  - 議案キー = (総会ID, 親議案番号, 子議案番号)。議案分類はキーに含めない
    (会社ごとに分類体系が異なるため属性として保持)

エンコーディング (暫定・Task 1 実査に基づく):
  賛成 +1 / 反対 -1 / それ以外の値 (棄権・白紙等) 0。
  実査 3 社の個別開示の賛否欄は賛成/反対のみだったため 0 は事実上未使用。
  未知の値はパーサが unknown_votes に記録し、黙って落とさない。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

VOTE_MAP = {"賛成": 1.0, "反対": -1.0}
VOTE_OTHER = 0.0  # 棄権・白紙委任等 (実データでの出現は Task 1 時点で未確認)
ABSTAIN_LIKE = {"棄権", "白紙", "白紙委任", "不行使"}

PROPOSER_MAP = {
    "会社": "company", "会社提案": "company",
    "株主": "shareholder", "株主提案": "shareholder",
}


@dataclass
class UnifiedRecord:
    manager: str          # 運用機関 ID (mufg_trust / amova / nissay / ...)
    sec_code: str         # 証券コード (文字列)
    company_name: str
    meeting_date: str     # ISO YYYY-MM-DD
    meeting_type: str     # 定時総会 / 臨時総会 / "" (不明)
    proposal_no: int
    sub_no: int           # 子議案・候補者番号。なしは 0
    proposer: str         # company / shareholder / "" (不明)
    category: str         # 会社固有の議案分類 (統一分類は将来 feature)
    vote: float           # +1 / -1 / 0
    vote_raw: str
    reason: str


_DATE_PATTERNS = [
    re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"),
    re.compile(r"^(\d{4})(\d{2})(\d{2})$"),
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$"),
    re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$"),
]


def normalize_date(v) -> str:
    """'20240625' / '2024-06-25' / '2024年06月25日' / datetime → 'YYYY-MM-DD'。"""
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    s = unicodedata.normalize("NFKC", str(v)).strip()
    for pat in _DATE_PATTERNS:
        m = pat.match(s)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            return f"{y:04d}-{mo:02d}-{d:02d}"
    raise ValueError(f"unrecognized date format: {v!r}")


def normalize_month(v) -> str:
    """SMTAM の総会日程 'YYYYMM' → 'YYYY-MM' (月精度。build 側で日精度に解決する)。"""
    s = unicodedata.normalize("NFKC", str(v)).strip()
    m = re.fullmatch(r"(\d{4})(\d{2})", s)
    if not m:
        raise ValueError(f"unrecognized month format: {v!r}")
    return f"{m.group(1)}-{m.group(2)}"


def parse_proposal_no(v) -> tuple[int, int]:
    """議案番号の各社表記 → (親議案番号, 子議案番号)。

    '2.10' (野村・大和) / '2-1' (SMDAM) / '2' / int 2 → (2, 10) 等。
    値はほぼ文字列格納 ('2.10' と '2.1' は区別される) だが、大和2024年版に
    孤立した float セル (例: 1.1 = 候補1番) が僅かに混在することを実査で確認。
    float は '%g' 表記で解釈する。理論上 '1.10' が float 化していると (1,1) に
    潰れるリスクがあるが、その場合は同一キー重複として build_matrix の
    矛盾検出に必ず現れる (黙って混ざらない)。
    """
    if isinstance(v, float) and not v.is_integer():
        v = "%g" % v
    if isinstance(v, (int, float)):
        return int(v), 0
    s = unicodedata.normalize("NFKC", str(v)).strip()
    for sep in (".", "-"):
        if sep in s:
            a, b = s.split(sep, 1)
            return int(a), int(b)
    return int(s), 0


def normalize_sub_no(v) -> int:
    """子議案番号: None / '' / '0' → 0、その他は int。"""
    if v is None:
        return 0
    s = unicodedata.normalize("NFKC", str(v)).strip()
    if s == "":
        return 0
    return int(float(s))


def normalize_sec_code(v) -> str:
    s = unicodedata.normalize("NFKC", str(v)).strip()
    if s.endswith(".0"):  # Excel の数値化対策
        s = s[:-2]
    if not s or not re.fullmatch(r"[0-9A-Z]{4,5}", s):
        raise ValueError(f"unexpected sec_code: {v!r}")
    return s


def map_vote(raw) -> tuple[float, bool]:
    """賛否文字列 → (エンコード値, 既知フラグ)。"""
    s = unicodedata.normalize("NFKC", str(raw)).strip().rstrip("*※")
    if s in VOTE_MAP:
        return VOTE_MAP[s], True
    if s in ABSTAIN_LIKE:
        return VOTE_OTHER, True
    return VOTE_OTHER, False


def map_proposer(raw) -> str:
    s = unicodedata.normalize("NFKC", str(raw or "")).strip()
    return PROPOSER_MAP.get(s, "")


def proposal_col_id(sec_code: str, meeting_date: str, proposal_no: int, sub_no: int) -> str:
    """DecisionMatrix の列 ID。"""
    return f"{sec_code}|{meeting_date}|{proposal_no}|{sub_no}"
