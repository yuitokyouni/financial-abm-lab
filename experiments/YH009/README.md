# YH009 — unwind-tape / 政策保有株解消イベントスタディ

実装・設定・入力資料・文書・テストの実体は **このディレクトリ**にある。
ルートの `unwind-tape` は `experiments/YH009` を指す互換シンボリックリンクであり、複製ではない。
Macのcron/launchdが旧パスを参照するため残している。定期実行設定を変更したわけではない。

## 最初に読む文書

[HANDOFF](HANDOFF.md)（進捗・受入条件）、[CLAUDE.md](CLAUDE.md)（不変条件）、
[FINDINGS](FINDINGS.md)、[設計文書](docs/)、[設定](configs/)、[開示転記ガイド](transcription/README.md)。
文書に記録された過去の評価と、今回の配置変更は区別する。

## 実行とテスト

```sh
# リポジトリルートから、API通信を行わない単体テスト
uv sync --extra dev
uv run pytest experiments/YH009/tests

# 既存コマンドの引数確認（取得処理は開始しない）
uv run python experiments/YH009/scripts/fetch_jpx_offauction.py --help
```

データを取得するコマンドとAPIキーの設定はHANDOFFと各スクリプトに従う。
この実験のスクリプトは共通パッケージに依存させず、従来の独立性を維持する。
ABM部分の `python -m abm...` は `experiments/YH009/` を作業ディレクトリにして実行する。

## 移行時の注意

Git管理済みの入力・CSV・原本・manifestは内容を変えず移動した。
**ローカルだけの無視ファイルやcron設定には、このPRからはアクセスできない。**
更新前に旧 `unwind-tape/` 以下のGit管理外データを退避し、更新後に `experiments/YH009/` 内の同じ相対位置へ移す。
旧パスが実ディレクトリのまま残っている場合はリンクへの置換が失敗するため、先にその退避が必要。
シンボリックリンク非対応のチェックアウトでは、新パスへ定期実行設定を更新する必要がある。

[配置台帳](experiment.toml) / [実験一覧](../README.md)
