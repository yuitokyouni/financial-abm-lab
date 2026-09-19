import numpy as np
import pytest

from yh010g.build_matrix import build_decision_matrix, records_to_rows
from yh010g.parsers import parse_amova, parse_mufg_trust, parse_nissay
from yh010g.schema import UnifiedRecord


def _rec(manager, sec="1301", date="2025-06-25", pno=1, sub=0, vote=1.0):
    return UnifiedRecord(manager=manager, sec_code=sec, company_name="X",
                         meeting_date=date, meeting_type="定時総会", proposal_no=pno,
                         sub_no=sub, proposer="company", category="c", vote=vote,
                         vote_raw="賛成" if vote == 1.0 else "反対", reason="")


def test_build_from_three_parsers(mufg_trust_file, amova_file, nissay_file):
    records = (parse_mufg_trust(mufg_trust_file) + parse_amova(amova_file)
               + parse_nissay(nissay_file))
    result = build_decision_matrix(records, matrix_id="yh010g-A-test",
                                   sources=[{"manager": "all", "url": "fixture",
                                             "retrieved_at": "", "format": "xlsx",
                                             "parser": "mixed", "file_sha256": ""}])
    dm = result.dm
    assert set(dm.row_ids) == {"mufg_trust", "amova", "nissay"}
    # 極洋 第1号議案は3社とも観測、賛否一致 (+1)
    j = dm.col_ids.index("1301|2025-06-25|1|0")
    assert not np.isnan(dm.values[:, j]).any()
    assert (dm.values[:, j] == 1.0).all()
    assert result.sidecar["coverage"]["managers"] == 3
    assert result.sidecar["coverage"]["meetings"] == result.n_meetings == 2
    assert result.duplicate_conflicts == []


def test_conflicting_duplicates_become_na():
    records = [_rec("m1", vote=1.0), _rec("m1", vote=-1.0), _rec("m2", vote=1.0)]
    with pytest.warns(UserWarning, match="conflicting duplicate"):
        result = build_decision_matrix(records, "id", sources=[])
    dm = result.dm
    i = dm.row_ids.index("m1")
    assert np.isnan(dm.values[i, 0])
    assert result.duplicate_conflicts == [("m1", "1301|2025-06-25|1|0")]


def test_identical_duplicates_deduped():
    records = [_rec("m1"), _rec("m1")]
    result = build_decision_matrix(records, "id", sources=[])
    assert result.dm.values[0, 0] == 1.0 and result.duplicate_conflicts == []


def test_records_to_rows_has_col_id():
    rows = records_to_rows([_rec("m1")])
    assert rows[0]["col_id"] == "1301|2025-06-25|1|0"
    assert rows[0]["manager"] == "m1"
