"""agora_engine — YH010 (価格空間) / YH010-g (ガバナンス空間) 共有エンジン。

正本仕様: specs/YH010_HANDOFF.md §7。
  1. DecisionMatrix: 主体 i × インスタンス j × 行動 a_ij (欠測マスク付き)
  2. FactorModel: a_ij = mu_j + sum_k lambda_ik f_jk + eps_ij (ルートA: EM補完低ランク分解)
  3. Intervention: 宣言的介入 (テープに必ず記録)
  4. テープ/サイドカー JSON 規約
モノカルチャー指標の定義は monoculture.py の一箇所のみ。
"""

from agora_engine.decision_matrix import DecisionMatrix
from agora_engine.factor_model import FactorFit, fit_pca_em
from agora_engine.intervention import Intervention
from agora_engine.monoculture import monoculture_index
from agora_engine.tape import (
    build_matrix_sidecar, git_sha, load_sidecar, sha256_file, utcnow_iso, write_sidecar,
)

__all__ = [
    "DecisionMatrix",
    "FactorFit",
    "fit_pca_em",
    "Intervention",
    "monoculture_index",
    "build_matrix_sidecar",
    "git_sha",
    "load_sidecar",
    "sha256_file",
    "utcnow_iso",
    "write_sidecar",
]
