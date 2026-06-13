# 金融マーケットABM　キャッチアップ

金融市場の Agent-Based Modelの主要論文をPython 実装し、
各モデルの理論的主張を数値的に検証する。Cont-Bouchaud (1997) の
パーコレーションモデルから Katahira et al. (2019) の Speculation Game まで、
古典 (1997-2010) から最近の拡張までを系統的にカバーする。
東京大学 SCSLAB (陳研究室) への進学準備の一環として実施。

## 実装リスト

| ID | モデル | 論文 | 状態 |
|----|--------|------|------|
| YH001 | Cont-Bouchaud Percolation | Cont & Bouchaud (1997) | Done (findings 記載済) |
| YH002 | Lux-Marchesi Volatility Clustering | Lux & Marchesi (2000) IJTAF (Param Set I) | Done (findings 記載済) |
| YH003 | Minority Game | Challet & Zhang (1997) | Done (findings 記載済) |
| YH004 | Grand Canonical MG | Jefferies et al. (2001) | Done (findings 記載済) |
| YH005 | Speculation Game Lite | Katahira & Chen (2019) arXiv:1909.03185 (論文2) | Done (findings 記載済) |
| YH005_1 | SG Phase 1: 3 層機構の数値実証 (論文2 Fig. 2/4/7/8/10 再現) | Katahira & Chen (2019) | Done (findings 記載済) |
| YH005_2 | 論文1 Fig 11/12/13 (asymmetry / leverage / gain-loss) — aggregate post-processing | Katahira et al. (2019) Physica A 524 (論文1) | Planned (5-6 月着手目安) |
| YH006 | SG を PAMS-LOB に移植 (2×2 world × wealth, N=100) | Katahira & Chen (2019) + Hirano-Izumi 2023 PAMS | Phase 1 完了 (findings 記載済) |
| YH006_1 | YH006 Phase 2: F1 interaction の機構解明 (wealth 階級別 funnel) | — | S1/S2/S3 完了 (仮説A primary evidence 確定; ablation 保留) |
| YH006_2 | SG on LOB: 論文1+2 完全再現 (LIMIT_ORDER 拡張 + Fig.11/12/13) | Katahira et al. (2019) Physica A 524 | Planned (スコープ検討中) |
| YH007 | Self-organized SG on LOB | Katahira & Chen (Physica A 2021) | Open (詳細記述 別途) |
| YH008 | LLM 活性レベル因果介入 (v_ATH KO/Rescue) | FCLAgent (LLM-as-agent) + 設計 v0.3 | 骨格 (実装は別 GPU セッション) |

**経緯メモ (transparency)**: 旧版表で `YH006 = Speculation Game Full (論文1+2 完全再現)` だった entry を 2026-04 に **`YH006 = LOB 移植` に意味変更**。実装は YH005_1 の 5 figure を PAMS-LOB 上で再現し 2×2 (world × wealth) 比較に拡張する方向 (`experiments/YH006/SPEC.md` §0)。これに伴い、旧 YH006 で予定していた**論文1 Fig 11/12/13 (aggregate post-processing)** は新設 `YH005_2` に retire。

**YH008 注記**: LLM-as-agent への活性レベル因果介入 (mech-interp)。**古典 ABM 再現系列 (YH001-YH007) とは別系譜 (FCLAgent route)。** SG コア系列とも区別される、方法論の新ブランチ。

## ディレクトリ構造

```
experiments/
├── YH001/          Cont-Bouchaud (1997) — 完了
├── YH002/          Lux & Marchesi (2000) Param Set I — 完了
├── YH003/          Challet & Zhang (1997) MG — 完了
├── YH004/          Jefferies et al. (2001) GCMG — 完了
├── YH005/          Katahira-Chen (2019) Speculation Game Lite — 完了 (Null test + 3 モデル比較)
├── YH005_1/        SG Phase 1: 3 層機構の数値実証 — 完了 (論文2 Fig. 2/4/7/8/10)
├── YH005_2/        論文1 Fig 11/12/13 (asymmetry / leverage / gain-loss) — 未着手
├── YH006/          SG on PAMS-LOB (2×2 world × wealth) — Phase 1 完了
├── YH006_1/        YH006 Phase 2: F1 interaction 機構解明 — S1/S2/S3 完了 (ablation 保留)
├── YH006_2/        SG on LOB 論文1+2 完全再現 — 未着手
├── YH007/          Self-organized SG on LOB — 詳細記述 別途
└── YH008/          LLM 活性レベル因果介入 (FCLAgent route) — 骨格 only、実装は別 GPU セッション

docs/
├── literature.md   先行研究整理
├── hypotheses.md   検証したい仮説
└── findings.md     各 YH の確認済み事項 (重複作業防止、新しい YH 着手前に読む)
```

各実験ディレクトリは `model.py` (モデル本体), `run_simulation.py` (実行・可視化),
`README.md` (実験ノート) を含む。

## セットアップ

```bash
pip install -r requirements.txt
cd experiments/YH001
python run_simulation.py
```

## 使用技術

- Python 3.x
- NumPy, SciPy, Matplotlib (全 YH 共通)
- powerlaw (Clauset-Shalizi-Newman テール推定、YH001 で使用)
- **PAMS 0.2.2** ([Hirano & Izumi 2023](https://github.com/masanorihirano/pams), YH006 の tick-scale LOB 環境)

YH006 SPEC §9 で許可されているが現状未 import の package: `pandas`。
networkx は requirements.txt から削除済 (どこにも import されていなかった)。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。
