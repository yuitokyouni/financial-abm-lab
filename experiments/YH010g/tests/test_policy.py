import pytest

from yh010g.policy import iss_policy, normalize_category, reconstruct_recommendations
from yh010g.policy.engine import coverage_report
from yh010g.schema import UnifiedRecord


def _rec(category, sec="1301", pno=1, sub=0, date="2025-06-25", manager="m1"):
    return UnifiedRecord(manager=manager, sec_code=sec, company_name="X",
                         meeting_date=date, meeting_type="定時総会", proposal_no=pno,
                         sub_no=sub, proposer="company", category=category,
                         vote=1.0, vote_raw="賛成", reason="")


def test_category_normalization_cross_manager():
    assert normalize_category("取締役の選解任") == "director_election"
    assert normalize_category("取締役の選任等に関する議案") == "director_election"  # ニッセイ
    assert normalize_category("買収防衛策の導入・更新・廃止") == "poison_pill"
    assert normalize_category("謎の新分類") == "unknown"


def test_policy_year_versioning():
    assert iss_policy(2025)["applies_from"] == "2025-02-01"
    assert iss_policy(2024)["applies_from"] == "2024-02-01"
    with pytest.raises(KeyError):
        iss_policy(2019)


def test_default_rules_fire_without_attributes():
    recs = reconstruct_recommendations(
        [_rec("買収防衛策の導入・更新・廃止"), _rec("剰余金の処分", pno=2), _rec("定款に関する議案", pno=3)],
        policy_year=2025)
    by_cat = {r.category: r.recommendation for r in recs.values()}
    assert by_cat["poison_pill"] == "against_default"
    assert by_cat["dividend"] == "for_default"
    assert by_cat["articles"] == "indeterminate"


def test_conditional_rule_with_attributes():
    r = _rec("取締役の選解任", sec="7203", pno=2, sub=1)
    col = "7203|2025-06-25|2|1"
    # ROE 基準に抵触する経営トップ → against (確定判定)
    attrs_bad = {col: {"roe_5y_avg": 0.03, "roe_improving": False, "is_top_management": True,
                       "policy_holdings_to_net_assets": 0.05, "n_female_directors_post_agm": 2,
                       "is_outside_director": False, "iss_independent": True, "attendance_rate": 1.0}}
    out = reconstruct_recommendations([r], 2025, attributes=attrs_bad)
    assert out[col].recommendation == "against" and out[col].fired_condition == "roe"
    # 全条件クリア → for (確定判定、_default ではない)
    attrs_ok = {col: {**attrs_bad[col], "roe_5y_avg": 0.09}}
    out2 = reconstruct_recommendations([r], 2025, attributes=attrs_ok)
    assert out2[col].recommendation == "for"
    # 属性なし → for_default + missing_fields 記録
    out3 = reconstruct_recommendations([r], 2025)
    assert out3[col].recommendation == "for_default"
    assert "roe_5y_avg" in out3[col].missing_fields


def test_retirement_bonus_outsider_recipient():
    r = _rec("退任役員の退職慰労金の支給", pno=4)
    col = "1301|2025-06-25|4|0"
    out = reconstruct_recommendations(
        [r], 2025, attributes={col: {"recipients_include_outsiders": True, "amount_disclosed": True}})
    assert out[col].recommendation == "against"
    assert out[col].fired_condition == "outsider_recipient"


def test_coverage_report_counts():
    recs = reconstruct_recommendations(
        [_rec("買収防衛策の導入・更新・廃止"), _rec("剰余金の処分", pno=2)], 2025)
    cov = coverage_report(recs)
    assert cov["n"] == 2
    assert cov["by_recommendation"] == {"against_default": 1, "for_default": 1}
