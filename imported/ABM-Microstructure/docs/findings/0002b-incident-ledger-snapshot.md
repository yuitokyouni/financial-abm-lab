# Incident 0002b — ledger スナップショット上書きによる lost update（2026-06-11）

**性格**: 0002a（同一性キー≠表示キー）と同日の第2の自己検出。**別の教訓**を持つ
独立 exhibit——「スナップショット上書きは台帳ではない」。whitepaper「検査自体の
信頼性」節の第2事例。

## 事象

BudgetLedger は読み込んだ JSON を更新のたび丸ごと書き戻す（last-writer-wins）
設計で、単一書き手を暗黙に仮定していた。並行 background run（Tier-3 / bcs_per_seed /
attribution）が同一 ledger を共有した結果、**監査 entry（audits[0]）が消え、charge も
lost update していた**（再構成で dense +35.0M、robustness +14.1M の計上漏れが判明）。

## 検出

外部レビューの要求（audits への一行追記）を実行しようとして KeyError——
書いたはずの audits[0] が存在しない、という形で表面化。監査記録自体が消えたことが
検出器になった。

## 対応（時系列）

1. **直列化（対症）**: lock file + read-modify-write で全更新を直列化
   （`BudgetLedger._locked`）、回帰テスト追加（並行 instance の charge 合算と
   audits 生存）。
2. **再構成**: 全 tier の spent を **artifacts から決定論的に再構成**: 各 CSV の
   periods_total は per-run の実消費を持ち、attribution の再計算 run は D-B12 により
   既存 run と同一（density/tier3 の値をそのまま流用可能）。唯一実測が無い部分
   （attr20 の新規 15 seed × 5 条件）は planned 上限で計上——予算の目的（B1）に
   対して安全側。全 tier cap 内。audits を lock 下で再記録。
3. **意思決定影響の有界化**（数値の修正と判定の非汚染証明は別の言明）: 汚染
   ウィンドウ中に gate を通過した run を列挙し、真値（再構成）のピークが全 tier で
   cap を恒常的に下回る（739/410/191M vs 1G）こと＝観測値がいくら過小でも誤通過は
   論理的に発生し得ず、refusals 0 件ゆえ誤拒否も無いことを ledger の audit entry に
   記録（`decision-impact bounding`）。証明は Δ の大きさ・出自に依存しない。
4. **根治 = 台帳の追記化**: lock は対症療法で、根本原因は可変状態の丸ごと
   read-modify-write。charge/refund/reconcile/audit を**追記専用 journal**
   （`budget.journal.jsonl`、1 行 1 イベント）として記録し、spent は journal の fold
   として導出（`rebuild_spent`）、snapshot はキャッシュへ格下げ（`verify` で一致を
   機械検査、snapshot 破損→journal 復元の回帰テスト付き）。lost update は型として
   起き得なくなり、再構成は例外処理ではなく通常動作になった。

## 差分表（snapshot 観測値 vs artifacts 再構成値、forensic）

| tier | 観測（再構成前） | 再構成 | Δ | Δ の帰属 |
|---|---|---|---|---|
| coarse | 739,236,803 | 739,236,803 | 0 | 汚染ウィンドウ中の更新なし |
| dense | 375,424,143 | 410,444,094 | **+35,019,951** | 喪失 event ＋ attr20 未実測 75 run の planned 上限計上（保守側余剰 ≥ 0）の**混合**。journal 導入前ゆえ event 単位の分解は不能——これ自体が追記台帳の論拠 |
| robustness | 176,910,853 | 190,981,553 | **+14,070,700** | **純粋な lost update**（全成分が厳密: bcs.csv 60,303,000 + tier3.csv 110,577,553 + bcs_per_seed 20,101,000=非収束で planned=actual）。charge 約 7 event 相当が tier3×bcs_per_seed の interleave で喪失 |

報告系列との照合: 「dense 197M」= attr20 投入前（density+attr5 = 196,752,058、これは
再構成でも不変）。「robustness 211M」= tier3 の planned 見積り（60+151M）であって
実測系列ではない——実測は tier3 の早期収束 refund で 110.6M に縮み、bcs_per_seed
20.1M が加わって 191.0M。全 Δ が正（観測の過小）なのは「charge 喪失 > refund 喪失」
と整合（charge は 2.01M/event と大きく、refund は早期収束分のみで小さい）。

## 教訓

単一書き手の仮定は守られない——強制されていない不変条件は incident の予約である
（0002a のキー衝突と同型の発生機序だが、教訓は別）。復旧を可能にしたのは今回も
決定論＋artifacts（periods_total の永続化）だった。一般化:
**スナップショット上書きは台帳ではない——台帳とは追記ログのことである。**

## 関連

- 同日の第1 incident: `0002a-incident-tier3-key-collision.md`（同一性キー≠表示キー）
- 実装: `src/microstructure/designmap.py::BudgetLedger`（journal/rebuild_spent/verify）
- 監査記録: `results/budget.json` audits（reconstruction / decision-impact bounding）
