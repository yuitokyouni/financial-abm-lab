<!-- 自動生成: 世界の ABM 文献を 29-agent workflow で調査した統合レポート(2026-06-08)。
     目的: 正準モデルが観測チャネルを持たない問題に対し、B2(観測情報チャネル介入)と
     before/after 測定を文献からどう実装するかを決める。 -->

# B2(観測情報チャネル介入)の文献地図と実装方針

正準金融 ABM における「エージェント観測チャネル」の有無、機構を ablate せず入力源だけ degrade する B2 介入の実装オプション、介入 before/after の測定法を、世界の ABM 文献(集約需要型・order book 型・herding/percolation 型・Minority Game 型・情報非対称型・社会的学習型・LLM/MARL 型・市場透明性 lab/field 実証)横断で統合する。

---

## 1. 観測チャネルを持つ/持たない ABM の地図

中心命題は二分ではなく**連続スペクトル**だが、「エージェントが式の中で明示的に読む観測量(価格履歴窓 / order book / 他者行動 / 公開履歴 / 私的シグナル)を、機構(判断ルール A)から syntactic に分離して持つか」で整理できる。

### (yes) 明示的観測チャネルを持つ — B2 を機構非破壊で刺せる本命

| モデル | degrade できる内部観測量 | 出典 |
|---|---|---|
| **Chiarella-Iori (2002) / Chiarella-Iori-Perelló (2009)** | chartist 成分が読む過去 τ 期 return の移動平均 `r̄_{L^i}`(エージェント固有 horizon L^i)、fundamentalist の `(p_f − p)`、order book(best bid/ask, depth)。式2が観測を分離して持つ正準 LOB モデルの代表 | Quant. Finance 2:346; JEDC 33:525 |
| **Chiarella-He-Hommes (2006) MA-HAM** | MA window 長 L が「どれだけ過去を観測し平滑化するか」そのもの。**L 操作 = B2 の低域通過/平均化と数学的に同型**。L≥5 で不安定化する susceptibility 既知 | JEDC 30:1729 |
| **Santa Fe ASM (Arthur-Holland-LeBaron-Palmer-Tayler 1997)** | 12-bit MarketState descriptor(bits1-6=fundamental 閾値、bits7-10=技術指標 = 価格 vs 5/10/100/500期 MA)。**bit を masking するだけで GA 学習を一切触らず観測 degrade できる理想形** | SFI; LeBaron-Arthur-Palmer (1999) |
| **Minority Game / El Farol** | 共通の m-bit 公開履歴 μ / 過去 d 週出席時系列。real→random history 差替え(Cavagna)、memory length m 縮小が確立した B2 | Challet-Zhang (1997); Arthur (1994); Cavagna (1999) |
| **ABIDES value agent (Byrd-Hybinette-Balch 2019)** | OU fundamental の noisy observation `ŷ_t = r_t + N(0,σ_y²)`。σ_y²(雑音)と pairwise network latency(遅延)が**設計に内蔵** | arXiv:1904.12066 |
| **Carro-Toral-San Miguel (2015)** | 外部情報フィールド `i(t)`、herding 係数経由 `h±=h0±(F/N)i(t)`。強度 F が degrade つまみ、(1−x²) gate で機構非破壊が定義上きれいに成立。**B2≠A の最もクリーンな先行例** | PLoS ONE 10(7):e0133287 |
| **情報拡散/Bayesian ABM (Di Francesco et al. 2024)** | private signal の clean/distorted、peer 経由の伝播遅延、network topology | arXiv:2412.16269 |
| **Glosten-Milgrom/Kyle 系・Das (2005) learning MM** | informed の私的シグナル精度 σ、MM が観測する order-flow 系列 | Quant. Finance 5(2):169 |
| **Brock-Hommes ABS** | 過去価格系列 + 各 predictor の公開 fitness(realized profit)。memory length が観測 coarsening の軸 | Econometrica 65; JEDC 22 |
| **voter/q-voter/Ising/Sznajd 金融版** | 各エージェントが近傍の他者行動を明示観測。herding(Model H)の観測チャネル化に最も自然 | Sznajd (2000); PNAS 2022 |
| **delay-ABM (Yang/Zhou/Li 2022/2023)** | 観測価格に遅延 τ を注入する B2「遅延」の直接先行例。**最適遅延で安定性最大の非単調応答** | Physica A 599:127518 |
| **Mizuta PAMS/PlhamJ・U-Mart・LLM-ABM (FCLAgent)** | U-Mart は machine-agent kit が観測ベクトルを API 分離。FCLAgent は 4チャネル perception を text prompt 化 | arXiv:2309.10729; 2510.12189 |

### (partial) 観測はあるが集約スカラに collapse — degrade すると A と混線しやすい

**Lux-Marchesi**(価格トレンド `dp/dt` と opinion index `x=(n+−n−)/n` を群共有)、**Franke-Westerhoff SSV**(switching index に `(p−p*)²`・`n_f−n_c`・過去 profit)、**Kirman/Alfarano-Lux-Wagner**(出会った相手1人の状態)。観測は存在するが mean-field の共有集約量で、degrade しようとすると herding 強度 β や misalignment 感応度 α_p = **機構 A を触らざるを得ない**。

### (no) 観測チャネル不在 — B2 の attach point が物理的に存在しない

**Gode-Sunder ZI/ZIC**(私的 value/cost + 予算制約のみ)、**Cont-Bouchaud/Stauffer-Sornette percolation**、**Cont-Stoikov-Talreja / Smith-Farmer-Gillemot-Krishnamurthy / Farmer-Patelli-Zovko**(IID Poisson order flow)、**DSSW**(誤信念 ρ_t を外生注入)。**これらは B2 の negative control(null layer)として価値**——観測を degrade しても応答が flat なはず。

---

## 2. 観測チャネル介入(B2)の実装オプション

機構を ablate せず入力源だけ degrade する手法は**4類型に収束**する。いずれも需要関数・switching 係数・学習機構を不変に保ち、観測層にのみ作用する。

| scheme | 文献上の実装 | 代表先行例 |
|---|---|---|
| **(a) 平均化/粗視化** | MA window L 延長、descriptor 閾値の量子化、m-bit 履歴の解像度低下 | Chiarella-He-Hommes の L; SFI bit; MG の m |
| **(b) 低域通過(EMA)** | 観測系列に EMA/移動平均、高周波成分除去 | Essex FX ABM; LtFE limited-info |
| **(c) 雑音注入(SNR↓)** | `p_obs = p + N(0,σ²)`、signal precision↓、bit-flip ε | ABIDES σ_y²; Das; Carro F |
| **(d) 遅延(lag τ)** | 観測を t→t−τ に置換、feed に propagation delay + jitter | delay-ABM; ABIDES latency; ABMMS |

**B2 に最も素直なモデルクラス**(実装容易度順): ABIDES 型 noisy oracle / U-Mart 型 API 分離観測 → Carro 型外部情報 field(ただし global field なので `o_{i,t}` masking にはローカル分散改造が要る) → Chiarella-Iori の chartist 価格履歴窓(Model T の正準注入点) → SFI descriptor-bit truncation → voter/Ising 近傍観測(Model H) → LLM prompt degrade。

**設計原則(文献が一致)**: degrade を「機構が読む直前の単一インターフェース」(本 repo の `ctx.observe` / `toy/observation.py`)に集約し、その層でのみ適用。**係数(trend strength, herding β)を 0 にするのは ablate=禁止、引数の S/N を下げるのが B2=正解**。

---

## 3. 介入 before/after の測定法

1. **Same-seed paired / Common Random Numbers (CRN)** — **最有力基盤**。同一乱数列で θ=0 と θ>0 を走らせ pathwise 差分。`var[X−Y]=var[X]+var[Y]−2cov(X,Y)` で cov 最大化、報告例で**分散 80–93% 削減**。本 repo の seed 固定・prov.json と直結。
   - **死活的 pitfall**: 介入が乱数 draw の index をずらすと CRN の共分散が壊れる(seed desync)。対策は **B2 の degrade 用乱数を本流 RNG とは別ストリームに分離**し、介入有/無で本流 draw を同期。これは `provabm` の `ctx.random`(decision 単位 RNG stream)設計要件に直結。
2. **Susceptibility / response curve** — degrade 強度 θ(σ, τ, L)を sweep し出力統計量を θ の関数に。`χ=∂⟨O⟩/∂θ`。**機構ごとに曲線形状(符号・非単調性・閾値)が違えば弁別シグナル**。
3. **Event-window / DiD** — 介入時刻 t* 前後窓で SF・volatility・ACF 比較。toy の same-seed on/off は DiD の counterfactual を seed で厳密化したもの。
4. **Input-Output Correlation (IOC)** — 外部シグナル `i(t)` と market opinion の最大 cross-correlation(Carro 2015)。susceptibility に最も近い完成形テンプレ。
5. **Post-intervention dynamics / Omori 緩和** — 介入後回復を `n(t)∝(t+τ)^{−Ω}` で定量化(Lillo-Mantegna 2003)。

**前提**: chaotic/SOC 系は初期条件鋭敏性で単一経路の前後差がノイズに埋もれる → **アンサンブル(M=1000)で susceptibility を測る**。**「B2 を機構非改変で sweep し、same-seed event-window で SF 等価機構ペアを応答曲線で弁別する」測定設計は文献にほぼ不在**——ここが本 toy の貢献領域。

---

## 4. どの observable で signal が出るか

**load-bearing な実証知見**:

- **日次 SF(Hill tail index, |return| ACF, kurtosis, vol clustering)は介入応答が鈍く、SF 等価点では潰れやすい**(Eichfelder-Lau 2016, France FTT)。
- **intraday microstructure(1分足 realized vol, variance ratio, quoted spread/depth, Kyle's λ, magnet effect)は tick/tax 介入で明確に動く**(Kirchler-Huber-Kleinlercher 2011, lab)。
- **tick/tax の signal は spread/depth/price diffusion に出て日次 return 分布には弱い。しかも符号が市場構造で反転**(dealership は tax で vol↓、CDA は↑)。単一スカラで測ると機構弁別が崩れる。
- **delay と noise は安定性への符号が逆**(Yang 2022)。B2 の4 scheme は応答曲線が scheme ごとに符号まで割れうる → scheme 別に独立 response curve。

含意: toy の `analysis.py` は **microstructure 層と daily 層の two-layer measurement を並走**させ、検出力差そのものを弁別量に据える。これは「SF では分けられないが介入応答では分けられる」(設計ノート §2.5)を実証側から支持する。

---

## 5. 結論: この toy で B2 をどう実装すべきか(推奨)

**採るモデルクラス**: Model T・Model H の双方を**「観測ベクトル `o_{i,t}` → 機構 → order」の3層に分解**し、観測層を集約需要方程式から外在化する。これは spec §3.2/§3.3 の設計と整合し、文献が一致して示す唯一の機構非破壊 B2 経路。集約需要型(Lux-Marchesi/Franke-Westerhoff)をそのまま採ると観測が機構に collapse し B2 が A と混線する**文献上の失敗モードを構造的に回避**する。

**観測チャネルの定義先**:
- **Model T**: Chiarella-Iori 式2 の `過去 τ 期 return の移動平均`(+ fundamental gap + noise)を観測 core に据える。文献整合性が最高。
- **Model H**: voter/Ising 金融版・Carro 型の `集約行動履歴 ā_{t−L:t}`(他者行動の社会信号)を観測。

**B2 を刺す場所**: `toy/observation.py` の観測ベクトル構築段(= `ctx.observe` の中間層)にのみ degrade を post-process として挿入。masking scheme を文献の4類型に1対1で写像((a)平均化=MA window、(b)低域通過=EMA、(c)雑音=Gaussian σ、(d)遅延=lag τ)。機構層(`agents/trend.py`, `agents/herd.py`)・価格更新(`market.py`=B1)には**一切触れない**。

**何を測るか**:
- **基盤**: same-seed CRN(別 RNG ストリーム + 同期で seed desync 回避)を `provabm` の L2 capture と統合。
- **主弁別量**: θ-sweep の susceptibility curve を **scheme 別・two-layer(daily SF + intraday microstructure)で並走**。曲線形状を IR classifier の入力特徴に。
- **null layer**: 観測を読まない退化エージェント(ZI 相当)を入れ、B2 応答が flat であることを確認 → B2 が観測非依存経路に漏れていないことの検出。

**代替案とトレードオフ**:
- *集約方程式型同士のペア(FW vs Lux)*: B1 でしか叩けず B2 弁別実験が成立しない。**棄却**。
- *Carro 型 global field をそのまま採用*: 機構非破壊性は最もクリーンだが per-agent でない → ローカル分散改造が要る。
- *LOB を本格実装(Chiarella-Iori フル板観測)*: 観測 richness 最大だが B1 と混線、v0 スコープ超。**v0 は価格履歴窓 + 集約行動履歴の最小観測、板観測は将来拡張**。

**死活的注意**(spec に明示すべき): B2 実装時に「機構 A を ablate していない」ことを分離検証。対照群として **B1(tick/tax)介入と A(switching 強度)介入を並走**させ、「同一機構ペアに対し B1・A では弁別できないが B2 では弁別できる」非対称を取れば、Atlas の楔の edge を清潔に test できる。
