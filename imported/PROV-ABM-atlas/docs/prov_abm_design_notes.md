# PROV-ABM / Intervention Atlas — 設計ノート

`date: 2026-06-04` · `source: Claude との対話から起こし` · `status: working / 未確定多数`

---

## 0. TL;DR（今日確定した骨）

1. **作るのは「経済学者向けモデリング framework」でも「標準そのもの」でもない。** 楔=機構弁別ベンチ（**Intervention Atlas**）、土台=provenance/再現性スペック（**PROV-ABM**）。この二本立て。
2. ベンチマークが測るのは **hygiene（監査可能性）であって validity ではない**。GT が無い以上、validity を直接ランクするのは原理的に不可能。validity と名乗った瞬間に信頼を失う。
3. `ctx.*` API（L2/L3）が買えるのは **再現性（安い）+ sound な invariance（honest/negligent 相手、AST 強制で）**。微細反実仮想（`must`）と adversarial soundness は L4＝restricted DSL が要る。ただし **その DSL は「制限付き Python サブセット」**で、新構文は要らない。
4. reachability は単一じゃなく **`reported` / `may` / `must` / `exact`** の4分割。**主張↔reach の対応を validator が強制**することで標準が「正直」になる。
5. 最大の未解決ゲート二つ:**(i)** メインストリーム経済学が ABM に何を要求してるか（検証/再現性 か、対 DSGE/VAR の OOS forecast か）。**(ii)** 介入応答は stylized facts では分けられない機構を**本当に弁別するか**。両方とも、重い実装の**前**に確かめる。

---

## 1. 戦略フレーム

### 1.1 賭けの再定義
- 行動指針:「ABM を新時代経済学の必須道具に昇格させ、その第一人者になる」。ただし**昇格させるのは Simudyne / Macrocosm 等でも構わない**。
- 採った賭け:**hero-builder（the Nth sim を作る）ではなく leverage position（arena / 審判 / 検証層を握る）**。Nth の sim より arena を握る方がレバレッジが大きい。← turn 1 の「帝国を建てる癖」からの実質的修正として妥当。

### 1.2 テーゼの弱い形 vs 強い形
- **弱い形**「検証標準が分野の昇格を unblock する」← 因果が怪しい。ImageNet は DL を unblock してない、capability が unblock した。検証インフラは普通**成熟の lagging indicator**。
- ただし経済学には固有の disanalogy:ABM が嫌われる理由は方法論的 **respectability**（何でも fit/規律なし/反証不能/forking paths）。規律を課す弁別ベンチは ML より causally 効きうる（pre-registration + replication が実証経済・心理の不信を攻めたのと同型）。
- **強い形（採用）**:「昇格は capability で起きる（LLM agent / quantitative macro ABM が急速に来てる）。その inflection の瞬間に **canonical な arena/審判を握った者が中心の durable な位置を取る**」。picks-and-shovels / Schelling-point の賭け。
- → 強い形なら最適化対象は **speed-to-canonical と adoption の breadth** であって foundation の rigor ではない。

### 1.3 二アーティファクト構成と coupling
- **(a) Intervention Atlas**＝機構弁別ベンチ／phase-diagram leaderboard。**公開の楔**。adoption physics は bottom-up・low-friction・maximally open（ImageNet/GLUE/MLPerf/LOB-Bench 型）。steward も buyer も要らず、便利で公開なら広がる。
- **(b) PROV-ABM**＝provenance/再現性スペック。**土台**。top-down・trust-required・heavyweight。
- 二つは adoption physics が**逆**。誤った couple は両方を殺す:「leaderboard 掲載に PROV-ABM 認証必須」は (a) を friction で殺し (b) を人工的に支える。切り離すと (b) が forcing function を失う。
- **唯一の clean な coupling**:`benchmark が dispute を生む → spec がその dispute を解決する`。leaderboard が contested になる（「X は cheat した/再現できない/介入が localize されてない」）時、spec が**紛争の審判プロトコル**として adopt される。後述の `may\must` gap がこの coupling の定量版（§5.5）。

### 1.4 メタ:継続監視すべき傾向（癖）
対話で**3回反復**した傾向 → 問題を見ると最大の構えに飛び、**adopt を駆動する楔より、rigor の効く土台に投資する**（turn1: governance≫implementation / turn2: spec≫benchmark / 全体: L4 機構≫L2 便益）。「証明可能で綺麗な部分」への引力で、レバレッジの実在（ぐちゃぐちゃで政治的な adoption）からの逃避として機能しうる。**今回の `reported`/L2-first 設計はこれを能動的に矯正する方向**だが、要・継続監視。canonical になるのは最も rigorous な奴ではなく、最初で・公開で・維持される奴。

---

## 2. Intervention Atlas（ベンチマーク）の設計

### 2.1 スコアは何を測るか — 三分割
leaderboard スコアの候補は2つではなく**3つ**:
1. **separation / discrimination** — モデルでなく**ベンチマークの性質**（battery が機構を分けるか）。**GT-free**。
2. **hygiene / auditability** — モデルの性質、**GT-free**（PROV-ABM の検査を通るか＝後述 Type1）。
3. **validity** — モデルの性質、**参照が要る**（GT/距離評価＝Type2）。

→ **1 と 2 は正直に提供できる。3 は参照なしには原理的に不可能。** v1 のスコアは **hygiene（Type1）**、決して validity と呼ばない。売り文句は「最も因果的に監査可能な ABM の leaderboard」。

### 2.2 survival test の Type1/Type2 分解（重要）
「反証への生存（survival against falsification）」は epistemic status が正反対の2つを隠す:
- **Type1:アーキ/因果整合性の生存**（到達不能ノードからの影響なし、未捕捉チャネルの非決定性漏れなし）。**現実への参照ゼロで検査可能**＝PROV-ABM validator がやること。GT-free。**だがランクするのは hygiene であって validity ではない**（ファンタジー経済の完璧監査モデルが首位に立つ）。
- **Type2:SME 許容境界**（応答が専門家定義の plausible range / 期待トレンド内か）。**GT を裏口から interval/directional 参照として持ち込む**＝OPEN-4 が帽子を被り替えただけ。ポパー召喚も救いにならない（反証は参照を消さず、severe test の選択に再配置するだけ；severity は理論から来る）。
- **Type2 の本当の危険**:メインストリーム理論で定義した許容境界は、**異端だが正しいモデルを正確に罰する**。fat tails / 内生的危機 / leverage cycle は当時の Gaussian-equilibrium prior を violate したもの。「期待からの逸脱」を減点する survival test は**正しかったモデルを最下位にする**＝consensus 強制装置＝**戦略目標（ABM 昇格）の正反対**。

→ **Type1 は keep（hygiene スコア＋ (a)↔(b) coupling）、Type2 は隔離**。

### 2.3 v1 の形
- **descriptive Atlas**（機構応答の地図、ランクなし）+ **hygiene スコアの leaderboard（Type1）** + **fit-for-purpose tracks**（介入目的＝use class ごとに分割。= PROV-ABM §8 use-bound cert / §G.2 per-battery。再導出せず使う）。
- 「Atlas」という命名は descriptive（territory を map する、評価しない）で正しい方を向いている。normative 層（どの応答が正しいか）は reference-pinning governance で後から accrete。
- 注意:純 descriptive な地図には順位が無い → atlas であって leaderboard じゃない。**leaderboard の competitive juice は hygiene スコアが担う**（validity ではなく）。

### 2.4 identifiability の背骨（欠けている）
- 弁別ベンチの核オブジェクト:既知機構 {M₁…Mₖ} × 介入 battery {do(X₁)…do(Xₙ)} に対し、応答ベクトル φ-response が応答空間で**分離**すること（機構→応答シグネチャ写像が分類可能な程度に injective）。これは experimental-design / identifiability 問題。
- 正しい背骨 = **optimal model-discrimination design**:**T-optimality（Atkinson & Fedorov 1975）**、Box–Hill。「競合モデルを最大に弁別する実験設計」がまさにこれ。介入の選び方に原理を与える。
- 「なぜ field が stylized-facts checklist を捨てて phase diagram に来るか」の唯一の答え = **identifiability**:checklist は非弁別的（fat tails も vol clustering も多くの機構が出す）、介入応答は弁別的（機構ごとに do(X) 応答が違う）。これを前面に。

### 2.5 ★ make-or-break（最優先・実装の前にやる）
**経験的主張「介入応答は、stylized facts では分けられない機構を分ける」を toy で検証したか?** 介入応答も似た応答に collapse する可能性は十分ある。collapse するなら楔に edge は無い。
→ 最小の既知機構ペア（例:fundamentalist 比率違いの2モデル）で、`do(X)` 応答が stylized facts より分離するかを確かめる。**1週間で済む。これが最優先。**

---

## 3. PROV-ABM 捕捉層:`ctx.*` API はどこまで sound か

API 形:`ctx.observe / ctx.read_own_state / ctx.random / ctx.submit_order`。問題は「ctx が何を見られて、何が横を漏れるか」に還元。**漏れ口は2種類**、それぞれ別の claim を壊す。

### 3.1 漏れ口 (A):intra-function（ctx は decide の内側が見えない）
ctx が知れるのは**入力集合と出力**だけ。関数内の実依存（order は price 依存か cash 依存か、`if` が何を分岐させたか）は黒箱 → **過大近似するしかない**（出力は記録した全入力に依存と仮定）。これは LLM-oracle over-approximation（§3.4）が任意の不透明 Python 関数に効くだけ。

例:
```python
def decide(ctx):
    price = ctx.observe("market_price", asset="A")  # 入力 ✓
    cash  = ctx.read_own_state("cash")              # 入力 ✓（読むが使ってない）
    noise = ctx.random("decision_noise")            # 入力 ✓ 再現可能
    if price + noise < 100:                         # control依存、ctx不可視
        return ctx.submit_order("buy", asset="A", qty=1)  # 出力 ✓
```
真:order ← {price, noise}。過大近似:order ← {price, cash, noise}。`do(cash)` に対し:
- **invariance（R⊇D*）**:過大近似は真の invariance（order は cash に不変）を**棄却**＝保守的＝sound だが弱い。**安全方向。**
- **response-read（R⊆D*）**:order に φ を読むと「これは do(cash) 応答」と**通ってしまう**が真の応答はゼロ ＝ **unsound 方向**。強い反実仮想は ctx だけからは出せない。

### 3.2 漏れ口 (B):hidden inputs（invariance を壊す本命）
過大近似が invariance に safe なのは**全入力が ctx を通る限り**。捉えてない入力があると真の辺が欠落 → R⊉D* → **invariance が unsound**。素 Python が許す経路:module-level mutable global / closure・共有 mutable / aliasing / **素の `self.cash`（ctx 経由を強制しない）** / 非 ctx 乱数（`np.random`）/ 外部 IO / wall-clock / entropy。
→ **`ctx` API 単体は hidden-channel-zero（B1/OPEN-1）を解かない。opt-in 規約であって境界じゃない。** ここが「ctx で済む / DSL が要る」の分水嶺。

### 3.3 主張別 soundness verdict

| claim | honest | negligent | adversarial |
|---|---|---|---|
| 再現性 (R0/R-env) | ctx 単体 | ctx + AST lint | ctx + AST + 固定ランタイム※ |
| invariance (R⊇D*) | ctx 単体（過大近似）| ctx + AST whitelist | **restricted DSL / sandbox（L4）** |
| 微細反実仮想 (R⊆D*) | ctx + **動的taint**（純Python限定）| + AST | **restricted DSL（L4）** |

※固定 PYTHONHASHSEED、`id()`依存・set順序・FP非決定性の封じ込め。

読み:**再現性はタダに近い**（AST で非ctx乱数/IO を静的に禁じれば honest/negligent は sound、adversarial もランタイム固定でほぼ届く）。**sound な invariance は L3+AST で届く（L4 不要）**。**微細反実仮想は本質的に L4**（または numpy/control 但し書きつき taint）。granularity 注意:**エージェント粒度**の反実仮想（効果はこのエージェントを通ったか）は ctx 単体で sound、taint/DSL が要るのは**サブエージェント粒度のチャネル帰属**（銀行内 leverage か price か）だけ。

### 3.4 dial-not-wall（核心の認識）
**L3→L4 の境界は壁でなく「Python をどれだけ禁じるか」のダイヤル。** global/closure/reflection/非ctx状態/非ctx乱数/非ctxIO を AST で禁じた**制限付き Python サブセットは、それ自体が restricted DSL**（構文と parser を Python から借りてるだけ）。経済学者は**新構文を覚えない**。彼らが書くのは見た目ふつうの `decide(ctx)`、checker が soundness を壊す構文を棄却、必要な claim にだけ taint を足す。
→ 「ctx API はどこで終わり DSL はどこで始まるか」の答え:**両者は重なる。** DSL = ctx API + 強制された構文・意味制限（+ R⊆D* 用 taint）。別言語ではない。

### 3.5 enforcement spectrum（脱出口つき）
1. **AST whitelist（静的）** — 偶発+多くの adversarial を捕捉。だが厳しくすると ≒ DSL。脱出:dynamic reflection（要・追加禁止）。
2. **restricted builtins/namespace（動的）** — honest-author 防御、adversarial に漏れる。
3. **proxy taint（動的）** — 関数内 data-dependence 精度（R⊆D*）を回復。但し **numpy/pandas/torch の C 拡張が taint を洗濯**、**implicit/control flow を取りこぼす**、観測者効果（B3）リスク、10–1000× 遅い。
4. **bytecode 書換/compile** — = L4。

---

## 4. レベル梯子（L0–L5, refined）

| Lv | 名前 | 内容 | 用途 / licenses |
|---|---|---|---|
| L0 | 自由 ABM | 任意（NetLogo/Python）+ ログ/seed/環境 | 探索・教育・仮説形成 |
| L1 | Reproducible | seed/依存/入力digest/出力digest 記録、同環境で再実行 | 再現性 appendix |
| L2 | Instrumented | ctx 主要API（observe/decide/order/settle/random）だけ記録 | 系譜・感度battery・実験記録 ＝ **adoption engine** |
| L3 | Capability | world を渡さず capability だけ + 静的AST + namespace | **migration bridge**。sound `may` → invariance（非adversarial）|
| L4 | Restricted DSL / exact | 全 read/write/control 捕捉（制限Python = DSL）| **claim certification**。sound `must`/`exact` → 微細反実仮想・因果経路・adversarial invariance |
| L5 | Formal Core | Lean で validator/reachability の性質を形式化 | logic 象限の保証（実務直接ユーザー外）|

**L4 の梯子バレットは2つの別物を混ぜていた**ので分離した:L4 が固有に買うのは **(a) adversarial 耐性** と **(b) 関数内 R⊆D* 精度** の2つだけ。honest/negligent の invariance は L3+AST で届く。
**teleology 注意**:L3 は「全員が渡る橋」でなく「claim を出す少数派の任意 off-ramp」。研究者の9割は L2 に永住。adoption 価値は恒久的に L1–L2。**研究者便益（再現性appendix / seed・data digest / 感度battery / 反実仮想比較表 / バージョン追跡 / 「どのコードで出たか」）は全て L1–L2 に乗り、OPEN-1 に一切触れない。** → 楔（便益）は土台（exact capture）から切り離せる。

---

## 5. reachability 四分割

### 5.1 may/must/exact = PL の標準双対
`may`/`must` は dataflow analysis の may/must-analysis 双対で、soundness 方向に完璧写像:
- **`may reach` = 過大近似 = R⊇D***（v は u に依存し**得る**）
- **`must reach` = 過小近似 = R⊆D***（v は u に**必ず**依存）
- **`exact reach` = may=must = D***（exact capture/L4 でのみ）

**概念の心臓（直感と逆）**:「到達**しない**」の証明には最も寛大な reach（may）が要る（寛大な may でさえ除外＝真に除外）。「本当に到達**する**」の証明には最も吝嗇な reach（must）が要る（吝嗇な must でさえ含む＝真に含む）。invariance は does-not 性質→上界、反実仮想は does 性質→下界。

### 5.2 `reported reach` が独立カテゴリな理由
ctx ログ上の reach は **2軸で歪む**:関数内は**過大**（may 的）、hidden channel は**過小**（欠落）。**よってどちらの方向にも sound bound でない**（over でも under でもなく両方向に外れる）→ invariance にも反実仮想にも sound に使えない、再現性/探索専用。
**`reported` が sound な `may` に昇格するのは hidden-channel gap を閉じた後だけ**（AST whitelist 強制後）。これが L3 enforcement の正確な効能 = `reported` → sound `may` のアップグレード。

### 5.3 払い戻し表（主張 ↔ reach。validator が強制）

| 主張 | sound に出せる reach | 論理 |
|---|---|---|
| invariance「X は Y に到達しない」 | **may**（⊇D*）| a∉may ⟹ a∉D* |
| 微細反実仮想 / response-read | **must**（⊆D*）| a∈must ⟹ a∈D* |
| 因果経路の厳密帰属 | **exact**（境界内）| may=must |
| 再現性 / 探索 / 系譜提示 | **reported** | 因果主張ゼロ |

→ **validator は `reported`/`must` からの invariance 発行を拒否する。invariance は `may` からのみ、反実仮想は `must` からのみ。** これが標準を「正直」にする機構。marketing slippage（`reported` で経路が見えない→「不変」）はここで構文的に禁じる。

### 5.4 reach ↔ level 対応

| reach | 必要な捕捉 | レベル | licenses |
|---|---|---|---|
| `reported` | ctx ログのみ | L2 | 因果主張なし |
| `may`(sound) | 入力完全性=全入力 ctx 経由（AST 強制）| L3 | invariance（honest+negligent）※ |
| `must`(sound) | 関数内依存を下から確定（taint=部分/DSL=完全）| L3.5–L4 | 微細反実仮想 |
| `exact` | 完全性+精度を対 adversary | L4 | 因果経路・adversarial invariance |

※ adversarial invariance は reflection 脱出で `may` 完全性が崩れるため exact/L4 要。

**但し書き**:(1) flavor は4つで終わらず **may/must × {data, control, all} basis の直積**が真の対象（§4.1）。証明書は健全な既定（反実仮想=`must-data`、invariance=`may-all`）を報告。(2) `exact` は絶対でなく**「effect 型境界内で may=must」**。covert channel 含む絶対 exact は対 adversary で到達不能（OPEN-1）→ `exact reach (within declared boundary)` と必ず但し書く。

### 5.5 ★ `may \ must` gap（今日いちばんの上物）
may ⊇ D* ⊇ must なので、**`may \ must` = 未決領域**（真の子孫か否か、捕捉/解析が決められない addr）。**サイズ |may \ must| が精度メトリクス**（§4.2 control_precision_loss の一般化）。
効く理由:
- **GT 不要で計算できる**（正しさでなく解析精度の話、純 G 上）。
- だから**正当な leaderboard 軸**:「因果構造をどれだけタイトに pin down できるか」= hygiene ランク（§2.1-2 の Type1 と一致）。
- **capture level を上げると gap が縮む**（L2→L3 で hidden channel 閉じ may が締まる、taint/L4 で must が太る）→ gap 縮小 = 上位 level 採用を**報酬**。
→ **§1.3 の (a)↔(b) coupling の定量版**。「leaderboard 上位＝捕捉を締める＝foundation を採る」が gap 一個のスカラで効く。ベンチのスコア（hygiene 軸）・標準の claim 正直性・capture level の adoption 圧が `may\must` で一点に結ばれる。

---

## 6. Open questions / 次アクション

**ゲート（重いものの前に）**
- [ ] **(i) 経済学が ABM に何を要求してるか**を解決:検証/再現性 か、対 DSGE/VAR の OOS forecast か。referee の reject 理由・方法論批判・econ faculty に直接。最安・最高 ROI・全戦略を gate。(ii) なら検証層は時期尚早、forecast を示す側へ。
- [ ] **(ii) 介入応答の弁別性を toy で検証**（§2.5）。collapse するなら楔に edge なし。

**設計を詰める候補**
- [ ] validator の「主張↔reach」拒否ロジック最小仕様（どの組合せを REJECT するか）。
- [ ] `may\must` gap を leaderboard スコアにする時の正規化（モデルサイズ・battery 依存の bleach。JFWE task 管理の time-reference bleaching と同型問題）。
- [ ] taint で `must` を部分提供する時、numpy 洗濯をどこまで許容し証明書にどう開示するか。
- [ ] AST whitelist の最小ルールセット（何を静的に棄却するか）。
- [ ] capture-failure 検出機構:**canary intervention** を battery に必ず混ぜ、validator が拾えなければ捕捉不全（「証拠がある」→「逃げを検出する仕掛けがある」）。

**寝かせる**
- §G ガバナンス層は (a) が紛争を生み、誰かが「無いと困る」と言い出すまで「審判プロトコルの草案」として寝かせる（OPEN-3 は「今は解かない」に再分類）。
- Lean は logic 象限のみ固める（validator-correctness given exact capture）。capture（§3/OPEN-1）・reference（§G/OPEN-4）・power（§5）は別象限。「Lean やれば全部硬くなる」は錯覚。形式化労力は決定を変える場所（control 精度 / soundness 境界）にのみ。

**信頼の4象限（再掲）**:`logic = Lean` / `capture = §3+OPEN-1` / `reference = §G+OPEN-4` / `power = §5`。