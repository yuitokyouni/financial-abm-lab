import pytest

from yh010g.attributes import load_attributes_csv
from yh010g.build_matrix import drop_class_meetings, long_rows_to_matrix
from yh010g.policy import get_policy, recommendation_splits, reconstruct_recommendations
from yh010g.schema import UnifiedRecord


def _rec(category, pno=1, manager="m1"):
    return UnifiedRecord(manager=manager, sec_code="1301", company_name="X",
                         meeting_date="2025-06-25", meeting_type="定時総会", proposal_no=pno,
                         sub_no=0, proposer="company", category=category,
                         vote=1.0, vote_raw="賛成", reason="")


def test_get_policy_dispatch():
    assert get_policy("iss", 2025)["policy"] == "iss"
    assert get_policy("gl", 2025)["policy"] == "gl"
    with pytest.raises(KeyError):
        get_policy("egan-jones", 2025)


def test_idg1_default_split_retirement_bonus():
    """退職慰労金: ISS原則賛成 vs GL原則反対 → 既定規則だけで分裂が出る。"""
    recs = [_rec("退任役員の退職慰労金の支給"), _rec("買収防衛策の導入・更新・廃止", pno=2),
            _rec("剰余金の処分", pno=3)]
    iss = reconstruct_recommendations(recs, 2025, policy="iss")
    gl = reconstruct_recommendations(recs, 2025, policy="gl")
    splits = recommendation_splits(iss, gl)
    assert list(splits.values()) == [("for_default", "against_default")]
    assert "1301|2025-06-25|1|0" in splits  # 退職慰労金のみ分裂 (防衛策は両社反対・配当は両社賛成)


def test_gl_policy_holdings_midband_rule():
    """GL固有: 政策保有10-20%帯は縮減計画なし・ROE8%未満のときのみ反対。"""
    r = _rec("取締役の選解任")
    col = "1301|2025-06-25|1|0"
    base = {"policy_holdings_to_net_assets": 0.15, "has_reduction_plan": False,
            "roe_5y_avg": 0.05, "roe_latest": 0.06,
            "n_female_directors_post_agm": 2, "is_board_chair": False,
            "has_poison_pill": False, "is_outside_director": False, "attendance_rate": 1.0}
    out = reconstruct_recommendations([r], 2025, attributes={col: dict(base)}, policy="gl")
    assert out[col].recommendation == "against"
    assert out[col].fired_condition == "allegiant_shares_midband"
    # ROE 8%以上なら反対を控える → 全条件クリアで確定 for
    out2 = reconstruct_recommendations(
        [r], 2025, attributes={col: {**base, "roe_5y_avg": 0.09, "roe_latest": 0.09}}, policy="gl")
    assert out2[col].recommendation == "for"


def test_drop_class_meetings_and_conflict_na():
    recs = [_rec("定款に関する議案"),
            UnifiedRecord(manager="m1", sec_code="1301", company_name="X",
                          meeting_date="2025-06-25", meeting_type="種類株主総会",
                          proposal_no=1, sub_no=0, proposer="company",
                          category="定款に関する議案", vote=-1.0, vote_raw="反対", reason="")]
    kept, n = drop_class_meetings(recs)
    assert n == 1 and len(kept) == 1 and kept[0].meeting_type == "定時総会"
    # 矛盾重複は NA 化される
    dm, conflicts = long_rows_to_matrix([("m1", "c1", 1.0), ("m1", "c1", -1.0), ("m2", "c1", 1.0)])
    import numpy as np
    assert conflicts == [("m1", "c1")]
    assert np.isnan(dm.values[dm.row_ids.index("m1"), 0])


def test_load_attributes_csv(tmp_path):
    p = tmp_path / "attrs.csv"
    p.write_text("key,roe_5y_avg,has_reduction_plan,note\n"
                 "1301,0.04,true,テスト\n"
                 "7203|2025-06-12|2|1,,false,\n", encoding="utf-8")
    attrs = load_attributes_csv(p)
    assert attrs["1301"] == {"roe_5y_avg": 0.04, "has_reduction_plan": True, "note": "テスト"}
    assert attrs["7203|2025-06-12|2|1"] == {"has_reduction_plan": False}  # 空セルは未整備
