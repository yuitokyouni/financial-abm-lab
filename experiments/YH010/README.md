# YH010 — agent-agora（協調 vs モノカルチャーの観測的識別）

**仕様の一次情報は [`specs/YH010_HANDOFF.md`](../../specs/YH010_HANDOFF.md)。**
姉妹翼 YH010-g（議決権行使ガバナンス）は [`specs/YH010g_HANDOFF.md`](../../specs/YH010g_HANDOFF.md)。

実装パッケージ:

- `packages/agora_engine/` … 共有エンジン（意思決定行列・因子モデル・介入テープ）
- `packages/yh010g/` … YH010-g パイロット（policy 再構成・総会 sim・EDINET 属性）

プレレジ草案・調査ノートは `docs/2026-07-19-YH010-*.md` / `docs/2026-07-23-YH010g-*.md` /
`docs/2026-07-24-YH010g-*.md`。

**現在地 (2026-07-24 merge)**: PR #15 で文献調査のみ main に入っていた状態から、
`claude/agent-agora-research-330ilj` 上の YH010 プレレジ/HANDOFF と YH010-g Task 0–6
（パイロット行列・ISS/GL 再構成・総会エンジン・IRT・EDINET）を main 向けに取り込み済み。
