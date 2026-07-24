"""パネル分析: モノカルチャー指標の四半期時系列 + ルートA/B照合 + ID-g1分裂検出。

実行: uv run python -m yh010g.panel_analysis
出力: data/processed/yh010g/panel_report.json
注意: 記述目的。lopsided閾値等は仮置き (登録時固定)。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from agora_engine import fit_pca_em, monoculture_index
from agora_engine.factor_model import fit_irt
from yh010g.build_matrix import long_rows_to_matrix
from yh010g.policy import recommendation_splits, reconstruct_recommendations
from yh010g.schema import UnifiedRecord

OUT_DIR = Path("data/processed/yh010g")
MIN_MANAGERS = 5
LOPSIDED = 0.05


def _quarter(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def quarterly_series(df: pd.DataFrame) -> list[dict]:
    out = []
    for q, g in sorted(df.groupby(df.meeting_date.map(_quarter))):
        n_mgr = g.manager.nunique()
        dm, _ = long_rows_to_matrix(list(zip(g.manager, g.col_id, g.vote)))
        dmf = dm.filter_cols(min_observed=MIN_MANAGERS, min_minority_share=LOPSIDED)
        row = {"quarter": q, "managers": int(n_mgr),
               "proposals": len(dm.col_ids), "split_cols": len(dmf.col_ids)}
        if n_mgr >= MIN_MANAGERS and len(dmf.col_ids) >= 50:
            fit = fit_pca_em(dmf, k=1, max_iter=1000)
            row |= {"monoculture_k1": round(monoculture_index(fit), 4),
                    "converged": fit.converged, "n_iter": fit.n_iter}
        else:
            row |= {"monoculture_k1": None,
                    "note": "insufficient managers or split columns"}
        out.append(row)
    return out


def route_comparison(df: pd.DataFrame) -> dict:
    """ルートA (PCA-EM) と ルートB (IRT) の主体スコアの一致度 (Task 5 頑健性比較)。"""
    dm, _ = long_rows_to_matrix(list(zip(df.manager, df.col_id, df.vote)))
    dmf = dm.filter_cols(min_observed=MIN_MANAGERS, min_minority_share=LOPSIDED)
    fa = fit_pca_em(dmf, k=1, max_iter=1000)
    fb = fit_irt(dmf)
    r = float(np.corrcoef(fa.scores[:, 0], fb.theta)[0, 1])
    return {"shape": list(dmf.values.shape),
            "route_a": {"converged": fa.converged, "n_iter": fa.n_iter,
                        "monoculture_k1": round(monoculture_index(fa), 4)},
            "route_b": {"converged": fb.converged, "n_iter": fb.n_iter},
            "score_correlation_abs": round(abs(r), 4),
            "row_ids": dmf.row_ids,
            "route_a_scores": [round(float(v), 3) for v in fa.scores[:, 0]],
            "route_b_theta": [round(float(v), 3) for v in fb.theta]}


def idg1_reconstruction_splits(df: pd.DataFrame) -> dict:
    """ISS/GL 再構成推奨の分裂 (ID-g1)。属性未整備のため既定規則ベースの下限値。"""
    recs = [UnifiedRecord(**{f: row[f] for f in UnifiedRecord.__dataclass_fields__})
            for row in df[df.meeting_date >= "2025-02-01"].to_dict("records")]
    iss = reconstruct_recommendations(recs, policy_year=2025, policy="iss")
    gl = reconstruct_recommendations(recs, policy_year=2025, policy="gl")
    splits = recommendation_splits(iss, gl)
    from collections import Counter
    by_cat = Counter(iss[c].category for c in splits)
    return {"n_proposals": len(iss), "n_splits_default_rules": len(splits),
            "splits_by_category": dict(by_cat),
            "note": ("既定規則のみの分裂 (退職慰労金: GL原則反対 vs ISS原則賛成が主)。"
                     "属性整備後は政策保有10-20%帯・ROE 5-8%帯・女性取締役の対象差で拡大予定")}


def main() -> dict:
    df = pd.read_parquet(OUT_DIR / "panel_long.parquet")
    report = {
        "n_records": int(len(df)),
        "managers": sorted(df.manager.unique().tolist()),
        "period": [df.meeting_date.min(), df.meeting_date.max()],
        "quarterly": quarterly_series(df),
        "route_comparison_pooled_2023on": route_comparison(df[df.meeting_date >= "2023-01-01"]),
        "idg1_splits": idg1_reconstruction_splits(df),
        "filters": {"min_managers": MIN_MANAGERS, "lopsided": LOPSIDED,
                    "note": "仮置き閾値・記述目的 (登録時固定)"},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "panel_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for row in report["quarterly"]:
        if row.get("monoculture_k1") is not None:
            print(f"{row['quarter']}: idx={row['monoculture_k1']:.3f} "
                  f"(mgr={row['managers']} split_cols={row['split_cols']} conv={row['converged']})")
    rc = report["route_comparison_pooled_2023on"]
    print("route A vs B |corr|:", rc["score_correlation_abs"], "shape:", rc["shape"])
    print("ID-g1 splits (default rules):", report["idg1_splits"]["n_splits_default_rules"])
    return report


if __name__ == "__main__":
    main()
