PRISM — 要件定義・仕様書 (v0.1 / draft)
Provenance-backed Reproducible Intervention-response Scoring of Mechanisms
静的に区別不能な機構を、介入というプリズムでスペクトルに分離する装置。 採点軸は「生成市場が本物っぽいか」ではなく「構造を一つ動かしたとき、現象が実データの自然実験と同じ向き・同じ大きさで動くか」。

0. 一行要約
任意の金融 ABM を、既知の構造変更を伴う実市場の自然実験コーパスに通し、「モデルが予測する stylized facts の変化量 ΔF̂」を「実データで観測された変化量 ΔF」と照合して機構の正しさを採点する、完全再現可能・監査可能な評価基盤。出力は順位表ではなく 位相図テンソル(機構族 × 介入クラス × fact → 一致度)。

1. 背景と立脚点 (なぜ作るのか)
静的 realism は機構を同定できない。 生成市場と実市場の分布距離(Wasserstein 等)を測る現行パラダイム(代表: LOB-Bench)は、underdetermination を原理的に解けない。構造的に異なる機構が同一の静的 facts 束を出すため、測っている量が機構を分離しない。分布距離をどれだけ精緻化しても「この機構が正しい」には一歩も近づかない。
機構の十分統計量は介入応答。 静的に等価な二機構でも、構造(tick size / 取引税 / latency 下限 / circuit breaker 等)を一つ動かしたときの facts の動き方が違えば、そこで初めて分離できる。識別情報は「静的等価な機構が介入下で乖離する場所」にのみ宿る。
市場には自然実験が大量にある。 米 decimalization (2001)、SEC Tick Size Pilot (2016–18)、仏取引税 (2012)、伊取引税 (2013)、瑞典取引税の失敗 (1980s)、HFT 参入、MiFID II、T+1 移行、フラッシュクラッシュ。各々が「既知の構造変更 × 測定済みの前後 facts 変化」のペア。
これは「現象論的だが非予測的」の完璧な操作化。 明日の価格は予測しない。予測するのは「構造をこう変えたら現象がこう変わる」という現象論そのものの変化。「理解した」を反証可能形に落とした状態であり、予測/収益軸(例: Izumi 研)とも静的 realism 軸(LOB-Bench)とも異なる 第三の正当性軸。SCSLab の知的指向に最も整合する。
北極星(ツールのスコープ外、後述の下流科学)。 介入応答を全 facts × 全介入で埋めると、Cont (2001) 以来フラットに並ぶ stylized facts チェックリストを 依存 DAG に書き換えられる可能性がある。「どの fact がどの fact の上流か」「どの少数 order parameter から残りが従属するか」。少数の order parameter から残りが状態方程式的に出る構造を発見できれば、それが金融 ABM のカルノーサイクルになる。PRISM はその実験装置であって、DAG 発見そのものはツール要件ではない(§10)。

2. ポジショニングと先行研究 (作る前に潰すべき前提)
既存物
何をしているか
PRISM との関係
LOB-Bench (Nagy et al. 2025, JPM AI Research / Oxford)
LOBSTER 形式の生成データの静的 realism を分布距離・判別器・market impact で採点
直交・補完。 静的 realism は PRISM では「入場券」= 適格ゲート(§6.1)に格下げ。採点軸ではない
微細構造の DiD/合成コントロール研究群 (Tick Size Pilot, FTT 等)
各介入の経験的効果を因果推論で推定
正解(ground truth)の供給源。 ただし推定量であり手法依存。provenance で封じる対象(§3.1)
agent-based FTT 文献 (Westerhoff 系等, 2000s〜)
ABM に取引税を入れて volatility 等の比較静学を観察
比較静学の先行例。 査読対策上の差別化点は「モデルが何を言うか」→「自然実験のΔに当たるか」への軸移動

新規性の所在(検証要): 部品はすべて存在する。存在しないのは「ΔF̂ vs ΔF を機構族 × 介入クラスのテンソルとして、因果推論側と ABM 側を縫い、完全再現可能に採点する装置」。この「縫い目」が未開拓と判断するが、WP0 で正式な文献レビューにより確証/反証する。

3. コアデータモデル
3.1 Natural Experiment Record (NER) — 経験側の正解原子
自然実験 1 件を再現可能に封じた不変レコード。正解は固定値ではなく、識別仮定つき推定量であることを構造で強制する。
ner_id: "tspp_2016_us_equity"
intervention:
  class: "tick_size_increase"          # Abstract Intervention Space のクラス(§3.2)
  spec:
    canonical_params: {min_tick: {from: 0.0001, to: 0.05, unit: "USD/share_price_ratio"}}
    venue: "US_equity_smallcap"
    date_effective: "2016-10-03"
    assignment: "randomized"           # 識別の質に直結する最重要メタ
data:
  pre:  {source: "LOBSTER", vintage: "...", window: "2016-Q3", hash: "sha256:..."}
  post: {source: "LOBSTER", vintage: "...", window: "2016-Q4", hash: "sha256:..."}
  control_group: {definition: "...", hash: "sha256:..."}   # DiD の対照
ground_truth_delta:                    # 1 介入につき複数の fact について
  - fact_id: "volatility_realized"
    estimator_version: "fact_lib@1.3.0"
    causal_method: "did_firm_fe"        # 因果同定法(差し替え可能・複数併記可)
    causal_assumptions: ["parallel_trends", "no_anticipation", "post_pilot_reversal_check"]
    delta_hat: {value: +0.18, ci95: [0.11, 0.25], unit: "relative"}
    confounds_handled: ["venue_migration_maker_taker"]
    references: ["..."]                 # 実測 Δ の出典(再算出 or 引用)
provenance: {...}                       # §3.5

要件:
同一介入に対し 複数の causal_method を併記可能(頑健性は「どの同定法でも Δ の符号が一致するか」で測る)。
assignment: randomized か否かを必須メタとし、スコアの信頼度重みに反映(§6.4)。
実測 Δ は可能な限り PRISM 内で生データから再算出する(引用値の丸呑みは provenance 上「外部主張」とタグ付け)。
3.2 Abstract Intervention Space (AIS) — 装置か逸話集かの分水嶺
これが解けると装置になり、解けないと逸話集で終わる。 最重要設計対象。
decimalization・取引税・latency 下限・circuit breaker・最小ロット等の異種介入を、機構パラメータへの写像が一意に定まる正準空間へ射影する schema。
各介入クラスは (canonical_params, mechanism_mapping) を持つ。
mechanism_mapping: 正準パラメータ → ABM の構造パラメータへの写像規約(例: tick_size_increase → LOB の価格グリッド離散化幅; transaction_tax → round-trip コスト項)。
写像が一意でない介入(例: MiFID II = 複合介入)は 分解可能性 を必須属性とし、分解不能なものは MVP 対象外に明示分類。
AIS は versioned。新介入クラス追加は schema 拡張 PR として provenance に残る。
MVP は AIS を 1〜2 クラス(tick_size, transaction_tax)に限定。汎用化は Phase 3。
3.3 Fact Estimator Library — 実データと模擬データに同一コードを適用
stylized facts を計算する versioned 関数群。実データと ABM 出力に対して同一実装を適用することを契約で強制(片側だけ別実装だと Δ 比較が無意味化する)。
初期 fact 集合(MVP): volatility_clustering, leverage_effect, gain_loss_asymmetry。拡張: fat_tails, epps_effect, volume_volatility, autocorr_structure ... 各 fact は (estimator_fn, version, output_schema, applicable_data_types) を持つ。
3.4 Model Adapter — 任意 ABM を差し込む契約
class ModelAdapter(Protocol):
    def calibrate_baseline(self, pre_data: MarketData, ais_context: dict) -> CalibrationArtifact:
        """介入前レジームへ較正。返り値は provenance 可能な不変成果物。"""
    def apply_intervention(self, calib: CalibrationArtifact,
                           intervention: CanonicalIntervention) -> "ModelAdapter":
        """AIS の正準介入を構造パラメータへ写像して適用した新インスタンスを返す。"""
    def simulate(self, seed: int, n_paths: int) -> SimulatedMarketData:
        """canonical 出力形式(LOBSTER 互換 or 集約 facts 入力形式)で吐く。"""
    def describe_complexity(self) -> ComplexitySpec:
        """MDL 重み用: free parameter 数 + 構造記述長(§6.4)。"""

SG (Speculation Game) は最初の参照 adapter。3-action / round-trip / 現実-認知世界の相互射影を実装。
adapter は ABM 本体に非侵襲(wrapper)。ABM のソースは外部 repo のまま、commit hash で参照。
3.5 Provenance Layer (#2 の統合) — PRISM の本体
経験側 Δ 抽出とシミュレーション側 Δ 生成の両方を bit 単位で再現・監査可能にする横断層。1 セル(機構 × 介入 × fact)の結果は、以下を完全に復元できなければ「未検証」とする:
経験側: data vintage + hash / causal_method + assumptions / fact estimator version
模擬側: ABM commit hash / calibration artifact / seed + RNG state / AIS 写像規約 version / fact estimator version (経験側と同一であること)
採点側: scoring function version / match 判定規約 version / MDL 重み規約 version
内部表現は W3C PROV (PROV-O) を採用(Entity=データ/較正/結果, Activity=較正/介入適用/推定, Agent=モデル/手法)。ただし PROV-O は内部実装であり製品の前面には出さない。外面は「監査レポート(誰でも 1 セルを再実行して同じ数字が出る)」として提供。

4. アーキテクチャ
　　　┌─────────────────────────────────────────────┐
            │            Provenance Layer (PROV-O)         │ ← 全 Activity/Entity を記録
            └─────────────────────────────────────────────┘
   経験側パイプライン                          模擬側パイプライン
 ┌──────────────────┐                      ┌──────────────────────────┐
 │ Raw market data  │                      │ Model Adapter (e.g. SG)  │
 │  (pre/post/ctrl) │                      └────────────┬─────────────┘
 └────────┬─────────┘                                   │ calibrate_baseline(pre)
          │                                              ▼
 ┌────────▼─────────┐                      ┌──────────────────────────┐
 │ Causal Estimator │                      │ apply_intervention(AIS)  │ ← AIS 写像
 │ (DiD / SynthCtrl)│                      └────────────┬─────────────┘
 └────────┬─────────┘                                   │ simulate(seed)
          │ ΔF (ci95)                                    ▼ ΔF̂
 ┌────────▼─────────┐   ┌───────────────┐   ┌────────────────────────┐
 │ Fact Estimator   │◄──┤ Fact Lib (共有)├──►│ Fact Estimator         │
 └────────┬─────────┘   └───────────────┘   └───────────┬────────────┘
          │                                              │
          └──────────────────┬───────────────────────────┘
                              ▼
                  ┌────────────────────────┐
                  │   Scorer (ΔF̂ vs ΔF)    │  ← match 判定 + MDL 重み
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │  Phase-Diagram Tensor   │  機構族 × 介入クラス × fact
                  └────────────────────────┘

設計原則: Fact Estimator は経験側・模擬側で物理的に同一モジュールを共有(分岐実装を禁止)。

5. インターフェース契約(抜粋)
NER schema: §3.1。YAML/JSON、JSON Schema で検証。
ModelAdapter API: §3.4。新規 ABM はこの Protocol を満たせば即評価対象。
CanonicalIntervention: AIS が発行する正準介入オブジェクト。adapter 側が mechanism_mapping で構造パラメータへ落とす。
Result cell: (model_id, model_commit, intervention_class, fact_id, delta_hat_model, delta_obs, match, confidence, provenance_uri)。
公開面: Python ライブラリ + CLI。prism run --adapter sg --ner tspp_2016 --facts leverage,volclust。結果は再現可能アーティファクトとして emit。

6. スコアリング設計
6.1 適格ゲート(静的 realism = 入場券)
ABM がそもそも基準レジームの静的 facts を最低限満たすかを LOB-Bench 流の安価なチェックで確認。通らないモデルは介入採点に進めない(計算節約 + 「曲線すら当てられない機構の介入応答」を排除)。ゲートはスコアではない。
6.2 一次採点 = 符号一致 (direction)
sign(ΔF̂) == sign(ΔF) か。最も頑健で、交絡耐性が高い。MVP の主指標。
6.3 二次採点 = 大きさ一致 (magnitude)
ΔF̂ が ΔF の ci95 内か / 正規化距離。較正誤差の多くは Δ(差分)で相殺されるが、レベル較正がレジーム違いだと Δ も歪むため confidence と併記。
6.4 機構間比較 = MDL 重み
パラメータ寡少で多くの介入を当てる機構を上に。score = coverage(正しく当てた介入クラス数) − λ · description_length。description_length の操作化(free parameter 数 + 構造記述長)は versioned かつ監査可能な規約として固定し、規約自体を provenance に残す(恣意性を封じる)。
6.5 出力 = 位相図テンソル(順位表ではない)
T[mechanism_family][intervention_class][fact] = {match, confidence}。可視化は「どの機構族がどの介入クラスを当てるか」のヒートマップ/相図。スカラ順位は導出ビューの一つに過ぎない。

7. 致命的な設計判断(推奨つき)
AIS 標準化の深さ — 完全汎用を狙うと永遠に出荷できない。推奨: MVP は tick_size と transaction_tax の 2 クラスにハードコード気味に作り、3 クラス目を足す時に初めて抽象化を一般化する(早すぎる抽象化を避ける)。
最初の試金石 — 推奨: SEC Tick Size Pilot を 1 セル目(ランダム割当 → 交絡最小 → 配管検証に最適; tick は LOB グリッドへ一意写像)。取引税(仏2012/伊2013)を 2 セル目(SG の round-trip 機構を実際に割りに行く診断的介入)。順序を逆にすると配管バグと機構失敗が区別不能になる。
正解の再算出 vs 引用 — 推奨: 生データから再算出を既定。引用値は「外部主張」タグで暫定許可するが、再算出で置換するまで「未検証」表示。
match の定義 — 推奨: MVP は符号一致を主、大きさは confidence 付き副指標。最初から magnitude を主にすると較正未成熟で全モデルが落ちる。
較正負担 — baseline 較正は重い。推奨: 較正ハーネスは別モジュールとして切り出し(将来 idea#6 として独立資産化可能)。較正の不確実性は Δ の confidence に伝播させる。
交絡の縫い目 — 因果推論側(DiD/合成コントロール)を経験側に内蔵し、ABM 側の比較静学と同じ fact 定義で突き合わせる。この縫い目が PRISM の中核的貢献であり、手抜き不可。

8. フェーズ計画と MVP
Phase
内容
終了条件
WP0 先行研究・データ可用性スパイク
LOB-Bench / 微細構造 DiD / agent-based FTT の正式レビュー。Tick Size Pilot と仏/伊 FTT の facts レベル micro データ入手可否を確認。新規性の確証/反証
「縫い目が未開拓」が確証 or 反証。MVP データが入手可能と確認
Phase 1 単一セル end-to-end
SG × Tick Size Pilot × {leverage, vol clustering, gain/loss}。provenance 完備で 1 セルが他人に bit 再現される
第三者が prism run で同一 Δ を再現。符号一致の可否が出る
Phase 2 診断介入 + 2機構目
取引税を 2 クラス目に追加。SG とは別の機構族(例: Chiarella-Iori 型)を 2 体目の adapter に。位相図が 2×2 で埋まる
「静的等価だが介入で割れる」事例を 1 つ実証
Phase 3 一般化 + 下流科学
AIS 一般化、facts 数拡大、依存 DAG 解析モジュール(下流科学)を接続
複数 fact 間の上流/下流関係の仮説が 1 つ提示できる

MVP = Phase 1。 「SG に tick size 介入を入れたとき、leverage effect/vol clustering が Tick Size Pilot の DiD 推定と同じ符号に動くか」を、誰でも再現できる形で 1 つ出す。これが出れば概念実証として十分。

9. 受け入れ基準(Definition of Done)
任意の第三者が公開アーティファクトから 1 セルを再実行し、同一の Δ̂ と同一の match 判定を得られる(bit 再現)。
経験側 Δ が causal_method・assumptions・ci95 つきで記録され、別の causal_method に差し替えて符号頑健性を確認できる。
Fact 計算が経験側・模擬側で同一モジュールであることが provenance 上検証可能。
静的適格ゲートを ON/OFF できる。
位相図テンソルがスカラ順位に潰れていない(セル単位で confidence 付き)。

10. スコープ外(明示)
価格予測・売買シグナル・収益最適化(ルート(a) の価値観に反する)。
静的 realism を一次採点軸にすること(それは LOB-Bench の役割)。
stylized facts 依存 DAG / order parameter / 「熱力学」の発見そのもの(これは PRISM が可能にする下流の科学であって、ツール要件ではない。Phase 3 で解析モジュールとして接続するに留める)。
分解不能な複合介入(初期は MiFID II 等を除外)。

11. リスクと失敗モード
逸話集化 — AIS 標準化に失敗すると、各介入が個別ハックの寄せ集めになり装置にならない。最大リスク(§7-1 で緩和)。
較正信頼性 — baseline 較正がレジーム違いだと Δ も歪み、当局/査読者が相手にしない。Δ 採点 + confidence 伝播で緩和するが本質的弱点。
交絡漏れ — 自然実験は介入と同時に他要因が動く(例: tick 変更時の venue migration)。因果同定が甘いと「正解」が汚染。複数 causal_method 併記で頑健性を可視化。
査読「Westerhoff が先」 — agent-based FTT の比較静学は既出。差別化は「自然実験の実測Δに当てる + 再現可能テンソル」という軸移動であることを明示し続ける。
データ可用性 — facts レベルの micro データ(特に古い瑞典 FTT、仏/伊 FTT)が入手困難な可能性。WP0 で先に潰す。
MDL の恣意性 — description_length 定義次第で順位が動く。規約を versioned 監査対象にして緩和。

12. 製作者(claude code)が実装中に決めて良いオープン論点
どこを最初に深掘りするか: (a) AIS = 介入空間の抽象化 / (b) facts 依存 DAG の定式化 / (c) SG に対する最初の自然実験の選定。本仕様は (c)=Tick Size Pilot を既定にしているが、研究的興奮は (b) にある——MVP は (c)、北極星は (b)、という二段構えで合意するか。
2 体目の機構族を何にするか(SG と「静的等価だが介入で割れる」関係にある候補を意図的に選ぶ必要がある)。
MDL の description_length 定義の初版規約。
公開範囲: PRISM 本体を OSS オープンコアにする(ルート(a) の評判戦略)か、Atlas(NER コーパス)と本体を分離するか。
「match」の合否しきい値: 符号一致のみで Phase 1 を合格とするか、ci95 内一致まで要求するか。

v0.1 draft. §12 が解けてから v1.0。WP0 未了のまま Phase 1 着手禁止。

