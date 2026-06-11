# 事前登録 — density spoke の解釈規則（P2 移植可能性監査・主結果）

**登録日**: 2026-06-11（OSF registration: https://osf.io/63pj2/ — Open-Ended Registration、
public、本ファイル添付・git commit `3cad65f` 参照。結果生成前に登録済み）
**登録時点で density spoke の結果は一切生成されていない**（後述 §5 の開示参照）。
本書の判定基準・縮退規則は登録後変更しない。変更が必要になった場合は amendment として
OSF 側に記録し、versioned に切り直す（サイレント編集禁止）。

## 1. 主張（この実験が判定するもの）

P2 目標文（`docs/research-design.md` §9.1）の節 (ii)：

> 行動レベル（greedy limit-cycle）で認定可能な共謀 regime は事象密度 × 学習率空間の
> 特定領域に限られる——あるいは tabular 予算内に存在しない。

## 2. 実験設計（固定済み・実行前）

- **セル**: 中心セル `cont-committed-lam5-J1-fee0-mem1-n2-qlearning`（baseline）から、
  (noise_rate ν, lr) ∈ {(10, 0.02), (30, 0.02), (30, 0.15)} × 6 条件
  {cont, batch5, batch20} × {committed, revisable} = **18 セル × 5 seed**。
  実装: `src/microstructure/designmap.py::density_spoke`（コードが定義の一次ソース）。
- **設計根拠**（事前に記録済み）: SNR ∝ √pn/√lr。(ν=30, lr=0.02) で隣接 arm の
  利得ギャップ/Q ノイズ ≈ 2.7 となり cycle 収束が物理的に可能。(30, 0.15) は lr の
  寄与を分離する対照。(10, 0.02) は中間点。finding 0002 / research.md D-B6 v2。
- **収束判定**: D-B6 v2 = greedy limit-cycle（10⁴ 期ごとの決定論 probe、連続 10 回不変）。
  t_max = 2×10⁶ 期。基準は結果を見て緩めない。
- **予算**: dense tier ≈ 1.81×10⁸ 期 ≤ cap 1×10⁹（D-B9）。ledger が機械 enforce。

## 3. 判定規則（機械適用・裁量なし）

1. **認定**: セルの認定は commit 時点の `src/microstructure/verdict.py::certify` を
   機械適用する（収束 + supra-Nash markup 有意 + impulse-response gate）。
   人手での再判定・基準の事後調整は行わない。
2. **「認定可能 regime が存在する」** ⟺ 18 セル中少なくとも 1 セルで certified=True。
3. **headline セルの選択規則**（複数認定時の cherry-picking 防止）:
   認定セルのうち**事象密度 ν が最小のもの**（最も現実に近い疎側）を headline とする。
   同 ν 内に複数あれば committed を revisable に優先し、batch interval の小さい方を取る。
4. **従の主張（batch 変調）**: 認定セルが存在する場合のみ、その (ν, lr) 上で
   Δ_total / Δ_GP / Δ_pred（`designmap.compare_conditions`、seed ペア差 ±2SE 分類）を主張する。
5. **報告様式**: 全指標 seed 横断 mean ± SE + n=5。単一 seed の数値は本文に出さない。

## 4. 縮退規則（結果が negative の場合に主張がどう縮むか）

- **認定ゼロの場合**: 主張 (ii) は「tabular 予算内（t_max=2×10⁶、表形式 Q/SARSA）に
  認定可能 regime は存在しない」という否定枝で立つ。Tier-3 robustness は
  「基準 v2 でも非収束が algo/HP 横断で再現する」ことの検査に充当する（D-B9 改定）。
  この枝でも P2 の主主張（移植可能性監査）は成立する——むしろ強まる。
- **lr 対照の解釈**: (30, 0.02) のみ認定・(30, 0.15) 非認定なら「疎報酬の障害は
  学習統計（平均化不足）を主成分とする」。両方認定なら密度そのものが支配的。
  (10, 0.02) の帰結は regime 境界の位置を与える。いずれの組合せも事前に解釈を固定した。
- **経済 vs 統計の分離の限界**（スコープの正直な明示）: 本 spoke は noise_rate と
  報酬密度が連動するため、Green-Porter 的「監視シグナルの疎さ」単独の効果は
  完全には分離できない。分離主張はしない（将来 feature の領分）。

## 5. 登録時点で存在するデータの開示

- **baseline 疎度の pilot**（2 seed × 4 条件、全て非収束ラベル）: finding 0002 の表。
  spoke の設計（SNR 算術）はこの pilot から導出された。
- **memory=0 の sanity run**: 同種の dense 設定で 6/6 seed 収束を確認済み（spoke が
  物理的に可能であることの根拠）。これは memory=0 であり本実験（memory=1）とは別物。
- **coarse 地図**（72 セル、実行中・部分完了）: 全て baseline 事象密度（ν=1）であり、
  spoke のセル（ν ∈ {10,30}）とは重ならない。spoke の結果は未生成。
- 本 repo の git 履歴（public、commit hash）が内部タイムスタンプとして本書に先行する。

## 6. 関連文書

- 主張構造: `docs/research-design.md` §9 ／ プログラム: `PROV-ABM-atlas/docs/program_claims_v1.md`
- 設計決定: `specs/002-exp-b-collusion-harness/research.md` D-B6 v2 / D-B9
- 発見の経緯: `docs/findings/0002-sparse-reward-convergence.md`
