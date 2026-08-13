# YH007 — Kronos × microstructure: リアル LOB 上の SF 生成機構同定

**現在地 (2026-08-13)**: spec 003 round6 完結後、P0 監査 (docs/audit/) の是正で
φ/σ 較正を修正値 0.615/3.81e-3 に統一。**P3-F は旧較正下の条件付き合格**
(kronos recenter ret_acf[1] = −0.020±0.03 は較正非依存だが、agg parity 判定が
旧較正参照 0.102 に対するもの。修正較正の参照は 0.072)。**P4 (headline run) の
held は継続** — 解除の前提は修正較正での P3-F 再走 (docs/audit/BACKLOG.md)。
その先の P5 (機構 ablation 再走) は 003 の scope 外 (002 §11 へ差し戻し)。

## 位置付け

Kronos (K 線基盤モデル) を意思決定則に据えた異種エージェント群を、自己組織化した
連続ダブルオークション板の上で競争させ、stylized facts が何の機構から生まれるかを
ablation で同定する系列。**ground truth は `specs/002`**。

- **旧 YH007 (自己組織化 Speculation Game = Katahira & Chen 2021 の C 内生化) は
  `imported/speculation-game-info/experiments/YH006_3/` に改称・凍結済み** (2026-07-02)。
  以後 YH007 は本系列を一意に指す。
- SG 系譜 (YH005/006) の往復取引・認知価格会計・凍結病理は捨て、MG 族の
  「競争による内生的 SF 創発」だけを残す方針転換 (002 §1)。

## このディレクトリの構成

```
YH007/
├── README.md          # 本ファイル (現在地インデックス)
├── specs/
│   ├── 002-yh007-kronos-microstructure.md   # 方針転換 spec (ground truth)
│   └── 003-yh007-8-self-organized-book.md   # YH007-8 自己組織化板サブ spec (P0-P4)
└── scripts/           # 実験スクリプト (yh007_1〜yh007_8_*)
    ├── yh007_1_aggregate.py 〜 yh007_6_7_amplifier_ablation.py   # naïve 系列 (002、結論撤回済)
    ├── yh007_8_p1_calibration.py 〜 yh007_8_p3f_recenter.py      # YH007-8 (003、P1〜P3-F)
    └── yh007_kronos_smoke.py / yh007_midprice_diagnostic.py      # 診断・疎通
```

実行例は各スクリプト冒頭 docstring (`uv run python -m experiments.YH007.scripts.yh007_...`)。

## コア実装の所在 (このディレクトリには置かない)

再利用可能なモデル実装は spec 001 の規約どおり `packages/abm_models/` 側:

- `packages/abm_models/abm_models/kronos_aggregate/` — YH007-1 (板無し即時 clearing)
- `packages/abm_models/abm_models/kronos_lob/` — naïve LOB 系列 (002 YH007-2〜7)
- `packages/abm_models/abm_models/self_organized_book/` — YH007-8 自己組織化板 (003)

## 経緯の要点 (詳細は specs/ の改訂履歴)

1. naïve 設計 (002 YH007-2〜7) の機構 ablation は **2 つの測定 artifact**
   (market 価格 = bid-ask bounce / mid = 量子化ジャンプ) により**全結論撤回** (002 §8.x)。
2. YH007-8 (003): 全 agent LIMIT 化 + 流動性内生化で artifact を構造的に消去する
   substrate を構築。P1 (mock) で bounce/量子化解消 → P2 (実 Kronos) で bounce 再来
   (−0.413) → P3 FAIL 裁定「Kronos 戦略構造由来」 → P3-D/E (SharedAR1Hub、hub_scope)
   で二重乖離確定 → **P3-F (recenter) 合格 = substrate 完成** (2026-07-21)。
3. P3 FAIL は「同一基盤モデル共有 → directional 同期 → 集合 over-reaction」という
   **候補 finding として保存** (003 §12 round4 裁定、破棄しない)。
