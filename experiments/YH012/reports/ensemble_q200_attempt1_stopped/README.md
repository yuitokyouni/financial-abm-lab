# Q=200・40 seed 実験の停止記録

2026-09-05、seed 0〜39 を事前に固定して実行したが、**seed 13 の発注時刻に売り板がなく停止**した。
依頼された40 seed 平均・標準偏差・信頼区間・終盤インパクト推定は未算出。
途中で完了した seed だけを平均すると標本が選別されるため、部分平均も公開しない。

## 条件と停止原因

- Q=200、最良 ask+2 の買い指値1本、t0=25,000、初期評価窓 [25,000,26,000]。
- end_time=50,000 を維持し、終盤 [45,000,50,000] の観察期間を確保した。
- 40 seed は結果を見る前に選定。8コア・16 GiB の Mac で4プロセスを使用した。
- seed 0 の試行は65.32秒。本実行は450.48秒で停止。seed 数・終了時刻・市場条件は変更していない。
- 例外は `RuntimeError: ImpactAgent requires a best ask at t0`。
  Factual の `run_pair` 内で発生し、seed 13 のペアは完成していない。
- 介入前のバイト不一致による停止ではない。完成した11ペアは保存後の再読込でも
  `logs_byte_equal` とパディングを含む生バイト比較の両方に合格した。

完了: **0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 12**。
停止検知時に実行中の **8, 11, 14** を終了・回収し、**15〜39** は未開始。
seed 6 は200の発注に対して45しか約定していない。未約定残を持つ seed や
初期窓平均が負・ゼロの seed を除外する処理は入れていない。

売り板の復帰を待って発注すれば全 seed を残す設計にできるが、介入時刻が seed ごとに変わる。
これは単なる計算量調整ではないため、扱いを確認するまで元の発注ルールを保持している。
指定された条件のままでは、永続インパクトや振動の残存について結論を出せない。

## 保存したもの

- [事前の実行計画](plan.json)、[実際の進捗・停止状態](progress.json)、[停止理由と11件の一致証明](stop_reason.json)。
- [元ログの圧縮アーカイブ](attempt_logs.tar.gz): 完成した11組の F/B バイナリ、
  各 seed の設定・メタデータ・mid 系列、未完了 seed の設定・実行ログ。
- [アーカイブと各ファイルの SHA-256](log_manifest.json)。圧縮後、全ファイルを展開して元の全バイトと照合済み。

全ペアの `ExperimentMeta.lobcore_version` は
`4fb83dcb2c0d17cc5239816606d2ec4cc0e3fabf`。
市場・介入モデルは FAL `7f53978ce81cacedf243d992fffba75c2fc2f50b` と同じ。
追加したのは実行管理・集計・保存・作図のコードで、シミュレーションの挙動は変えていない。

```bash
mkdir -p experiments/YH012/artifacts/restored_ensemble_attempt1
tar -xzf experiments/YH012/reports/ensemble_q200_attempt1_stopped/attempt_logs.tar.gz \
  -C experiments/YH012/artifacts/restored_ensemble_attempt1

# 保存された任意の完了ペアを再検証できる。例: seed 0。
.venv/bin/python -m experiments.YH012.inspect_saved_pair \
  --run-dir experiments/YH012/artifacts/restored_ensemble_attempt1/seed0000
```

## コードの確認

既存の YH012・lobcore Python テストを含む47件が通過した後、追加・拡張した
ensemble テスト10件を再実行して全件通過（既存41件＋ensemble10件）。
共通時刻への整列、標準偏差と信頼区間の区別、時間相関を壊さない終盤推定、
欠測の除外防止、停止時の子プロセス終了、保存ログからの再解析・圧縮復元を確認した。
ruff と `git diff --check` も通過。実データ40 seed での集計図は、実験未完了のため未生成。
