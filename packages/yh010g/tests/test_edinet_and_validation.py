"""EDINET パース・抽出 (フィクスチャ) と精度検証ハーネスのテスト (ネットワークなし)。"""

from yh010g.edinet import (
    EL_NET_ASSETS_SUMMARY, EL_POLICY_HOLDINGS, EL_ROE,
    extract_attributes, parse_edinet_csv,
)
from yh010g import validate_policy


def _fixture_csv() -> str:
    header = "要素ID\t項目名\tコンテキストID\t相対年度\t連結・個別\t期間・時点\tユニットID\t単位\t値"
    rows = [
        # ROE 5年分 (パーセント表記)。連結を優先させるため NonConsolidated も混ぜる
        f"{EL_ROE}\tROE\tCurrentYearDuration\t当期\t連結\t期間\tPure\t％\t3.5",
        f"{EL_ROE}\tROE\tCurrentYearDuration_NonConsolidatedMember\t当期\t個別\t期間\tPure\t％\t9.9",
        f"{EL_ROE}\tROE\tPrior1YearDuration\t前期\t連結\t期間\tPure\t％\t4.0",
        f"{EL_ROE}\tROE\tPrior2YearDuration\t前々期\t連結\t期間\tPure\t％\t4.5",
        f"{EL_ROE}\tROE\tPrior3YearDuration\t3期前\t連結\t期間\tPure\t％\t5.0",
        f"{EL_ROE}\tROE\tPrior4YearDuration\t4期前\t連結\t期間\tPure\t％\t5.5",
        f"{EL_NET_ASSETS_SUMMARY}\t純資産\tCurrentYearInstant\t当期\t連結\t時点\tJPY\t百万円\t1,000,000",
        f"{EL_POLICY_HOLDINGS}\t政策保有\tCurrentYearInstant\t当期\t連結\t時点\tJPY\t百万円\t250,000",
    ]
    return "\n".join([header, *rows])


def test_parse_and_extract():
    rows = parse_edinet_csv(_fixture_csv())
    assert len(rows) == 8
    ext = extract_attributes(rows, "7203")
    # 連結が選ばれる (当期3.5%、個別9.9%ではない)
    assert ext.roe_series[0] == 0.035
    assert ext.roe_series[4] == 0.055
    assert ext.net_assets == 1_000_000
    assert ext.policy_holdings == 250_000
    d = ext.to_attr_dict()
    assert abs(d["roe_latest"] - 0.035) < 1e-9
    assert abs(d["roe_5y_avg"] - (0.035 + 0.04 + 0.045 + 0.05 + 0.055) / 5) < 1e-9
    # 政策保有 25% → 20%基準超過
    assert abs(d["policy_holdings_to_net_assets"] - 0.25) < 1e-9


def test_extract_records_unmatched():
    rows = parse_edinet_csv("要素ID\tコンテキストID\t値\njpcrp_cor:Foo\tCurrentYearInstant\t1")
    ext = extract_attributes(rows, "9999")
    assert EL_ROE in ext.unmatched and EL_POLICY_HOLDINGS in ext.unmatched
    assert ext.to_attr_dict() == {}  # 何も取れない → 空 (黙って0を返さない)


def test_validation_harness_manual_only():
    """EDINET なし: mechanical は検証可、financial は属性不足で ISS ミス (期待挙動)。"""
    report = validate_policy.main(edinet_path=None)
    mech = report["by_mechanism"]
    # 機械的規則 (女性ゼロ・買収防衛策) は完全一致
    assert mech["mechanical"]["iss_acc"] == 1.0
    # financial (政策保有) は EDINET 不在で ISS 反対を再現できない
    assert mech["financial"]["iss_acc"] == 0.0
    assert mech["financial"]["gl_acc"] == 1.0  # GLは縮減計画例外で賛成=既定と一致
    # judgmental は範囲外。トヨタ2023(ISS賛成)は既定と偶然一致、2024(反対)はミス → 0.5
    assert mech["judgmental"]["iss_acc"] == 0.5
    assert mech["judgmental"]["gl_acc"] == 0.0


def test_validation_harness_with_edinet(tmp_path):
    """EDINET 財務を注入すると financial 系 ISS が反対を再現する (end-to-end)。"""
    edinet_csv = tmp_path / "attrs.csv"
    edinet_csv.write_text(
        "key,policy_holdings_to_net_assets\n8411,0.28\n8309,0.31\n8306,0.25\n",
        encoding="utf-8")
    report = validate_policy.main(edinet_path=str(edinet_csv))
    mech = report["by_mechanism"]
    assert mech["financial"]["iss_acc"] == 1.0  # 政策保有充填で ISS 反対を再現
    assert mech["mechanical"]["iss_acc"] == 1.0  # 機械的規則は不変
