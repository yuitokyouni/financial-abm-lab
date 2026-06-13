# Implementation Plan: 実験A — CLOB 抽出検証 harness

**Branch**: `001-exp-a-clob-harness`（main 上で作業）| **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-exp-a-clob-harness/spec.md`

## Summary

外生 GBM 価格の下で CLOB/quoting-MM・反応的 arbitrageur・noise trader を回す**離散時間 simulator** を建て、その出力（competitive spread・抽出量）を **sim とは独立に実装した解析アンカー**（Glosten-Milgrom break-even / Budish sniping レント）に対し、任意パラメータで許容誤差内に一致させる。一致が成果物＝実験Bを信じる license（原則I・SC-005 gate）。連続 vs N期 uniform-price batch の抽出量差も定量化する。実装は ABM フレームワークを使わず、監査可能な小さい純 Python エンジンで行う。

## Technical Context

**Language/Version**: Python 3.13（環境既存。`uv`/`pip` 管理）

**Primary Dependencies**: numpy（数値・seeded RNG）、pytest（検証＝本 feature の成果物）。scipy は GM の正規分布計算で必要なら限定使用（まず `math.erf` で代替可）。matplotlib は σ-sweep 図のみ任意。**ABM フレームワーク（Mesa/ABIDES 等）は使わない**（→ research.md ADR）。

**Storage**: なし。run 結果は in-memory → 任意で CSV/JSON に dump（`scripts/run_sweep.py`）。

**Testing**: pytest。検証テストが US1 の deliverable そのもの。`numpy` の `default_rng(seed)` で決定論。

**Target Platform**: ローカル（Windows/Linux、CLI）。GUI なし。

**Project Type**: single project（research simulation library + 検証テスト + sweep スクリプト）。

**Performance Goals**: 単一 run（10^5〜10^6 period）が数秒。検証 suite（≥8 パラメータ点 × 複数 seed）が数分でローカル完走。**この per-run/per-cell の実測が B1（compute 予算）の入力を生む**（A を建てる＝B の grid を見積もる材料を作る）。

**Constraints**: 監査可能性最優先（constitution: auditability/reproducibility）。アンカーは sim と**コード共有しない**。全乱数は単一 seeded Generator 由来（FR-011）。

**Scale/Scope**: 数百〜千行規模（research-design §6）。エージェント種3、機構2、指標4、アンカー2。

## Constitution Check

*GATE: Phase 0 前に通すこと。Phase 1 後に再評価。*

- **I 検証先行（NON-NEGOTIABLE）**: plan の中心が `anchors.py`＋pytest 照合。B（学習/collusion）は Out of Scope。SC-005 が gate。→ **PASS**
- **II 二失敗モードは別物**: 本 feature は A のみ（非学習）。→ **PASS**
- **III 地図/null 先取り禁止**: A は findings を出さない（検証と定量化のみ）。→ **PASS（該当なし）**
- **IV single run is nothing**: 決定論 + 複数 seed + 許容誤差判定。検証は単一 run に依存しない。collusion 認定は本 feature に無い。→ **PASS**
- **V スコープ正直**: 外生 GBM、内部整合（解析モデル相手）のみ、実在銘柄アンカー不要を spec に明記。→ **PASS**
- **knot（A1+C4+C5）**: competitive spread の唯一定義 = arbitrageur 逆選択への GM break-even（`metrics.competitive_spread` と `anchors.gm_break_even` が同一概念の sim 側/解析側）。逆選択源 = arbitrageur。→ **PASS**

違反なし → Complexity Tracking は空。「ABM フレームワーク不使用」は simplicity 方向の選択（違反ではない、ADR で根拠を残す）。

## Project Structure

### Documentation (this feature)

```text
specs/001-exp-a-clob-harness/
├── plan.md              # 本ファイル
├── research.md          # Phase 0: 技術判断（言語/no-framework ADR/arb latency モデル/GM・Budish の具体形/許容誤差）
├── data-model.md        # Phase 1: エンティティ→具体 dataclass/フィールド
├── quickstart.md        # Phase 1: 検証と sweep の走らせ方
├── contracts/
│   └── sim-interface.md # Phase 1: SimConfig/RunResult/MarketMechanism protocol/anchors API
└── tasks.md             # Phase 2（/speckit-tasks で生成・本コマンドでは作らない）
```

### Source Code (repository root)

```text
src/microstructure/
├── __init__.py
├── config.py        # SimConfig（params, seed, tolerances）dataclass
├── price.py         # GBM(+jump) 外生 true price。取引から独立
├── book.py          # limit order book（価格優先・時間優先）
├── agents.py        # MarketMaker(規則, inventory-free) / Arbitrageur(反応, 学習なし) / NoiseTrader
├── mechanisms.py    # MarketMechanism protocol → ContinuousMatching / BatchAuction(N)
├── engine.py        # 離散時間ループ: price→agents→mechanism→metrics を毎期 wiring
├── metrics.py       # extraction / effective_spread / mm_net_pnl / competitive_spread(GM)
└── anchors.py       # gm_break_even / budish_sniping_rent（sim と独立実装）

tests/
├── test_anchors_match.py        # SC-001/002: sim vs 閉形式（≥8 パラメータ点, 複数 seed）
├── test_continuous_vs_batch.py  # SC-003: batch < continuous, σ で単調
├── test_determinism.py          # SC-004: 同一 seed→同一出力
└── test_incentive.py            # US3: MM 純 PnL の符号

scripts/
└── run_sweep.py     # σ/fee/N sweep を回し結果（+ per-run timing）を出力
```

**Structure Decision**: single project。package = `src/microstructure`（`scripts/generate_diagrams.sh` の `ABM_PKG=src/microstructure` に接続 → commit ごとに構造図再生成）。`anchors.py` を engine/metrics から import 上独立に保ち、検証の真値が sim ロジックを共有しないことを構造で担保する。

## Complexity Tracking

> Constitution Check に違反なし。記載不要。
