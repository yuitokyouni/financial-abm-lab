# ADR 0001 — 正準 SG は YH005 実装とする (PRISM/PROV-ABM の "SG" は別モデル)

- Status: Accepted
- Date: 2026-06-13
- Context: spec 001 Stage B / T0 backbone

## 背景

統合前、SG (Speculation Game) は3リポで「三重実装」されていると認識していた:
speculation-game-info (YH005)、PRISM (`adapters/sg.py`)、PROV-ABM-atlas (`toy/models/sg.py`)。

core 抽出に先立ち3実装を精査した結果、**これらは同一モデルの3実装ではなかった**:

- **speculation-game-info / YH005** = 本物の Speculation Game (Katahira-Chen 2019)。
  5進履歴 lookup (μ ∈ [0, 5^M))、認知閾値 C による量子化 h∈{-2..+2}、認知価格 P、
  K=5^M 戦略表、round-trip wealth、Δp = D/N。論文忠実で findings 検証済み (Hill α=4.53 等)。
- **PRISM / PROV-ABM-atlas の "sg.py"** = fundamentalist/chartist/noise demand +
  softmax(β·perf) による戦略 weight の連続切替。実体は Franke-Westerhoff / Brock-Hommes 系の
  別モデルで、"SG" は名称の誤用。**PRISM 版と PROV-ABM 版は互いに byte 同一** (import パスのみ差)。

## 決定

`packages/abm_models/sg/` の**正準 SG = YH005 実装** (論文忠実、findings に provenance あり、
Yuito の研究対象そのもの) とする。reference (per-agent) と vectorized (bit-parity) の2 backend を持つ。

PRISM/PROV-ABM の "SG" は正準 SG に**畳まない**。intervention_atlas 系 experiment を移行する際は:
- 正準 SG を使うか、
- 当該モデルを正しい名前 (FW 系の簡易代用) で別途扱う。
`architecture` フラグで両者を1クラスに混ぜる案は **却下** (異なるモデルの Frankenstein 化は
parity を濁らせ、機構弁別という研究目的に反する)。

## 帰結

- spec 001 の「SG 三重実装の統一」は「**本物 SG 1つを正準化 + 別モデル2つの誤名を是正**」に
  正確化される。
- T0 backbone は本物 SG で実施し、parity を達成 (`docs/backbone_parity.md`)。
- PRISM/PROV-ABM の FW系モデルの扱いは intervention_atlas 移行時に別途決める (本 ADR の射程外)。
