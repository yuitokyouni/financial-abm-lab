# Phase 0 Research — 実験A harness の技術判断

各項目 Decision / Rationale / Alternatives。非自明な判断は `docs/adr/` にも1枚残す候補。

## D1. 言語 = Python 3.13
- **Decision**: Python。
- **Rationale**: 環境既存、numpy で GBM/RNG/閉形式が簡潔、pytest で検証をそのまま成果物化。research-design §6 が「数百行規模」と言う通り、速度より監査性・可読性が要件。
- **Alternatives**: Julia/Rust（速いが、A の規模では over-engineering。B で grid が重くなったら hot path だけ移植を検討＝下流）。

## D2. ABM フレームワーク不使用（ADR 候補）
- **Decision**: Mesa / ABIDES 等を使わず、purpose-built な小エンジンを書く。
- **Rationale**: 本 feature の唯一の価値は「sim 出力が閉形式と一致する」ことの監査可能な証明（原則I・auditability）。フレームワークは scheduler/agent 抽象を不透明に挟み、閉形式と sim の差分の原因切り分けを難しくする。数百行の自前ループの方が「どの行がアンカーと対応するか」を追える。
- **Alternatives**: Mesa（教育向け、連続/uniform-price batch の clearing を厳密に書くのに不向き）、ABIDES（重い、LOB は本格的だがセットアップ/監査コストが A に過剰）。→ 却下。

## D3. arbitrageur の latency / sniping モデル（速度非対称の表現）
- **Decision**: BCS 型の **1 期 staleness**。各 period: (1) true price 更新 → (2) **arbitrageur（ゼロ latency）が更新後価格を観測し、MM の更新前 stale quote が利益的なら即 picking-off** → (3) MM は次 period の頭で気配を更新。noise trader は到着して mid 周りで約定。
- **Rationale**: これが「速い主体が stale quote を抜く」を最小に表現し、Budish の sniping 構造と GM の逆選択源を同一主体（arbitrageur）に統一する（knot）。MM の速度劣位＝quote 更新が 1 期遅れる、で表現。
- **Alternatives**: 連続時間ポアソン到着＋明示 latency δ（より現実的だが閉形式照合が煩雑）。→ A では離散 1 期 staleness、連続時間化は B/将来。

## D4. Glosten-Milgrom break-even（competitive spread の解析アンカー）
- **モデル primitives（閉形式が出るよう sim primitive をこれに一致させる）**:
  - fundamental `V`。連続時間 jump 強度 `λ`・diffusion `σ`。1 ステップ `dt` で jump 確率 `λ·dt`、diffusion `σ·√dt`。**`dt→0` で連続時間極限＝アンカー**（D6 収束チェックの土台）。jump size ±`J` 対称。
  - 各 period に taker 1名到着：確率 `alpha` で arbitrageur（informed＝ジャンプ後 `V` を知り、利益的な側を取る）、確率 `1-alpha` で noise（50/50 で買い/売り、無情報）。
  - MM は mid `m`（`V` の事前期待）周りに half-spread `h` で両側気配（inventory-free＝在庫で歪めない）。
- **break-even 条件**: ゼロ利潤 `E[MM profit | trade] = 0`。informed 買いで MM は `(V-ask)` を失い、noise 買いで `h` を得る。これを解いた `h*` が competitive half-spread。
- **Decision**: `anchors.gm_break_even(p_jump, J, alpha, ...)` が `h*` を**閉形式で**返す。正確な定数は anchors.py で導出し、**手計算した1点を unit test で pin**（plan に定数を書いて誤りを密輸しない）。sim 側 `metrics.competitive_spread` は同じ primitives の sim から測った h で、両者の一致が SC-001。
- **Rationale**: 解析側と sim 側が同一概念・別実装＝共有バグを排除（A2/構造決定）。
- **Alternatives**: 連続 GM（Kyle λ）も別アンカーに使えるが、A の主アンカーは離散 GM。Kyle は将来の追加チェック。

## D5. anchor battery（A2 の layered validation：spread・impact・sniping・clearing）
GM だけでは impact 層・clearing 層が未検証。A2 に従い4層を独立に張る。**LVR は含まない**（CLOB に pool 無し＝算出不能。AMM variant 専用）。

### D5a. Budish sniping レント（抽出量）
- 連続マッチングの sniping 損 = stale quote が jump で取り残され picking-off される確率 × 逆選択サイズ。`anchors.budish_sniping_rent(...)` が連続時間閉形式を返す。N 期 batch は intra-batch の picking-off 機会を除去 → N とともに減少。検証: SC-002/003。

### D5b. Kyle λ（price impact 層）— v2: identity-blind flow 回帰（finding 0001 ③ の閉鎖, 2026-06-10）
- **Decision**: impact 層は **identity-blind な flow 回帰**で検証する。
  - **sim 側** `metrics.price_impact`：取引主体を知らずに、符号付き flow `x` と価格変動 `Δp` の原点回帰 `λ̂ = Σx·Δp / Σx²`。連続は per-step（`x_t` = arb 符号 + noise 符号、`Δp_t` = step 増分）、batch は per-batch（`x_b` = arb 符号 + noise net、`Δp_b` = clear 間 net 変位）。
  - **anchor 側** `anchors.kyle_lambda(lambda_jump, jump_size, alpha, noise_rate, dt, half_spread, batch_interval)`：flow 組成の混合期待値から独立導出（pure-jump・committed-quote）。`S_N` = バッチ net 変位（K~Binom(N, λ·dt)、上方 u~Binom(K,½)、S=(2u−K)·J）として
    `λ(N) = α·E[|S_N|·1{|S_N|>h}] / (α·P(|S_N|>h) + N·noise_rate·dt)`
    分子＝informed flow が運ぶ価格情報、分母＝informed 参加率＋noise 希釈（N·dt で線形蓄積）。
  - **GM identity**：N=1（かつ h<J）で `λ(1) = αλJ/(αλ+noise_rate) = gm_break_even`（dt は cancel）。「competitive spread＝adverse-selection impact」という GM の定理を、spread 層（PnL break-even scan）と impact 層（flow 回帰）という**別経路の sim 測定が同一閉形式に収束する三角検証**として使う。
- **Rationale（v1 の circularity 是正）**: v1 は anchor `=J`・sim 側「arb と分かっている fill の |Δp| 平均」で、両辺とも構成上 J＝検出力ゼロ（α/noise_rate の到着バグ、方向相関バグ、|disp|>h 条件付けバグが全部素通り）。v2 は sim 推定量（識別盲回帰）と anchor 導出（flow 組成）が経路を共有せず、impact 層が初めて独立チェックになる（A2 充足）。batch の λ(N) は netting（binomial net 変位）× noise 希釈を同時に検証し、実験B の学習 MM が直面する逆選択の impact 構造に直結する。
- **限界**: 閉形式は pure-jump（σ=0）。diffusion σ>0 の impact アンカーは ①（finding 0001、外部妥当性④と並走）で別途。
- **Alternatives**: GM だけで済ます→A2 違反（却下）。Kyle(1985) 静的 auction（λ=½√(Σ₀/σᵤ²)）の独立単体テスト→本 harness は価格外生で flow→価格チャネルが無く、別モデルの検証になる（B の revisable-quote／価格発見拡張で再訪）。旧 `informed_impact`（識別条件付き平均）は診断メトリクスとして残すが検証には使わない。

### D5c. uniform-price clearing（clearing 層）
- **Decision**: clearing 価格・約定割当の正しさを **engine と独立な単体テスト**で固定（既知の supply/demand に対し手計算 clearing 価格と一致、marginal quote が全約定に効く）。
- **Rationale**: batch clearing は B の collusion 動学が乗る層。ここが狂うと全 batch 結果が無効。

> **LVR を A から完全除去**：CLOB spine に pool が無く算出不能。LP 抽出は GM/Budish で測る。LVR は後回しの AMM variant feature 専用（spec Out of Scope）。

## D6. 許容誤差 = tight consistency ＋ 収束チェック（「緩い方」は廃止）
- **Decision**: gate の強度 = SC-001 の許容そのもの。よって「緩い方」を取らない。二段に分離：
  - (i) **統計 consistency**：seed を増やして縮めた **tight な SE**（例 ±2·σ̂/√M）を許容に使う。精度を買ったらその精度で判定（flat 5% に逃げると 4% のバグが通る）。
  - (ii) **系統ギャップ（離散化・有限頻度・fee）**：flat tolerance に吸わせず、**dt→0 収束チェック**で扱う。複数解像度 dt で `|sim−anchor|` が期待オーダーで減衰することを示す。単一解像度の「5%以内」はバグと離散化誤差の相殺（or 正しい sim の棄却）を許す。
- **Rationale**: SC-007（B license）の信頼性は許容の tightness に等しい。pass は mechanical かつ tight に。
- **判定**: 各アンカーで (a) 関数形再現 (b) dt→0 収束 (c) tight SE 内一致 の **3点 AND**。

## D7. 決定論
- **Decision**: 単一 `numpy.random.default_rng(seed)` を engine が保持し、price/agents/arrival の全乱数をそこから引く。`SimConfig.seed`。複数 seed は外側ループ（検証・sweep）で回す。
- **Rationale**: FR-011・SC-004。再現性が監査の前提。

## D8. 抽出量・実効スプレッドの会計定義
- **extraction**: arbitrageur の各約定 PnL = `(true price − 約定価格) × 符号付き数量` の累積（MM 犠牲分）。MM 側に同額の逆符号で計上 → ゼロサム整合を assert（会計の sanity check）。
- **effective spread**: noise trader の約定について `2 × |約定価格 − mid|`（符号付き版も保持）。
- **mm_net_pnl**: `fees 収入 − extraction`（会計補助）。
- **participation margin（US3, D9）**: `f·(noise 約定量) − sniping 損 − c`。

## D9. participation margin（US3 — competitive frame の vacuous を回避）
- **問題**: GM break-even で価格する competitive MM は構造的に利益ゼロ → 「PnL 符号」での US3 は US2(spread) に潰れるか vacuous。
- **Decision**: participation margin = `f·(noise 約定量) − sniping 損 − c`（`f`=fee, `c`=機会コスト＝退出閾値）。margin<0 で MM 退出。US3 = 連続 vs batch が**退出判定を反転させるか**。
- **Rationale**: AMM の「swap fee が LVR を補償→LP 残留か」サステナビリティ問題と同型。spread 水準と独立な本物の問い。
- **Alternatives**: 元の「MM 純 PnL 符号」（competitive では構造ゼロ＝中身なし、却下）。

## 残 NEEDS CLARIFICATION
- なし（全項目 Decision 済）。GM/Budish の正確な定数は実装フェーズで導出し unit test で pin する設計とした（plan に数値を埋めない）。
