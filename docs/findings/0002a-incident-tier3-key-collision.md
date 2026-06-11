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
- 検査を売る側の信用は宣言では作れない。**自分のパイプラインに同じ規律を適用し、
  実際に汚染を未読のまま破棄した**という記録がその代替物になる。

## 追記 — 同日第2の自己検出: ledger 並行書き込みの lost update（2026-06-11）

**事象**: BudgetLedger は読み込んだ JSON を更新のたび丸ごと書き戻す（last-writer-wins）
設計で、単一書き手を暗黙に仮定していた。並行 background run（Tier-3 / bcs_per_seed /
attribution）が同一 ledger を共有した結果、**監査 entry（audits[0]）が消え、charge も
lost update していた**（再構成で dense +35.0M、robustness +14.1M の計上漏れが判明）。

**検出**: 外部レビューの要求（audits への一行追記）を実行しようとして KeyError——
書いたはずの audits[0] が存在しない、という形で表面化。監査記録自体が消えたことが
検出器になった。

**対応**: (1) lock file + read-modify-write で全更新を直列化（`BudgetLedger._locked`）、
回帰テスト追加（並行 instance の charge 合算と audits 生存）。(2) 全 tier の spent を
**artifacts から決定論的に再構成**: 各 CSV の periods_total は per-run の実消費を
持ち、attribution の再計算 run は D-B12 により既存 run と同一（density/tier3 の値を
そのまま流用可能）。唯一実測が無い部分（attr20 の新規 15 seed × 5 条件）は planned
上限で計上——予算の目的（B1）に対して安全側。再構成前後: dense 375.4M → 410.4M、
robustness 176.9M → 191.0M、coarse 不変。全 tier cap 内。audits を lock 下で再記録。
(3) **意思決定影響の有界化**（数値の修正と判定の非汚染証明は別の言明）: 汚染
ウィンドウ中に gate を通過した run を列挙し、真値（再構成）のピークが全 tier で
cap を恒常的に下回る（739/410/191M vs 1G）こと＝観測値がいくら過小でも誤通過は
論理的に発生し得ず、refusals 0 件ゆえ誤拒否も無いことを ledger の audit entry に
記録（`decision-impact bounding`）。二大 reconciliation（739.2M / 120.8M）の生存は
artifacts 照合で確認（coarse 再構成値が pilot2+coarse.csv と厳密一致）。
(4) **根治 = 台帳の追記化**: lock は対症療法で、根本原因は可変状態の丸ごと
read-modify-write。charge/refund/reconcile/audit を**追記専用 journal**
（`budget.journal.jsonl`、1 行 1 イベント）として記録し、spent は journal の fold
として導出（`rebuild_spent`）、snapshot はキャッシュへ格下げ（`verify` で一致を
機械検査、snapshot 破損→journal 復元の回帰テスト付き）。lost update は型として
起き得なくなり、再構成は例外処理ではなく通常動作になった。

**教訓**: 単一書き手の仮定は守られない——強制されていない不変条件は incident の
予約である（キー衝突と同型）。復旧を可能にしたのは今回も決定論＋artifacts
（periods_total の永続化）だった。一般化:
**スナップショット上書きは台帳ではない——台帳とは追記ログのことである。**

## 関連

- 修正 commit: `990eddc`（schema + テスト + 文言確定）／ 精算: `results/budget.json`
  reconciliations[1]・audits ／ 凍結: `prereg-tier3.md` §2.1 注記・§2.5
