# unwind-tape

日本株の unwind (一定期間内解消) イベントを組成する tape 研究プロジェクト。

- **設計上のground truth**: `CLAUDE.md`
- **進捗・受け入れ条件**: `HANDOFF.md`

## Task A — JPX 立会外取引情報 daily capture

```
python3 unwind-tape/scripts/fetch_jpx_offauction.py
```

初回は現掲載分(過去2週間)を全件バックフィル。以後は追記 + idempotent dedupe。
成功で exit=0、schema_mismatch で exit=3、fetch_error で exit=4。

cron 例は `cron/jpx_offauction.crontab`。デプロイ手順は `HANDOFF.md` に記載。
