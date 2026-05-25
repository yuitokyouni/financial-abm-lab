#!/bin/bash

# 設定値
MAX_STALLS=3
STALL_COUNT=0
WORKSPACE_DIR=$(pwd)

echo "Starting Autonomous Claude Harness..."

while true; do
    COMMIT=$(git rev-parse --short HEAD)
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOGFILE="agent_logs/agent_${COMMIT}_${TIMESTAMP}.log"
    
    # 実行前のコミットハッシュを取得
    PREV_HASH=$(git rev-parse HEAD)
    
    # 動的プロンプトの構築
    DYNAMIC_PROMPT=$(cat AGENT_PROMPT.md)
    if [ $STALL_COUNT -gt 0 ]; then
        DYNAMIC_PROMPT="${DYNAMIC_PROMPT}\n\n【システムからの警告】前回までのセッションで有効なコミットがありません（連続${STALL_COUNT}回目）。直前のアプローチが破綻している可能性が高いです。エラーを分析し、全く別のアプローチを試みるか、現状のブロッカーを progress.md に詳細に記述してください。"
    fi

    echo "[${TIMESTAMP}] Launching Claude session..."
    
    # タイムアウト付きで実行 (2700秒 = 45分)
    timeout 2700 claude -p "$DYNAMIC_PROMPT" > "$LOGFILE" 2>&1
        
    # 実行後のコミットハッシュを取得
    CURRENT_HASH=$(git rev-parse HEAD)

    # 状態変化の検証 (コミットが進んだか)
    if [ "$PREV_HASH" = "$CURRENT_HASH" ]; then
        STALL_COUNT=$((STALL_COUNT + 1))
        echo "Warning: No new commits detected. Stall count: ${STALL_COUNT}"
        
        if [ $STALL_COUNT -ge $MAX_STALLS ]; then
            echo "Critical: Agent is stuck. Initiating auto-rollback..."
            # 未コミットの迷走コードをすべて破棄し、前回の正常な状態へ切り戻す
            git reset --hard HEAD
            git clean -fd
            echo "Rollback complete. Reverted to clean state of ${CURRENT_HASH:0:7}."
            
            # トークン浪費を防ぐための冷却時間 (5分)
            echo "Initiating 5-minute cool-down..."
            sleep 300 
            STALL_COUNT=0
        else
            sleep 10
        fi
    else
        # 新しいコミットが作成された場合は進捗ありとみなす
        echo "Progress detected (New commit). Resetting stall counter."
        STALL_COUNT=0
        sleep 5
    fi
done