"""YH007-8 φ/σ 較正値の regression guard。

spec 003 §12 round6 追記 (2026-07-21, ecb788d) の裁定:
  「以後の dose-match には修正値 φ=0.615/σ=3.81e-3 を使うこと」
(旧 0.418/6e-3 は bar 内 last-wins pairing の drift 汚染値。P0 監査
 docs/audit/P0_yh007_parameter_provenance.md で全 9 箇所が旧値のまま =
 更新漏れと裁定された)

このテストは、コード既定値が spec の修正値と一致し続けることを固定する。
較正を再実測して値が変わる場合は、spec 003 改訂履歴に記録した上で
ここの期待値を同一コミットで更新すること。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from abm_models.self_organized_book import SelfOrganizedBookMarket, ZIAgent
from abm_models.self_organized_book.model import build_sob_config

# spec 003 §12 round6 追記の修正較正値 (first-entry pairing 規約)
PHI_CORRECTED = 0.615
SIGMA_CORRECTED = 3.81e-3


def _defaults(func):
    sig = inspect.signature(func)
    return {k: v.default for k, v in sig.parameters.items()
            if v.default is not inspect.Parameter.empty}


def test_build_config_defaults_use_corrected_calibration():
    d = _defaults(build_sob_config)
    assert d["zi_phi_ar1"] == PHI_CORRECTED
    assert d["zi_sigma_ar1_abs"] == SIGMA_CORRECTED
    assert d["zi_strategy_phi_ar1"] == PHI_CORRECTED
    assert d["zi_strategy_sigma_ar1_abs"] == SIGMA_CORRECTED


def test_market_init_defaults_use_corrected_calibration():
    d = _defaults(SelfOrganizedBookMarket.__init__)
    assert d["zi_phi_ar1"] == PHI_CORRECTED
    assert d["zi_sigma_ar1_abs"] == SIGMA_CORRECTED
    assert d["zi_strategy_phi_ar1"] == PHI_CORRECTED
    assert d["zi_strategy_sigma_ar1_abs"] == SIGMA_CORRECTED


def test_zi_agent_settings_fallback_uses_corrected_calibration():
    """settings dict 経由の fallback 既定値 (zi_agent.py setup 内リテラル) も修正値。

    ZIAgent は PAMS runner 経由でしか生成できないため、fallback リテラルは
    ソースを直接検査する (settings.get("phiAr1", X) の X)。
    """
    src = inspect.getsource(ZIAgent.setup)
    m_phi = re.search(r'settings\.get\("phiAr1",\s*([0-9.e+-]+)\)', src)
    m_sig = re.search(r'settings\.get\("sigmaAr1Abs",\s*([0-9.e+-]+)\)', src)
    assert m_phi and m_sig, "phiAr1/sigmaAr1Abs の fallback 既定値が見つからない"
    assert float(m_phi.group(1)) == PHI_CORRECTED
    assert float(m_sig.group(1)) == SIGMA_CORRECTED


def test_p3d_cli_override_defaults_use_corrected_calibration():
    """p3d スクリプトの CLI override 既定値 (--phi-ar1 / --sigma-ar1-abs) も修正値。

    呼び出し点ハードコードを common.get(...) + CLI 既定値に置き換えたことで
    値の定義箇所が 1 つ増えた (P0_numeric_literal_diff.md の残注意)。較正定数の
    入力アーティファクト化 (BACKLOG の Contract 要件 1) までの追随漏れガード。
    """
    script = (Path(__file__).resolve().parent.parent
              / "experiments" / "YH007" / "scripts" / "yh007_8_p3d_shared_ar1.py")
    src = script.read_text()
    m_phi = re.search(r'"--phi-ar1",\s*type=float,\s*default=([0-9.e+-]+)', src)
    m_sig = re.search(r'"--sigma-ar1-abs",\s*type=float,\s*default=([0-9.e+-]+)', src)
    m_get_phi = re.search(r'common\.get\("phi_ar1",\s*([0-9.e+-]+)\)', src)
    m_get_sig = re.search(r'common\.get\("sigma_ar1_abs",\s*([0-9.e+-]+)\)', src)
    assert m_phi and m_sig and m_get_phi and m_get_sig, \
        "p3d の CLI/common.get 既定値が見つからない (構造変更時はこのテストを追随させること)"
    for m in (m_phi, m_get_phi):
        assert float(m.group(1)) == PHI_CORRECTED
    for m in (m_sig, m_get_sig):
        assert float(m.group(1)) == SIGMA_CORRECTED


def test_matched_ar1_run_wires_corrected_defaults_to_agents():
    """既定値のまま run した agent の実効 φ/σ が修正値であること (配線の end-to-end)。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=20, main_steps=30, n_zi=2,
        bar_size=10, order_ttl=10, zi_mode="matched_ar1",
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    res = m.run(seed=0)
    agents = [a for a in res["agents"] if getattr(a, "zi_mode", "") == "matched_ar1"]
    assert agents, "matched_ar1 agent が生成されていない"
    for a in agents:
        assert a.phi_ar1 == PHI_CORRECTED
        assert a.sigma_ar1_abs == SIGMA_CORRECTED
