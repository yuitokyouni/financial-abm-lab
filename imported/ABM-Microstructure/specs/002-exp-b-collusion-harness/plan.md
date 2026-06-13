# Implementation Plan: 実験B — 学習 MM collusion harness

**Branch**: `002-exp-b-collusion-harness`（main 上で作業）| **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-exp-b-collusion-harness/spec.md`

## Summary

検証済み実験A harness（001）の上に、**逐次決定の学習ループ**を新設する。市場世界（外生 jump 価格・1期/1バッチ staleness・arbitrageur 1体・noise flow・会計規約）は 001 と同一に保ち、quoting MM だけを tabular Q-learning 集団（n≥2）に差し替える。各条件 {連続, batch×N} × {committed, revisable} で (i) markup を**機構別 myopic-Nash 分母**（001 anchors の流量計算から解析導出）で測り、(ii) **impulse-response gate**（それ自体を合成 policy で検証する）を通過した点のみ collusion と認定し、(iii) (抽出, markup) の設計マップを tiered grid＋事前固定 compute 予算（3×10⁹ 学習期）で作る。二力（Green-Porter vs predation）の帰属は revisable-quote ablation（sniping 消失）で識別する。

## Technical Context

**Language/Version**: Python 3.13（001 と同一。`uv` 管理）

**Primary Dependencies**: numpy・pytest のみ（**RL ライブラリ不使用**——tabular Q/SARSA は自前 ~100 行。状態数 |A|^(n·m) ≤ 数万で表形式が成立し、監査可能性が deep-RL 系より高い）。matplotlib は地図描画 script のみ任意。

**Storage**: run 結果は in-memory → `scripts/run_design_map.py` が CSV/JSON dump（DesignMapPoint 単位）。予算消費 log を同梱。

**Testing**: pytest。**gate（impulse-response 分類器）自体をテストする**のが本 feature の検証の中心：合成 policy（手書き grim-trigger = PASS すべき／固定高止まり = FAIL すべき）で分類器の検出力を学習コードと独立に固定する（001 の「anchor は sim と独立」の B 版）。

**Target Platform**: ローカル（Windows/Linux、CLI）。並列は seed/セル単位の process 並列（任意）。

**Project Type**: single project（001 package への追加モジュール群）。

**Performance Goals**: 学習 1 期 ≈ 5μs 級（保守見積り）。1 run（≤2×10⁶ 学習期）≈ 10 秒。coarse grid 480 runs ≈ 1.3 h serial。**総予算 3×10⁹ 学習期**（runner が enforce、research D-B9）。

**Constraints**: 001 の検証済み vectorized engine は**変更しない**（license を churn しない）。学習ループは新設の逐次 env が担い、共有するのは config 語彙・会計規約・anchors の流量数学のみ。benchmarks（markup 分母）は env/qlearn を import しない（独立性の構造担保、001 の anchors 規律と同型）。

**Scale/Scope**: 追加 ~600–900 行（env/qlearn/benchmarks/verdict/designmap + tests）。

## Constitution Check

*GATE: Phase 0 前に通すこと。Phase 1 後に再評価。*

- **I 検証先行（NON-NEGOTIABLE）**: 前提の license は成立済み（001 anchor battery 緑＋finding 0001 ③ Kyle λ 独立化閉鎖）。① diffusion σ>0 は gate を塞がない（finding 0001 で確認済み・並走）。B 固有の検証は「gate 分類器の合成 policy テスト」「benchmarks の解析独立」「縮退 sanity」で 001 と同じ規律を貫く。→ **PASS**
- **II 二失敗モードは別物**: B でも arbitrageur は 1体・反応的のまま（gross 抽出極限）。抽出と markup は同一 B 世界の別指標として測る（C5）。→ **PASS**
- **III 地図/null 先取り禁止**: outcome space = {促進/抑制/無影響} ＋「創発せず」。SC-001 に null 経路明記。prior の confirmation risk は predation チャネル（本物の対抗力）と tight gate で再均衡済み。→ **PASS**
- **IV single run is nothing**: 認定 gate（impulse-response）通過点のみ collusion、下流（memory 閾値）は通過点のみ。≥2 アルゴリズム（Q-learning + SARSA）× ≥5 seed/セル × tiered grid。収束は経験的安定（W=10⁵ 期 policy 不変）で機械判定、非収束セルはラベルで区別。→ **PASS**
- **V スコープ正直**: 外生価格＝価格発見 scope 外。**inelastic noise 下では collusive ceiling = action grid 上限**という構造的限界を明示し（research D-B11）、需要弾力性 R を robustness 軸として用意。④ 外部アンカーの venue 選定は research D-B10 で確定。→ **PASS**
- **knot（A1+C4+C5）**: markup 分母 = **その機構の** stage game の同一 n myopic-Nash（離散 grid 上で解析計算。grid 細分の極限で GM break-even h\* に一致＝001 anchor に接続）。逆選択源 = 同一の arbitrageur。地図は両軸 B 世界。→ **PASS**

違反なし → Complexity Tracking は空。

## Project Structure

### Documentation (this feature)

```text
specs/002-exp-b-collusion-harness/
├── plan.md                   # 本ファイル
├── research.md               # Phase 0: 学習設定/期構造/分母計算/gate 数値/予算 B1/④ 選定
├── data-model.md             # Phase 1: LearnConfig/MarketEnv/CollusionVerdict/DesignMapPoint
├── quickstart.md             # Phase 1: 単一セル→gate→coarse map の走らせ方
├── contracts/
│   └── learning-interface.md # Phase 1: train/measure/impulse_response/benchmarks API
└── tasks.md                  # Phase 2（/speckit-tasks で生成・本コマンドでは作らない）
```

### Source Code (repository root)

```text
src/microstructure/
├── （001 既存: config/book/agents/engine/metrics/anchors — 変更しない）
├── learnconfig.py   # LearnConfig: 市場 primitives + 機構/staleness + 学習ハイパー + grid + 予算
├── env.py           # MarketEnv: 学習期構造（observe→quote→clear→reward）、committed/revisable、tie-split
├── qlearn.py        # QLearner / SARSA / ZIPolicy / FixedPolicy（表形式・ε-greedy 減衰・決定論 RNG spawn）
├── benchmarks.py    # myopic_nash_spread / monopoly_grid / zi_floor（解析。anchors のみ import）
├── verdict.py       # 収束判定・impulse-response protocol・markup 統計 → CollusionVerdict
└── designmap.py     # DesignMapPoint 集計・CSV/JSON 出力・予算カウンタ

tests/
├── （001 既存 6 ファイル — 変更しない）
├── test_benchmarks.py     # Nash→GM h* 収束（grid 細分）/ monopoly=grid 上限 / ZI 解析=実測
├── test_env_mechanics.py  # revisable⇒抽出≡0 / tie-split / staleness 順序 / batch 期構造 / 決定論
├── test_verdict_gate.py   # 合成 policy: grim-trigger=PASS / 固定高止まり=FAIL / 探索ノイズ非誤検出
└── test_qlearn_sanity.py  # n=1→上限方向 / memory=0→Nash 近傍 / floor 単調性（ZI≤Nash≤実現）

scripts/
└── run_design_map.py      # tiered grid runner（予算 enforcement・地図出力・timing log）
```

**Structure Decision**: 001 の vectorized engine と B の逐次 env を**並置**し、コードパスを分ける（検証済み資産を凍結）。会計規約（抽出 = arb PnL = MM 犠牲、fee、退出系）と価格過程パラメータは LearnConfig が SimConfig と同じ語彙で持ち、対応を test で pin。`benchmarks.py` は `anchors.py` と同様に env/qlearn から import 独立——markup 分母が学習コードのバグを共有しない構造。

## Complexity Tracking

> Constitution Check に違反なし。記載不要。
