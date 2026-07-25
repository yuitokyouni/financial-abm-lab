from pathlib import Path

import pytest

from yh010g.parsers import (
    parse_amova, parse_daiwa, parse_mufg_am, parse_mufg_trust,
    parse_nissay, parse_nomura, parse_smdam, parse_smtam,
)
from yh010g.schema import proposal_col_id


def test_mufg_trust_parser(mufg_trust_file):
    recs = parse_mufg_trust(mufg_trust_file)
    assert len(recs) == 4
    r0 = recs[0]
    assert (r0.sec_code, r0.meeting_date, r0.proposal_no, r0.sub_no) == ("1301", "2025-06-25", 1, 0)
    assert r0.vote == 1.0 and r0.proposer == "company"
    # 子議案番号: '1' はそのまま、'*' 付き賛否も賛成に正規化
    assert recs[1].sub_no == 1 and recs[1].vote == -1.0
    assert recs[2].vote == 1.0 and recs[2].vote_raw == "賛成*"
    assert recs[3].proposer == "shareholder" and recs[3].meeting_type == "臨時総会"


def test_amova_parser(amova_file):
    recs = parse_amova(amova_file)
    assert len(recs) == 3
    assert recs[0].meeting_date == "2025-06-25"  # 'YYYYMMDD' 形式
    assert recs[2].meeting_date == "2025-06-20"  # 'YYYY-MM-DD' 形式の混在に対応
    assert recs[1].vote == -1.0 and recs[1].reason == "基準未達"
    assert recs[2].proposer == "shareholder"


def test_nissay_parser(nissay_file):
    recs = parse_nissay(nissay_file)
    assert len(recs) == 3
    r0 = recs[0]
    # NFKC 正規化により全角括弧は半角に揃う
    assert (r0.sec_code, r0.company_name, r0.meeting_date) == ("1301", "(株)極洋", "2025-06-25")
    assert r0.meeting_type == ""  # ニッセイは総会種類を開示しない
    assert recs[1].vote == -1.0 and recs[1].sub_no == 1
    assert recs[2].sec_code == "9999" and recs[2].proposer == "shareholder"


def test_cross_manager_join_key(mufg_trust_file, amova_file, nissay_file):
    """3社が同一総会・同一議案を同じ列 ID に解決すること (名寄せの核心)。"""
    all_recs = (parse_mufg_trust(mufg_trust_file) + parse_amova(amova_file)
                + parse_nissay(nissay_file))
    kiyokyo_p1 = {r.manager for r in all_recs
                  if proposal_col_id(r.sec_code, r.meeting_date, r.proposal_no, r.sub_no)
                  == "1301|2025-06-25|1|0"}
    assert kiyokyo_p1 == {"mufg_trust", "amova", "nissay"}


REAL_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "yh010g"

REAL_CASES = [
    ("mufgtrust_2404-2406.xlsx", parse_mufg_trust, 16000),
    ("mufgtrust_2504-2506.xlsx", parse_mufg_trust, 13000),
    ("amova_24q1.xlsx", parse_amova, 16000),
    ("amova_25q1.xlsx", parse_amova, 14000),
    ("nissay_2407.xlsx", parse_nissay, 14000),
    ("nissay_2507.xlsx", parse_nissay, 13000),
    ("nomura_2024q2.xlsx", parse_nomura, 17000),
    ("nomura_2025q2.xlsx", parse_nomura, 14000),
    ("daiwa_202406.xlsx", parse_daiwa, 15000),
    ("daiwa_202506.xlsx", parse_daiwa, 13000),
    ("smdam_2024q2.xlsx", parse_smdam, 17000),
    ("smdam_2025q2.xlsx", parse_smdam, 15000),
    ("mufgam_2024q2.xlsx", parse_mufg_am, 17000),
    ("mufgam_2025q2.xlsx", parse_mufg_am, 14000),
    ("smtam_2024q2.csv", parse_smtam, 17000),
    ("smtam_2025q2.csv", parse_smtam, 14000),
]


@pytest.mark.parametrize("fname,parser,min_rows", REAL_CASES)
def test_real_files(fname, parser, min_rows):
    """実ファイル煙テスト (data/raw/yh010g がある環境のみ。CI ではスキップ)。"""
    path = REAL_DIR / fname
    if not path.exists():
        pytest.skip(f"{path} not present")
    recs = parser(str(path))
    assert len(recs) >= min_rows
    assert all(r.vote in (1.0, -1.0, 0.0) for r in recs)
    # SMTAM は月精度 ('YYYY-MM') — build 側で日精度に解決される
    expected_len = 7 if parser is parse_smtam else 10
    assert all(len(r.meeting_date) == expected_len for r in recs)
