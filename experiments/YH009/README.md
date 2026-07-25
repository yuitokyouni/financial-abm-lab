# YH009 — unwind-tape (政策保有株解消イベントスタディ)

**実体はリポルート直下の [`unwind-tape/`](../../unwind-tape/) にある。**

YH0xx 再編 (2026-07-23) で experiments/ 配下への移動も検討したが、ユーザ Mac の
cron/launchd が `unwind-tape/scripts/fetch_jpx_offauction.py` のパスを直接参照して
毎日発火しているため、**パスを壊さないことを優先してルート配置を維持**した。
本ディレクトリは一覧性のためのポインタのみ。

- 進捗・受け入れ条件の一次情報: `unwind-tape/HANDOFF.md`
- 規約・不変条件: `unwind-tape/CLAUDE.md`
- マスター台帳 (YH009 節): `imported/speculation-game-info/docs/findings.md`

**現在地 (2026-07-24 merge)**: EDINET/TCA/benchmark/residual/stylized-facts エンジン、
開示転記パイプライン、ABM regime harness、FINDINGS v1（記述・サイズ説明力・SF）まで
`claude/unwind-tape-data-foundation-0txm6z` から main 向けに取り込み済み。詳細は
`unwind-tape/HANDOFF.md` / `FINDINGS.md`。
