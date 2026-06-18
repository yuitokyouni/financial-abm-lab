# Spec 002 — Minimum Viable Arena (Intervention Atlas を「核候補」から「最小 arena」へ)

- Status: draft v0 (2026-06-18)
- Author: Yuito
- Depends on: `specs/001-monorepo-consolidation.md` (Stage B 正準化), `imported/PROV-ABM-atlas/docs/program_claims_v1.md` (P1), `imported/PROV-ABM-atlas/docs/model_contract_v0.md`
- Decisions: 中心=参照 atlas / 提出審査=CI gate(人依存を外す) / scoring=scalar rank でなく profile / ignition は P1 GO + scalp に gate

---

## 0. 位置づけ (なぜこの spec か)

現状の正確な自己認識:

> **今のプロジェクトは arena ではなく、arena の核候補である。**

握れているのは設計原理だけ ——「validity を騙らない」「claim と evidence level を対応させる」「介入応答で機構分離を見る」「PROV-ABM で監査可能性を担保する」。これらは arena を握るための**思想的・技術的な資格**であって、arena そのものではない。このまま進むと到達点は良くても「よく設計された個別研究 (P1)」か「監査仕様つきのベンチ提案」で止まる。

arena を握るには正しさだけでは足りない。**他人がそこで戦いたくなる構造**が要る。本 spec はその構造の**最小形 (Minimum Viable Arena, MVA)** を、夢としてではなく受け入れ条件付きで定義する。

`prov_abm_design_notes.md §1.4` の警告(rigor trap / framework-first)はここでも効く:**leaderboard インフラを先に作るのは arena 版の rigor trap**。MVA はそれを構造的に禁じる(§6 ignition gate)。

---

## 1. 5つの不足と仕分け (Why)

arena に足りないものは5つ。並列ではなく **launch 前提 / 軌道** と **安い / 偽れない** で仕分ける。

| # | 不足 | launch前提か軌道か | 安い/偽れない | 本 spec での扱い |
|---|---|---|---|---|
| ① | 参加者の得が弱い | **前提** | 設計で安い | §4 payoff stack |
| ② | 初期モデル密度が低い (20-30) | **半分前提・半分軌道** | 偽れない(が転用可) | §3 参照 atlas = Stage B に畳む |
| ③ | scoring が禁欲的すぎる | 前提 | 安い(見せ方) | §5 profile(scalar rank でない) |
| ④ | 運営主体が弱い | 軌道(信頼の前提) | 偽れない | §7 CI 自動審査 + named humans |
| ⑤ | 権威づけが弱い | 前提(ただし最後) | 偽れない | §6 ignition gate (venue×scalp) |

**主張A**: ②④ は `specs/001` Stage B の正準化に畳める。`packages/abm_models` に正準実装が入る = model contract を満たす = 参照 atlas の行になる、を同一視すれば、密度作りと正準化と dogfood が一本になる(§3.2)。

**主張B**: 密度 20-30 は launch 前提ではない。launch 前提は**外部提出ゼロでも独立に有用な参照 atlas**。提出が来る前から引用される参照物(Papers-with-Code / ImageNet 物理)なら cold-start は解けている。20-30 は軌道で accrete する。launch 条件は「N=8-12 でも比較セクションに引ける形」。

---

## 2. 成果 (Outcomes / Desired End State)

- **O1 (参照 atlas)**: `packages/abm_models` の正準機構を機構×介入応答空間に並べた参照地図が、**外部提出ゼロでも** ABM 論文の比較セクションで引用に値する形で存在する。
- **O2 (低摩擦の入口)**: 外部研究者が **contract 準拠1ファイル + CI green** だけで自分のモデルを地図に載せられ、人間審査を要しない。
- **O3 (得の反転)**: 載せると引用可能な model card・自動比較 (自分 vs 既存機構)・失敗の掲載枠が**自動で**生成され、「監査される面倒」が「載せると成果物が増える」に反転している。
- **O4 (validity を騙らない熱量)**: scalar validity rank を出さずに、研究者が改善したくなる GT-free な **scoring profile** を提供する。
- **O5 (運営の人依存排除)**: 提出の適合審査・再現・分散測定が CI gate で自動化され、一学生プロジェクトに見えない最小の運営体制 (named 2-3) が宣言されている。
- **O6 (点火の規律)**: 投稿インフラ・leaderboard は **P1 GO + 最初の scalp が出るまで作らない**ことが spec として固定され、空のベンチの launch を構造的に防ぐ。

---

## 3. 参照 atlas (MVA の中心)

### 3.1 形 (launch artifact)

参照 atlas = **行 × 列の地図**。外部提出ゼロでも有用な「系統樹的参照物」であること。

- **行 (rows)** = `packages/abm_models` の正準機構 (launch 時 N=8-12)。
- **列 (columns)** =
  1. **SF profile** — `packages/stylized_facts` の battery 上の位置 (どの機構が SF 等価類に落ちるか)。
  2. **intervention response signature** — model contract の介入面に対する応答ベクトル φ-response (`atlas/protocols.py` の `Response`)。
  3. **hygiene profile** — §5 の GT-free profile。

地図の読み方が「自分の機構を置くと既存 N 機構のどれと応答が同型/異型か即わかる」になっていること。これが O1 の「引用に値する」の操作的定義。

### 3.2 行の供給 = Stage B 正準化 (②④ の畳み込み)

launch 時の行は新規収集ではなく**手元の正準実装**から供給する。`specs/001` の到達点で `packages/abm_models` に既に 8 モデル (SG/CI/ZI/LM/FW + CB/MG/GCMG) が REGISTRY 揃いで parity GREEN。ここに ALW・Genoa-ZI+(`model_contract_v0.md §4` の参照アダプタ群)・toy T/H を加えれば N=10-12 に届く。

> **密度作り = 正準化 = dogfood。** 別タスクとして 20-30 本を外から集めるのではなく、Stage B の出力をそのまま行にする。13 本目以降が安くなるのは §4 の contract が固まるから(軌道)。

### 3.3 「Yuito の論文付録」に見えないための条件

参照 atlas が「標準」に見えるか「個人の付録」に見えるかは、行が**分野が 30 年読んできた古典**であるかで決まる(`program_claims_v1.md §2.2`)。launch 行は自作機構でなく CB/LM/ALW/ZI/MG/GCMG 等の正準を中心にする。自作 (SG/T/H) は補助列に置く。

---

## 4. model contract と payoff stack (①③ の土台)

arena の重心は leaderboard UI でなく **contract**(Gym が arena を取ったのは `env.step()`、`model_contract_v0.md §0`)。

### 4.1 `model_contract_v1` (v0 から昇格)

`model_contract_v0.md §1` の `Simulator` protocol (reset/step/observe/intervene/emit/provenance、channels 静的宣言、θ=0 恒等) を v1 として確定し、`packages/` に置く。適合レベル C0/C1/C2 (`v0 §3`) を踏襲。

**提出 = contract を満たす1ファイル + CI green**(人間審査ゼロ)。CI gate が機械判定するもの:
- 決定性 (同一 config+seed → bit 同一; C0)
- prov.json 生成 (L2; C2)
- SF battery 通過の有無 (落ちても掲載; §4.3)
- 介入面の有無 (channels 宣言; channels=() は陰性対照として有効な掲載)

### 4.2 payoff stack (得の反転)

contract を満たすと**自動で**生成され、提出者の得になるもの:
- 引用可能な **model card** (prov 付き、再現手順込み、永続 ID)。
- **自動比較** — 自分の機構 vs 既存 N 機構の SF profile / 応答 signature の差分。
- **mechanism placement** — 参照 atlas 上での自分の位置 (どの等価類か)。

### 4.3 失敗の家 (隠れた最大の得)

ABM 研究者は「SF を通らなかった / 効果が出なかった」モデルを死蔵している。**negative でも掲載され引用される枠**(§5 の failure transparency が高いほど良い掲載)を作る。これは他のどの venue も提供していない非対称な得であり、publication bias の逃げ場として働く。

---

## 5. scoring = profile (③: validity を騙らずに熱量)

scalar validity rank は GT を要求し原理的に不可能(`design_notes §2.1`)。代わりに **radar/profile** を出す。scalar 1本は validity gaming を誘発するが、profile は「自分のレーダーを埋めたくなる」誘因になり「誰が一番か」を構造的に回避する。

GT-free な 6 軸 (全て参照不要):
1. **claim admissibility** — validator (`provabm/validator.py`) を通る主張の割合。
2. **audit completeness** — `may\must` gap の裏返し。**単独では地味なので profile の1成分に格下げ**(主役にしない)。
3. **intervention coverage** — 宣言 channels に対し定義できる介入 scheme の網羅率。
4. **mechanism separability profile** — その機構が既存 N 機構から介入応答で分離する/しないの像。
5. **replication stability** — seed 横断の分散 (再現の固さ; `program_claims §3` の分散報告様式)。
6. **failure transparency** — 落ちた SF / flat な応答を隠さず開示しているか。

> validity を採点しないが、研究者が改善したくなる軸を出す。`may\must` gap だけだと地味すぎる、を §5 の格下げで解消。

---

## 6. ignition = venue × scalp (⑤: 最後、偽れない、前倒し不可)

arena は自然発生しない。点火には**権威ある場への接続 (venue)** と**既存の強いモデルを同じ盤面に引きずり出した実績 (scalp)** が要る。

- **venue 候補**: NeurIPS D&B / ACM FAccT / AAMAS / EC / 金融マイクロストラクチャ系 / ABM workshop に dataset・benchmark・challenge として出す。JEDC / Computational Economics の論文単独では弱い。
- **scalp**: 有名モデルを「落とす」か「意外な形で整理する」結果。`design_notes §2.5` の make-or-break (介入応答が SF の分けられない機構を分けるか) を P1 が GO で決着させ、かつ既存正準機構に対して非自明な分離/等価を示すこと。

### ignition gate (本 spec の最重要規律)

> **投稿インフラ (外部投稿フロー / leaderboard UI / challenge ページ) は、P1 が GO を出し最初の scalp が出るまで作らない。**

理由: scalp 前にインフラを作り込むと「よく設計された個別研究」より悪い「**誰も載らない空のベンチ**」で止まる。MVA の launch 前にやるのは §3 参照 atlas と §4 contract と §5 profile **だけ**。これらは P1 の走らせ方を規定する dogfood なので前倒しが正当化される。scalp が出た瞬間に投稿フローを足すだけで点火する。

P1 の critical path は `toy/intervention.py` の介入4 scheme 実装 + 板上の識別障害解消 (Finding 0002 の次の作業) を通る。scalp はこの完了に gate される(前倒し不可)。

---

## 7. 運営 (④: 人依存を外す)

- **自動化が一次防衛**: 提出審査は §4.1 の CI gate。人間レビューは契約逸脱の例外処理のみ。監査が機構の数にスケールする条件 (`model_contract_v0 §2`)。
- **named humans (最小)**: 一学生プロジェクトに見えないための最小体制 = 研究室 / 共同著者 / 外部 advisor / 小 steering group のうち最低2-3名を spec に明記。MVA launch の前提ではないが ignition (§6) の前提。
- **バージョン規律**: spec・contract・scoring profile の変更は versioned に切り直す (`program_claims §5`、サイレント編集禁止)。古い結果は prov で保存。

---

## 8. スコープ

### 8.1 MVA に含む (launch 前にやる)

- `model_contract_v1` の確定と CI gate (§4.1)
- 参照 atlas (N=8-12 行、3 列; §3)
- scoring profile 6 軸の定義と GT-free 計算 (§5)
- payoff stack の自動生成 (model card / 自動比較 / placement; §4.2-4.3)

### 8.2 ignition まで作らない (§6 gate)

- 外部投稿フロー / leaderboard UI / challenge ページ
- Type2 survival test (`design_notes §2.2`、恒久的にスコープ外)
- scalar validity rank (原理的に不可能、恒久的にスコープ外)

### 8.3 明示的に scope 外

- PROV-ABM L3+ (AST/taint/strict validator; `specs/001 §3.3` 踏襲、L2 のまま)
- agent 側契約 (Shachi 互換層; `model_contract_v0 §5`、P3 対象選定後)
- マルチ資産 / 連続時間 (LM が要求した時点で contract v2)

---

## 9. 受け入れ条件 (EARS 風・検証可能)

### 参照 atlas (中心)

- **AC1**. WHEN 参照 atlas を生成したとき、THE SYSTEM SHALL `packages/abm_models` の正準機構 **N≥8 行**を、SF profile・介入応答 signature・hygiene profile の3列で並べた地図として出力する。
- **AC2**. WHEN 外部提出が**ゼロ**の状態で参照 atlas を見たとき、THE SYSTEM SHALL「任意の新機構が既存 N 機構のどの等価類に入るか」を判定できる比較物 (距離 or 分類器) を提供する (= 引用に値するの操作的定義)。
- **AC3**. WHEN launch 行を選ぶとき、THE SYSTEM SHALL 自作機構 (SG/T/H) でなく古典正準 (CB/LM/ALW/ZI/MG/GCMG 等) を行の中心に置く。

### contract と提出 (低摩擦)

- **AC4**. WHEN 研究者が `model_contract_v1` 準拠の1ファイルを提出したとき、THE SYSTEM SHALL 決定性・prov.json・SF 通過有無・介入面有無を **CI gate で人間審査なしに**判定する。
- **AC5**. WHEN 提出が contract を満たしたとき、THE SYSTEM SHALL model card・自動比較・atlas placement を**自動生成**する。
- **AC6**. WHEN 提出が SF を通らない / 応答が flat なとき、THE SYSTEM SHALL それを失敗としてでなく failure-transparent な掲載として記録する (channels=() の陰性対照を含む)。

### scoring (熱量・validity を騙らない)

- **AC7**. THE SYSTEM SHALL scalar validity rank を出さず、§5 の 6 軸 profile を出力する。各軸は GT 参照ゼロで計算可能であること。
- **AC8**. THE SYSTEM SHALL `may\must` gap を profile の1成分に留め、leaderboard の主役にしない。

### ignition gate (規律)

- **AC9**. WHILE P1 が GO を出していない、THE SYSTEM SHALL 外部投稿フロー / leaderboard UI / challenge ページを実装しない。
- **AC10**. WHEN P1 GO + 最初の scalp が出たとき、THE SYSTEM SHALL §6 の venue 1 つへ dataset/benchmark として接続する準備に入る。

### 運営

- **AC11**. WHEN MVA を公開するとき、THE SYSTEM SHALL named 2-3 名の運営体制を spec に明記する (ignition の前提)。
- **AC12**. WHEN contract / scoring profile を変更するとき、THE SYSTEM SHALL versioned に切り直し、古い結果を prov で保存する。

---

## 10. タスク分解 (依存順)

> ignition gate (§6) により、T4 (投稿インフラ) は P1 GO + scalp まで着手しない。

- **T0. 棚卸し** — `imported/` 配下と `packages/abm_models` の実在モデルを全て洗い、何本が contract 化の素材になるか (参照 atlas の launch 行候補) を表にする。
- **T1. `model_contract_v1` 確定** — `model_contract_v0.md` を v1 化、`packages/` に protocol を置き、C0/C1/C2 適合検査を property test 化 (θ=0 恒等・決定性)。
- **T2. 参照 atlas 生成** — launch 行 (N=8-12) を contract に通し、SF profile + 応答 signature + hygiene profile の3列を生成。AC2 の比較物 (距離/分類器) を実装。
- **T3. scoring profile** — §5 の 6 軸を GT-free で計算、radar 出力。`may\must` gap は1成分。
- **T4. payoff 自動生成** — model card / 自動比較 / placement を提出時に自動生成 (CI 連携)。
- **【ignition gate】** ← P1 GO + scalp までここで停止
- **T5. 点火** — venue 1 接続 + 投稿フロー + named 運営体制宣言。

---

## 11. リスクと留意

- **R1 (空のベンチ)**: scalp 前にインフラを作り込み誰も載らない → §6 ignition gate と T4 停止で構造的に防ぐ。
- **R2 (個人付録に見える)**: 行が自作機構中心だと標準に見えない → AC3 で古典正準を行の中心に強制。
- **R3 (validity gaming)**: scalar rank を出すと validity を騙る誘因 → AC7/AC8 で profile に限定。
- **R4 (運営力で先を越される)**: より運営力のあるグループに「妥当性を騙らない ABM 監査」ポジションを取られる → T5 の named 運営体制と venue 接続を ignition の必須前提にする。
- **R5 (critical path 依存)**: scalp が `toy/intervention.py` 実装 + 板の識別障害解消に gate される → P1 の完遂が MVA 点火の律速。前倒し不可を受け入れる。

---

## 12. Checklist (要件の "unit test" — レビュー用)

完全性:
- [ ] 5つの不足 (§1) が全て Outcomes (§2) と AC (§9) に対応しているか
- [ ] 参照 atlas の launch 行 N と供給元 (§3.2) が一意に決まっているか
- [ ] ignition gate の発火条件 (P1 GO + scalp) が数値/判定で書かれているか

明確性:
- [ ] 「引用に値する参照 atlas」が操作的定義 (AC2) に落ちているか
- [ ] 「validity を騙らない」が scoring profile の GT-free 6 軸 (§5) で具体化されているか
- [ ] 「人依存を外す」が CI gate (AC4) に落ちているか

一貫性:
- [ ] §2 Outcomes と §9 AC が対応 (O1↔AC1-3, O2↔AC4, O3↔AC5-6, O4↔AC7-8, O5↔AC11, O6↔AC9-10)
- [ ] scope 外 (§8.2/8.3) とタスク (§10) に矛盾がないか (gate 後タスクを前倒ししていないか)
- [ ] `specs/001` Stage B との接続 (参照 atlas 行 = 正準化出力) が矛盾なく書かれているか

実行可能性:
- [ ] T0-T4 が ignition なしで完結し、scalp 前に MVA の核が立つ設計か
- [ ] 各タスクが依存順 (contract → atlas → scoring → payoff) に並んでいるか
