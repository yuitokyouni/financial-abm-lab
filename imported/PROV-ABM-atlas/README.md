# real-prism — 真・PRISM toy + PROV-ABM / Atlas framework

[![CI](https://github.com/yuitokyouni/PROV-ABM-atlas/actions/workflows/ci.yml/badge.svg)](https://github.com/yuitokyouni/PROV-ABM-atlas/actions/workflows/ci.yml)

撤退判定された PRISM の load-bearing な経験的前提——
**「介入応答は stylized facts では分けられない機構を分ける」**——を controlled toy experiment で検証する。
同じ toy が、将来構築する **PROV-ABM**(provenance/再現性 framework)と **Intervention Atlas**(機構弁別ベンチ)の
最初の dogfood として走る。

> v0 の最優先は **toy 実験の完遂**。framework は toy が要求する分だけ最小で育てる。
> 詳細は [`CLAUDE.md`](./CLAUDE.md) と [`docs/`](./docs) を参照(spec が ground truth)。

## パッケージ構成

| パッケージ | 役割 | v0 ステータス |
|---|---|---|
| `provabm/` | provenance / 捕捉層(`ctx.*` API、reach、validator、prov.json) | **L2 minimum** 実装 |
| `toy/` | 真・PRISM toy 実験本体(market、Model T/H、observation、SF、介入) | market/agents/observation 実装、SF/calibration/介入は scaffold |
| `atlas/` | 機構弁別ベンチの format scaffold | 抽象 protocol のみ |
| `experiments/` | Hydra config + runner + Snakemake DAG | run_one + 基本 config |

## セットアップ

```bash
uv sync                       # 依存解決(uv.lock 固定)
uv run pre-commit install     # lint gate を有効化
uv run pytest                 # 全テスト(unit + property + integration smoke)
```

## 1 run 実行(smoke)

```bash
uv run python -m experiments.runners.run_one
# → runs/{config_hash}_{seed}_{uuid7}.parquet と同名 .prov.json を出力
```

各 run は L2 provenance(git commit / resolved config の sha256 / seed / env / output sha256 / uuid7)を
sidecar JSON に記録する。`reach_claim` は v0 では `reported` のみ受理(`provabm.validator`)。

## スコープと留保

- **留保 1/2**(SF calibration anchor / SF battery scope)が確定するまで、
  `toy/calibration.py`・`toy/sf_battery.py` の本体は `NotImplementedError("awaiting v0.2")` で停止。
- Type1 hygiene(auditability / reproducibility)のみ。Type2(SME 許容境界)はスコープ外。

## ライセンス

MIT — [`LICENSE`](./LICENSE)
