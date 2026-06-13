# atlas — Intervention Atlas (format scaffold のみ)

**このパッケージは v0 では format scaffold に過ぎない。実装は将来。**

`protocols.py` に `Battery` / `Mechanism` / `Response` の抽象 protocol(型 + signature のみ)を置く。
中身(実際の battery、leaderboard infrastructure、scoring 機構、Type2 survival test)は
**CLAUDE.md スコープ規律表により v0 ではスコープ外**。

## なぜ空なのか(framework-first 禁止)

設計ノート §1.4 / CLAUDE.md 反パターン:綺麗な framework を先に作り込み toy を後から合わせる順序は禁止。
正しい順序は **toy-first** — `toy/` が market・機構・介入・SF を先に実装し、それが安定した時点で
本 protocol に逆輸入する。toy が動かない framework は無価値。

## スコープ境界

- **やる(将来)**: descriptive Atlas(機構応答の地図)+ hygiene スコア leaderboard(Type1、GT-free)+ fit-for-purpose tracks。
- **やらない**: validity ランク(参照が要る=原理的に不可能)、Type2 survival test(SME 許容境界=consensus 強制装置)。

詳細は [`docs/prov_abm_design_notes.md`](../docs/prov_abm_design_notes.md) §2。
