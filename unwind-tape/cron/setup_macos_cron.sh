#!/bin/bash
# unwind-tape — macOS cron 登録ヘルパー
#
# 使い方:
#   bash unwind-tape/cron/setup_macos_cron.sh              # dry-run: crontab 行を stdout に出すだけ
#   bash unwind-tape/cron/setup_macos_cron.sh --install    # 現ユーザの crontab に追記
#   bash unwind-tape/cron/setup_macos_cron.sh --time 09:00 # 実行時刻を変更 (デフォルト 21:00 JST)
#
# macOS の落とし穴 (このスクリプトはこれらを検知/回避します):
#   1. Full Disk Access が cron/bash に必要 (System Settings > Privacy & Security)
#   2. Mac がスリープしていると cron は動かない → launchd 代替を末尾に案内
#   3. flock はデフォルト未搭載 → mkdir(atomic) ベースのロックに置換
#   4. Homebrew Python と system Python の差 → which python3 を明示化

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$REPO_ROOT/unwind-tape/scripts/fetch_jpx_offauction.py"
LOG_DIR="$REPO_ROOT/unwind-tape/data/logs"
LOCK_DIR="/tmp/unwind_tape_jpx.lockd"

TIME_HHMM="21:00"
INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --time)   shift; TIME_HHMM="$1"; shift ;;
    --time=*) TIME_HHMM="${arg#--time=}" ;;
    -h|--help)
      sed -n '3,17p' "$0"
      exit 0
      ;;
  esac
done

HH="${TIME_HHMM%%:*}"
MM="${TIME_HHMM##*:}"

# ---- pre-flight checks ---------------------------------------------------

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python3 not found in PATH. Install via https://python.org or 'brew install python@3.11'." >&2
  exit 2
fi

if ! "$PYTHON" -c "import requests, openpyxl, yaml" 2>/dev/null; then
  echo "WARN: python3 dependencies missing. Run:"
  echo "  $PYTHON -m pip install --user requests openpyxl PyYAML"
  echo ""
fi

if [[ ! -x "$SCRIPT" ]] && [[ ! -r "$SCRIPT" ]]; then
  echo "ERROR: $SCRIPT not found. Check REPO_ROOT (currently: $REPO_ROOT)" >&2
  exit 2
fi

TZ_NAME="$(date +%Z)"
UTC_OFFSET_HOURS="$(date +%z | awk '{ h=substr($0,1,3)+0; print h }')"

echo "==========================================================="
echo "REPO_ROOT: $REPO_ROOT"
echo "PYTHON:    $PYTHON"
echo "SCRIPT:    $SCRIPT"
echo "LOG_DIR:   $LOG_DIR"
echo "SYSTEM TZ: $TZ_NAME (UTC${UTC_OFFSET_HOURS:+$UTC_OFFSET_HOURS})"
echo "TARGET:    ${TIME_HHMM} system-local time"
echo "==========================================================="
echo ""

mkdir -p "$LOG_DIR"

# ---- build crontab line --------------------------------------------------
# Use mkdir as atomic single-instance lock (portable, no flock dependency).
# Redirect both stdout/stderr into rotating cron logs.

CRON_LINE="${MM} ${HH} * * * cd \"$REPO_ROOT\" && \\
    ( mkdir \"$LOCK_DIR\" 2>/dev/null || exit 0 ; \\
      trap 'rmdir \"$LOCK_DIR\"' EXIT ; \\
      \"$PYTHON\" \"$SCRIPT\" ; \\
    ) >> \"$LOG_DIR/cron.stdout.log\" 2>> \"$LOG_DIR/cron.stderr.log\""

# Flatten to single line (crontab requires one entry per line).
CRON_LINE_ONE_LINE="$(echo "$CRON_LINE" | tr -d '\n' | sed 's/  */ /g; s/\\ //g')"

echo "cron entry to register:"
echo "----------------------------------------------------------"
echo "$CRON_LINE_ONE_LINE"
echo "----------------------------------------------------------"
echo ""

# ---- Full Disk Access reminder ------------------------------------------

cat <<'MACOS_TIPS'
【macOS 必須設定 — 一度だけ】
  System Settings > Privacy & Security > Full Disk Access で
  以下に許可を付ける (どちらか一方でよい):
    /usr/sbin/cron
    /bin/bash
  設定しないと raw ファイル書き込みで "Operation not permitted" が出ます。
  cron の権限は Finder → Shift+Cmd+G → "/usr/sbin/cron" で追加できます。

【スリープ対策】
  Mac がスリープすると cron は動きません。以下のいずれかで対処:
   (a) System Settings > Battery > "Prevent your Mac from automatically sleeping..." を ON
   (b) 深夜稼働用に pmset schedule で wake を仕込む:
       sudo pmset repeat wakeorpoweron MTWRFSU 20:55:00
   (c) この cron を launchd に載せ替える (StartCalendarInterval は起動時キャッチアップも可能)
       → unwind-tape/cron/setup_macos_launchd.sh を用意しています

【動作テスト】
  cron 登録前に手動で 1 回走らせて動作を確認するのを強く推奨。
MACOS_TIPS
printf "  手動実行:     %s %s\n" "$PYTHON" "$SCRIPT"
printf "  ログ確認:     tail -f %s/cron.stdout.log %s/cron.stderr.log\n" "$LOG_DIR" "$LOG_DIR"
printf "\n"

# ---- install -------------------------------------------------------------

if [[ "$INSTALL" == 1 ]]; then
  echo "installing to crontab ..."
  # detect if line already registered
  EXISTING="$(crontab -l 2>/dev/null || true)"
  if echo "$EXISTING" | grep -qF "$SCRIPT"; then
    echo "  ! crontab already contains a line referencing $SCRIPT — skipping install."
    echo "  ! (edit manually with: crontab -e)"
    exit 0
  fi
  # append
  {
    echo "$EXISTING"
    echo "# unwind-tape JPX daily fetch (installed by setup_macos_cron.sh)"
    echo "$CRON_LINE_ONE_LINE"
  } | crontab -
  echo "  ok. verify:  crontab -l"
else
  echo "dry-run only. To install, re-run with --install."
fi
