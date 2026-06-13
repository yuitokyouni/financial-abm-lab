"""aggregate-demand 側 (C0u / C0p / 旧 C0 reference) の metrics loader。

2×2 world×wealth 比較の aggregate 側:
    load_c0u()  -> N=100 uniform  (本 YH006 で生成、run_aggregate_c0.py)
    load_c0p()  -> N=100 Pareto   (本 YH006 で生成、run_aggregate_c0.py)

N scaling reference (2×2 には含めない、補遺用):
    load_c0_reference_1000() -> YH005_1 の N=1000 uniform result
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
YH005_1_METRICS = HERE.parent / "YH005_1" / "outputs" / "phase1_metrics.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"metrics not found at {path}")
    with open(path) as f:
        return json.load(f)


def load_c0u() -> Dict[str, Any]:
    """N=100 aggregate-demand × uniform initial wealth。"""
    return _load_json(HERE / "outputs" / "c0u_metrics.json")


def load_c0p() -> Dict[str, Any]:
    """N=100 aggregate-demand × Pareto α=1.5 initial wealth。"""
    return _load_json(HERE / "outputs" / "c0p_metrics.json")


def load_c0_reference_1000() -> Dict[str, Any]:
    """旧 C0: N=1000 aggregate-demand × uniform (YH005_1 output)。

    2×2 には含めず、N=100 vs N=1000 の有限サイズ効果を示す補遺として使う。
    """
    return _load_json(YH005_1_METRICS)


# 後方互換 (既存 import 保護用、deprecated)
def load_c0_metrics() -> Dict[str, Any]:
    """Deprecated: use load_c0u / load_c0p / load_c0_reference_1000。

    historical: YH005_1 の N=1000 uniform を返す (= load_c0_reference_1000)。
    2×2 化後は C0u / C0p に移行。
    """
    return load_c0_reference_1000()


if __name__ == "__main__":
    def _fmt(m: Dict[str, Any]) -> None:
        p = m.get("params", {})
        print(f"  N={p.get('N')} T={p.get('T')} wealth_mode={p.get('wealth_mode', 'uniform(hardcoded)')}")
        print(f"  num_round_trips = {m['price_stats']['num_round_trips']}")
        print(f"  wealth α_hill   = {m['wealth']['alpha_hill_xmin_p90']:.3f}")
        print(f"  median wealth   = {m['wealth']['median_wealth']:.1f}")
        print(f"  horizon median  = {m['horizon']['median_horizon']:.1f}")
        print(f"  passive_hold    = {m['hold_ratio']['passive_hold']:.3f}")
        print(f"  active_hold     = {m['hold_ratio']['active_hold']:.3f}")

    for name, fn in [
        ("C0u (N=100 uniform)", load_c0u),
        ("C0p (N=100 Pareto α=1.5)", load_c0p),
        ("C0 reference (N=1000 uniform, YH005_1)", load_c0_reference_1000),
    ]:
        try:
            m = fn()
            print(f"--- {name} ---")
            _fmt(m)
        except FileNotFoundError as e:
            print(f"--- {name}: NOT FOUND ---")
            print(f"  {e}")
