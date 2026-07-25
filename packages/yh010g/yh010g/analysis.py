"""Task 3: FactorModel ルートA の実データ適用とモノカルチャー指標の初回推定。

実行: uv run python -m yh010g.analysis
出力: data/processed/yh010g/analysis_report.json (行列サイドカーの matrix_id を参照)

注意 (TwinMarket 禁止則): 本モジュールの数値は記述・パイプライン検証目的であり、
論文主張には事前登録した閾値・手続きを経るまで使わない。
lopsided 閾値 (5%)・min_observed (5) は Bubb & Catan 2022 の慣行の仮置き — 登録時に固定。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from agora_engine import DecisionMatrix, fit_pca_em, load_sidecar, monoculture_index
from yh010g.policy import normalize_category, reconstruct_recommendations
from yh010g.schema import UnifiedRecord

OUT_DIR = Path("data/processed/yh010g")

LOPSIDED_MIN_MINORITY = 0.05   # 仮置き (B&C 2022)。感度: 0.03-0.10 を登録時に指定
MIN_OBSERVED = 5               # 8社中5社以上が投票した議案のみ


def classification_stats(dm: DecisionMatrix, fit) -> dict:
    """±1 データの符号分類: CP (正答率) と APRE (少数派誤り削減率)。"""
    X = dm.values
    obs = dm.observed_mask
    recon = fit.reconstruct()
    pred = np.where(recon >= 0, 1.0, -1.0)
    correct = (pred == X) & obs
    cp = float(correct.sum() / obs.sum())
    # APRE: 列ごとの多数決ベースラインの誤り (=少数派数) に対する誤り削減
    minority_total, model_err_total = 0, 0
    for j in range(X.shape[1]):
        col = X[obs[:, j], j]
        if len(col) == 0:
            continue
        n_plus = int((col == 1.0).sum())
        minority = min(n_plus, len(col) - n_plus)
        errs = int((pred[obs[:, j], j] != col).sum())
        minority_total += minority
        model_err_total += errs
    apre = float(1.0 - model_err_total / minority_total) if minority_total else float("nan")
    return {"cp": cp, "apre": apre}


def manager_bootstrap_ci(dm: DecisionMatrix, k: int, n_boot: int = 200, seed: int = 0) -> dict:
    """機関単位ブートストラップ (HANDOFF §6)。N=8 では粗い — 参考値として列版も併記。"""
    rng = np.random.default_rng(seed)
    n = len(dm.row_ids)
    vals_rows, vals_cols = [], []
    for _ in range(n_boot):
        rows = rng.integers(0, n, size=n)
        sub = dm.values[rows, :]
        keep = (~np.isnan(sub)).sum(axis=0) >= 2
        try:
            vals_rows.append(monoculture_index(fit_pca_em(sub[:, keep], k=k, max_iter=60)))
        except ValueError:
            continue
        cols = rng.integers(0, len(dm.col_ids), size=len(dm.col_ids))
        sub_c = dm.values[:, cols]
        keep_c = (~np.isnan(sub_c)).sum(axis=0) >= 2
        vals_cols.append(monoculture_index(fit_pca_em(sub_c[:, keep_c], k=k, max_iter=60)))
    def ci(v):
        v = np.asarray(v)
        return {"mean": float(v.mean()), "p2.5": float(np.percentile(v, 2.5)),
                "p97.5": float(np.percentile(v, 97.5)), "n_boot": len(v)}
    return {"manager_bootstrap": ci(vals_rows), "column_bootstrap": ci(vals_cols)}


def poison_pill_validation(df: pd.DataFrame) -> dict:
    """Task 2 の暫定検証: ISS再構成の against_default (買収防衛策) と各社実投票の一致率。

    属性未整備のため発火するのは既定規則のみ — 「ISSが原則反対とするカテゴリで
    各社がどれだけ反対しているか」の記述統計であり、精度検証の代替ではない
    (本検証セットは著名議案の照合で別途構築する)。
    """
    pp = df[df.category.map(normalize_category) == "poison_pill"]
    out = {}
    for m, g in pp.groupby("manager"):
        out[m] = {"n": int(len(g)), "against_share": float((g.vote == -1.0).mean())}
    return out


def main() -> dict:
    df = pd.read_parquet(OUT_DIR / "pilot_long.parquet")
    side = load_sidecar(OUT_DIR / "pilot_sidecar.json")
    dm_full = DecisionMatrix.from_long(
        list(zip(df.manager, df.col_id, df.vote)))
    dm = dm_full.filter_cols(min_observed=MIN_OBSERVED,
                             min_minority_share=LOPSIDED_MIN_MINORITY)

    report: dict = {
        "matrix_id": side["matrix_id"],
        "filter": {"min_observed": MIN_OBSERVED, "min_minority_share": LOPSIDED_MIN_MINORITY},
        "shape_full": list(dm_full.values.shape),
        "shape_filtered": list(dm.values.shape),
        "k_selection": [],
    }
    for k in (1, 2, 3, 4):
        fit = fit_pca_em(dm, k=k)
        stats = classification_stats(dm, fit)
        report["k_selection"].append({
            "k": k, "converged": fit.converged, "n_iter": fit.n_iter,
            "monoculture_index": monoculture_index(fit), **stats,
        })

    # 主指標は k=1 と k=2 を併記 (N=8 では k>=3 は過学習リスク大)
    report["bootstrap_k1"] = manager_bootstrap_ci(dm, k=1)
    report["bootstrap_k2"] = manager_bootstrap_ci(dm, k=2)

    # Task 2 暫定検証 + カバレッジ
    records = [UnifiedRecord(**{f: row[f] for f in UnifiedRecord.__dataclass_fields__})
               for row in df.to_dict("records")]
    recs_2025 = reconstruct_recommendations(
        [r for r in records if r.meeting_date >= "2025-02-01"], policy_year=2025)
    from yh010g.policy.engine import coverage_report
    report["iss_reconstruction_2025"] = coverage_report(recs_2025)
    report["poison_pill_validation"] = poison_pill_validation(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
