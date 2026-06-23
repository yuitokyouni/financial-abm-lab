# 002 — YH007 大幅方針変更: リアル LOB × Kronos 戦略による SF 生成機構の同定

**状態: ドラフト (設計合意前)**。本 spec は `imported/speculation-game-info/experiments/YH007/`
の旧骨格(自己組織化 Speculation Game = Katahira & Chen 2021 の C 内生化再現)を
**supersede** する。旧 YH007 はコード未実装の骨格(README + PDF のみ)であり、本方針転換に
よる手戻りは無い。作業ブランチ `claude/yh007-policy-overhaul-h1rya4` はこの overhaul 用。

> 旧 YH007 の自己組織化 SG 系譜は破棄ではなく**凍結**。`imported/.../YH007/README.md` は
> 履歴として残す。本 spec が新 YH007 の ground truth。

---

## 0. 一行サマリ

**Kronos(K 線基盤モデル)を意思決定則に据えた異種エージェント群を、リアル化した
連続ダブルオークション(CDA)板の上で競争させ、stylized facts (SF) が *何の機構から*
生まれるかを ablation で同定する。** SG 系譜の往復取引(round-trip)・認知価格会計は捨て、
MG 系譜を逆流して $-game / GCMG 型の「毎バー・実価格結合 payoff」に置き換える。

---

## 1. 方針転換の本質 — 何を捨て、何を残すか

旧 SG 系譜(YH005/006)の中核 = **往復取引(open→hold→close)+ 認知価格 P で測る損益 ΔG**。
これが新目的(リアル LOB × Kronos)と構造的に衝突する:

- **損益が認知価格で測られ、実約定価格が ΔG に入らない**
  (`imported/.../docs/refs_sg_lob_code_semantics.md §3.3`)。→ LOB が「どの往復が完了するか」の
  *サンプリングゲート*に縮退し、価格生成器にならない。リアル LOB で Kronos に実価格を予測させる
  なら、損益は実約定に mark-to-market したい。
- **「凍結」病理**(同 §4): 往復が閉じない→ wealth 凍結→破産せず→ turnover ゼロ。往復会計固有の
  荷物で、Kronos とは無関係。

→ **往復・認知価格・funnel・凍結機構は丸ごと落とす。** MG 族の「競争による内生的 SF 創発」だけ残す。

MG 族の 3 層分解と本実験での扱い:

| 層 | SG/MG/GCMG の中身 | YH007 (新) での扱い |
|---|---|---|
| (a) 意思決定則 状態→行動 | 戦略ルックアップテーブル | **Kronos に置換** |
| (b) payoff / 淘汰構造 | SG = 往復の認知 P&L | **$-game / GCMG 型・毎バー実価格 payoff に再設計** |
| (c) 相互作用 / 創発機構 | minority / frustration | **残す(MG 系譜の価値そのもの)** |

「新規 MG 派生ゲーム」とは、実は **SG(MG の往復化末端派生)から一段戻り、$-game
(Andersen-Sornette 2003)/ GCMG(Jefferies et al. 2001)の毎ステップ価格結合 payoff に戻す**
ことに等しい。ゼロから作らない。

---

## 2. リサーチクエスチョン

> **Kronos 駆動のリアル LOB 市場で、stylized facts (fat tails, volatility clustering,
> 無相関リターン) は *何の機構*から生まれるのか。**

候補機構(対立仮説として ablation で切り分ける):

1. **板の流動性ゆらぎ**(Farmer-Gillemot-Lillo-Mike-Sen 2004): 大変化は大口注文ではなく
   板の *gap* で起きる。薄い瞬間に普通サイズの成行 → fat tail。
2. **order flow の長期記憶**(Bouchaud): 大口 parent の分割執行 → 符号付きフロー自己相関 →
   vol clustering。← **執行層**(§4.3)が直接効く。
3. **異種・適応・可変参加の生態**(GCMG grand-canonical / Lux-Marchesi switching):
   取引者数の変動それ自体が vol clustering の源。
4. **捕食的流動性消費**(新規参入の注文を食う; Brunnermeier-Pedersen 2005): 増幅器仮説。
5. **見せ板 / spoofing**(layering): 増幅器仮説。

econophysics の通説では (1)(2)(3) が頑健な「生成器」、(4)(5) は「増幅器」(SF は spoofing
登場前・電子化前から普遍)。**本実験の価値は、(4)(5) をユーザ仮説として (1)(2)(3) と並べ、
Kronos 市場で実際にどれが効くかを同定する点**にある。

---

## 3. アーキテクチャ — 3 層分離

`refs_execution_algorithms.md §9.4` の「執行層を別レイヤで挟む」設計を踏襲:

```
[戦略層]  Kronos: 直近 K 線列 → 次バーの予測分布 → 売買方向 + 確信度
   ↓ parent order (方向, サイズ)
[執行層]  parent → child schedule (TWAP/POV/IS)   ← 現 design A' に欠落(機構 2 の標的)
   ↓ child orders (MARKET / LIMIT)
[LOB 層]  PAMS CDA 板 + 流動性供給層   ← YH006_1 から流用、LIMIT/queue/impact でリアル化
```

3 層を分離する理由 = 機構 ablation のため(各層を独立に on/off して SF への寄与を切り分ける)。

---

## 4. コンポーネント設計

### 4.1 Kronos = 意思決定則(ローソクのみ)

- 入力は OHLCV バーのみ(板・フローは見ない)。これは弱点であると同時に、**板を見る非 Kronos
  agent(MM・捕食・見せ板)に固有のニッチを与える**(Kronos の盲点 = 彼らの飯のタネ)。
- バー集約レイヤ必須: LOB の tick/event 列 → OHLCV バー(「N step = 1 バー」を決める)。
- 出力は確率予測(次バー分布)。**mode ではなく sample** を引いて確信度を測る。

### 4.2 ① 同じ Kronos 出力を 2 通りに読む(順張り/逆張りの遺伝子)

単一基盤モデルから fund/chart 二分法を導出する(手書き fundamentalist を足さない):

- **順張り (chartist)**: 予測の *ドリフト方向*(分布中心のシフト)に賭ける。
- **逆張り (contrarian / fundamentalist)**: 予測の *中心値を fair value* とみなし、
  **現在価格の fair value からの乖離を fade** する(price > Kronos 想定 → 売り)。

→ 「Kronos が間違ってると思う agent」という人工的定義を避け、**読み方の違い**だけで
逆張りを生む。これが「Kronos だけだと全員同じ出力」縮退への直接の解。

補助的な逆張り源(遺伝子の多様化):
- **インベントリ駆動 MM**(Avellaneda-Stoikov): 信念ゼロでも在庫リスクで mean-revert。
  既存 MMFCN(fundamental 寄り)が種。
- horizon / lookback 多様性(長 lookback は回帰、短は momentum を予測しやすい)。

### 4.3 (b) payoff = $-game / GCMG 型・毎バー実価格結合

- GCMG(`packages/abm_models/gcmg/`)を fork。signed rolling-window スコア + **参加閾値 r_min
  (abstain 可能)** をそのまま使う。
- **decide() を Kronos 条件付きに差し替え**、Kronos の **確信度を参加ゲート r_min に流す**
  (低確信 → abstain)。GCMG の参加機構 ↔ Kronos confidence の自然な結婚。
- **payoff を認知価格でなく実約定/実バーリターンに mark**。これで LOB が「ゲート」から
  「因果」に昇格(= リアル化の本丸)。$-game payoff ≈ a_i(t−1)·r(t)。

### 4.4 ④ 淘汰が逆張り比率を内生決定

逆張りを手チューニングしない。順張り過多で価格が行き過ぎると fade した逆張りが儲かる →
GCMG の payoff 選択が逆張り個体群を**ニッチとして内生維持**。①〜が遺伝子を供給、④ が混合比を
決める。**逆張り比率は外生パラメータでなく観測量**(どんな市場条件で逆張りが増えるか)。

### 4.5 LOB リアル化(直交 2 軸)

1. **執行・注文タイプ軸**: 単発成行 → LIMIT/queue/分割執行/square-root impact(機構 2)。
2. **時間軸**: 離散同期ラウンド → (任意)非同期イベント駆動。Kronos はバー単位 = 離散と相性が
   良いので、**まず軸 1 に振り、軸 2 は後段**(YH007-後半)。

> 現状確認: 既存 LOB は PAMS の整数ステップ同期ラウンド(`configs/_base.py:53-70`)。
> マッチングは CDA(連続)だが時間軸は離散。「連続」の 2 義に注意。

---

## 5. サブ実験分割 (YH007-1, -2, …) — YH006_1 流儀

1 サブ実験 = 1 機構の検証。bit-parity は要求しない(各サブで疎通テストのみ)。

| ID | 主題 | 検証内容 |
|---|---|---|
| **YH007-1** ✅ | ① 最小実装 (aggregate) | Kronos 2 読みで順張り/逆張りが分岐するか。板無し即時 clearing で疎通。**実装済** (`packages/abm_models/abm_models/kronos_aggregate/`, `experiments/speculation_game/yh007_1_aggregate.py`, tests 5/5 GREEN, 実 Kronos 閉ループ smoke 5 step 0.68s で trend mean=+0.2 / fade mean=-0.2 = 逆符号 ✓)。 |
| **YH007-2** ✅ | LOB 化 | YH007-1 を PAMS CDA 板に乗せる。実約定 payoff。SF が出るか(baseline)。**実装済** (`packages/abm_models/abm_models/kronos_lob/`, `experiments/speculation_game/yh007_2_lob.py`, tests 4/4 GREEN)。**baseline 結果 (mock 11 min, 220 bar): SF は出ない** (Hill α=8.97, vol_acf τ=50≈0, ret_acf τ=1=-0.47 = bid-ask bounce 支配)。これは想定通り = 機構 ablation の出発点。実 Kronos 閉ループ smoke (n=30 bar, 79s) では Hill α=2.51 で fat tail だが短時系列で値が不安定。 |
| **YH007-3** ✅ | ④ 内生混合 | GCMG 参加ゲート × payoff 選択で逆張り比率が内生決定されるか。**実装済** (`kronos_lob/adaptive_agent.py`, tests 5/5 GREEN)。**baseline 結果 (mock 9 min, 40 adaptive, T=50)**: strategy mix が時系列で変動 (trend 98.4% / fade 1.5% / abst 0.1%, std=0.12) = 内生混合 ✓。**vol_acf τ=50 が YH007-2 の -0.024 から +0.059 へ改善** (vol clustering 指標が初めて正に)。Hill α=8.36 (fat tail まだ ✗), ret_acf τ=1=-0.67 (bid-ask bounce 残)。 |
| **YH007-4** | 執行層 (機構 2) | parent→child 分割執行を on/off。長期記憶フロー → vol clustering 寄与。 |
| **YH007-5** | 流動性ゆらぎ (機構 1) | 板 depth を厚/薄で振る。gap → fat tail 寄与。 |
| **YH007-6** | 捕食 agent (機構 4) | 新規注文を食う agent を on/off。増幅器仮説の検証。 |
| **YH007-7** | 見せ板 agent (機構 5) | layering/spoofing agent を on/off。増幅器仮説の検証。 |

(順序・粒度は実装しながら調整。YH007-1→3 が背骨、4 以降が機構 ablation。)

---

## 6. インフラ現実(本ブランチで実測済み)

このセッションのクラウド環境 = **Linux コンテナ**(ユーザの Windows 端末でも Mac でもない)。
実測結果:

| 項目 | 結果 | 含意 |
|---|---|---|
| PAMS 0.2.2 | ✓ PyPI から install、YH006 が使う全 API import OK | **「PAMS は Mac 限定」は思い込み。Linux で動く** |
| YH006 LOB smoke (前回計測) | ✓ end-to-end 完走 1.3s (submits=572, RT=238, subs=7) | PAMS CDA 基盤はこの環境で稼働 |
| torch 2.12.1+cpu | ✓ install & CPU 推論 OK(CUDA 無し) | torch 自体は問題なし |
| **HuggingFace API** | **✓ `huggingface.co` HTTP 200/307**(2026-06-23 ネットワーク Full 化で開通) | API/メタデータ取得は可 |
| HF LFS CDN | ✗ `cdn-lfs.huggingface.co` は DNS 解決不可(継続) | LFS 経由のモデルは落ちない |
| **Kronos weights 取得** | ✓ Tokenizer-base 16MB を 0.9s, Kronos-small 99MB を 3.5s で完走 | NeoQuasar/Kronos-* 全リポが LFS 未使用(`lfs=False`)で CDN を経由しない |
| **Kronos 実推論 (CPU)** | ✓ `KronosPredictor.predict` 動作。Tokenizer load 1.94s + Kronos-small load 3.64s (24.7M params, fp32, 4 threads) | ループ前に 1 度だけ払う固定費 |
| **推論レイテンシ (pred_len=1, lookback=128)** | sample_count=1: **≈ 100 ms**, =4: ≈ 300 ms, =16: **≈ 1.0〜1.5 s** | 並列 CPU 4 thread, fp32, 2 run 中央値。再現: `experiments/speculation_game/yh007_kronos_smoke.py`。詳細は §7 地雷 4 |

→ **Kronos 実行はこのクラウド環境で可能**(NeoQuasar の Kronos リポが LFS を使っていない間)。
当初検討した選択肢の現状評価:

- **(A) ネットワークポリシー変更**: 不要(現状 `huggingface.co` 自体は通る)。将来 Kronos が LFS に
  移行したら `cdn-lfs.huggingface.co` の allowlist 追加が要る。
- **(B) weights を vendor**: 不要。`KronosTokenizer.from_pretrained(...) / Kronos.from_pretrained(...)` で直接ロード可。
- **(C) 役割分担**: 不要。クラウドで閉ループ実行可能。
- **(D) 外生シグナル設計**: 閉ループ要件なら採らない(従来通り)。

**監視点**: NeoQuasar 側が将来 weights を LFS に乗せ替えた場合、CDN ブロックが直撃する。
モデル取得は CI/setup で fail-fast にして検出可能にする(`hf_hub_download` の戻りサイズ確認)。

> MultiAgent-Trader 側の既存 Kronos 統合は参考として残すが、本リポ内で `shiyu-coder/Kronos`
> の `KronosPredictor` から直接ロードできるので必須ではない。ロード作法のスニペット共有は
> 「あれば便利」レベルに格下げ。

---

## 7. 設計地雷(spec 確定前に決定が要る)

1. **Kronos 実行モード = 閉ループ vs 外生**:
   - 閉ループ(Kronos が *シミュレート価格* を条件付け)→ ループ内ライブ推論必須。§6 の通り
     weights 取得 ✓ / CPU 推論 ✓ で技術的には実行可能。研究問い「Kronos 市場の SF 生成機構」に忠実。
   - 外生(Kronos が *実履歴* を条件付け、事前計算)→ 軽いが Kronos が「外生情報注入器」になり
     問いが変わる。閉ループ要件なら不採用。
2. **zero-shot 転移**: Kronos は *実市場*学習済み。sim 内投入は分布シフト下の zero-shot。
   sim 上 fine-tune は「自分の生成価格で自分を学習」する循環。**較正環境≠実行環境**問題
   (`refs_execution_algorithms.md §8` の square-root 係数ズレ、YH006 の c_ticks self-consistency
   と同型)。SF 創発が *ゲームの frustration* 由来か *Kronos の群れ* 由来か識別できる設計に。
3. **ゲームの役割**: (i) Kronos 変種個体群への*淘汰圧* か (ii) Kronos を特徴量に使う*alpha 生成
   相互作用* か。論文が変わる。**未決(ユーザ確認事項)**。
4. **計算コスト**: N agent × T step のループ内推論。§6 実測値で見積もり可:

   - 全 agent **共有 1 シグナル + 異種解釈**: T × 1 × t_pred。sample_count=1 (≈ 0.1s/step) なら
     T=1000 step で ≈ 100s(<2 min)。sample_count=16 (≈ 1.5s/step) で T=1000 が ≈ 25 min。
     → **CPU 閉ループ実行は十分現実的**。
   - Agent **別推論**: N × T × t_pred。N=50, T=1000, sample_count=1 で ≈ 80 min。
     sample_count=16 で ≈ 21 h。→ 同一信号の共有が暗黙の要請。「異質性は信号でなく **読み方**
     (§4.2) に出す」設計はレイテンシ的にも正当化される。
   - 並列化余地: torch.set_num_threads, 複数 sample のバッチ化(`auto_regressive_inference`
     内の vectorization)。CUDA があれば桁違いに高速だが、ここは無いので CPU 前提で組む。

---

## 8. 受け入れ基準(暫定、サブ実験ごとに精緻化)

- **YH007-1** ✅ **達成 (2026-06-23)**: 同一 Kronos 予測から順張り/逆張りの 2 行動が決定論的に分岐する(seed 固定で再現)。
  実 Kronos 閉ループ 5 step = **0.68s (≈ 136 ms/step)**(§7 地雷 4 の見積もり ≈ 100 ms/step とほぼ一致)、
  **drift が時間変化し fade が完全に逆符号**を確認。
- **YH007-2/3**: 実約定 payoff の LOB で SF が出る — fat tail(Hill α ∈ [2,5] 目安)、
  vol clustering(|r| ACF が τ=50 で正、緩減衰)、リターン無相関。
  - **YH007-2 baseline (機構なし、対称構成 25 trend + 25 fade) では 3/3 ✗** (Hill α=8.97 mock, vol_acf τ=50≈0, ret_acf τ=1=-0.47 = bid-ask bounce)。**これが ablation の出発点**: YH007-3 以降の機構追加で各指標がどう動くかを観察する。
- **機構 ablation (YH007-4〜7)**: 各機構の on/off で SF 指標が有意に動くか。
  **「どの機構を切ると SF が消えるか」が主要アウトプット**。
- 全サブ実験: config 駆動(README Appendix の fabm 規約)、multi-seed、結果を table 保存
  (`run_id, git_commit, config, seed, params, metrics, artifact_paths`)。

---

## 9. 既存資産の流用マップ

| 必要物 | 流用元 |
|---|---|
| CDA 板 + agent 基盤 | PAMS 0.2.2(install 確認済み) |
| LOB SG agent パターン(reconcile, 2-account, self-cancel, guard) | `imported/.../YH006/speculation_agent.py` |
| 流動性供給層 | `imported/.../YH006/mm_fcn_agent.py`(MMFCN) |
| ゲーム payoff / 参加ゲート | `packages/abm_models/gcmg/model.py`(signed score + r_min) |
| MG 系基盤 | `packages/abm_models/minority_game/model.py` |
| 古典 fund/chart 参照 | `packages/abm_models/{chiarella_iori,lux_marchesi,franke_westerhoff}/` |
| SF battery | `packages/stylized_facts/` |
| 執行理論 | `imported/.../docs/refs_execution_algorithms.md`(§9.4 が設計済み) |
| Kronos 戦略層 | `shiyu-coder/Kronos`(`model.kronos.{Kronos,KronosTokenizer,KronosPredictor}`、master ブランチ) + NeoQuasar/Kronos-* weights。本リポでは scratchpad / vendored クローンに置き PYTHONPATH 経由で参照、または `pip install git+https://...` で導入(設計確定後) |
| Kronos 統合パターン参考 | MultiAgent-Trader(別リポ、要スニペット共有 — 必須ではない) |

---

## 10. 未解決(ユーザ確認事項)

1. **ゲームの役割**(地雷 3): 淘汰圧 か alpha 生成相互作用 か。← spec の背骨を決める。
2. **Kronos 実行モード**(地雷 1): 閉ループ か 外生キャッシュ か(§6 の通り weights 取得・
   推論コストはクラウドで成立、ネットワークポリシー変更も現状不要)。
3. **LOB リアル化の範囲**(§4.5): 軸 1 のみ か 軸 1+2 か。
4. **MultiAgent-Trader の Kronos ロード方法**: あれば参考、無くても可
   (`KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base')` +
   `Kronos.from_pretrained('NeoQuasar/Kronos-small')` → `KronosPredictor` で直接ロード可能)。

---

## 改訂履歴
| 日付 | 内容 |
|---|---|
| 2026-06-22 | 初版ドラフト。旧 YH007(自己組織化 SG)を supersede。リアル LOB × Kronos × $-game/GCMG、機構 ablation 設計、サブ実験分割、インフラ実測(PAMS✓/torch✓/HF✗)、設計地雷。 |
| 2026-06-23 | §6 全面更新: ネットワーク Full 化で HF API 200 復活 + NeoQuasar/Kronos-* が LFS 未使用 → Kronos-Tokenizer-base/Kronos-small の実 weights 直接 download 完走を実測。CPU 推論レイテンシ計測 (sample_count=1: ≈ 100 ms, =16: ≈ 1.0〜1.5 s, 4 thread, fp32)。再現スクリプト `experiments/speculation_game/yh007_kronos_smoke.py` 追加 + gitignore に `.venv-yh007/`。§7 地雷 4 をレイテンシ実測値で書換 (共有信号アーキ → CPU 閉ループ実行が現実的)。地雷 1・未解決 2/4 を整合反映。§9 流用マップに `shiyu-coder/Kronos` の `KronosPredictor` 経由ロードを追記。 |
| 2026-06-23 | ユーザ確認: Game 役割 = (i) alpha 生成相互作用 (YH007-1〜2), Kronos モード = 閉ループ, LOB 範囲 = 軸 1 のみ。**YH007-1 実装完了** (`abm_models/kronos_aggregate/` + experiment + tests)。同一 Kronos 信号 → Trend/Fade が決定論的に逆符号 (mock 5/5 GREEN, 実 Kronos 閉ループ 5 step smoke OK)。§5 表に ✅ マーク + 既定 backend 切替 (mock/kronos)。 |
| 2026-06-23 | 実 Kronos 閉ループ 5 step = **0.68s (≈ 136 ms/step)** を実測 — §7 地雷 4 のレイテンシ見積もり (≈ 100 ms/step, sample_count=1) とほぼ一致。drift が時間変化 + fade が完全に逆符号を確認し、**§8 YH007-1 の受け入れ基準を達成**(§8 に ✅ 反映)。 |
| 2026-06-23 | **YH007-2 実装完了** (`abm_models/kronos_lob/`: bar_aggregator + signal_hub + agents + model, tests 4/4 GREEN, 既存 14 件 regression なし)。PAMS CDA + MMFCN (流動性供給, YH006 流用) + Kronos shared-signal × 2-reading × 共有信号 hub × bar 集約。mock baseline (warmup=200 + main=2000 step, bar_size=10, 220 bar, 11 min): **SF は出ない** (Hill α=8.97, vol_acf τ=50≈0, ret_acf τ=1=-0.47 = bid-ask bounce 支配)。実 Kronos 閉ループ smoke (warmup=100 + main=200, n=30 bar, 79s): Hill α=2.51 だが短時系列で値不安定。**この結果は機構 ablation の出発点 = baseline**。§5/§8 を反映。 |
| 2026-06-23 | **YH007-3 実装完了** (`abm_models/kronos_lob/adaptive_agent.py`: KronosAdaptiveAgent, tests 5/5 GREEN, 全 23 件 regression GREEN)。両戦略 (Trend/Fade) を保持し rolling payoff score (T-window) で高い方を選択、参加閾値 r_min を Kronos 確信度連動。mock baseline (n_adaptive=40, T=50, 220 bar, 9 min): strategy mix が時系列で変動 (trend 98.4% / fade 1.5% / abst 0.1%, std=0.12) = **内生混合 ✓**。**vol_acf τ=50 が YH007-2 baseline の -0.024 から +0.059 へ改善 ✓** (vol clustering 指標が初めて正に)。Hill α=8.36 (fat tail まだ ✗), ret_acf τ=1=-0.67 (bid-ask bounce, MARKET_ORDER 構成由来で execution 層で改善する想定)。実 Kronos smoke (N=30, T=30, 200 step, 60s) も完走、trend dominant 98.6%。§5 表に ✅。 |
