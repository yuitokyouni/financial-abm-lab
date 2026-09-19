# 新規実験の作り方

`experiments/<ID>/` を作り、READMEには「問い／介入・比較条件／使用する共通コード／必要な入力と環境／
実行コマンド／seedと評価方法／結果の保存先／制限と未完了項目」を書く。
コピーするのはこの文書の項目であり、他実験のモデル実装ではない。

`experiment.toml` の最小例:

```toml
id = "YOUR_ID"
title = "研究の問い"
kind = "design"
shared_packages = []
paths = []
commands = []
archives = []
```

`kind` は `simulation`, `empirical`, `workflow`, `design`, `archive` のいずれか。
`paths` は実験ルートからの存在する相対パス、`archives` はリポジトリルートからの旧資料パス。
`shared_packages` は `packages/` のディレクトリ名。`commands` は確認済みの実行方法だけを書く。
別環境が必要な実験を自動的にroot workspaceへ追加しない。追加する際は依存解決とテスト範囲も更新する。

配置の確認: `python tools/check_layout.py`。計算結果の妥当性はこの検査だけでは確認できない。
