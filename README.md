# financial-abm-lab

金融市場のエージェントベースモデルと関連する実証研究のモノレポ。
**実験は`experiments/<ID>/`、再利用する実装は`packages/`、全体の説明は`docs/`**に分ける。

[実験一覧](experiments/README.md) · [文書入口](docs/README.md) · [共通コード](packages/README.md) · [配置規約](docs/architecture/repository-layout.md)

## 最初に読む場所

| 目的 | 入口 |
|---|---|
| ある研究を実行・理解する | `experiments/<ID>/README.md` と `experiment.toml` |
| モデルの式・共有実装を見る | `packages/abm_models/` |
| YH010-gの実験固有実装を見る | `experiments/YH010g/yh010g/` |
| 全体の設計・運用を調べる | `docs/README.md` |
| 旧実装や保存済みの証拠を調べる | 実験READMEから`imported/`へのリンク |

モデルだけでは実験にならない。問い、入力、介入条件、seed、測定方法と結果の置き場は各実験が持つ。
共通モデルは複製せずimportする。実験固有のコードは、インストール可能なPython packageであっても実験側に置く。

## 構成

```text
experiments/
  YH001/ ... YH005/    古典モデル・Speculation Gameの個別実行入口
  YH006/              旧SG-on-LOBへのアーカイブ入口
  YH007/              共有予測×板：scripts / specs / docs / tests / reports
  YH008/              LLM内部活性介入の資料・旧実装への入口
  YH009/              unwind-tapeの実体（コード・設定・入力・文書・テスト）
  YH010/              agent-agoraの仕様と調査
  YH010g/             ガバナンス実験package・テスト・検証入力・文書
  YH012/              LOBcoreインパクト実験（専用環境）
  fingerprint_atlas/  比較・研究探索の文書と生成済みレポート
packages/             abm_models / stylized_facts / provenance / agora_engine / fingerprint_atlas
src/fabm/             既存の共通補助コード
tests/               共通API・モデルparity・リポジトリ配置のテスト
docs/                全体の使い方・設計・横断的な監査
imported/            旧リポの履歴・実装・証拠
data/                研究横断のDB・文献データ
proposals/           採用前の研究提案
unwind-tape -> experiments/YH009   外部定期実行用の互換リンク
```

## セットアップ・検証

```sh
uv sync --extra dev
python tools/check_layout.py
uv run pytest -m "not slow"

# 既存baselineを個別に実行（軽量smokeではない）
uv run python -m experiments.YH001.baseline --seed 42
uv run python -m experiments.YH005.baseline --seed 777
```

rootの標準テストは共通コードとYH007/YH009/YH010-gを含む。
[YH012](experiments/YH012/README.md)は別途LOBcoreが必要で、root環境へ自動的に混在させない。
[新規実験の作り方](experiments/_template/README.md)に従って追加する。

## 履歴と移行

旧6リポは`imported/`に保持する。元の統合経緯は[統合仕様](docs/architecture/001-monorepo-consolidation.md)を参照。
今回の整理は研究結果を再評価するものではない。YH012の保存済み39 seedの結果や旧ログを変更しない。
YH011/YH013は対象mainに実体がなかったため、新しいフォルダや結果を作っていない。

**更新前にローカルのGit管理外データを退避すること。** YH009とYH010-gのREADMEに復元先を記載した。
Macのcron/launchdは変更していない。旧`unwind-tape`パスは互換リンクで維持する。
[移動対応表](docs/architecture/migration-2026-09-19.md)。

capital-allocation（実運用）、MultiAgent-Trader、SIEVE、LOBcore等の別リポはこの整理では変更しない。
