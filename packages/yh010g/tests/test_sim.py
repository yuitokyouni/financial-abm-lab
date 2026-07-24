import numpy as np
import pytest

from agora_engine import fit_pca_em, monoculture_index
from yh010g.sim import (
    Advisor, InvestorSpec, MeetingSimConfig, aggregation_efficiency, mixed_investors,
    selection_quality, simulate,
)
from yh010g.sim.engine import mixed_investors  # noqa: F811 (再エクスポート確認を兼ねる)


def _cfg(**kw):
    base = dict(n_proposals=1500, n_advisors=2, rho=0.5,
                investors=mixed_investors(4, 4, 4, n_advisors=2), seed=7)
    base.update(kw)
    return MeetingSimConfig(**base)


def test_determinism_same_seed():
    r1, r2 = simulate(_cfg()), simulate(_cfg())
    assert np.array_equal(r1.dm.values, r2.dm.values)
    r3 = simulate(_cfg(seed=8))
    assert not np.array_equal(r1.dm.values, r3.dm.values)


def test_followers_replicate_advisor():
    cfg = _cfg(investors=[InvestorSpec("follower", advisor=0),
                          InvestorSpec("follower", advisor=0),
                          InvestorSpec("follower", advisor=1)])
    res = simulate(cfg)
    assert np.array_equal(res.dm.values[0], res.recommendations[0])
    assert np.array_equal(res.dm.values[1], res.recommendations[0])
    assert np.array_equal(res.dm.values[2], res.recommendations[1])


def test_monoculture_index_responds_to_following():
    # 完全追随・助言1社 → 分裂列がほぼ消え、残る列の相関は極大
    followers = MeetingSimConfig(
        n_proposals=1500, n_advisors=1, rho=0.0,
        investors=[InvestorSpec("follower", advisor=0) for _ in range(10)]
        + [InvestorSpec("independent") for _ in range(2)], seed=1)
    independents = MeetingSimConfig(
        n_proposals=1500, n_advisors=1, rho=0.0,
        investors=[InvestorSpec("independent") for _ in range(12)], seed=1)
    def idx(cfg):
        res = simulate(cfg)
        dmf = res.dm.filter_cols(min_observed=2, min_minority_share=0.05)
        return monoculture_index(fit_pca_em(dmf, k=1, max_iter=80))
    assert idx(followers) > idx(independents) + 0.2


def test_idg1_recovers_advisor_assignment():
    """受入基準 (HANDOFF §9): 推奨分裂列上の因子が助言者割当 (地図因子) を回復する。"""
    cfg = MeetingSimConfig(
        n_proposals=4000, n_advisors=2, rho=0.3, advisor=Advisor(sigma_pol=1.5),
        investors=(
            [InvestorSpec("follower", advisor=0) for _ in range(5)]
            + [InvestorSpec("follower", advisor=1) for _ in range(5)]
            + [InvestorSpec("independent") for _ in range(4)]),
        seed=42)
    res = simulate(cfg)
    split = res.split_cols
    assert split.sum() > 100  # 分裂議案が十分ある
    sub = res.dm.values[:, split]
    fit = fit_pca_em(sub, k=1, max_iter=100)
    score = fit.scores[:, 0]
    # 追随者10名のスコア符号が助言者割当と完全一致 (符号は全体反転を許す)
    assign = np.array([+1] * 5 + [-1] * 5)
    follower_scores = score[:10]
    sign_match = np.sign(follower_scores) * assign
    agree = max((sign_match > 0).mean(), (sign_match < 0).mean())
    assert agree == 1.0
    # 追随者のスコア絶対値は独立投資家より大きい (地図因子は追随者に載る)
    assert np.abs(follower_scores).min() > np.abs(score[10:]).mean()


def test_condorcet_gain_and_its_destruction():
    """独立多数決は個票精度を上回り (陪審定理)、完全追随はその利得を消す。"""
    n_inv = 15
    indep = simulate(MeetingSimConfig(
        n_proposals=3000, n_advisors=1, rho=0.0,
        investors=[InvestorSpec("independent") for _ in range(n_inv)], seed=3))
    agg_i, sel_i = aggregation_efficiency(indep), selection_quality(indep)
    assert agg_i > sel_i + 0.05  # 集約利得が存在
    follow = simulate(MeetingSimConfig(
        n_proposals=3000, n_advisors=1, rho=0.0,
        investors=[InvestorSpec("follower", advisor=0) for _ in range(n_inv)], seed=3))
    agg_f, sel_f = aggregation_efficiency(follow), selection_quality(follow)
    assert abs(agg_f - sel_f) < 1e-9  # 全員同票 → 集約利得ゼロ
    assert agg_i > agg_f  # 独立多数決は助言一斉追随より決議の質が高い


def test_config_validation():
    with pytest.raises(ValueError, match="advisor index"):
        MeetingSimConfig(investors=[InvestorSpec("follower", advisor=3)], n_advisors=2)
    with pytest.raises(ValueError, match="rho"):
        MeetingSimConfig(rho=1.5, investors=[InvestorSpec("independent")])
    with pytest.raises(ValueError, match="unknown investor kind"):
        InvestorSpec("robo")
    with pytest.raises(ValueError, match="requires advisor"):
        InvestorSpec("follower")
