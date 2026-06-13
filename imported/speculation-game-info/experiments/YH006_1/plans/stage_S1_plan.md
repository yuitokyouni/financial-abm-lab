# Stage S1 plan v2 — Phase 1 データ再分析 (tentative)

| 項目 | 値 |
|---|---|
| Stage | S1 (Phase 1 既存データ再分析、新規 sim なし) |
| Status | **承認済 (Yuito 承認 v2 反映、実装着手可)** |
| 想定 runtime | 数分〜数十分 (1 trial × 4 条件の集計のみ) |
| 新規 sim | 不要 |

本 plan は Stage S1 のみを扱い、S2 以降の話は **意図的に混ぜていない** (Brief §0 の two-step workflow 規約)。

---

## v2 改訂サマリ (v1 → v2)

Yuito 承認時の 6 点指示 + Layer 2 scope 切り分けを反映:

1. **tentative S1 の役割を再定義**: plan A/B 分岐の決定点ではない。役割は (a) 5 指標実装の sanity check / (b) Phase 1 → Phase 2 schema アダプタ確定 / (c) 桁感の事前確認、の 3 点に限定。**S2/S3 は tentative S1 結果に関わらず実行**。plan A/B 分岐判定は S3 完了後の **S1-secondary** でのみ行う (= 100 trial ensemble の bootstrap CI で確定)。
2. **timescale 切り基準**: sim-time midpoint ではなく **round-trip count median** に変更。各 trial 内で RT を `t_open` 昇順に並べ、最初の `⌊N_RT/2⌋` 個を前半、残りを後半。aggregate (T=50000, K~10⁶) と LOB (T=1500, K~10³) の sim 長差を sample-size で normalize。
3. **τ_max cap での position 処理**: (b) 持ち越しではなく **(i) 強制 MARKET_ORDER**。手順: active limit を全 cancel → 反対方向 MARKET_ORDER で全量約定 (MMFCN backstop) → wealth 更新 → substitute。pilot で backstop 正常性を必ず確認、不約定ケースが見つかった場合のみ defer-to-next-step を fallback。
4. **`w_init` 解釈**: metric ごとに使い分け。agent-level (生涯初期) と round-trip-level (建玉時) は **別 column**。SPEC §2.1 `w_open`/`w_close` (RT 単位) と §2.2 `w_init`/`w_final` (agent 単位) で対応。Phase 1 で欠落分は post-hoc 再構成。
5. **C2/C3 pkl 配置**: Mac → Windows 転送、`experiments/YH006_1/data/_phase1_imported/` に配置。S1 plan 冒頭で **pkl 整合性チェック** (file size + 1 trial sample の RT 数 / Phase 1 README 整合) を必ず実施。
6. **`q_const` を全 A1 条件で同一値使用**: SPEC Appendix A.1 pilot は C3 で実施、得られた q_const を **C2_A1 と C3_A1 の両方に適用**。ablation design の要請 (q を均すことで wealth → q 経路を切る)。

加えて **Layer 2 timescale concern (Phase 1 LOB T=1500 が Katahira 標準 T=50000 より短い、本 sim 長を超える長期での F1 持続性が未検証) は Phase 2 scope 外**。Phase 2 README と将来 proposal の limitation 節に明記する。

---

## 0. Brief §6 の 6 点 prerequisites report

実装に入る前に CC が確認すべき 6 点 (Brief §6) を以下に明記する。Yuito 承認 v2 を踏まえ、不要になった confirm 事項は削除済。

### 0.1 Phase 1 round-trip データ schema

**Source**:
- aggregate (C0u/C0p): `aggregate_sim.simulate_aggregate()` 返り dict の `round_trips` (= YH005 simulate と同 schema、aggregate_sim.py:300-307 で構築)
- LOB (C2/C3): `SpeculationAgent.round_trips` (list of dict) を `yh006_to_yh005_adapter.build_yh005_compatible_dict()` で numpy arrays に変換 (yh006_to_yh005_adapter.py:153-160)

**両世界共通の Phase 1 schema** (numpy arrays、length = K = round-trip 件数):

| Phase 1 key | dtype | 意味 | Phase 2 §2.1 schema へのマッピング |
|---|---|---|---|
| `agent_idx` | int64 | agent ID | `agent_id` |
| `open_t` | int64 | 建玉 step (LOB は warmup 引いて main session 内座標) | `t_open` |
| `close_t` | int64 | 手仕舞い step | `t_close` |
| `entry_action` | int8 ∈ {−1, +1} | open 方向 | `direction` |
| `entry_quantity` | int64 | open 時 q | `q` |
| `delta_G` | int64 | cognitive ΔG (整数のまま、float upcast 不要) | `delta_g` |

**Phase 2 schema にあって Phase 1 に無い列、本 S1 で post-hoc 再構成する**:

- `horizon` = `close_t − open_t` (純粋計算)
- `rt_idx` = agent ごとの round-trip 通し番号 (`agent_idx` ごとに `argsort(close_t)` で derive)
- **`w_open` / `w_close`** (RT 単位、SPEC §2.1):
  - aggregate: agent ごとに RT を時刻順に sort し、`w_init`(生涯初期、§0.4 参照) から累積で再構成 (`w_open[k+1] = w_close[k]`、`w_close[k] = w_open[k] + delta_G[k] × entry_quantity[k]`)。bankruptcy substitute 発生時は `final_wealth` ≠ 累積結果になるので、その agent の `num_substitutions` を `_meta` から取れない場合は単純累積で近似 (substitute 直前 RT までは正確、それ以降は不正確) と注記。
  - LOB: 上と同じ。`SpeculationAgent.substitute_events` ((t, dead_w, new_w)) も pkl に乗っていれば併用すれば substitute 跨ぎも正確に再構成可能 (pkl 整合性チェックで存在確認)。
- **`w_init`** (agent 単位、SPEC §2.2):
  - aggregate: `init_u100` (RNG 消費順 §0.4) から `w[i] = B + init_u100[i]` (uniform) または Pareto 経路 `w[i] = floor(xmin × U^(-1/α))` で再 draw。これは `aggregate_sim.simulate_aggregate` の同 seed で RNG state を再現すれば bit-一致で取れる (test_aggregate_parity で検証済の経路)。
  - LOB: `SpeculationAgent.setup()` 内 wealth_mode 分岐で draw された値。Phase 1 では agent-level で記録していない可能性あり → **pkl 整合性チェックで `_meta` または agent 属性に `w_init` 配列があるか確認**。無ければ同 seed で SG agent class を再 instantiate して RNG state を再現、initial wealth 配列のみ抽出する補助 script を `reanalyze_phase1.py` 内に書く。
- `cond`, `seed`: trial level メタ、parquet 出力時に付ける

### 0.2 Phase 1 sim 長 T と timescale 切り基準

| 条件 | sim 長 T (主 session) | warmup |
|---|---:|---:|
| C0u / C0p | 50,000 | 0 (aggregate、warmup 概念無し) |
| C2 / C3 | 1,500 | 200 (adapter 出力後、warmup 引いた main session 内座標) |

**timescale 切り基準** (Yuito 指示 v2): **round-trip count median**。各 trial 内で RT を `t_open` 昇順に並べ、最初の `⌊N_RT / 2⌋` を前半、残り `N_RT − ⌊N_RT/2⌋` を後半。

実装:
```python
order = np.argsort(rt["open_t"], kind="stable")
n_half = len(order) // 2
first_half = order[:n_half]
second_half = order[n_half:]
```

これで aggregate K~10⁶ / LOB K~10³ の **どちらの世界でも前半・後半の sample size が等しく** なる (aggregate は 5×10⁵ vs 5×10⁵、LOB は 500 vs 500 等)。sim 長差を sample-size で normalize し、相対 timescale で interaction の安定性を評価できる。

**Layer 2 timescale concern** (本 plan の scope 外): Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短い。本 sim 長を超える長期での F1 持続性は未検証で、(a) 真の長期定常分布での interaction 値、(b) substitute dynamics の収束、(c) wealth persistence の半減期が T=1500 内で観察される範囲外、の 3 つは Phase 2 では検証しない。**Phase 2 README と将来 proposal の Limitations 節に明記する** (本 S1 での action は不要、S7 README 執筆時に書く)。

### 0.3 Phase 1 既存 trial 数 (条件別、新規 sim なしの再分析範囲)

| 条件 | seed | trial 数 | データ source (転送後) |
|---|---|---:|---|
| C0u | 777 | 1 | `experiments/YH006_1/data/_phase1_imported/c0u_result.pkl` |
| C0p | 777 | 1 | `experiments/YH006_1/data/_phase1_imported/c0p_result.pkl` |
| C2 | 777 | 1 | `experiments/YH006_1/data/_phase1_imported/C2_result.pkl` (Mac から転送) |
| C3 | 777 | 1 | `experiments/YH006_1/data/_phase1_imported/C3_result.pkl` (Mac から転送) |

**tentative S1 の役割** (Yuito 指示 v2 反映):

各条件 1 trial しかないので bootstrap CI 不可。tentative S1 は **plan A/B 分岐の判定点ではなく**、以下 3 点の sanity check に scope を限定:

| 役割 | 内容 | 完了条件 |
|---|---|---|
| (a) **5 指標実装の sanity check** | Pearson, Spearman, Kendall, bin variance slope, quantile slope diff の 5 指標が 4 条件 × 1 trial で計算でき、NaN や数値破綻がない | コードが完走、`tab_S1_phase1_reanalysis.csv` に 5×4 = 20 値 + interaction 5 値が出る |
| (b) **Phase 1 → Phase 2 schema アダプタ確定** | 4 pkl を読んで Phase 2 §2.1 (round-trip 単位) parquet schema に変換、`w_open/w_close` の post-hoc 再構成、`w_init` agent-level 取得まで通る | `phase1_reanalysis_round_trips.parquet` (RT 単位) と `phase1_reanalysis_agents.parquet` (agent 単位) が出力 |
| (c) **桁感の事前確認** | 5 指標の点推定値が「論文や Phase 1 README の数値と桁レベルで整合するか」を Yuito が読んで判断できる材料を揃える | bar chart `fig_S1_indicator_comparison.png` に 4 条件 × 5 指標の値が並ぶ |

**plan A/B 分岐の最終判定は S3 完了後の S1-secondary で 100 trial bootstrap CI を取って確定する**。tentative S1 では分岐判定を出さない (= README に「α/β/γ/δ/ε のどれか」を書かない)。代わりに「点推定 5 指標の暫定値、S1-secondary 確定待ち」を README に書く。

**SPEC §S1 完了条件の再解釈**: 元の文「F1 が指標横断で robust か判定 (= L1 達成判定 + plan A/B 分岐)」は **S1-secondary** に移譲。tentative S1 では「(a)(b)(c) の 3 点 sanity check 完了 + S1-secondary 用のアダプタ + 計算経路の準備が整う」を完了条件とする。

### 0.4 PAMS 0.2.2 MMFCNAgent 設定 (Phase 1 の正確な値、S2-S6 で再現)

`configs/_base.py:30-44` の `_FCN_AGENTS` block 全体:

```python
_FCN_AGENTS = {
    "class": "MMFCNAgent",          # pams.agents.FCNAgent subclass
    "numAgents": 30,                 # run_experiment.py:42 default
    "markets": ["Market"],
    "assetVolume": 50,
    "cashAmount": 10000,
    "fundamentalWeight": {"expon": [2.0]},
    "chartWeight": {"expon": [0.1]},
    "noiseWeight": {"expon": [0.5]},
    "meanReversionTime": {"uniform": [50, 100]},
    "noiseScale": 0.001,
    "timeWindowSize": [100, 200],
    "orderMargin": [0.01, 0.05],
    "orderVolume": 30,               # MMFCNAgent 独自 param、pams 0.2.2 hardcoded 1 を override
}

_MARKET = {
    "class": "Market",
    "tickSize": 0.00001,
    "marketPrice": 300.0,
}
```

Sessions: warmup 200 step (`withOrderExecution=False`) + main 1500 step (`withOrderExecution=True`)、`maxNormalOrders=500`。

SG block (configs/_base.py:77-101 `sg_block`): `numAgents=100`, `cashAmount=9` (= B), `assetVolume=0`, `M=5`, `S=2`, `B=9`, `cTicks=` (calibrate from C1, 既存 calibration JSON 流用)、`wealthMode` ∈ {uniform, pareto}, `paretoAlpha=1.5`, `paretoXmin=9.0`。

Phase 2 で固定するもの: 上記すべて。MMFCN sensitivity scan は SPEC §11.3 で proposal の保険として温存、Phase 2 implementation 外。

### 0.5 SG agent クラスの `q_i` 計算箇所 (S4 A1 ablation で override する場所)

**LOB (`speculation_agent.py:218`)**:
```python
q = max(1, int(self.sg_wealth // self.B))     # open 時の q
```
これが Katahira 2019 Eq.1 (`q_i = ⌊w_i/B⌋`) の対応。close 側は同 file:244 `q = int(self.entry_quantity)` で **open 時に決めた q を継承**するので、A1 で open 側を `q_const` に置換すれば close も自動で `q_const` になる。

A1 ablation 実装案:
- `experiments/YH006_1/code/ablation.py` に `QConstSpeculationAgent(SpeculationAgent)` を subclass で書く (Phase 1 monkey patch 禁止 §4.4)
- 新規 attr `q_const: int` を `setup()` で読ませて、line 218 の `q = max(1, ...)` を `q = self.q_const` に差し替え
- 実装パターン: `submit_orders_by_market` を全コピー override (DRY 違反だが Phase 1 を touch しない条件下では妥協)
- assertion: 全 round-trip で `entry_quantity == q_const` を sim 終了後に検証 (Brief §4.2)

**aggregate (`aggregate_sim.py:113`)**:
```python
quantity[is_open_mask] = w[is_open_mask] // B
```
SPEC §3 matrix で **C2_A1 / C3_A1 のみ A1 condition、aggregate 側 A1 は無い** ので aggregate へ A1 実装不要。

**`q_const` の共有設計** (Yuito 指示 v2 反映):

SPEC Appendix A.1 pilot は C3 (LOB + Pareto α=1.5) で実施するが、得られた `q_const` (single int) を **C2_A1 (LOB + uniform) と C3_A1 (LOB + Pareto) の両方に適用**する。これは ablation design の要請: 「q を全 agent で均一化することで wealth → q 経路を切る」が ablation の本質、両条件で異なる q_const を使うと「条件間の q 平均差」が交絡変数として残るため。pilot output `pilot/q_const_calibration.json` に「C3 で calibrate、C2_A1/C3_A1 共通適用」と明記する。

### 0.6 Phase 1 forced liquidation ロジック箇所 (S6 τ_max cap で再利用)

**LOB**: `speculation_agent.py:367-387` `_substitute(t)` メソッド。

- 現状トリガー: `_reconcile()` 内の close 完了直後 (line 329-330)
  ```python
  if self.sg_wealth < self.B:
      self._substitute(t=int(self.close_step))
  ```
- 処理内容: strategies/G を再 draw、position/entry_*/v_* を全クリア、sg_wealth を `B + prng.random()*100` に reset、`num_substitutions++`、`substitute_events` に `(t, dead_wealth, new_wealth)` を append

**問題**: `_substitute` は **close 完了直後にしか呼ばれない設計**。τ_max cap で「active position 中に τ_max 経過した agent」を強制 substitute するには、現コードに無い経路を追加する必要がある。

**A3 ablation 実装** (Yuito 指示 v2 反映、**(i) 強制 MARKET_ORDER 経路**):

`experiments/YH006_1/code/ablation.py` に `LifetimeCappedSpeculationAgent(SpeculationAgent)` を subclass:

```python
class LifetimeCappedSpeculationAgent(SpeculationAgent):
    def setup(self, settings, ...):
        super().setup(settings, ...)
        self.tau_max = int(settings.get("tauMax", 1_000_000))
        self.birth_step: int = -1
        self.lifetime_capped: bool = False
        self.num_lifetime_caps: int = 0
        self.num_force_close_failures: int = 0   # (i) MARKET 不約定の検出用

    def submit_orders_by_market(self, market):
        t = market.get_time()
        if self.birth_step < 0:
            self.birth_step = t
        elapsed = t - max(self.birth_step, self._last_substitute_t)
        if elapsed >= self.tau_max:
            return self._force_substitute_orders(market, t)
        return super().submit_orders_by_market(market)

    def _force_substitute_orders(self, market, t):
        orders = []
        market_id = market.market_id
        # (1) 全 outstanding limit を Cancel
        for ord_obj in self._outstanding.pop(market_id, []):
            if not ord_obj.is_canceled and ord_obj.order_id is not None:
                orders.append(Cancel(order=ord_obj))
                self.num_cancels_sent += 1
        # (2) active position を opposing MARKET で強制全量約定 (MMFCN backstop)
        if self.position != 0:
            is_buy = (self.position < 0)  # short → buy で close
            opp_best = market.get_best_sell_price() if is_buy else market.get_best_buy_price()
            if opp_best is not None:
                orders.append(Order(
                    agent_id=self.agent_id, market_id=market_id,
                    is_buy=is_buy, kind=MARKET_ORDER,
                    volume=int(self.entry_quantity),
                ))
                # 約定確認は次 step の _reconcile に委譲、wealth 更新もそこで起きる
                self.pending_intent = "force_close"
                self.pending_action = 1 if is_buy else -1
                self.pending_quantity_sent = int(self.entry_quantity)
            else:
                # MMFCN backstop が dry: pilot 段階で見つかった場合のみ defer-to-next-step を fallback
                self.num_force_close_failures += 1
                # **本 v2 では fallback を実装しない**: pilot でゼロ件であることを確認、
                # ゼロでない場合のみ Yuito 相談で fallback を追加実装。
        # (3) lifetime cap flag + substitute (新規 agent と入れ替え相当)
        self.lifetime_capped = True
        self.num_lifetime_caps += 1
        self._substitute(t=t)
        self.birth_step = t
        return orders
```

**Caveats**:
- `(2)` で MMFCN backstop が dry のケースを `num_force_close_failures` でカウント。pilot で **これがゼロであることを必ず確認**。ゼロでない場合は Yuito に相談、defer-to-next-step fallback を導入してから本実装に進む。
- forced 決済の round-trip は通常の `_reconcile` 経由で記録 (`pending_intent="force_close"` を新設、reconcile ロジックで close と同様に round_trips に append、ただし `force_close` フラグを RT 単位 schema に追加)。
- A3 では `cond["wealth"]` が一致した状態で新規 agent が再 draw される (= Pareto α=1.5 で再 draw)。SPEC §3 行 73 `C3_A3` は wealth init = Pareto なので一貫。
- `lifetime_capped` flag は agent-level の attr。同じ agent インスタンスが再利用されるため、Phase 2 §2.2 schema の `lifetime_capped: bool` は **agent ID 単位で「一度でも τ_max cap で retire したか」** とする。`num_lifetime_caps` で累計回数も記録 (中間予測解析で使用)。
- `forced_retired` (wealth < B) と `lifetime_capped` (τ_max) は両立しうる。schema は両 flag を併記。

**aggregate**: SPEC §3 で C3_A3 のみ LOB 条件、aggregate 側 τ_max 実装は不要。

### 0.7 C2/C3 pkl 配置と整合性チェック (Yuito 指示 v2 反映)

C2/C3 既存 pkl は Mac から Windows env に転送し、`experiments/YH006_1/data/_phase1_imported/` に配置する (新規ディレクトリ、本 S1 で作成)。

S1 plan 冒頭 (= `reanalyze_phase1.py` の最初の処理) で **pkl 整合性チェック** を実施:

| チェック項目 | 期待値 (Phase 1 README from `experiments/YH006/README.md` 行 77-89) | fail 時の挙動 |
|---|---|---|
| C0u file size | ~ 49 MB (Windows で生成済) | 要 re-run、stop |
| C0p file size | ~ 49 MB | 同上 |
| C2 file size | (Mac 生成、~ 数 MB 想定、要 Yuito 報告) | 転送漏れ疑い、stop |
| C3 file size | (同上) | 同上 |
| C0u `round_trips["close_t"].size` | 1,041,712 | ±1% 以内なら pass、外れなら stop |
| C0p `round_trips["close_t"].size` | 1,049,903 | 同上 |
| C2 `round_trips["close_t"].size` | 879 | 同上 |
| C3 `round_trips["close_t"].size` | 1,080 | 同上 |
| C0u `wealth.alpha_hill` (再計算 vs Phase 1 metrics JSON) | 3.910 | ±5% 以内、外れなら warn |

整合性チェック失敗時は実装を停止し、`logs/errors/{timestamp}_S1_integrity_check.log` に詳細 dump、Yuito 報告。

---

## 1. tentative S1 の目的 (Yuito 指示 v2 反映)

**S2/S3 は tentative S1 結果に関わらず実行**するので、tentative S1 は plan A/B 分岐判定を行わない。役割は §0.3 の (a)(b)(c) 3 点に限定:

(a) 5 指標実装の sanity check
(b) Phase 1 → Phase 2 schema アダプタ確定 (`w_open/w_close` 再構成、`w_init` 抽出)
(c) 桁感の事前確認 (Phase 1 README の Pearson −0.27 と整合、論文値と整合)

S1 のみで Stage 完了。S2 以降は Yuito 承認後に進む (本 plan の scope 外)。

## 2. 入力データ (転送後)

- `experiments/YH006_1/data/_phase1_imported/c0u_result.pkl` (Windows 生成済 → 同 path にコピー)
- `experiments/YH006_1/data/_phase1_imported/c0p_result.pkl` (同上)
- `experiments/YH006_1/data/_phase1_imported/C2_result.pkl` (Mac 転送)
- `experiments/YH006_1/data/_phase1_imported/C3_result.pkl` (Mac 転送)

**前提**: 4 pkl すべてが上記 path に配置されている状態で `reanalyze_phase1.py` が走る。配置されていない場合は §0.7 の整合性チェックで stop。

## 3. 作業項目

### 3.1 新規ファイル (`experiments/YH006_1/code/`)

1. `__init__.py`
2. `analysis.py` — 指標計算 (SPEC §4 / §5 の statistic 実装)
   - `corr_pearson(h, dG)`, `corr_spearman(h, dG)`, `corr_kendall(h, dG)` (`scipy.stats`)
   - `bin_variance_slope(h, dG, K=15)` (Brief §5.3 のコード通り)
   - `quantile_slopes(h, dG, taus=(0.10, 0.50, 0.90))` (Brief §5.4 のコード通り、`statsmodels.api.QuantReg`)
   - `quantile_slope_diff(h, dG)` = `slopes[0.90] − slopes[0.10]` (主 funnel 直接指標)
   - `hill_estimator(values, n_tail_frac=0.10)` (Brief §5.5 のコード通り)
   - `skewness_high_low_diff(h, dG)` — h を中央値で 2 分し各 bin で `scipy.stats.skew(dG)` を計算、差分
   - `corr_winit_h_spearman(rt_df, agents_df)` — agent ごとの `w_init` (生涯初期) と `h` (RT 単位) を join、Spearman ρ
3. `stats.py` — Brief §5.1 / §5.2 (S1 では bootstrap は使わない、骨だけ実装、actual call は S3 以降)
4. `reanalyze_phase1.py` — 本 Stage の主スクリプト
   - **Step 1**: §0.7 pkl 整合性チェック、fail 時 stop
   - **Step 2**: 4 pkl を load、Phase 2 §2.1 / §2.2 schema へ変換 (`w_open/w_close` post-hoc 再構成、`w_init` 抽出)
   - **Step 3**: 各 trial で 5 主指標 + plan B 先取り指標を計算
   - **Step 4**: timescale 解析 (round-trip count median split、§0.2 実装)
   - **Step 5**: interaction 計算: `[ρ(C3) − ρ(C2)] − [ρ(C0p) − ρ(C0u)]` を 5 主指標で
   - **Step 6**: 出力 (parquet + csv + figure + README 追記)

### 3.2 計算する指標一覧 (SPEC §4 / §4.5 と Brief §3 S1 行 22-30)

| カテゴリ | 指標 | 計算範囲 | 使う `w_init` |
|---|---|---|---|
| 主指標 (3 種相関) | Pearson `ρ(|ΔG|, h)` | 全 trial / 前半 RT / 後半 RT | — |
| | Spearman `ρ(|ΔG|, h)` | 同上 | — |
| | Kendall `τ(|ΔG|, h)` | 同上 | — |
| Funnel 直接 | bin variance slope (K=15) | 全 trial | — |
| | quantile slope diff `q90 − q10` | 全 trial | — |
| Plan B 先取り | `corr(w_init, h)` (Spearman) | 全 trial | **agent-level (生涯初期)** |
| | `Skew(ΔG | h_high) − Skew(ΔG | h_low)` | 全 trial | — |
| | Hill exponent of `|ΔG|` | 全 trial | — |
| Interaction | 上記 5 主指標で `[ρ(C3) − ρ(C2)] − [ρ(C0p) − ρ(C0u)]` | 全 trial / 前半 / 後半 | — |

**`w_init` 解釈** (Yuito 指示 v2 反映): metric ごとに使い分け。

- SPEC §4.5 「`corr(w_init, h)`」 → **agent-level の生涯初期 wealth** (= Phase 2 §2.2 `w_init`)。RT 単位 dataframe に agent-level `w_init` を join して RT 単位で計算。
- SPEC §2.1 `w_open/w_close` (RT 単位、建玉時/手仕舞い時残高) → 別 column として post-hoc 再構成、本 S1 では parquet に書き出すのみで指標として使わない (Phase 2 §4.4 中間予測で S3 以降が使う)。

### 3.3 出力 (SPEC §8 / Brief §3 S1)

| パス | 内容 |
|---|---|
| `data/phase1_reanalysis_round_trips.parquet` | 4 条件 merge した round-trip 単位 (SPEC §2.1 schema、`w_open/w_close` 再構成済) |
| `data/phase1_reanalysis_agents.parquet` | 4 条件 merge した agent 単位 (SPEC §2.2 schema、`w_init/w_final` 含む) |
| `outputs/tables/tab_S1_phase1_reanalysis.csv` | 条件 × 指標 の点推定値 + interaction 行 + 前半/後半行 |
| `outputs/figures/fig_S1_indicator_comparison.png` | bar chart (4 条件 × 5 主指標)、interaction を別パネルに併記 |
| `README.md` (新規作成) | tentative S1 結果サマリ + (a)(b)(c) 完了確認 + S1-secondary 待ちであることの明記、200 字程度 |
| `plans/stage_S1_diff.md` | Brief §7 format に従う実装報告 |

### 3.4 plan 分岐判定の運用 (Yuito 指示 v2 反映)

tentative S1 では plan A/B 分岐判定を **出さない**。README には:

- 5 主指標の点推定値表
- 「S2/S3 結果待ち、確定判定は S1-secondary」の明記
- 暫定的な観察 (例: 「Pearson は Phase 1 単 trial と同符号同桁、Spearman/Kendall は ±X、bin variance は ...」) を記述するが、これは sanity check のための **記述** であり判定ではない

S2 開始の go/no-go は **tentative S1 の sanity check (a)(b)(c) すべて pass** が条件。点推定値の中身に関わらず S2 へ進む。

## 4. 完了条件 (Yuito 指示 v2 反映)

- [ ] §0.7 pkl 整合性チェック全 pass
- [ ] (a) 5 主指標の計算が 4 条件 × 1 trial で完走、NaN なし
- [ ] (b) Phase 1 → Phase 2 schema アダプタ完成、`phase1_reanalysis_round_trips.parquet` と `phase1_reanalysis_agents.parquet` が出力 (`w_open/w_close/w_init/w_final` の post-hoc 再構成含む)
- [ ] (c) `tab_S1_phase1_reanalysis.csv` と `fig_S1_indicator_comparison.png` が完成、Yuito が桁感を読める状態
- [ ] timescale 解析 (前半/後半、RT count median split) で各指標 × 各条件 × 2 期間 = 30 値が出ている
- [ ] plan B 先取り指標 (`corr(w_init, h)`, Skew 非対称, Hill α) が 4 条件で出ている
- [ ] `README.md` (新規) に tentative S1 結果サマリ + S1-secondary 待ち明記、200 字
- [ ] `plans/stage_S1_diff.md` を提出、Yuito レビュー待ち状態

## 5. Yuito 確認事項 (実装後 / S2 開始前)

v1 の 5 点中 1-4 は Yuito v2 指示で resolve 済。本 plan では **実装後** の確認事項のみ列挙:

1. tentative S1 完了報告 (`stage_S1_diff.md`) を読んだ上で、(a)(b)(c) 3 点 sanity check pass 判定を Yuito が行う
2. 桁感の暫定値が予想外 (例: Pearson 符号反転、5 指標の桁が完全にバラバラ) ならば Yuito との緊急相談 → SPEC 改訂か続行か判断 (基本は **続行**、tentative S1 は判定点ではないため)

実装段階での Yuito 相談トリガー (本 plan 実装中に発生したら停止して相談):

- §0.7 pkl 整合性チェック fail (転送漏れ / file 破損)
- `w_init` の post-hoc 再構成で Phase 1 RNG state が再現できない (= bit-一致しない、aggregate parity test と矛盾)
- 5 指標いずれかで NaN / inf が出て計算経路の bug が疑われる

これら以外は独断で実装完走、`stage_S1_diff.md` で報告。

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 | Stage S1 plan 初版、Brief §6 の 6 点 prerequisites + S1 作業項目 + 分岐判定運用 + Yuito 確認事項 5 点 |
| v2.0 (本書、承認版) | Yuito 6 点指示反映: (1) tentative S1 を sanity check に scope 限定、plan A/B 分岐は S1-secondary に移譲、S2/S3 は tentative S1 結果に関わらず実行 / (2) timescale 切り基準を RT count median split に変更 / (3) τ_max cap を (i) 強制 MARKET_ORDER 経路に確定、MMFCN backstop 不約定は pilot で計測してゼロ確認 / (4) `w_init` を agent-level と RT-level の別 column 化、metric ごとに使い分け / (5) C2/C3 pkl を `data/_phase1_imported/` に配置、整合性チェック追加 (§0.7) / (6) `q_const` を C2_A1/C3_A1 で共有 (C3 で calibrate)。Layer 2 timescale concern を Phase 2 scope 外として明記 (S7 README で記述、本 S1 では action なし)。 |
