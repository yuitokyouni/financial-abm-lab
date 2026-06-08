# SG / LOB 実装のセマンティック解説 — code walkthrough

**目的**: YH006 / YH006_1 の実コード (Speculation Game の認知ロジック + aggregate 世界 +
LOB 移植 + ablation hook + データ schema) を、何をどの順で計算しているかの**意味**で
読み下す。全主張に `file:line` を張る。執行理論一般は [[refs_execution_algorithms]]
(理論 companion)。本書は「このリポのコードが実際に何をしているか」に限定する。

読む順序の地図:
```
認知レイヤ (SG decision rule) ── aggregate_sim.py に vectorized 実装
   │  同じ rule を                  speculation_agent.py に per-agent 実装
   ▼
履歴 μ(t) / 認知価格 P ──────── history_broadcast.py (LOB) / YH005 history.py (agg)
   │
   ▼
約定レイヤ                aggregate: 即時 clearing (D/N で価格、全 order 約定)
   が二股               LOB: PAMS CDA 板 + 設計 A' (MARKET + self-cancel + guard) + MMFCN 流動性
   │
   ▼
ablation hook ── _compute_open_quantity (A1) / _should_force_retire (A3)
   │
   ▼
adapter.py ──── 認知状態 → RT / agent / wealth parquet (survival・funnel 分析の入力)
```

---

## 1. 認知レイヤ — SG decision rule の意味論

aggregate (`experiments/YH006/aggregate_sim.py`) と LOB
(`experiments/YH006/speculation_agent.py`) は**同一の SG 認知ロジック**を持ち、違うのは
「注文が約定するか」の部分だけ。まず両者共通の認知ロジックを確定する。

### 1.1 戦略表 (strategy table)
各 agent は `S=2` 本の戦略を持ち、各戦略は `5^M (M=5) = 3125` 状態 → `{-1, 0, +1}`
(sell / hold / buy) の lookup table。

- agg: `strategies = rng.choice([-1,0,1], size=(N,S,K))` (`aggregate_sim.py:80`)
- LOB: `flat = [prng.choice([-1,0,1]) for _ in range(S*K)]` → reshape `(S,K)`
  (`speculation_agent.py:150-151`)

`active_idx` が今どの戦略で動いているか (`speculation_agent.py:153`)。

### 1.2 履歴 μ(t) と認知価格 P — ここが SG の心臓
agent は市場価格そのものではなく、**価格変化を 5 値に量子化した base-5 shift register
μ(t)** を「市場状態」として見る。

量子化 (`history_broadcast.py:18-28`、agg は `YH005/history.py` の同名関数):
```
Δp > C       → +2
0 < Δp ≤ C   → +1
Δp == 0      →  0
-C ≤ Δp < 0  → -1
Δp < -C      → -2
```
`C` = SG 認知閾値。LOB では `c_ticks` (= 28 tick、§4.4 で詳述)、agg では `C=3.0`
(`aggregate_sim.py:46`)。

shift register (`history_broadcast.py:31-33`):
```
mu ← (mu * 5) % 5^M + (h + 2)      # h+2 ∈ {0..4} を右端に push、最古桁を drop
```
→ `mu` は直近 M=5 step の量子化価格変化列を base-5 で 1 整数に畳んだもの。これが
`strategies[active_idx, mu]` の index になる。

**認知価格 P** = `Σ h` (量子化ステップの累積、`history_broadcast.py:80` / `aggregate_sim.py:168`)。
**重要**: round-trip の損益はこの P (認知価格、整数) で測られる。実約定価格ではない (§3.3)。

LOB の lag (`history_broadcast.py:8-10`): step t の submit 時点で P_mid(t) は未確定なので
`Δ = P_mid(t-1) - P_mid(t-2)` を h(t) に使う。agg は同 step の `dp = D/N` をそのまま使える
(`aggregate_sim.py:164-167`) — clearing が即時だから。

全 SG が同一 step で同一 μ を見るために、LOB では履歴を `Simulator` に attach した
`SharedHistoryState` で共有し、最初に呼んだ agent が `advance_to` で追いつかせ、以降は
冪等 (`history_broadcast.py:58-83`)。これが「aggregate の global history を LOB で
再現する」翻訳の肝。

### 1.3 意思決定 — open / close / hold
`rec = strategies[active_idx, mu_t]` (`speculation_agent.py:249` / `aggregate_sim.py:142`):

| 条件 | 意味 | action |
|---|---|---|
| `position==0 & rec!=0` | 無ポジ + 売買シグナル | **open** (`speculation_agent.py:251`) |
| `position!=0 & rec==-position` | 保有 + 反対シグナル | **close** (`:278`) |
| `position!=0 & rec==0` | 保有 + hold | active_hold |
| `position!=0 & rec==position` | 保有 + 同方向 | passive_hold |

round-trip = open → (保有) → close の 1 往復。これが研究の基本観測単位 (RT)。

### 1.4 round-trip の損益 ΔG と wealth 更新
close 時 (`speculation_agent.py:345-348` / `aggregate_sim.py:176,184`):
```
ΔG = entry_action × (P_close − P_open)      # 認知価格差 × 方向
G[active_idx] += ΔG                          # 戦略の累積 fitness
sg_wealth     += ΔG × entry_quantity         # 資産更新 (q 倍)
```
ファネル構造はここに宿る: horizon が長い RT ほど `(P_close − P_open)` の分散が広く、
さらに `entry_quantity` (= 資産依存の大口) が掛かるので大口・長期ほど損益が散る。

### 1.5 sizing — 資産が注文サイズに化ける経路
`q = ⌊sg_wealth / B⌋` (B=9、`speculation_agent.py:175-176` の `_compute_open_quantity`,
agg は `aggregate_sim.py:159` の `w // B`)。資産不平等が注文サイズの不平等に直結する。
**この 1 行が仮説 A (q-pollution) の標的**であり、A1 ablation はここを定数で潰す (§5.1)。

### 1.6 戦略選択 (virtual round-trip)
非 active 戦略も「もし使っていたら」を毎 step 評価して `G` を貯める
(`speculation_agent.py:386-406` `_update_virtual` / `aggregate_sim.py:199-217`)。
real close のたびに `active_idx ← argmax G` (tie はランダム、`speculation_agent.py:362-369`)。
→ G は real + virtual 込みの累積認知損益で、agent は事後的に勝ってる戦略へ乗り換える。

### 1.7 bankruptcy と substitute (turnover の源泉)
real close 直後に `sg_wealth < B` なら退場 (`speculation_agent.py:370-371`)。
`_substitute` (`:417-437`) で戦略・G・position・wealth を全 redraw:
```
new_wealth = B + prng.random()*100          # ← uniform 再 draw (Pareto 条件でも!)
```
agg も同じ (`aggregate_sim.py:230-231`)。**ここが決定的**: 初期 wealth は Pareto/uniform で
分岐する (`speculation_agent.py:158-164`) が、**substitute 後の再 draw は常に uniform**。
だから「agent が頻繁に入れ替わる ⇒ 初期 Pareto 分布が uniform へ希釈される / 入れ替わらない
⇒ 初期 Pareto が persist する」。これが仮説 A revised (persistence dominant) の機械的根拠で、
A3 (lifetime cap) が直接いじる所 (§5.2、dossier §5.2)。

---

## 2. aggregate 世界 — 即時 clearing の意味論

`aggregate_sim.py::simulate_aggregate`。N agent を numpy で vectorize し、1 step で全員
同時処理。

価格形成 (`aggregate_sim.py:163-167`):
```
D  = Σ_i (effective_i × quantity_i)     # 全 agent の符号付き需要を集計
dp = D / N                               # 価格変化 = 平均需要
p += dp;  h = quantize(dp, C);  P += h   # 認知価格を更新
```
**約定という概念が無い**: open は必ず position を持ち (`:191-197`)、close は必ず ΔG を
確定して wealth を更新する (`:174-189`)。誰も板待ちしない。→ round-trip は出せば必ず
閉じ、wealth は毎 close で動き、bankruptcy は定常 hazard で発火し、cohort は回り続ける
(dossier §5.3 の agg 側 = 一定 hazard ~3e-3)。

uniform 経路は YH005 と bit-parity (`aggregate_sim.py:11-16,86-87`)。Pareto は
inverse-CDF `w = xmin · U^(−1/α)` で 1 回余分に RNG 消費する新規 run (`:88-92`)。

---

## 3. LOB 世界 — 設計 A' と約定摩擦の意味論

`speculation_agent.py::SpeculationAgent` を PAMS の `Agent` subclass として実装し、
連続ダブルオークション (CDA) 板に注文を流す。認知ロジック (§1) は agg と同一。違いは
**「注文が約定するとは限らない」**ことだけ。だがこの 1 点が研究の全結論を生む。

### 3.1 設計 A' — 単発成行 + self-cancel + opposing-liquidity guard
(`speculation_agent.py:13-29` docstring、実装 `:251-302`)

open/close は常に `MARKET_ORDER` を**1 発**送る (執行理論で言えば parent=child=1 の最も
素朴な aggressive 執行。スケジューリングも分割も無い = 執行層不在、[[refs_execution_algorithms]] §9)。
3 つの仕掛け:

1. **opposing-liquidity guard** (`:253-257`, `:280-284`): 送る直前に反対板 best price を
   確認。`None` (反対 LIMIT 無し) なら **submit を skip** して `num_liquidity_skips++`。
   → 約定不能な瞬間に注文を投げない。
2. **self-cancel** (`:195-210`): 各 step 冒頭で前 step の未約定 order を無条件 Cancel
   (PAMS の `cancel` は既 fill/expire に対し no-op)。注文は 1 step しか板に残らない。
3. guard + self-cancel が無いと、反対板が一時 dry な step で cancel→resubmit が累積して
   book が 300→1600 に爆発、`priority_queue.remove` O(N) × 100 cancel で **O(N²) / T² scaling**
   になる (`:23-29`、probe で特定)。guard は accumulation を bound する防御弁。

> セマンティック含意: guard は「大口 q が薄い反対板に対して約定できない時、注文ごと
> 取り下げる」装置でもある。約定が rare になる一因がここに居る (dossier §5.3、軸2 の標的)。

### 3.2 fill の reconcile — 約定は「次 step に判明する」
PAMS は同 step 内に matching するが、SG は自分の fill を**次 step 冒頭で `asset_volumes`
から逆算**する (`_reconcile`, `:315-384`):

- **open の reconcile** (`:321-340`):
  - `actual_vol == 0` → 1 個も約定せず → `num_zero_opens++`、entry を破棄 (open 不成立)。
  - `actual_vol != 0` → `position = sign`、`entry_quantity = |actual_vol|`。
    `|actual_vol| < 送った q` なら **partial open** (`:332-333`)。
    → **entry_quantity は「送った q」ではなく「実際に約定した量」**。部分約定で q が縮む。
- **close の reconcile** (`:342-384`):
  - `actual_vol == 0` (= position 解消完了) → round-trip 確定。ΔG 計算・wealth 更新・
    `round_trips` に記録・戦略乗換・bankruptcy 判定 (`:343-371`)。
  - `|actual_vol| < entry_quantity` → **partial close**、残ポジで continue (`:372-376`)。
  - `actual_vol == entry_quantity` (= 全く減ってない) → close は前 step に約定せず
    self-cancel された。次 step で再送 (`:377-381`)。

### 3.3 ΔG は認知価格、約定価格ではない — 最重要の設計ポイント
close 確定時の損益 (`:345`):
```
dG = entry_action × (close_price_cog − entry_price_cog)
```
`close_price_cog` / `entry_price_cog` は P (認知価格、§1.2) のスナップショット
(`:264, :289`)。**LOB の実約定価格は ΔG に一切入らない**。LOB が変えるのは
「round-trip が**完了するか**」だけで、完了した時の損益は agg と同じ認知価格差で決まる。

→ だから funnel は cognitive-price 空間の構造で、LOB の効果は「どの round-trip が
完了して観測に入るか」という**サンプリングのゲート**として効く。この理解が S5.5
(funnel gap は sample size で説明できない) の解釈と直結する。

### 3.4 2-account wealth — sg_wealth と LOB cash の分離
(`speculation_agent.py:31-39, 80-81, 164-166`)
- `sg_wealth`: 認知資産。sizing (`q=⌊sg_wealth/B⌋`) と bankruptcy 判定はこれのみ。
  YH005 の `w` に対応、`final_wealth` として agg と直接比較可能。
- `self.cash_amount`: PAMS が cost basis を追う LOB cash。SG ロジックは一切参照しない
  ので、deeply negative になっても認知ロジックは壊れない。

→ 「執行の現実 (cash) は記録するが、認知・淘汰は cognitive wealth で回す」レイヤ分離。
YH006_2 で執行層を足すなら、この分離思想の上に「parent(q)→child schedule」を挟むのが
自然 ([[refs_execution_algorithms]] §9.4)。

### 3.5 stale-fill recovery
`pending_intent is None & position==0` なのに `asset_volumes != 0` = SG が把握しない
過去 MARKET_ORDER の遅延約定が残っている状態。次の reconcile で誤読され entry_quantity が
倍化するバグを、flatten MARKET_ORDER で position=0 に戻して回避 (`:216-235`)。
warmup→main 境界・substitute 後 re-init 境界で発生 (S4 で発見)。A3 の強制交代後の残ポジ
回収もこの経路が担う (`:240-247` のコメント)。

### 3.6 MMFCN — SG が唯一取引できる流動性
`mm_fcn_agent.py::MMFCNAgent`。PAMS の `FCNAgent` を subclass し、`order_volume` を
config 可能にしただけ (`mm_fcn_agent.py:30-41`)。素の FCNAgent は `order_volume=1`
ハードコードで、SG 100-500 体の MARKET 需要に対し 30 FCN × 1 = 30 shares/step では
20:1 の需給不足で約定率 5-15% に潰れる (`:5-11`)。

- fundamental 弱・chart ほぼ無効・noise 主体の LIMIT 注文を出す (`:90-145`)。
- `ttl = time_window_size ∈ [100,200]` の**定数** → T に依らず板が堆積しない
  (S5.8 で T=10000 でも堆積なしを実証、dossier §2.2)。
- FCN は研究対象ではなく**流動性の structural condition**。なので `order_volume` は
  controlled variable として動かしてよい (S5.6 の sensitivity scan の根拠)。

> セマンティック含意: SG round-trip の反対側に立つのは基本この MMFCN。SG 同士が
> 直接約定することもあるが、流動性の主供給は MMFCN。「約定が rare」かどうかは
> SG の MARKET と MMFCN の LIMIT がどれだけ価格的に出会うかで決まり、そこに
> c_ticks (trigger 率) と guard (執行可否) が効く。

---

## 4. aggregate ⇄ LOB の機構的分岐 — 凍結はコードのどこで起きるか

研究の全結論はこの 1 枚に圧縮できる:

| | aggregate (`aggregate_sim.py`) | LOB (`speculation_agent.py`) |
|---|---|---|
| open | 必ず position 取得 (`:191-197`) | guard skip / zero-fill / partial あり (`:251-277, :321-340`) |
| close | 必ず ΔG 確定 + wealth 更新 (`:174-189`) | 約定しないと round-trip 未完了 (`:342-384`) |
| wealth | 毎 close で動く | round-trip が閉じない限り **sg_wealth 凍結** |
| bankruptcy | 定常 hazard で発火 (`:229`) | `w<B` に到達しない → **発火しない** (`:370`) |
| turnover | cohort 回り続ける | 初期 shake-out 後 **凍結** |

凍結の機械的経路 (dossier §5.3 をコードで辿る):
```
guard skip / 反対板に出会わない  (speculation_agent.py:255, 281)
   → open/close が約定しない       (reconcile actual_vol==0, :322/:343)
   → round-trip が閉じない          (round_trips に追記されない)
   → sg_wealth が動かない           (:348 が呼ばれない)
   → w < B に到達しない             (:370 が False)
   → substitute されない            (:417 が呼ばれない)
   → hazard → 0 (凍結)
```
S5.8 で延長 8500 step で退場 event 0 件 = この経路が定常に閉じていることを実証。
**「約定が rare」がなぜか** = guard で弾かれる (fill 側) のか、そもそも RT trigger が
低い (c_ticks 側) のか、が S5.9 の切り分け対象 (§4.4)。

### 4.1 c_ticks の self-consistency 問題 (P2) をコードで見る
`c_ticks` は §1.2 の量子化閾値 C そのもの (`history_broadcast.py:79` の `quantize(dp, c_ticks)`)。
28 tick は **SG 投入前の C1 (MMFCN のみ) の mid 揺らぎ**で較正された値
(`config.py:69`、`calibrate_c_ticks.py`)。SG 投入後は volatility regime が変わるのに
28 は据え置き = self-consistent でない。

- c_ticks が実 regime に対し過大 → Δmid が `±c_ticks` 内に収まりやすい → h が 0/±1 に
  偏る → μ が動きにくい → strategy が open シグナルを出しにくい → **RT trigger 率低下** →
  凍結に寄与。
- これは「fill が無い」のとは別経路 (trigger 側)。軸2 (執行層 = fill 側を埋める) では
  治らない。だから S5.9 (c_ticks 再較正) が軸2 の前提切り分け。

---

## 5. ablation hook の意味論 — Phase 1 を 1 行も壊さずに介入する

Phase 2 ルール: 「Phase 1 への後方互換拡張は許容、動作変更は禁止」。monkey patch 禁止、
subclass override のみ (`sg_agent.py:1-7`)。default 経路は Phase 1 と bit-一致。

### 5.1 A1 (q-pollution test) — `_compute_open_quantity`
- Phase 1 base: `max(1, sg_wealth // B)` (`speculation_agent.py:175-176`)。
- A1 subclass `QConstSpeculationAgent._compute_open_quantity` → `max(1, q_const)`
  (`sg_agent.py:75-76`)。wealth → 注文サイズの経路 (§1.5) を定数で**切断**。
- 結果 (dossier §4.2): C2_A1 は agg 水準へ復帰 (−0.31)、C3_A1 は動かず (−0.09)
  → 仮説 A 単純版 (q 経路) 反証、仮説 A revised (persistence) へ。

### 5.2 A3 (persistence test) — `_should_force_retire`
- Phase 1 base: 常に `False` (`speculation_agent.py:408-415`) = lifetime cap 無し。
- A3 subclass `LifetimeCapSpeculationAgent._should_force_retire` (`sg_agent.py:118-125`):
  ```
  在籍 (t − _last_substitute_t) ≥ τ_max  →  True
  ```
  fire すると `_substitute` で強制交代 (`speculation_agent.py:244-247`)。pending order が
  in-flight の step は 1 step 延期して reconcile 整合を保つ (`sg_agent.py:119`)。
- 意味: §1.7 で見た「substitute 後の再 draw は uniform」を**強制発火**させ、凍結して
  persist していた初期 Pareto wealth-tail を人為的に希釈する。funnel が agg 側へ戻れば
  「凍結 tail が funnel を弱めていた」が確定 (S6、判定は funnel 復元のみ、lifetime 変化は
  トートロジーなので成功条件にしない、dossier §5.2)。

### 5.3 hook の呼び出し位置 (なぜ bit-一致が言えるか)
両 hook とも `submit_orders_by_market` の reconcile 直後に 1 回だけ呼ばれ
(`speculation_agent.py:237-247, 259`)、base 実装が「既存挙動と同じ値」(False / ⌊w/B⌋) を
返すので、subclass を差さない限り RNG 消費順も分岐も Phase 1 と完全一致。これが
「parity test 全再走で default 経路の bit-一致を毎回確認する」protocol の土台。
agent class の差し替えは config 1 行 (`run_experiment.py:252-259`)。

---

## 6. データ schema — 認知状態が survival / funnel 分析になるまで

`adapter.py` が sim 終了時の agent 群を 3 つの parquet schema に変換。分析 (KM survival,
bin_var_slope) はこの parquet だけ見る。

### 6.1 RT 単位 (`adapter.py:31-105`, `round_trips_to_df`)
1 行 = 1 round-trip。`horizon = t_close − t_open`、`q = entry_quantity` (実約定量)、
`delta_g`。`w_open` / `w_close` は substitute イベントを消化しながら**事後再構成**
(`:73-99`) — sg_wealth は sim 中に保存され続けないので RT 列から積み直す。
→ funnel 指標 `bin_var_slope` (horizon bin ごとの ΔG 分散の傾き) はここから出る。

### 6.2 agent 単位 (`adapter.py:112-173`, `agents_to_df`)
1 行 = 1 agent identity。**lifetime = 最初の substitute までの間隔**、一度も substitute
されなければ `lifetime = T_total` (censored, `:155-159`)。`forced_retired` は bankruptcy
退場フラグ。→ survival 分析の生データ。LOB で censored (= 生涯退場しない) が 72-91% に
なるのが凍結の表れ (dossier §4.3)。

### 6.3 全 lifetime sample long-format (`adapter.py:176-220`)
1 agent_id が複数回 substitute されると複数 lifetime sample を生む。各 segment に
`censored` (sim 終了時生存) フラグ。S5.7/S5.8 の KM はこの long-format を使う。

### 6.4 LOB 側の抽出 (`run_experiment.py:281-333`)
sim 後に SG agent 群から `w_init` / `final_wealth (=sg_wealth)` / `round_trips` /
`substitute_events` を集約。**warmup (200 step) 内の RT は除外**し、t を main 基準に
shift (`:297-314`)。→ 観測は main session [0, main_steps] のみ。

---

## 7. study 時に効く「読み違えやすい」セマンティック注意

1. **ΔG は認知価格 P、約定価格ではない** (§3.3)。LOB はサンプリングのゲートで、損益の
   生成器ではない。「LOB で funnel が浅い」は「約定価格が穏やか」ではなく「完了する RT の
   構成が変わる」。
2. **entry_quantity は実約定量** (§3.2)。partial fill で q が縮み、wealth 更新も縮んだ q で
   行う。送った ⌊w/B⌋ がそのまま効くわけではない。
3. **substitute の再 draw は常に uniform** (§1.7)。Pareto は初期分布のみ。だから persistence
   (= substitute されない) が初期 Pareto を保存し、A3 がそれを壊す。
4. **agent_id ≠ agent identity の寿命**。1 つの agent_id が substitute で何世代も生まれ変わる。
   lifetime は identity reset 間隔 (§6.2)。lifetime と RT horizon は別物 (dossier §4.3 の
   ラベル規約、median 390 vs 2)。
5. **guard skip は「執行不在」、c_ticks は「trigger 不全」**。凍結の 2 候補因は別レイヤ
   (§4)。混同すると軸2 の go/no-go を誤る。
6. **aggregate に「約定」概念は無い** (§2)。agg と LOB の比較は「即時 clearing ⇄ CDA 板」の
   比較であって、同じ約定エンジンのパラメタ違いではない。

---

## 8. 参照ファイル一覧
| ファイル | 役割 |
|---|---|
| `experiments/YH006/aggregate_sim.py` | aggregate 世界 (即時 clearing、vectorized) |
| `experiments/YH006/speculation_agent.py` | LOB SG agent (設計 A'、reconcile、2-account) |
| `experiments/YH006/history_broadcast.py` | μ(t) / 認知価格 P / c_ticks 量子化 (LOB 共有) |
| `experiments/YH006/mm_fcn_agent.py` | MMFCN 流動性供給層 |
| `experiments/YH006_1/code/sg_agent.py` | Phase 2 subclass (WInit / QConst=A1 / LifetimeCap=A3) |
| `experiments/YH006_1/code/run_experiment.py` | LOB session orchestration + 抽出 |
| `experiments/YH006_1/code/adapter.py` | 認知状態 → RT/agent/wealth parquet |
| `experiments/YH006_1/code/config.py` | 7 条件 spec、LOB_PARAMS |

---

## 改訂履歴
| 日付 | 内容 |
|---|---|
| 2026-06-08 | 初版。SG/LOB 実装のセマンティック code walkthrough。認知レイヤ→aggregate→LOB(設計A')→ablation hook→data schema を file:line 付きで。凍結機構を §4 でコードから辿る。執行理論一般は [[refs_execution_algorithms]]。 |
