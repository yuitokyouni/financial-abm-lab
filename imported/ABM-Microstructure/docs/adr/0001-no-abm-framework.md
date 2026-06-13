# ADR 0001 — ABM フレームワークを使わず purpose-built エンジンで実装する

**Status**: Accepted (2026-06-02)

## Context
実験A harness の唯一の価値は「sim 出力が解析アンカー（GM break-even / Kyle λ / Budish rent / uniform-price clearing）に合致することの監査可能な証明」（原則I・auditability）。Mesa / ABIDES 等の ABM フレームワークを使う選択肢がある。

## Decision
ABM フレームワークを使わず、numpy だけの purpose-built な離散時間エンジン（`src/microstructure/`、数百行）で実装する。

## Consequences
- 良い面: sim の各行が解析アンカーのどの項に対応するかを追える＝差分（バグ vs 離散化誤差）の切り分けが容易。検証の独立性（`anchors.py` が engine を import しない）を構造で担保できる。依存が numpy のみで再現性が高い。
- 悪い面: scheduler / agent 抽象を自前で持つ。将来エージェント種が増えると再実装コスト。
- 後で効く制約: 実験B で grid が重くなったら hot path（engine ループ）だけ Rust/numba 等へ移植を検討（下流）。フレームワークへの移行は検証の独立性を壊すので避ける。

## Alternatives considered
- **Mesa**: 教育向けで scheduler が不透明。連続/uniform-price batch の厳密な clearing を書くのに不向き。却下。
- **ABIDES**: LOB は本格的だがセットアップ・実行・監査コストが A の規模に過剰。閉形式照合の差分追跡が難しい。却下（B で本格 LOB が要るなら再検討）。
