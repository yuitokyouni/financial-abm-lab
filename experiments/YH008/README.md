# YH008 — LLM-as-Agent への活性介入 (mech-interp)

**現在地 (2026-05-29)**: P0.5 完了、判定 = `PASS_STAGE2_LOSS_CONDITIONAL_CONFIRMED`
(Stage 2 着手許可)。**次 = Stage 2 (loss-conditional v_ATH 同定) を GPU セッションで実行**。
A100 環境 (RunPod 想定) の再確保と HF gated token (meta-llama) の再投入が必要で、
本リポの CPU 環境では走らない。

## 一次資料の所在

設計・ブリーフ・実行結果は現状すべてアーカイブ側にある:

```
imported/speculation-game-info/experiments/YH008/
├── design_v0.3.pdf                      # 設計根拠
├── stage13_implementation_brief.md      # Stage 1-3 実装ブリーフ
├── addendum_v0.3.2.md                   # 正本 addendum (ブリーフ §7・§8 を置換)
├── stage2_implementation_brief.md       # ★次の GPU セッションへのタスク指示書
├── src/                                 # render / model / states / metrics / run_*
└── outputs/20260529-*_P0{,_5}/          # v1 → P0 → P0.5 の REPORT
```

Stage 2 実行時は **stage2 ブリーフ + design v0.3 + addendum v0.3.2 + P0/P0.5 REPORT を
セットで**実装セッションに渡すこと (詳細は同ディレクトリ README)。

## 本ディレクトリの役割

YH0xx 再編 (2026-07-23) に伴う**継続作業の受け口**。Stage 2 以降の新規成果物
(方向テンソル・config・レポート) はアーカイブ側ではなくここに置く。
