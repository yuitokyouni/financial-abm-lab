#!/usr/bin/env bash
# 構造図を決定論的に抽出して Obsidian が描ける markdown に書く。
# 前提: pip install pylint pydeps （pyreverse は pylint 同梱）
# パッケージ or pyreverse が無い間は no-op（commit を壊さない）。
set -euo pipefail

# 対象パッケージのパス。引数 > ABM_PKG > 既定(src/microstructure)。
PKG_PATH="${1:-${ABM_PKG:-src/microstructure}}"
PKG_NAME="$(basename "$PKG_PATH")"
OUT="docs/architecture.md"

if [[ ! -d "${PKG_PATH}" ]]; then
  echo "generate_diagrams: package '${PKG_PATH}' not found — skipping (no code yet)."
  exit 0
fi
if ! command -v pyreverse >/dev/null 2>&1; then
  echo "generate_diagrams: pyreverse missing (pip install pylint) — skipping."
  exit 0
fi

mkdir -p docs .diagrams

# クラス図 + パッケージ図 を mermaid で出力
# ※ pylint が古く -o mmd 非対応なら -o dot/plantuml に切替
pyreverse -o mmd -p "$PKG_NAME" "$PKG_PATH" -d .diagrams >/dev/null

{
  echo "# Architecture (auto-generated)"
  echo
  echo '## Packages'; echo '```mermaid'; cat ".diagrams/packages_${PKG_NAME}.mmd"; echo '```'
  echo
  echo '## Classes';  echo '```mermaid'; cat ".diagrams/classes_${PKG_NAME}.mmd";  echo '```'
} > "$OUT"

echo "wrote $OUT"
