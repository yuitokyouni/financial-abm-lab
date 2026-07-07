#!/bin/bash
# unwind-tape — macOS launchd 登録ヘルパー (cron の代替、スリープ耐性◎)
#
# 使い方:
#   bash unwind-tape/cron/setup_macos_launchd.sh          # plist を出して手順を案内
#   bash unwind-tape/cron/setup_macos_launchd.sh --install # ~/Library/LaunchAgents/ に配置してロード
#
# launchd の cron との違い:
#   - スリープ中に発火時刻を跨いだ場合、次回起動時にキャッチアップ実行される
#   - Full Disk Access は同じく必要 (今度は python3 に付ける)
#   - StartCalendarInterval で 21:00 JST 定時発火

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$REPO_ROOT/unwind-tape/scripts/fetch_jpx_offauction.py"
LOG_DIR="$REPO_ROOT/unwind-tape/data/logs"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"

TIME_HHMM="21:00"
INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --time)   shift; TIME_HHMM="$1"; shift ;;
    --time=*) TIME_HHMM="${arg#--time=}" ;;
  esac
done
HH="${TIME_HHMM%%:*}"
MM="${TIME_HHMM##*:}"

LABEL="com.unwind-tape.jpx"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$LOG_DIR"

TMP_PLIST="$(mktemp)"
cat > "$TMP_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>          <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$SCRIPT</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO_ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TZ</key><string>Asia/Tokyo</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>   <integer>$HH</integer>
    <key>Minute</key> <integer>$MM</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOG_DIR/launchd.stdout.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launchd.stderr.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF

echo "==========================================================="
echo "generated plist for $LABEL:"
echo "-----------------------------------------------------------"
cat "$TMP_PLIST"
echo "-----------------------------------------------------------"
echo ""
echo "target install path: $PLIST"
echo ""

if [[ "$INSTALL" == 1 ]]; then
  mv "$TMP_PLIST" "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load  "$PLIST"
  echo "loaded. verify:"
  echo "  launchctl list | grep $LABEL"
  echo "  next fire time can be seen with:"
  echo "  launchctl print gui/\$(id -u)/$LABEL | grep -E 'next|state'"
else
  echo "dry-run only. To install, re-run with --install."
  echo "or manually copy: cp $TMP_PLIST $PLIST"
fi

cat <<'TIPS'

【Full Disk Access】
  System Settings > Privacy & Security > Full Disk Access で
  python3 (which python3 で見えるパス) に許可を付ける。
  cron と違い launchd 経由でもこの権限は必要。

【スリープ挙動】
  Mac が 21:00 の時点でスリープしていた場合、
  次に起きた瞬間にキャッチアップして 1 回だけ実行される。
  cron はスリープ中の分がロストするが launchd はしないのが最大の利点。

【アンロード】
  やめたいとき:  launchctl unload $HOME/Library/LaunchAgents/com.unwind-tape.jpx.plist
  完全削除:      launchctl unload $HOME/Library/LaunchAgents/com.unwind-tape.jpx.plist && rm $HOME/Library/LaunchAgents/com.unwind-tape.jpx.plist
TIPS
