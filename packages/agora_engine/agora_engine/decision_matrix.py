"""DecisionMatrix — 主体 i × インスタンス j の意思決定行列 (YH010_HANDOFF §7-1)。

値は float 行列で保持し、NA (非保有・非観測) は np.nan。
YH010-g のエンコーディング既定: 賛成 +1 / 反対 -1 / 棄権系 0 / 非保有 NaN。
棄権 0 の実データ上の値域確定は Task 1 の残課題 (HANDOFF §10) — 本クラスは値に非依存。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DEFAULT_ENCODING = {"for": 1, "against": -1, "abstain_or_other": 0, "not_held": "NA"}


@dataclass
class DecisionMatrix:
    values: np.ndarray  # (N, P) float, NaN = 非観測
    row_ids: list[str]  # 主体 (運用機関 / エージェント)
    col_ids: list[str]  # インスタンス (議案 / 価格設定機会)
    encoding: dict = field(default_factory=lambda: dict(DEFAULT_ENCODING))

    def __post_init__(self) -> None:
        self.values = np.asarray(self.values, dtype=float)
        if self.values.shape != (len(self.row_ids), len(self.col_ids)):
            raise ValueError(
                f"shape mismatch: values {self.values.shape} vs "
                f"({len(self.row_ids)}, {len(self.col_ids)})"
            )
        if len(set(self.row_ids)) != len(self.row_ids):
            raise ValueError("duplicate row_ids")
        if len(set(self.col_ids)) != len(self.col_ids):
            raise ValueError("duplicate col_ids")

    @property
    def observed_mask(self) -> np.ndarray:
        return ~np.isnan(self.values)

    def coverage(self) -> dict:
        """サイドカー JSON の coverage ブロック用の要約。"""
        obs = self.observed_mask
        return {
            "rows": len(self.row_ids),
            "cols": len(self.col_ids),
            "cells_observed": int(obs.sum()),
            "cells_na": int((~obs).sum()),
        }

    @classmethod
    def from_long(
        cls,
        records: list[tuple[str, str, float]],
        encoding: dict | None = None,
    ) -> "DecisionMatrix":
        """(row_id, col_id, value) の長形式から構築する。

        同一 (row, col) の重複は、値が一致すれば黙って一意化し、
        矛盾していれば ValueError (上流のパーサ/名寄せの欠陥をここで顕在化させる)。
        """
        seen: dict[tuple[str, str], float] = {}
        for r, c, v in records:
            key = (r, c)
            if key in seen and not (np.isnan(seen[key]) and np.isnan(v)) and seen[key] != v:
                raise ValueError(f"conflicting duplicate cell {key}: {seen[key]} vs {v}")
            seen[key] = v
        row_ids = sorted({r for r, _, _ in records})
        col_ids = sorted({c for _, c, _ in records})
        ri = {r: i for i, r in enumerate(row_ids)}
        ci = {c: j for j, c in enumerate(col_ids)}
        values = np.full((len(row_ids), len(col_ids)), np.nan)
        for (r, c), v in seen.items():
            values[ri[r], ci[c]] = v
        return cls(values=values, row_ids=row_ids, col_ids=col_ids,
                   encoding=encoding or dict(DEFAULT_ENCODING))

    def to_long(self) -> list[tuple[str, str, float]]:
        out = []
        obs = self.observed_mask
        for i, r in enumerate(self.row_ids):
            for j, c in enumerate(self.col_ids):
                if obs[i, j]:
                    out.append((r, c, float(self.values[i, j])))
        return out

    def filter_cols(self, min_observed: int = 1, min_minority_share: float = 0.0) -> "DecisionMatrix":
        """列フィルタ (lopsided 議案の除去など。Bubb & Catan 2022 / Bolton et al. 2020 の慣行)。

        min_minority_share: 観測票のうち少数派の割合がこの値未満の列を落とす
        (全会一致列は相対選好の情報を持たない)。閾値は登録文書で固定し感度分析すること。
        """
        keep = []
        for j in range(len(self.col_ids)):
            col = self.values[:, j]
            obs = col[~np.isnan(col)]
            if len(obs) < min_observed:
                continue
            if min_minority_share > 0.0 and len(obs) > 0:
                # +1/-1 コーディング前提の少数派割合。他の値域では votes の一致で計算
                _, counts = np.unique(obs, return_counts=True)
                minority = 1.0 - counts.max() / counts.sum()
                if minority < min_minority_share:
                    continue
            keep.append(j)
        return DecisionMatrix(
            values=self.values[:, keep],
            row_ids=list(self.row_ids),
            col_ids=[self.col_ids[j] for j in keep],
            encoding=dict(self.encoding),
        )
