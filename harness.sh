#!/bin/bash

# 設定値
MAX_STALLS=3
STALL_COUNT=0
WORKSPACE_DIR=$(pwd)

# 3. ログディレクトリの事前作成
mkdir -p agent_logs

echo "Starting Autonomous Claude Harness..."

while true; do
    # ミッション完了フラグの検出
    if [ -f MISSION_COMPLETE ]; then
        echo "=== MISSION COMPLETE ==="
        echo "Final report: docs/FINAL_REPORT.md"
        echo "Harness stopped at $(date)."
        break
    fi

    COMMIT=$(git rev-parse --short HEAD)
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOGFILE="agent_logs/agent_${COMMIT}_${TIMESTAMP}.log"
    
    # 実行前のコミットハッシュを取得
    PREV_HASH=$(git rev-parse HEAD)
    
    # 2. 動的プロンプトの構築 (改行リテラルの修正)
    DYNAMIC_PROMPT=$(cat AGENT_PROMPT.md)
    if [ $STALL_COUNT -gt 0 ]; then
        DYNAMIC_PROMPT+=$'\n\n【システムからの警告】前回までのセッションで有効なコミットがありません（連続'"${STALL_COUNT}"'回目）。直前のアプローチが破綻している可能性が高いです。エラーを分析し、全く別のアプローチを試みるか、現状のブロッカーを progress.md に詳細に記述してください。'
    fi

    echo "[${TIMESTAMP}] Launching Claude session..."
    
    # 1. タイムアウト処理の代替 (Bashネイティブ)
    (
        # Claudeをバックグラウンドで起動
        claude --dangerously-skip-permissions -p "$DYNAMIC_PROMPT" > "$LOGFILE" 2>&1 &
        CLAUDE_PID=$!
        
        # タイムアウト監視用サブプロセス (2700秒 = 45分)
        ( sleep 2700 ; kill $CLAUDE_PID 2>/dev/null ) &
        WATCHDOG_PID=$!
        
        # Claudeプロセスの終了を待機
        wait $CLAUDE_PID
        
        # Claudeがタイムアウト前に正常終了した場合は監視プロセスを破棄
        kill $WATCHDOG_PID 2>/dev/null
    )
        
    # 実行後のコミットハッシュを取得
    CURRENT_HASH=$(git rev-parse HEAD)

    # 状態変化の検証 (コミットが進んだか)
    if [ "$PREV_HASH" = "$CURRENT_HASH" ]; then
        STALL_COUNT=$((STALL_COUNT + 1))
        echo "Warning: No new commits detected. Stall count: ${STALL_COUNT}"
        
        if [ $STALL_COUNT -ge $MAX_STALLS ]; then
            echo "Critical: Agent is stuck. Initiating auto-rollback..."
            
            # 未コミットの迷走コードをすべて破棄
            git reset --hard HEAD
            git clean -fd
            
            # 4. 無限ループ防止: 失敗の事実を記録して強制コミット
            echo -e "\n- **[SYSTEM ALERT] $(date +%m/%d_%H:%M)** 連続停滞(${MAX_STALLS}回)により自動ロールバックが発動しました。直前のアプローチは手詰まりと判定され破棄されました。同じ手段を繰り返さず、別のアプローチ（リサーチ、ログ出力の追加など）を検討してください。" >> progress.md
            git add progress.md
            git commit -m "chore: system auto-rollback due to consecutive stalls"
            
            echo "Rollback complete. System alert injected to progress.md."
            echo "Initiating 5-minute cool-down..."
            sleep 300 
            STALL_COUNT=0
        else
            sleep 10
        fi
    else
        echo "Progress detected (New commit). Resetting stall counter."
        STALL_COUNT=0
        sleep 5
    fi
done