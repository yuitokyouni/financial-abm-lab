# CC タスク: YH008 Stage 2 — v_ATH 同定（loss-conditional、clean-probe canonical）

## 0. まず読む（権威ある仕様 + 直前の確定事項）

`experiments/YH008/`:
- `design_v0.3.pdf`
- `stage13_implementation_brief.md` §5（Stage 2 方法論本体）
- `addendum_v0.3.2.md`（held-out 分離 / named control 構築レシピ / artifact 規約 / null 相対メタルール）
- `outputs/20260529-131847_7de0bb4_P0_5/REPORT_v3.md`（直前判定: `PASS_STAGE2_LOSS_CONDITIONAL_CONFIRMED`）
- `outputs/20260529-120955_7de0bb4_P0/`（ATH バグ修正版 paired-state、disposition by framing）

既存 src は `experiments/YH008/src/`（render.py / model.py / states.py / metrics.py / config.yaml / run_*.py）。Stage 2 はこれを拡張する。

---

## 1. ライブで確定済みの事実（再導出しない）

直前 3 ラウンド（v1 / P0 / P0.5）の結果を所与とする:

- **GPU = A100-SXM4-80GB**、stack = TransformerLens 3.3.0 + nnsight 0.7.0、torch 2.11+cu130、HF token は次セッションで再投入
- **モデル**: `meta-llama/Llama-3.1-8B-Instruct`、revision pinned in `config.yaml`、**fp32**、TL load OK（〜200秒、VRAM 32GB）
- **canonical wording = `sec1_faithful`**（凍結、config.yaml `probe_canonical_wording`）
- **token 群**: `True`/`true`/`False`/`false` の id 凍結（全て単一トークン）、Yes/No/1/0 は除外、in-group mass ~e-5
- **ATH 構築ロジック**: 全状態で `ATH ≥ max(price, purchase)` を保証（P0 で states.py 修正済）
- **exploration / held-out 分割**: 固定 seed で確定。**Stage 2 は exploration のみ。held-out は Stage 3 ゲートまで温存**
- **probe**: chat_template + assistant prefix `{"0": {"is_buy": "` literal、群和 `P(sell)`、bit-exact 決定的、自己回帰生成なし
- **backend 中立 API**: `model.py` の `cache(layer, pos)` / `apply_direction_hook(...)` で TL / nnsight 差し替え可能

### Stage 1 phenotype（sec1_faithful canonical、bootstrap K=1000）

- **disposition proxy**: clean-probe **+0.0172** [+0.0102, +0.0249] / behavioral **+0.2599** [+0.2435, +0.2778] → **両 framing で正、頑健**
- **loss 文脈 ATH 非対称**: clean-probe 3 wording 全て正（+0.0107 / +0.0288 / +0.0277、CI が 0 を含まない）
- **gain 文脈 ATH 非対称**: null（unchanged）→ **v_ATH のターゲットにしない**
- **behavioral framing の ATH 反転**（−0.0704）は reason-gen artifact 確定 → **Stage 2 では使わない**

---

## 2. 固定された研究判断（再決定しない）

- **v_ATH は loss-conditional に同定**（gain 文脈の null を踏まえた gate 判定）
- **canonical wording = sec1_faithful のみ**、behavioral は除外
- **paired-state は ATH のみ振る**（同一 current price / purchase / unrealized gain、ATH ∈ {no-drawdown, drawdown}、P0 で確定したロジック）
- **probing 手法 = difference-in-means**（MVP、ブリーフ §5 確定）。SAE / linear probe は本 Stage 外
- **介入は活性層のみ**。プロンプト介入禁止
- **行動差フィルタ**: ATH を変えて `|ΔP(sell)| > τ` のペアのみを教師信号に使う。τ は Stage 0 で凍結された値（config.yaml）
- **control 構築 = v_ATH と同一 paired-state 方式・同一 N・抽出は v_ATH 最良層**（addendum §0.3.2 named control 構築レシピ）

---

## 3. スコープ（Stage 2 のみ）

### 3.1 paired-state 拡張

- 既存 113 ペア（P0/P0.5 で構築、loss 文脈・canonical wording）を再利用
- exploration 上で**行動差 pass ≥ 300 ペア**を確保するまで拡張
- **held-out paired-state は Stage 2 で構築しない / 触らない**（Stage 3 専用）

### 3.2 v_ATH 同定（diff-in-means、全層）

各 paired (S_drawdown=loss + ATH>price, S_no_drawdown=loss + ATH==max(price,purchase)) について:
1. 行動差フィルタ pass のペアのみを抽出
2. 全 32 層で decision 位置の `resid_post` を cache
3. `v_ATH[l] = mean(h_drawdown[l] − h_no_drawdown[l])` over filtered pairs
4. 正規化テンソル保存 → `directions/v_ATH_loss_perlayer.pt`

### 3.3 named control 同定（**着手前に prompt review が必要**）

6 control（caution / pessimism / cash preference / fundamental valuation / numeric sensitivity / generic-sell bias）について:

- **paired-state prompt は研究判断 → CC が draft → Yuito review → 承認後に着手**
- **着手前に止まって 6 control の paired-state spec を提示してレビューを受けること**
- 同じ paired-state 方式（一変数だけ振る）、N ≥ 200 ペア（v_ATH と同等規模）
- v_ATH と同じパイプラインで diff-in-means、全層で `v_control[l]` 構築
- `directions/v_<name>_perlayer.pt` に保存

### 3.4 random direction null

addendum §0.3 / §0.4 準拠:
- **K = 1000** のノルム一致ランダム方向を生成・保存
- 全層分: `directions/v_random_K1000_perlayer.pt`
- 後の Stage 3 ゲート判定で null 分布の base になる

### 3.5 cosine sim + 直交化（§5.4 step 1-2 のみ）

各層 l で:
- v_ATH[l] と 6 named control[l] の **cosine similarity マトリクス** → `cosine_matrix_perlayer.json`
- v_ATH[l] を control subspace で射影除去 → `v_ATH_orth[l]`、テンソル保存
- **step 3-4（micro phenotype effect の直交化前後比較 / held-out specificity）は Stage 3 で実施**（held-out を触らないため）

### 3.6 層 sweep（exploration model selection）

各層の v_ATH（および v_ATH_orth）で simple steering test:
- exploration の小サブセット（例 50 paired-state）で α=+1 の add-direction を試し、`P(sell|ATH drawdown)` がどれだけ動くか測定
- **α grid 本走は Stage 3**。ここは best-layer 候補を絞るための exploration model selection
- `layer_sweep.json` に結果保存
- 推定 best-layer を `selected_layer.json` で凍結

### 3.7 report

`REPORT_v4.md` に:
- 行動差 pass ペア数
- 各層 v_ATH の norm / 直交化前後 cosine
- 6 control の cosine vs v_ATH（マトリクス）
- 層 sweep の steering 効果（数値表で OK）
- best-layer 候補と理由
- 構築リスクの flag（特に control prompt の任意性、行動差フィルタ較正の安定性）

---

## 4. 停止条件・受け入れ

報告して**停止**:

1. control prompt の Yuito review を**着手前に**通過
2. paired-state 拡張完了、行動差 pass 数報告
3. v_ATH per-layer 同定、テンソル保存
4. 6 control per-layer 同定、テンソル保存
5. random direction K=1000 per-layer 保存
6. cosine matrix per-layer 保存
7. 層 sweep 結果報告、best-layer 候補凍結
8. 全 artifact 保存 + tarball 作成
9. **Stage 3（KO / Rescue / Amp gate）は作らない**。次ハンドオフで指示する

---

## 5. 規約・境界

- **run/artifact**: `outputs/{run_id}_stage2/...`、run_id = timestamp + git short-hash + `_stage2` suffix
- **/workspace quota 制約は健在**: コード・成果物は `/root/yh008_work/` 配下に書く。/workspace には**書かない**
- **held-out には触らない**: paired-state 構築、層 sweep、steering test 全て exploration 上
- **flag, don't guess**: control prompt（最大の研究判断）、行動差フィルタしきい値の再較正可否、層 sweep の best-layer 単一/複数の扱い
- **やらないこと**:
  - Stage 3 ゲート評価をしない
  - behavioral framing を使わない（reason-gen artifact）
  - held-out を触らない
  - gain 文脈で v_ATH を構築しない（null 確定済）
  - プロンプト介入をしない

---

## 6. 着手前 checklist（Yuito review 通過点）

1. **6 control の paired-state prompt draft** を提示
2. 各 control の paired-state spec（変える変数、固定する変数、N、想定される行動差方向）
3. paired-state 拡張で何ペア構築するかの見積もり（GPU 時間と合わせて）
4. /root の disk 余裕確認（per-layer cache + tarball 化方針）

これらを Yuito が OK したら着手。

---

## 7. 持ち帰り（commit/push フロー）

/workspace quota のため A100 側で git push 不可。完了時:

1. `/root/yh008_work/yh008_stage2.tgz` を作成（src 差分 + outputs/{run_id}_stage2/ + REPORT_v4.md）
2. sha256 を報告
3. JupyterLab で DL → Mac へ
4. Mac CC が `experiments/YH008/outputs/{run_id}_stage2/` 配下に展開 → ハッシュ照合 → commit & push

---

*Stage 2 の核心: (1) loss-conditional v_ATH を diff-in-means で同定、(2) named control の paired-state は研究判断で着手前 review 必須、(3) random null と合わせて Stage 3 ゲート判定の材料を揃える。Stage 3 は別ハンドオフ。*
