#!/usr/bin/env bash
# 公開時の bit-reproduction エントリ(v0: scaffold)。
#
# 目的: prov.json に記録された (git_commit, config_yaml, seed, env) から run を
# bit 単位で再生成し、output_sha256 が一致することを保証する(設計ノート §13.2)。
#
# v0 では smoke レベルの 1 run 再現のみ。full sweep 再現と Zenodo deposit 連携は後続。
set -euo pipefail

PROV_JSON="${1:-}"
if [[ -z "${PROV_JSON}" ]]; then
  echo "usage: scripts/reproduce.sh <path/to/run.prov.json>" >&2
  echo "  記録済み provenance から run を再生成し output_sha256 を照合する。" >&2
  exit 2
fi

# TODO(Week3+): prov.json を読み、git_commit を checkout、config/seed を復元して
#   experiments.runners.run_one を再実行、output_sha256 を照合する。
echo "reproduce.sh: not yet implemented (scaffold). target=${PROV_JSON}" >&2
exit 1
