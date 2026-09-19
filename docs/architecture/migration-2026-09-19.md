# 2026-09-19 配置の移行

研究内容の変更ではなく、ファイルの所有範囲を揃える変更。旧アーカイブと保存済み証拠の内容は維持する。
`unwind-tape`のみ外部定期実行への互換リンクを残す。既存Python import名`yh010g`は変わらない。
ローカルのGit管理外データは本変更では移動できないため、各実験READMEの移行手順に従う。

| 旧パス | 新パス |
|---|---|
| `unwind-tape` | `experiments/YH009` |
| `packages/yh010g` | `experiments/YH010g` |
| `experiments/speculation_game` | `experiments/YH005` |
| `tests/test_yh007_1_aggregate.py` | `experiments/YH007/tests/test_yh007_1_aggregate.py` |
| `tests/test_yh007_2_lob.py` | `experiments/YH007/tests/test_yh007_2_lob.py` |
| `tests/test_yh007_3_adaptive.py` | `experiments/YH007/tests/test_yh007_3_adaptive.py` |
| `tests/test_yh007_4_execution.py` | `experiments/YH007/tests/test_yh007_4_execution.py` |
| `tests/test_yh007_6_7_predator_spoofer.py` | `experiments/YH007/tests/test_yh007_6_7_predator_spoofer.py` |
| `tests/test_yh007_8_calibration_values.py` | `experiments/YH007/tests/test_yh007_8_calibration_values.py` |
| `tests/test_yh007_8_p0.py` | `experiments/YH007/tests/test_yh007_8_p0.py` |
| `tests/test_yh007_8_p2_kronosci.py` | `experiments/YH007/tests/test_yh007_8_p2_kronosci.py` |
| `tests/test_yh007_8_p3_zi_matched_ar1.py` | `experiments/YH007/tests/test_yh007_8_p3_zi_matched_ar1.py` |
| `tests/test_yh007_8_p3d_shared_ar1.py` | `experiments/YH007/tests/test_yh007_8_p3d_shared_ar1.py` |
| `tests/yh007_concept.txt` | `experiments/YH007/docs/concept.txt` |
| `tests/yh008_concept.txt` | `experiments/YH008/docs/concept.txt` |
| `docs/backbone_parity.md` | `experiments/YH005/docs/backbone_parity.md` |
| `docs/2026-07-18-agent-agora-literature-survey.md` | `experiments/YH010/docs/2026-07-18-agent-agora-literature-survey.md` |
| `docs/2026-07-19-YH010-handoff-review.md` | `experiments/YH010/docs/2026-07-19-YH010-handoff-review.md` |
| `docs/2026-07-19-YH010-prereg-plan.md` | `experiments/YH010/docs/2026-07-19-YH010-prereg-plan.md` |
| `docs/2026-07-23-YH010g-disclosure-inventory.md` | `experiments/YH010g/docs/2026-07-23-YH010g-disclosure-inventory.md` |
| `docs/2026-07-23-YH010g-method-notes-bolton-bubbcatan.md` | `experiments/YH010g/docs/2026-07-23-YH010g-method-notes-bolton-bubbcatan.md` |
| `docs/2026-07-23-YH010g-prior-art.md` | `experiments/YH010g/docs/2026-07-23-YH010g-prior-art.md` |
| `docs/2026-07-23-YH010g-share-and-novelty-survey.md` | `experiments/YH010g/docs/2026-07-23-YH010g-share-and-novelty-survey.md` |
| `docs/2026-07-23-YH010g-task01-report.md` | `experiments/YH010g/docs/2026-07-23-YH010g-task01-report.md` |
| `docs/2026-07-23-YH010g-task23-report.md` | `experiments/YH010g/docs/2026-07-23-YH010g-task23-report.md` |
| `docs/2026-07-23-YH010g-task4-report.md` | `experiments/YH010g/docs/2026-07-23-YH010g-task4-report.md` |
| `docs/2026-07-24-YH010g-batch-report.md` | `experiments/YH010g/docs/2026-07-24-YH010g-batch-report.md` |
| `docs/2026-07-24-YH010g-task6-edinet.md` | `experiments/YH010g/docs/2026-07-24-YH010g-task6-edinet.md` |
| `docs/2026-07-24-YH010g-validation-set.md` | `experiments/YH010g/docs/2026-07-24-YH010g-validation-set.md` |
| `docs/yh010g_validation_groundtruth.csv` | `experiments/YH010g/data/fixtures/validation_groundtruth.csv` |
| `docs/audit/P0_control_oldvalues_yh007_8_p3d.json` | `experiments/YH007/reports/audit/P0_control_oldvalues_yh007_8_p3d.json` |
| `docs/audit/P0_numeric_literal_diff.md` | `experiments/YH007/docs/audit/P0_numeric_literal_diff.md` |
| `docs/audit/P0_rerun_yh007_8_p3d.json` | `experiments/YH007/reports/audit/P0_rerun_yh007_8_p3d.json` |
| `docs/audit/P0_yh007_parameter_provenance.md` | `experiments/YH007/docs/audit/P0_yh007_parameter_provenance.md` |
| `docs/audit/P0_yh007_recalibration_rerun.md` | `experiments/YH007/docs/audit/P0_yh007_recalibration_rerun.md` |
| `docs/2026-07-02-branch-audit-fingerprint-atlas.md` | `experiments/fingerprint_atlas/docs/2026-07-02-branch-audit-fingerprint-atlas.md` |
| `docs/2026-07-02-branch-findings-full.json` | `experiments/fingerprint_atlas/reports/audit/2026-07-02-branch-findings-full.json` |
| `docs/canon_atlas_next_actions.md` | `experiments/fingerprint_atlas/docs/canon_atlas_next_actions.md` |
| `specs/001-monorepo-consolidation.md` | `docs/architecture/001-monorepo-consolidation.md` |
| `specs/YH010_HANDOFF.md` | `experiments/YH010/specs/HANDOFF.md` |
| `specs/YH010g_HANDOFF.md` | `experiments/YH010g/specs/HANDOFF.md` |
| `notebooks/atlas_v1` | `experiments/fingerprint_atlas/reports/atlas_v1` |
| `notebooks/atlas_v2` | `experiments/fingerprint_atlas/reports/atlas_v2` |
| `notebooks/atlas_v3` | `experiments/fingerprint_atlas/reports/atlas_v3` |
| `notebooks/atlas_v3_periods` | `experiments/fingerprint_atlas/reports/atlas_v3_periods` |
| `notebooks/atlas_v4` | `experiments/fingerprint_atlas/reports/atlas_v4` |
| `lm_tree.html` | `experiments/fingerprint_atlas/reports/genealogy/lm_tree.html` |
| `mg_tree.html` | `experiments/fingerprint_atlas/reports/genealogy/mg_tree.html` |
| `notebooks/inverse_abm_heatmap.png` | `experiments/fingerprint_atlas/reports/inverse_abm_heatmap.png` |
| `notebooks/propose_analytics` | `experiments/fingerprint_atlas/reports/propose_analytics` |

古典4モデルの`experiments/classical/baseline.py`はYH001–004の個別入口へ分割し、旧ファイルは互換集約入口にした。
空の`configs/experiment_example.yaml`と空の`notebooks/00_sanity_check.jpynb`は未実装scaffoldとして除去した。
root `specs/` のYH007向け旧案内スタブは、実際のYH007/specsへのリンクを更新して除去した。
変更前のポインタREADMEや旧配置はGit履歴に残る。
