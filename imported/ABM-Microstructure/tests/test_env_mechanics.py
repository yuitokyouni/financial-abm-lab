"""T006: MarketEnv の機構恒等式・会計・決定論。

revisable ⇒ extraction ≡ 0 は tolerance なしの恒等（predation ablation の構造保証）。
committed の抽出は 001 検証済みの Budish anchor と統計一致（B env と A 世界の接続）。
"""
import numpy as np
import pytest

from microstructure import anchors
from microstructure.env import MarketEnv, derive_rngs
from microstructure.learnconfig import LearnConfig

BASE = dict(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=1.0)


def _run_fixed(cfg, action_profile, periods):
    env = MarketEnv(cfg, derive_rngs(cfg)["env"])
    rewards = np.zeros((periods, cfg.n_mm))
    infos = []
    for t in range(periods):
        r, info = env.step(action_profile)
        rewards[t] = r
        infos.append(info)
    return rewards, infos


@pytest.mark.parametrize("mech,N", [("continuous", 1), ("batch", 10)])
def test_revisable_extraction_identically_zero(mech, N):
    cfg = LearnConfig(mechanism=mech, batch_interval=N, staleness="revisable",
                      n_mm=2, seed=1, **BASE)
    _, infos = _run_fixed(cfg, (0, 3), 20000)   # 最低 h = 最大 sniping 露出でも 0
    assert all(info["extraction"] == 0.0 for info in infos)


@pytest.mark.parametrize("mech,N", [("continuous", 1), ("batch", 10)])
def test_committed_extraction_positive_low_h(mech, N):
    cfg = LearnConfig(mechanism=mech, batch_interval=N, n_mm=2, seed=1, **BASE)
    _, infos = _run_fixed(cfg, (0, 3), 20000)
    assert sum(info["extraction"] for info in infos) > 0


def test_reward_accounting_zero_sum():
    """Σ rewards = noise_pnl + fees − extraction（毎期、抽出=arb 利得=MM 損のゼロサム規約）。"""
    cfg = LearnConfig(mechanism="batch", batch_interval=5, n_mm=3, fee=0.01,
                      seed=2, **BASE)
    rewards, infos = _run_fixed(cfg, (2, 2, 8), 5000)
    for t, info in enumerate(infos):
        pool = info["noise_pnl"] + info["fees"] - info["extraction"]
        assert rewards[t].sum() == pytest.approx(pool, abs=1e-9)


def test_tie_split_equal_and_loser_zero():
    cfg = LearnConfig(n_mm=3, seed=3, **BASE)
    rewards, _ = _run_fixed(cfg, (2, 2, 8), 5000)
    assert np.array_equal(rewards[:, 0], rewards[:, 1])   # tie の 2 体は等分
    assert np.all(rewards[:, 2] == 0.0)                   # 負けは 0


def test_tie_rotate_one_winner_per_period():
    cfg = LearnConfig(n_mm=2, tie_rule="rotate", seed=4, **BASE)
    rewards, infos = _run_fixed(cfg, (5, 5), 2000)
    nonzero_pool = [t for t, info in enumerate(infos)
                    if info["noise_pnl"] + info["fees"] - info["extraction"] != 0.0]
    for t in nonzero_pool:
        assert (rewards[t] != 0).sum() == 1               # 輪番: 毎期 1 体だけが pool
    got = (rewards[nonzero_pool] != 0)
    assert abs(got[:, 0].sum() - got[:, 1].sum()) <= 1    # 均等に回る


def test_env_determinism():
    cfg = LearnConfig(mechanism="batch", batch_interval=7, n_mm=2, seed=5, **BASE)
    r1, i1 = _run_fixed(cfg, (3, 6), 3000)
    r2, i2 = _run_fixed(cfg, (3, 6), 3000)
    assert np.array_equal(r1, r2)
    assert i1 == i2


def test_continuous_extraction_matches_budish_anchor():
    """B env（committed・連続）の抽出が 001 検証済み anchor と統計一致（A 世界への接続）。"""
    cfg = LearnConfig(n_mm=1, seed=6, **BASE)
    h = cfg.action_grid[2]
    _, infos = _run_fixed(cfg, (2,), 120000)
    rate = sum(info["extraction"] for info in infos) / (120000 * cfg.dt)
    anchor = anchors.budish_sniping_rent(cfg.lambda_jump, cfg.jump_size, cfg.alpha,
                                         cfg.dt, h, 1)
    assert rate == pytest.approx(anchor, rel=0.10)


def test_batch_extraction_matches_budish_anchor():
    cfg = LearnConfig(mechanism="batch", batch_interval=10, n_mm=1, seed=7, **BASE)
    h = cfg.action_grid[2]
    periods = 20000
    _, infos = _run_fixed(cfg, (2,), periods)
    rate = sum(info["extraction"] for info in infos) / (periods * 10 * cfg.dt)
    anchor = anchors.budish_sniping_rent(cfg.lambda_jump, cfg.jump_size, cfg.alpha,
                                         cfg.dt, h, 10)
    assert rate == pytest.approx(anchor, rel=0.10)


def test_noise_reserve_reduces_fills():
    """有限 R（弾力 noise, D-B11 robustness 軸）で fill 数が単調減。"""
    cfg_in = LearnConfig(n_mm=1, seed=8, **BASE)
    cfg_r = LearnConfig(n_mm=1, seed=8, noise_reserve=1.0, **BASE)
    a = 3  # h ≈ 0.66 < R=1.0 → 受諾率 1−h/R ≈ 0.34
    _, inf_in = _run_fixed(cfg_in, (a,), 20000)
    _, inf_r = _run_fixed(cfg_r, (a,), 20000)
    n_in = sum(i["n_noise"] for i in inf_in)
    n_r = sum(i["n_noise"] for i in inf_r)
    assert 0 < n_r < n_in
