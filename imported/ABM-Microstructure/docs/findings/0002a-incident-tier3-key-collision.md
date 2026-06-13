# Incident 0002a — 結果行キー衝突の検出と未読破棄（Tier-3、2026-06-11）

**性格**: 監査機構の自己適用の記録。検査パイプライン自身に汚染 class が見つかり、
部分結果を未読のまま破棄し、返金まで監査証跡に残した完結事例。whitepaper
「検査自体の信頼性」節の exhibit。

## 事象

設計マップ runner の結果行は cell id（mechanism / staleness / λ / J / fee / memory /
n / algo）でキーされていたが、Tier-3 robustness 変種の摂動軸（tie_rule、eps_beta、
gamma）は cell id にも CSV 列にも乗らない。このため変種 9 job 中 5 つ
（tie=rotate、eps_beta ×0.5/×2、γ=0.90/0.99）が**出力上互いに区別不能**——完走しても
HP 感度一覧が解釈不能であり、さらに override（--noise-rate/--lr）構成と非 override
構成の結果が resume で混ざる bug class を構成していた。

## 検出

外部レビュー（Yuito、2026-06-11）が「override × resume のキー照合」を指摘。即時の
検証で、**実行中の Tier-3 run 自身が汚染 class 内**にあることを確認した。

## 対応（時系列、全て同日）

1. **停止**: 実行中 run を kill。完了済み 3 行は**読まずに** archive
   （`results/tier3.aborted-oldschema.csv`）。読まなかったのは、降格規則
   （prereg-tier3 §2）の判定対象になり得る数値を見てから手順を直すと
   clarification の正当性（未読性）が失われるため。
2. **修正**: DesignMapPoint に eps_beta / gamma / tie_rule / **config_hash**
   （seed を除く全 config フィールドの SHA-256 先頭 16 桁）を追加。resume 照合を
   hash に変更（旧 CSV は cell id fallback + 一意性 guard）。分離性のテストを追加
   （robustness 変種 9 種で id は衝突・hash は全て相異、`tests/test_designmap.py`）。
3. **精算**: 破棄 run の charge **120,767,539 期**を ledger の reconciliations に
   監査 entry 付きで返金（保持成果物 bcs.csv の 60,303,000 期は返金対象外）。
4. **凍結の補強**: 再投入前に prereg-tier3 へ「維持」の数値明確化（プール certify の
   成分ごとの判定構造）を**未読 clarification** として追記（commit `990eddc`）。
   完走前にさらに収束 20/20 の確率算術と解釈の非対称を追記（commit `fbc1b01`）。
5. **再投入**: 新 schema で決定論再実行（D-B12——同一 config+seed は bit 同一なので、
   再実行は再計算であり追加サンプリングではない）。
6. **fallback 安全性監査**: pre-hash で書かれた既存 CSV（coarse / density / bcs /
   pilot2 / calib_smoke）に override 使用 run が存在しないこと、density.csv の
   id 重複は uniqueness guard が resume を拒否するため誤 skip 不能であることを
   ledger の audits に記録。

## 教訓（一般化）

- **結果行の同一性キーは表示用 id ではなくフル構成 hash であるべき**。表示キーと
  同一性キーの混同は、摂動軸を増やすあらゆる監査系で再発する。
- 「未読破棄」が選択肢として存在できたのは、決定論（bit 再現）・予算 ledger・
  逐次追記（部分結果が artifact として独立）という3点が事前に揃っていたから。
  この組合せ自体が監査 harness の要件である。
- 信用の源泉は捕獲実績ではなく**手続の検証可能性**（pinned function・決定論・
  artifacts による再実行可能性——ISA 230 的な workpapers 観）。失敗記録はその正直な
  手続ログの一部であり、加えて「落ちることができる検査だった」ことの記録
  （severity の証拠）として働く。失敗が信用を作るのではない——「信用される監査には
  失敗が要る」は失敗の製造・温存の誘因を生む倒錯した規範（2026-06-12 訂正。
  本 exhibit の価値の正確な記述は「自己適用された手続が記録され再実行可能である
  こと」）。

## 関連 incident

同日に第2の自己検出（ledger スナップショット上書きによる lost update）が発生した。
教訓が別（同一性キー≠表示キー vs スナップショット上書きは台帳ではない）なので、
独立 exhibit として分離: **`0002b-incident-ledger-snapshot.md`**。

## 関連

- 修正 commit: `990eddc`（schema + テスト + 文言確定）／ 精算: `results/budget.json`
  reconciliations[1]・audits ／ 凍結: `prereg-tier3.md` §2.1 注記・§2.5
