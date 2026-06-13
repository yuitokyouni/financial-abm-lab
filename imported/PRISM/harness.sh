#!/bin/bash

# =============================================================================
# PRISM Autonomous Harness — Phase A-D (Scientific Validation)
# =============================================================================

# 設定値
MAX_STALLS=3
STALL_COUNT=0
WORKSPACE_DIR=$(pwd)

# 環境変数の読み込み
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "Environment loaded from .env"
else
    echo "WARNING: .env not found. J-Quants credentials may be missing."
fi

# ログディレクトリの事前作成
mkdir -p agent_logs

# フェーズの初期化（CURRENT_PHASE が無ければ A から開始）
if [ ! -f CURRENT_PHASE ]; then
    echo "A" > CURRENT_PHASE
    echo "Initialized CURRENT_PHASE to A"
fi

echo "Starting PRISM Autonomous Harness (Scientific Validation Mode)..."

while true; do
    # ミッション完了フラグの検出
    if [ -f MISSION_COMPLETE ]; then
        echo "=== MISSION COMPLETE ==="
        echo "Final report: docs/FINAL_REPORT.md"
        echo "Harness stopped at $(date)."
        break
    fi

    PHASE=$(cat CURRENT_PHASE)
    COMMIT=$(git rev-parse --short HEAD)
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOGFILE="agent_logs/phase${PHASE}_${COMMIT}_${TIMESTAMP}.log"

    # 実行前のコミットハッシュを取得
    PREV_HASH=$(git rev-parse HEAD)

    # --- 動的プロンプトの構築 ---
    DYNAMIC_PROMPT=$(cat AGENT_PROMPT.md)

    # フェーズ固有の指令を注入
    case "$PHASE" in
        A)
            DYNAMIC_PROMPT+=$'\n\n## 【現在のフェーズ: A — 1セル検証】\nJ-Quants API で JPX 2014 tick 変更の実データを取得し、PRISM の同一 estimator で経験側 ΔF を DiD で再導出せよ。external_claim を置換し、SG + ZI-C を構造介入のみで回して符号を検証せよ。\n**禁止事項:** 新しい adapter, NER, パッケージング, ドキュメント装飾の追加。Phase A の DoD を満たすことだけに集中せよ。'
            ;;
        B)
            DYNAMIC_PROMPT+=$'\n\n## 【現在のフェーズ: B — 有効セル選別】\n全 NER の引用文献を精査し、リターン系列 fact で ΔF を取れるものだけを残せ。スプレッド/流動性しか測っていない NER は科学的に成立しない。有効セル数が少なくても、それが本物の数だ。\n**禁止事項:** 新しい adapter, NER の追加。既存セルの科学的妥当性の検証だけに集中せよ。'
            ;;
        C)
            DYNAMIC_PROMPT+=$'\n\n## 【現在のフェーズ: C — 密輸監査 + adapter 修正】\n全 adapter の介入ロジックを監査せよ。介入は exogenous な構造制約（価格グリッド量子化幅、round-trip コスト項）としてのみ入れ、行動パラメータ（β, herd_strength 等）を手で回してはならない。ZI-C の創発応答をベースラインとし、行動モデルがそれを上回れるかで判別力を測定せよ。\n**禁止事項:** 新しい adapter, NER の追加。密輸の除去と構造介入への書き換えだけに集中せよ。'
            ;;
        D)
            DYNAMIC_PROMPT+=$'\n\n## 【現在のフェーズ: D — 工学資産の再接続】\nPhase A-C で確立した科学的に有効なセルに、既存の工学資産（provenance spine, scorer, CLI, 可視化）を再接続せよ。無効と判定されたセルの削除・整理も行え。\nこのフェーズでのみ、新しい adapter や NER の追加を許可する（ただし科学的妥当性を満たすもののみ）。'
            ;;
    esac

    # ストール警告の注入
    if [ $STALL_COUNT -gt 0 ]; then
        DYNAMIC_PROMPT+=$'\n\n【システムからの警告】前回までのセッションで有効なコミットがありません（連続'"${STALL_COUNT}"'回目）。直前のアプローチが破綻している可能性が高いです。エラーを分析し、全く別のアプローチを試みるか、現状のブロッカーを progress.md に詳細に記述してください。'
    fi

    echo "[${TIMESTAMP}] Phase ${PHASE} | Launching Claude session..."

    # タイムアウト付き実行 (2700秒 = 45分)
    (
        claude --dangerously-skip-permissions -p "$DYNAMIC_PROMPT" > "$LOGFILE" 2>&1 &
        CLAUDE_PID=$!
        ( sleep 2700 ; kill $CLAUDE_PID 2>/dev/null ) &
        WATCHDOG_PID=$!
        wait $CLAUDE_PID
        kill $WATCHDOG_PID 2>/dev/null
    )

    # 実行後のコミットハッシュを取得
    CURRENT_HASH=$(git rev-parse HEAD)

    # --- スコープ逸脱検出 (Phase A-C) ---
    if [ "$PHASE" != "D" ] && [ "$PREV_HASH" != "$CURRENT_HASH" ]; then
        SCOPE_VIOLATION=""
        # 新しい adapter ファイルの追加を検出
        NEW_ADAPTERS=$(git diff --name-only --diff-filter=A "$PREV_HASH" "$CURRENT_HASH" | grep '^src/prism/adapters/' | grep -v '__init__' || true)
        # 新しい NER ファイルの追加を検出
        NEW_NERS=$(git diff --name-only --diff-filter=A "$PREV_HASH" "$CURRENT_HASH" | grep '^data/ner/' || true)

        if [ -n "$NEW_ADAPTERS" ] || [ -n "$NEW_NERS" ]; then
            SCOPE_VIOLATION="Phase ${PHASE} でスコープ逸脱を検出: 新規 adapter/NER の追加は Phase D まで禁止。"
            echo "SCOPE VIOLATION: ${SCOPE_VIOLATION}"
            echo "  New adapters: ${NEW_ADAPTERS}"
            echo "  New NERs: ${NEW_NERS}"
            # 逸脱コミットを巻き戻す
            git reset --hard "$PREV_HASH"
            git clean -fd
            echo -e "\n- **[SCOPE GUARD] $(date +%m/%d_%H:%M)** ${SCOPE_VIOLATION} コミットを巻き戻しました。Phase ${PHASE} の DoD に集中してください。" >> progress.md
            git add progress.md
            git commit -m "chore: scope violation rollback in Phase ${PHASE}"
            STALL_COUNT=$((STALL_COUNT + 1))
            sleep 10
            continue
        fi
    fi

    # --- 状態変化の検証 ---
    if [ "$PREV_HASH" = "$CURRENT_HASH" ]; then
        STALL_COUNT=$((STALL_COUNT + 1))
        echo "Warning: No new commits detected. Stall count: ${STALL_COUNT}"

        if [ $STALL_COUNT -ge $MAX_STALLS ]; then
            echo "Critical: Agent is stuck. Initiating auto-rollback..."
            git reset --hard HEAD
            git clean -fd
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
