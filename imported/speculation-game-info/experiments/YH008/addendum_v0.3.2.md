# Stage 0 + 実装ハードニング addendum（v0.3.2 — 最新・正本）

> **関係:** 本体「Stage1-3_ClaudeCode_implementation_brief」の **§7・§8 を置き換え**、**Stage 1 の前に Stage 0 を挿入**する。2ラウンドのレビュー指摘の実体を畳み込み、RTX 4090 / Max x20 の計算エンベロープを明文化。本文（Stage 0 + ハードニング = 旧 v0.3.1）に末尾「Final: しきい値解決とメタルール（v0.3.2）」を統合した版。**これが最新・正本。** CCにはブリーフ本体と一緒に渡す。

---

## Stage 0 — smoke test + threshold pilot（NEW、Stage 1 の前に必ず実行）

**目的:** (a) インフラ確認、(b) nuisance knob の経験的設定、(c) gate しきい値を定義する null 分布の測定。

### 0.1 インフラ smoke test（指摘#1）

- HF gated access token（meta-llama）を準備。
- **Llama-3.1-8B-Instruct を TransformerLens（bf16）でロード。4090/24GB の唯一の実リスク:** TL の重み変換は一時的に約2倍メモリを食い、16GB の重みが24GBに迫る。
  - ロードが OOM したら順に: (i) bf16 + `from_pretrained_no_processing`、(ii) CPU で変換 → GPU へ転送、(iii) **nnsight にフォールバック**（HFモデル直ラップ、メモリ倹約）。
  - peak VRAM を記録。
- 1プロンプトで forward + `run_with_cache`。residual-stream hook 点へのアクセスを確認。**1 forward の wallclock と cache VRAM を実測**。
- **選択的キャッシュを検証:** decision位置の resid だけを層ごとに保存（~0.5MB/state）、フルcacheは破棄。これを守れば数千状態でもディスク数GB・VRAM単一forward分で収まる。

### 0.2 decision位置 / is_buy トークン化の仕様（固定判断2の急所、指摘#2）

- tokenizer を調べる: `True`/`False`/` True`/` False`/`true` がどう分割されるか。
- **`P(sell) = P(is_buy=False)` を「decision位置で True を綴るトークン群 vs False を綴るトークン群の確率質量」として定義。** 該当する変種トークンを合算。
- **その logit を読む位置（= 構造スロット `"is_buy": "` 直後）の residual を cache。自己回帰生成はしない。**
- 数状態で smoke-test: モデルがそのスロットで parseable な True/False を安定して出すか。出さないなら clean-probe フォーマットを調整（例: 強制選択形式 `Answer SELL or BUY:`、constrained decoding）して decision トークンを well-defined にする。

### 0.3 threshold pilot（指摘#3 を解決 + pre-commit と両立）

**exploration 状態セット上で**（held-out とは交わらない）:

- **α grid:** 暫定 {±2, ±4, ±8, ±16} × (典型 resid ノルムの一定割合)。単調な dose-response が出なければ拡張。可変・sweep対象。
- **候補層:** 全層 sweep。v_ATH steering が `P(sell|ATH)` を動かす層を特定。可変。
- **ATH近傍 binning / サンプリング範囲:** FCLAgent §4.1 のパラメータ（初期価格300 等）を中心に、含み益/損・近傍/非近傍を両方カバーする幅で設定。
- **null 分布の測定（指摘#4 を畳み込む）:** ノルム一致の **ランダム方向 K本** の KO が ATH非対称に与える効果分布を測る。**この null が gate しきい値を定義する。**

### 0.4 gate 基準 = null 相対（経験的設定と pre-registration の両立点）

**gate ルールはここで凍結する。held-out 確認の前に。**

- **Gate 1 PASS ⟺** KO(v_ATH) の ATH非対称低下が、KO(random direction) 低下の **95パーセンタイルを超える**（効果が null を超える）。
- **Gate 2（specificity）⟺** KO(v_ATH) の fundamental感応 / 一様売り / hold・cash への影響が **null の範囲内**に収まる。
- **Gate 3（rescue）⟺** Rescue が WT の **X% 以内**に戻る（X はここで凍結）。

**しきい値の数値は pilot の null から来るが、ルール（null相対）は held-out 結果を見た後に一切触らない。** これが「閾値を経験的に決める」と「pre-registration」の共存の仕方:**exploration データで規則を決めるのは可、held-out データで規則を決めるのは不可。**

---

## held-out 分離プロトコル（指摘#5）

- 状態アンサンブルを **解析前に・固定seedで** exploration / held-out に分割。
- v_ATH 同定（§5.3）、層 sweep（§5.5）、α grid、gate しきい値較正: **全て exploration のみ**で。
- **層 sweep の多重検定:** exploration 上で「最良層」を選ぶのは可（model selection）。選ばれた層 + 凍結 α + 凍結 gate ルールを、**held-out で一回だけ**評価。held-out を確認的結果、exploration を探索的結果として報告。
- held-out 状態は、v_ATH 構築に使った exploration の paired-state と `(current price, purchase, ATH)` タプルを共有しないこと。

---

## random-direction control（指摘#4）— primary に昇格

Gate 1 と**並べて**報告:
- KO(v_ATH) 効果 vs KO(ノルム一致ランダム方向) vs KO(named control: caution / pessimism / cash / fundamental / numeric / generic-sell)。
- **v_ATH は random を超え、かつ named control を超える**こと。これが specificity の中核証拠。「residual の任意方向を消せば売りが下がる」だけではないことを示す。

---

## behavioral faithfulness check（指摘#6、§4 失敗ブランチと統合）

- §3a の behavioral 変種を、**同じ exploration 状態で一度**走らせる。
- FCLAgent的挙動（PGR>PLR 方向、ATH非対称）が **behavioral 変種でも欠如** → baseline 減衰問題（Yee-Sharma ルート）→ §4 fallback（profile prompting / Gemma-2-9B）。
- behavioral では出るが **clean-probe では欠如** → clean-probe フォーマットが phenotype を殺した → **モデルでなくプローブ形式を直す**。
- この分岐判定を §4 の失敗ブランチに明示的に接続。

---

## run / artifact 規約（指摘#8）

- `outputs/{run_id}/{stage}/...`
- `run_id` = timestamp + git short-hash
- 各 run に同梱: `config.yaml` スナップショット、`git rev-parse HEAD`、`pip freeze`、モデルハッシュ、プロンプトハッシュ（両変種）、seed、保存方向テンソル（層ごと v_ATH、control、random 方向）
- **上書き禁止。Stage 間 checkpoint（長尺ジョブの途中再開）。** 落ちても致命的にしない。

---

## 計算エンベロープ（RTX 4090 / 24GB、orchestration は Max x20）

- **Stage 1-3 は 4090 で余裕。** 固定判断2（logit読み）= 各状態 **1 forward**（自己回帰生成なし）、single-turn = **市場ループなし**。見積: 数千状態 × {Stage1 1fwd / Stage2 1fwd・全層cache / Stage3 4条件+α grid} ≈ 低数万 forward ≈ **single-digit GPU時間**。
- **指摘#7 の「数十時間」はこのスコープに当たらない。** それが効くのは Stage 5-6（閉ループ ABM × 自己回帰判断 × 多seed）。4090 では足りない可能性が高いが、**後で渡る橋**。
- **RunPod:** RTX 4090 spot 1枚（~$0.3-0.7/hr）で Stage 0-3 完結。立てる → pilot + Stage 1-3 → artifact 保存 → 落とす。
- **予算ガード（CCセッション暴走防止、指摘#7）:** 1ジョブの最大 wallclock、最大リトライ回数を明示。§4 の「Gemma fallback」は **Stage 0 baseline が欠如し、かつ attenuation チェックを文書化した場合のみ**発火（気まぐれな別モデル試行を禁止）。

---

## FCLAgent 原論文 PDF（指摘#9、ブロッカー）

- renderer は §3a で Appendix A を参照するので、**`experiments/YH008/ABS_of_financial_market_with_LLM.pdf` がリポジトリに無いと書けない。** 実装セッションに渡す前にここで確認。

---

## あれば良い（落としても致命でない）

- **probing 手法のはしご（指摘#10）:** difference-in-means（MVP）→ linear probe / logistic（Stage 2 拡張）→ SAE（第2段階）。MVP は diff-in-means で確定、上位は順に硬くする。
- **負の結果ルート（指摘#11）:** Gate fail 時、§6 失敗ブランチ（subspace拡張 / 複数層 / 二重KO / dose-response）が尽きたら → v0.4 設計改訂（市場文脈プローブの見直し、別 reference 変数 S_purchase 先行、等）へ接続する一文を残す。

---

*Stage 0 を入れる最大の理由は二つ。(1) infra/tokenizer が落ちると実装初日で詰む（指摘#1・#2）。(2) 閾値を「flagで都度人間に訊く」ままだと実装セッションが Flag の嵐で停止する——pilot で nuisance knob を経験的に決め、gate ルールを null 相対で凍結すれば、自由な sweep と pre-registration が両立し、CC は止まらずに回る。*

---

## Final: しきい値解決とメタルール（v0.3.2）

### 統治メタルール（これが下記の約半分を subsume する）

**どの gate / filter しきい値も、事前推測の定数にしない。** 各しきい値は次のいずれか:
- **(a) 相対ルール:** Stage 0 が測る null（norm一致 random-direction KO）または WT-CI に対して定義。**ルールは今凍結、数値は Stage 0 が出す。**
- **(b) 較正出力:** Stage 0 の較正結果を held-out に触れる前に凍結。

**Stage 0 の成果物 = 凍結済みしきい値テーブル（frozen_thresholds.yaml）。** held-out 確認後はこのテーブルを一切変更しない。

### 今すぐ凍結（自明な値）

- **null K = 1000**（95パーセンタイルを seed 非依存に推定。最低 200、推奨 1000）。【指摘#4】
- **HF revision をピン留め:** `from_pretrained(..., revision="<sha>")` を `config.yaml` に。Llama-3.1-8B-Instruct は無告知で重みが差し替わる。モデルハッシュ保存だけだと事後検出しかできない。【指摘#8】

### 今すぐ追加（ルール1行 / エンジニアリング）

- **Gate 2（specificity）の null 化【指摘#1】:** specificity 3指標（fundamental感応 / 一様売り / hold·cash）**それぞれに** KO(random) の効果分布を Stage 0 で作る。pass = **各指標で v_ATH 効果が当該指標 null の中央95%以内**。3指標 AND（保守側、Bonferroni不要）。
- **Gate 3（Rescue）の導出原則【指摘#2】:** WT を K seed で bootstrap し ATH非対称の **95%CI** を作る。pass = **Rescue の ATH非対称が WT の 95%CI に重なる**。X% という magic number は使わない。
- **named control 構築レシピ【指摘#3】:** v_ATH と**同一 paired-state 方式・同一 N・抽出は v_ATH 最良層**。ただし各 control の**対比プロンプト中身**（pessimism ペア / caution ペア等の文面）は Stage 0 の作文タスク = **研究判断**。CC は draft し、人間が review（flag 対象）。
- **P(sell) 合算規約【指摘#5】:** decision位置で **True群トークン / False群トークンを logsumexp して2値正規化**。群外トークンは除外。**群外質量が閾値（暫定 >0.1）を超えたら flag**（probe形式の失敗）。群の具体トークン集合は Stage 0.2 で tokenizer を見て確定。
- **clean-probe 末尾構造【指摘#6】:** プロンプトを **`{"0": {"is_buy": "` まで literal 固定**し、次トークンを読む。Stage 0.2 で「次トークンが True/False を綴るトークンになる」ことを検証。ならなければ強制選択形式へ。
- **backend 中立 API【指摘#9】:** `model.py` に `cache(layer, position)` / `apply_direction_hook(layer, direction, mode)` を切り、**TransformerLens と nnsight を実装差し替え可能**に。fallback 発火で下流コードを書き直さないため。
- **Stage 0.5 baseline ゲート【指摘#10】:** exploration で baseline phenotype（disposition proxy >0、ATH非対称 >0）が**欠如したら、Stage 1 に進む前に §4 失敗ブランチへ分岐**。明文ゲート。

### Stage 0 が測って凍結（=穴ではなく設計。pre-freeze は禁止）

- 上記 Gate 1/2/3 の**数値しきい値**（null パーセンタイル、WT-CI 幅）。【#1・#2】
- **行動差フィルタしきい値【指摘#7】:** `|ΔP(sell)|` の閾値は、**P(sell) 測定ノイズ**（同一状態の反復評価で推定）より大きく取る。暫定 0.05、Stage 0 でノイズ相対に確定。
- **held-out n_min【指摘#11】:** exploration の効果量 + null SD から **80% power の最小 held-out 状態数**を Stage 0 末で簡易計算し、held-out ≥ n_min を保証。

---

*このv0.3.2で紙上ハードニングは完了とみなす。残る未確定は全て empirical（Stage 0 の出力）であり、紙の上では解けない。次の de-risk 情報は Stage 0 を 4090 で回すことからのみ出る。*