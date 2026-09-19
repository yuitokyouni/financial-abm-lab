# Fingerprint atlas — モデル比較・研究探索の実行記録

共有ライブラリは [`packages/fingerprint_atlas`](../../packages/fingerprint_atlas/) に置く。
このディレクトリには、そのライブラリを用いた比較の文書・生成図・監査出力を置く。

[文書](docs/) / [生成済みレポート](reports/) / [配置台帳](experiment.toml)。
旧 `notebooks/atlas_v*` はノートブックではなく生成画像・gate JSONだったため、`reports/` へ移動した。
ルートにあった `lm_tree.html` と `mg_tree.html` は `reports/genealogy/` にある。
自動生成workflowとdashboardの参照先も新パスへ更新している。

```sh
uv run python -m fingerprint_atlas.atlas --help
uv run python -m fingerprint_atlas.arxiv_cli --help
```

DBは共有研究資料としてルート `data/` に置く。提案段階の内容はルート `proposals/` に保持し、
実験結果と混同しない。実行にはDB・各コマンドの設定が必要で、上記は引数確認用。
新規の比較には入力、seed、commit、実行条件を添える。
[実験一覧](../README.md)
