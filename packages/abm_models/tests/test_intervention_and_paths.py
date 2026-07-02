"""正準 ABM の transaction_tax 介入 (#22) と n_paths 集計 (#23) の回帰テスト。

監査 (2026-07-02):
  #22: chiarella_iori / franke_westerhoff の transaction_tax が単位誤り
       (1 − rate/mid ≈ 1 − rate/100) で実質 no-op だった。税率 fraction で demand
       を (1 − rate) 倍にする意味論へ修正。
  #23: FW / CI / ZI が n_paths>1 で returns をパス間平均しており、kurtosis /
       volatility clustering など測定対象の stylized facts を破壊していた。独立パス
       を連結 (pool) する形へ修正。n_paths=1 は不変 (parity 保持)。
"""

from __future__ import annotations

import numpy as np

from abm_models.chiarella_iori.model import CIAdapter, CIParams
from abm_models.franke_westerhoff.model import FWAdapter, FWParams
from abm_models.zero_intelligence.model import ZIAdapter, ZIParams


# ---------------------------------------------------------------- #22

def test_fw_transaction_tax_dampens_volatility():
    """FW: 高い税率が excess demand を減衰させ、returns の分散を大きく下げる。

    旧 no-op 実装では税率を上げても std がほぼ不動 (ratio ≈ 1) だった。
    """
    r0 = FWAdapter(params=FWParams(n_steps=3000)).simulate(seed=1, n_paths=1).returns
    r9 = FWAdapter(params=FWParams(n_steps=3000, transaction_cost=0.9)).simulate(
        seed=1, n_paths=1
    ).returns
    assert np.std(r9) < 0.3 * np.std(r0), (
        f"transaction_tax が demand を減衰させていない: "
        f"std(tax=0.9)/std(tax=0)={np.std(r9) / np.std(r0):.3f}"
    )


def test_ci_transaction_tax_full_zeros_demand():
    """CI: 100% 課税で net demand が 0 になり価格が動かない (std ≈ 0)。

    CI の returns は ±spread のスイングで符号支配的なので中間税率では鈍いが、
    100% 課税は demand を完全に消す。旧実装は factor = 1 − rate/mid = 1 − 0.01 =
    0.99 で 100% 課税でも demand がほぼ残り std が下がらなかった (no-op)。
    """
    r0 = CIAdapter(params=CIParams(n_steps=2000)).simulate(seed=1, n_paths=1).returns
    r_full = CIAdapter(params=CIParams(n_steps=2000, transaction_cost=1.0)).simulate(
        seed=1, n_paths=1
    ).returns
    assert np.std(r0) > 0, "baseline が既に無変動 — テスト前提が崩れている"
    assert np.std(r_full) < 1e-9, (
        f"100% 課税でも価格が動いている (std={np.std(r_full):.2e}) — 税が効いていない"
    )


# ---------------------------------------------------------------- #23

def _pool_case(Adapter, Params):
    n_steps = 1000
    single = Adapter(params=Params(n_steps=n_steps)).simulate(seed=2, n_paths=1).returns
    pooled = Adapter(params=Params(n_steps=n_steps)).simulate(seed=2, n_paths=3).returns
    return n_steps, single, pooled


def test_npaths_pooling_preserves_length_and_scale():
    """FW/CI/ZI: n_paths=3 は 3 本を連結 (len = 3·n_steps) し、std を縮めない。

    旧 np.mean 実装では len = n_steps のまま、独立ノイズの平均で std が ~1/√3 に
    縮み stylized facts が薄い尾へ潰れていた。
    """
    for Adapter, Params in [
        (FWAdapter, FWParams),
        (CIAdapter, CIParams),
        (ZIAdapter, ZIParams),
    ]:
        n_steps, single, pooled = _pool_case(Adapter, Params)
        assert len(pooled) == 3 * n_steps, (
            f"{Adapter.__name__}: n_paths=3 の returns 長 {len(pooled)} != {3 * n_steps} "
            f"(パス平均で len が縮んでいる)"
        )
        # 平均だと std ≈ single/√3。連結なら single とほぼ同じスケール。
        assert np.std(pooled) > 0.7 * np.std(single), (
            f"{Adapter.__name__}: pooled std={np.std(pooled):.5f} が single "
            f"std={np.std(single):.5f} に対し過小 — 平均で潰れている疑い"
        )


def test_npaths_one_is_unchanged_single_path():
    """n_paths=1 は 1 本の path そのもの (parity 不変の確認)。"""
    for Adapter, Params in [(FWAdapter, FWParams), (CIAdapter, CIParams), (ZIAdapter, ZIParams)]:
        a = Adapter(params=Params(n_steps=500)).simulate(seed=7, n_paths=1).returns
        assert len(a) == 500


if __name__ == "__main__":
    test_fw_transaction_tax_dampens_volatility()
    test_ci_transaction_tax_full_zeros_demand()
    test_npaths_pooling_preserves_length_and_scale()
    test_npaths_one_is_unchanged_single_path()
    print("[intervention-and-paths] ✓ pass")
