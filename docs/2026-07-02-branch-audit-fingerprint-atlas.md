# fingerprint_atlas ブランチ監査レポート

- 実施日: 2026-07-02
- 対象: ブランチ `claude/vibrant-ptolemy-fapuxw` @ `11e9d59` (PR #7、main より 89 commits 先行)。**fingerprint_atlas パッケージ (~15.9k 行) + 30 テストファイル + 5 CI ワークフロー**。`origin/main` の正準コア (packages/abm_models の SG/古典4モデル、stylized_facts、imported の YH 実験線) は別途監査済みのため対象外。
- 方法: 27 並列監査 (エリア別 14 + 横断 7 + 実測 4 + 戦略 2) → 意味的重複排除 (321→227) → **敵対的検証** (finding ごとに反証専任エージェント 1 体、可能なら offline 再現)。総計 112 エージェント、560 万トークン。
- 結果: **確定 179 件** (critical 1 / major 65 / minor 89 / info 24)、うち **143 件は実測で再現済み**。研究ツーリングの不足アイデア 145 件。
- 検証フェーズは途中で Fable 5 のクレジット上限に当たり、48 件の finding が「検証できなかった」ため confirmed から除外された。**したがって本レポートに載る 179 件は全て「実測再現済み or 敵対的検証通過」の高確度のみ**で、これは floor (下限) — 実際の欠陥数はこれより多い。
- 全 finding の生データ (evidence / failure_scenario / suggestion / 検証ノート付き): [`2026-07-02-branch-findings-full.json`](./2026-07-02-branch-findings-full.json)

---

## 0. 総合評価 (TL;DR)

**fingerprint_atlas のコアは「モジュール単位では丁寧、しかし境界とパイプラインで壊れる」。** taxonomy 統合・coverage 浄化・multi-label 抽出という直近の一連の作業自体は健全で、テスト 245 件は完全オフラインで決定論的にパスする。幾何スタック (fingerprint→standardize→distance→atlas) も e2e 数値検証で 1e-9 まで手計算と一致した。

一方で、**この 89 commits が実際に作ってきた「研究成果物」を再現・検証・拡張できない構造的問題が最重要**:

1. **コーパスが git のどこにもコミットされていない** — 176 本の retag 済みコーパスは Yo の Mac 上にしか存在せず、この監査環境の DB は 0 行。coverage matrix / canon atlas / gap-mine / dashboard の全図が、バージョン管理外・単一障害点 (Yo のラップトップ) に依存している。CI ワークフロー 4 本も空 DB 上で走り、何も蓄積していない。
2. **破壊的操作に安全網がない** — `stylized-fact-other --retag` は LLM の空応答で既存 tag を恒久破壊し「成功」と報告する。`--summary` が印字する削除コマンドは id を 80 文字で切って `--yes` 付きなので、貼ると全件のつもりで一部だけ黙って消す。これらは Yo が実際に 85 行を一括削除した経路そのもの。
3. **LLM 出力の write-time 検証がほぼ無い** — 抽出結果は enum 外の fact ('liquidity' 等) を素通しし、提案は範囲外パラメータを素通しして execute 時に爆発、idea scaffold は LLM が選んだクラス名でパスを組んで既存モジュールを上書きする。

さらに、gap-mine の統計エンジンには**構造的に到達不能な領域**がある: 25 subfield 中 5 個はハイフン正規化のせいで永久にマッチせず、view C は 30 technique 中 7 個しか surface できず (DOI ref に join key が無い)、view B は重み最大の設計なのに salience スケールの非整合で view A/C に永久に負ける。有識者レビューが指摘した「salience が gap の surprise 順序を正しく表さない」も独立に確認された。

**結論の方向性: 提案・gap の「順位」を根拠に使うのはまだ危険。しかし土台のデータ層とテスト規律は健全なので、修復は現実的。** そして Yo が気にしていた「ブランチ統合」には明確な答えが出た (§6)。

---

## 1. Critical — 1 件

### C-1: 研究コーパスがバージョン管理外・単一障害点に依存 (再現不能リスク)

`.github/workflows/ingest_arxiv.yml:158` ほか (findings #47/#55/#56/#61 が同根)

監査環境の本番 DB `/home/user/test/knowhow/abm_knowhow.db` を read-only で開くと **`literature_methods` は 0 行**、`proposals` / `ideas` / `literature_code_snapshots` / `techniques` テーブルは存在しない。存在するのは `runs` (126 行、2026-06-27 の fingerprint 実行) と `methods` (11 seed) のみ。`freelist_count=0` かつ raw scan でも削除痕跡なし — このファイルにコーパスは一度も入っていない。

一方、直近コミット `11e9d59` は「minority-game (9) と Minority-Game (10) が別行になった」等、**ライブの ~176 本コーパスの実数を引用**している。つまり retag 済みコーパスは **Yo の Mac のローカル作業ツリーにしか存在せず、リポジトリのどこにもコミットされていない**。

これが意味すること:
- **coverage matrix / canon atlas / gap-mine / dashboard の全図が再現不能**。Mac が飛べば消える。
- **CI ワークフロー 4 本 (ingest / atlas_refresh / propose / methods_annotate) は全て空の `data/abm_knowhow.db` を snapshot から再構築するが、その snapshot ファイル自体が一度もコミットされていない** — 毎週空コーパスで走り、何も蓄積しない (#55)。`atlas_refresh.yml` の step B/C は空 DB で `exit 1` するので、そもそも成功できない (#47)。
- コミット済みの dashboard 図 `novelty_calibration.png` 等は、存在しない `proposals` テーブルの executed 行を必要とする (#56)。

**重要な但し書き**: これは「データが失われた」わけではない (Yo の Mac にはある)。だが **git 管理外・単一障害点・CI から再現不能**という状態は、修士論文の defense で「その図はどう再現するのか」と問われたときに答えられない致命的な弱点。severity critical は監査環境要因で幾分誇張されているが、**根の再現性リスクは本物**。

**対処 (最優先)**: いま Mac にあるうちに `load_literature()` で `data/literature_methods.json` にエクスポートして**コミット**する。CI に「復元後の行数 ≥ 前回コミット時の行数」アサーションを入れ、無言のコーパス喪失をビルド失敗にする。これで再現性・CI・defense の 3 つが同時に解決する。

---

## 2. Major 65 件 (テーマ別)

### 2a. 破壊的操作の安全性 (Yo が実際に事故った経路)

| # | 場所 | 内容 |
|---|---|---|
| 1 | `arxiv_cli.py:772` | **`stylized-fact-other --retag` が LLM 空応答で既存抽出を恒久破壊**。`extract-untagged` は空応答ガードを持つのに retag 経路には無く、空 payload を書き込んで「reclassified」とカウント。`extracted_by_model` は残るので、以後 `extract-untagged` は「対象なし」と言い、破壊が不可視。実測再現。 |
| 2 | `arxiv_cli.py:745` | **`--summary` の削除コマンドが id を 80 文字で切り `...` を足し `--yes` 付きで印字** → 貼ると 10 件中 7 件だけ黙って削除、`...` はゴミ token。Yo が 85 行削除した経路。実測再現。 |
| 5 | `arxiv_cli.py:294` | `scan-pdfs-for-code --rescan` が `source='manual'` 行まで選び、**手動 pin した code_url を PDF 正規表現ヒットで上書き** — `set-code-url` の保証を破る。 |
| 24 | `idea_plan.py:309` | scaffold が **クラス名の snake 変換だけをキーにモジュールを無条件上書き** — 再 scaffold や名前衝突で人間が仕上げたモデルコードを消す。 |
| 54 | `arxiv_cli.py:961` | `strip-arxiv-versions` が `literature_code_snapshots` を放置 → vN id のスナップショット孤児化。衝突分岐は vN 行を丸ごと DELETE し extraction/notes/tags を base 行にマージせず喪失。 |
| 35 | `methods_cli.py:365` | `import-md` が `## section` ヘッダの無いファイルを渡されると**5 コメント列を全消去**して rc 0 で「imported」。 |

### 2b. LLM 出力の write-time 検証欠如

| # | 場所 | 内容 |
|---|---|---|
| 11 | `arxiv_ingest.py:441` | `extract_paper_structured` が `stylized_facts_targeted` を **CANONICAL_FACTS に照合しない** — 'liquidity' 'volatility smile' 等が verbatim 保存され、coverage/gap で黙って捨てられる。 |
| 25/26/30/52 | `idea_plan.py:215`, `propose.py:387/404` | scaffold/proposal validator が **キー存在しか見ない** — 範囲外パラメータ・非数値値・ハルシネーション key が素通しし execute 時に爆発、または非識別子クラス名が非コンパイルモジュールを生む (なのに「scaffolded」と報告)。 |
| 23 | `idea_cli.py:280` | `cmd_promote_proposal` が status='judged' + judgment NULL の**行き止まり idea 行**を作る → 広告された `plan --id N` が常に拒否。 |

### 2c. gap-mine 統計エンジンの構造的欠陥 (研究の中核出力が静かに誤り)

| # | 場所 | 内容 |
|---|---|---|
| 17 | `gap_finder.py:84` | `_matches_subfield` が空白入り needle をハイフン正規化 tag に照合 → **25 subfield 中 5 個 (limit_order_book, market_impact, systemic_risk, el_farol, santa_fe_market) が view A/C で永久に 0 マッチ**。実測。 |
| 18 | `gap_finder.py:189` | **salience がビュー間で非可換**: view B は ≤1.3 に正規化されるが view A/C は ≥log(5)≈1.61 なので、**重み最大の view B gap は永久に A/C に負ける**。 |
| 19/41 | `gap_finder.py:254`, `techniques.py:54` | view C は **30 technique 中 7 個しか surface 不能** — 23 個が DOI-only/空 ref_papers で、join key (arxiv id / OA W-id) と噛み合わず構造的にゼロ行。 |
| 20 | `gap_finder.py:117` | view A が `other` catch-all を行列・行合計に算入 (coverage は除外) → **'other' のみ tag の subfield が最大 salience の偽 gap を生む**。 |
| 51 | `gap_finder.py:291` | salience `log(row+col+1)-log(cell+1)` が周辺分布に加法的 → **弱証拠 gap (小行×巨大列) を強証拠 gap (密行×中列) より上位に**。独立性期待からの surprise 順序が反転 (有識者レビュー指摘と一致)。 |
| 50 | `gap_finder.py:163` | view B の実市場 baseline が有限値 2 未満で std=1.0 に fallback → **「z-distance」が生の特徴量単位になるのに σ として報告・閾値判定**。 |
| 59 | `subfields.py:114` | `title_any` の汎用単語 ('market' 'learning' 'trading' 'return' 'volatility') が部分文字列マッチ → **subfield 帰属がほぼ false-positive で決まる**。 |

### 2d. OpenAlex / LLM クライアントの API 破損 (ライブで動かない)

| # | 場所 | 内容 |
|---|---|---|
| 6 | `openalex.py:336` | OpenAlex は `publication_year:<=YYYY` を **HTTP 400 で拒否** (`<` `>` のみ) → `--year-max` 付き canon クエリが全滅。実測。 |
| 7 | `openalex.py:655` | `find_citing_papers` の `cited_by_count:>=` も 400 拒否 + エラーが空リストに握り潰され、**`--min-cited-by` genealogy が root だけの木を無言生成**。 |
| 8 | `openalex.py:107` | `fetch_paper` が「OA に無い」と「429/5xx/ネットワーク障害」(90 秒 rate-lock 含む) を混同 → `enrich-via-oa` が健全な行に `oa_fetched_at` を stamp して**恒久スキップ**。S2 側で直したはずの silent-429 バグの再発。 |
| 9 | `openalex.py:549` | `_arxiv_id_from_work` の `ids.arxiv` 分岐はデッドコード (実 API は返さない) → **old-style preprint の arxiv id 抽出が None** (id は `work.doi` に明白にあり、docstring も読むと書いてあるのにコードは読まない)。 |
| 10 | `llm_client.py:92` | `_UNRECOVERABLE_MARKERS` の 'billing' が **Groq の 429 (本文にアップセル URL `.../settings/billing` を含む) を回復不能と誤分類** → 全 caller で Groq rate-limit の再試行が発火しない。Yo が extract で見た挙動の共有層版。 |

### 2e. データライフサイクル / DB 整合性

| # | 場所 | 内容 |
|---|---|---|
| 12/29 | `propose_cli.py:307/286` | `execute_proposal` が非アトミック + 重複実行ガード無し → 例外で**孤児 run 行**が残り、再実行/重複提案が atlas に同一点を反復投入、novelty distance を 0 に引っ張る。実測。 |
| 13 | `db.py:358` | comma-join 列 (mechanism_tags 等) に**エスケープ無し** → カンマを含む要素が phantom entry に分裂。 |
| 14 | `ingest_arxiv.yml:84` | 週次 snapshot 復元が **enrichment 列 (code_url, s2_*, oa_*, user_notes 等) を 1 サイクルで無言消去** — 全行復元 API が無い。 |
| 53 | `propose_cli.py:200` | proposal status 状態機械に遷移ガード無し → `approve`/`reject` が 'executed' を上書きし再 execute で**重複 run**。 |
| 28 | `preference.py:181` | `argsort(score)[::-1]` で **NaN スコア (壊れた fingerprint) が top-k ラベリング枠を占拠**。 |
| 57 | `db.py:88` | 本番 runs の 25 preference ラベルが **0.12 秒窓で一括書込** = task-#14 の自己ラベル疑似シミュレーション。人間の taste と区別不能で、ridge preference モデルがこれを既定で学習。 |

### 2f. 数値・fingerprint

| # | 場所 | 内容 |
|---|---|---|
| 31 | `adapters.py:194` | **GCMG fingerprint が誤系列で計算** — vectorized GCMG の `simulate()` が 'actions' key を返さず fallback が数学的に誤った n_players 式で abstention 無視。本番 12 行の GCMG 全て歪み。 |
| 32 | `fingerprint.py:138` | `_aggregational_kurt_decay` が生の excess kurtosis で除算 → 準ガウス系列で発散、単一 run が偽の幾何外れ値に。 |
| 33 | `fingerprint.py:157` | `compute_hill=False` が sentinel でなく `HILL_ALPHA_CAP=20.0` を捏造 → MG/GCMG 全行に偽の「最薄尾」測定が入り距離を系統バイアス (main 監査と一致)。 |

### 2g. curated data の事実誤り (seed_arxiv 誤り前科の残党)

| # | 場所 | 内容 |
|---|---|---|
| 37 | `abm_families.py:138` | lux_marchesi の family card が `cond-mat/9810262` = **シリコン破壊の材料科学論文** (subfields.py では修正済みだがここは未修正)。 |
| 38 | `techniques.py:159` | chartist_fundamentalist_mix も同じ誤 id を Lux-Marchesi 参照として引用。 |
| 39 | `techniques.py:137` | order_arrival_poisson の唯一の ref `1502.03003` = **共形重力の論文**。 |
| 40 | `techniques.py:340` | abc_rejection の唯一の ref `1903.04279` = **三元ボルツマン方程式の数理物理論文**。 |
| 22 | `subfields.py:173` | `validate_subfields()` は「canon_atlas から呼ばれる」と docstring が言うが**どこからも呼ばれないデッドコード** — bad seed を捕まえる設計のガードが不作動。 |

### 2h. テスト / CI / 描画

| # | 場所 | 内容 |
|---|---|---|
| 42 | `ci.yml:22` | **lint が `\|\| true` で無力化** — 76 個の ruff エラー (F821 undefined-name の実クラッシュ含む) を隠蔽。 |
| 43/44/58 | `test_propose.py:303` ほか | **executor (prediction_error/novelty の中核計算) はテストが実物を呼ばず簡易版をコピペ**。9 モジュールがカバレッジ 0%、arxiv_cli.py は 14% (1171/1364 文が未実行)、全体 47%。 |
| 15 | `coverage.py:291` | `render_markdown` の列合計行がヘッダより 1 セル少なく、**全列合計が 1 つ左の fact 列にずれて表示**。 |
| 16 | `literature_map.py:116` | `literature_map.primary_tag` が正規化/alias/deny-list の修正を受けておらず、**2D map の色・凡例・CSV が coverage が直した通りに mechanism を断片化**。 |
| 21 | `canon_atlas.py:320` | HTML の見出し「overall coverage」を `total_in_db/total_on_arxiv` で計算するが n_in_db は OA journal-only も数えるので **300% 表示** (per-cell 定義と矛盾)。 |
| 34 | `methods_annotate.yml:53` | daily 注釈ワークフローが毎回 seed から DB 再構築 → **queue-next が永久に同じ chiarella_iori を返す**。 |

### 2i. パッケージング / ワークフロー

| # | 場所 | 内容 |
|---|---|---|
| 60 | `pyproject.toml:6` | **matplotlib が 6 モジュールで import されるが依存宣言に無い** (逆に stylized-facts は宣言されるが未 import) → wheel 単独インストールで全描画機能が壊れる。 |
| 46/47 | `propose.yml:59`, `atlas_refresh.yml:91` | 週次 workflow が **CI ランナーからライブ Yahoo Finance fetch に依存** (キャッシュは gitignore で常に空) し、fetch エラーで `exit 1` → 全週次 run が LLM/PR ステップ前に死亡。 |
| 45/49 | `.gitignore:3/15` | `canon_atlas.html` パターンが生成物を無言除外 + commit `14e24c3` が改行無しで `*.csvdashboard/*.html` という**死んだパターン**を生成 (両方無効化、main の `*.csv` 無視も破壊)。 |
| 61 | `propose.yml:98` | **default ブランチ (main) から走る cron が今も `base: claude/vibrant-ptolemy-fapuxw` に PR を積む** — 修正はこのブランチにしか無い。 |

---

## 3. Minor 89 件 (要約)

カテゴリ内訳: robustness 30 / data-quality 16 / bug 14 / design 12 / docs-drift 9 / testing 3 / security 2 / その他 3。特に効く 12 件:

1. `arxiv_cli.py:729` — `--summary` の削除候補フィルタが `relevance_score == 0.0` を falsy `or` で 1.0 扱い → **最も無関係な論文が eyeball リストから漏れる**のに companion の delete-low-relevance は消す (リスト不一致)。
2. `arxiv_cli.py:105` — `--db` 省略で**全 DB コマンドが生の TypeError traceback でクラッシュ** (親しみやすいエラーにすべき)。
3. `arxiv_ingest.py:456` — `_coerce_relevance` が min/max 引数順で **NaN を 1.0 (最大関連度) にクランプ**。
4. `db.py:392` — `load_literature` の tag フィルタが LIKE パターンに `%`/`_` を非エスケープ interpolate → ワイルドカード文字を含む tag が誤マッチ。
5. `db.py:472` — `load_code_snapshots` が空 arxiv_ids リストを「フィルタ無し」扱いして**全テーブル返却** (意図と逆)。
6. `db.py:300` — `upsert_literature_metadata` が SELECT-then-INSERT を非トランザクションで実行 → 2 cron 同時実行で競合。
7. `coverage.py:69` — `_primary_tag` の OA-concept fall-through が deny-list を**バイパス** (fact 名/汎用概念が row になれる)。
8. `taxonomy.py:173` — `method_family` の ML substring パスが ABM パスより先 → '-learning' を含む古典 agent タグを ml に誤分類。
9. `gap_finder.py:337` — 1 行の scalar/'null' fingerprint_json が **find_gaps 全体をクラッシュ**。
10. `genealogy.py:244` — `render_html` が `json.dumps(tree)` を `</` 非エスケープで `<script>` に注入 → 論文タイトルに `</script>` があれば **stored XSS** (ローカル HTML だが)。
11. `openalex.py:167` — old-style メタデータ scrape が rate-lock 中も arxiv.org HTML を pacing 無しで叩き続ける。
12. `llm_client.py:37` — 広告された o1/o3/o4 ルーティングが動かない (`temperature` を常に送るが OpenAI reasoning models は拒否)。

---

## 4. 検証で確認できた健全性 (反証を試みて生き残ったポジティブ)

- **テスト 245 件が完全オフラインで決定論的にパス** (`unshare -n` でネットワーク遮断・逆順・反復で 5 回同結果)。全 arxiv/OpenAlex/S2/LLM 呼び出しが monkeypatch 済み。回帰ヒギエネ (version-suffix strip, LLM 出力 coercion, hallucination フィルタ, canon fallback) は良質。
- **幾何スタックが数値健全**: 12 論文の手計算コーパスで build_coverage を cell 単位検証、view B z-distance を 1e-9 まで手計算と一致。MODEL_BOUNDS は REGISTRY と完全一致 (テストで強制)、LHS sampler の層化・nested params split も正しい。
- **taxonomy コアは同期**: 両 LLM プロンプト (arxiv_ingest, idea_judge) が herding 降格込みの 10 CANONICAL_FACTS を正確に列挙、coverage/gap_finder の re-export shim は identity-true でテスト固定、全 fact が日本語ラベルに解決。
- **db.py は SQL injection 皆無** (全ユーザ/LLM 値が parameter bind、f-string SQL は内部定数のみ)。
- **静的健全性良好**: 43 モジュール全て py_compile 通過、fresh subprocess で <0.5s import・import cycle 無し、5 workflow YAML と 4 inline heredoc 全て parse、33 subparser = 33 handler が 1:1。
- **subfields の 2 seed は正しい** (`adap-org/9708006` = Challet-Zhang、`W1537415400` = Lux-Marchesi Nature 1999) — 誤 id は abm_families/techniques 側にのみ残存。
- **dashboard の HTML エスケープは一貫** (curated catalog / gap label / error / href が全て html.escape) — genealogy の 1 箇所を除き stored-XSS の lead は不発。

---

## 5. 足りていないアイデア — 145 件から統合した最重要 8 テーマ

### 5a. 論文 defense の証拠鎖 (有識者レビュー 5 要求の未達分)

- **行正規化 coverage heatmap** (要求#1) — 依然未実装。絶対数だけでは「どこに論文が多いか」しか答えていない。
- **抽出 instrument の信頼性監査** (要求#3) — 完全に欠如。LLM 抽出 vs 人間 gold ラベルの inter-rater κ を、~30 論文の spot-check で測る protocol。「あなたの gap は coding artifact では」への唯一の防御。
- **extraction-era A/B** (要求#2 follow-through) — single-label 時代と multi-label 時代の行が 1 図に era マーカー無しで混在。`mean_facts_per_paper` を era 別に出せば multi-label が効いた証拠になる。
- **'other' bucket 分解** (要求#4、半分) — minority-game の 7 本が何を targeting してるか割れば新 fact 列 (price impact, spread dynamics, bubbles) が立つ。
- **missing-not-at-random 注記** (要求#5、半分) — 未分類 209 本が MAR でない可能性を図の下に一言。

### 5b. gap ランキングの統計的正当化

- **bootstrap-over-papers 安定性**: top-15 gap を論文リサンプルで bootstrap し、順位の安定度を出す (安価)。
- **セルごとの統計的 null** (Fisher/permutation): 「密行の空セル」が独立性からどれだけ乖離してるかの p 値。有識者が最初に突く「誰もやってない vs 難しいだけ」に定量で答える。
- **salience を期待カウント baseline に**: `log(row+col+1)` でなく独立性期待 `row*col/total` からの残差にすれば surprise 順序が正しくなる (#51 の恒久修正)。

### 5c. データ耐久性・provenance (C-1 の恒久対策)

- **コーパス緊急救出 + row-count ratchet**: `data/literature_methods.json` をコミット、CI で行数の後退を失敗にする。
- **provenance stamp**: 全図・全ページに `DB content hash + git SHA + timestamp + row counts`。defense で「この図の再現手順は」に即答できる。
- **preprint/journal twin dedup**: arxiv 行と oa:W 行が同一論文で二重計上 → coverage 分母が膨らむ。DOI + 正規化タイトルで collapse。

### 5d. LLM 契約の一元強制

- **全 LLM 応答を Pydantic/jsonschema で write-time 検証** — enum 外 fact / 範囲外 param / 非数値値を DB 到達前に reject + reject ログ。#11/#25/#30/#52 を一箇所で潰す。
- **prompt↔taxonomy 同期テスト**: 抽出プロンプトの fact 列挙を taxonomy から生成 (single-source) し、ドリフトをテストで捕まえる。

### 5e. `db doctor` 整合性コマンド

この監査が手で走らせた全チェック (case-variant tag, enum 違反, vN 残党, oa:W 重複, 孤児 reference, parked 行) を 1 コマンドに。CI ゲートにもできる。

### 5f. 破壊的操作の undo 層

全 delete/overwrite 系に `--backup` (削除行を JSON に退避) と scaled confirmation (N 件超は件数タイプ要求)。#1/#2/#5/#24/#35 を横断で守る。

### 5g. scaffold の実行前ゲート

生成 .py を compile + import + protocol 準拠チェックしてから「scaffolded」と報告。base_method を REGISTRY 照合。#25/#26 を潰す。

### 5h. prior-art defense dossier

`arxiv_ingest` は param-sweep proposer にしか繋がっていない。**Yo 自身の新規性主張の先行研究防衛**にこそ使うべき — idea_judge に「この主張の prior art を OpenAlex で 1-hop 探索」を追加。

---

## 6. ブランチ統合プラン (Yo の「どっかで統合したい」への回答)

PR #7 (`claude/vibrant-ptolemy-fapuxw`, 89 commits, +15.6k/-193, **CI green, mergeable clean**) は main より trivial な README 修正 1 commit だけ後方で、**コンフリクト無しでマージ可能**。commit クラスタは (1) LLM-client 統一, (2) ideas pipeline, (3) code-link 抽出, (4) S2/OA enrichment, (5) canon atlas/genealogy/dashboard, (6) gap mining/i18n, (7) taxonomy/coverage 浄化 + junk commit 1 個 (`c0a648c` 'a' — 生成 dashboard と _idea_* stub を abm_models に漏らした)。

**リスクはコードコンフリクトでなく cron エコシステム**。手順:

**(0) マージ前にこのブランチで直す**:
- `.gitignore` の壊れた行 `*.csvdashboard/*.html` を修正 (#49) — さもないと main の `*.csv` 無視を破壊。
- 任意: `_idea_*` stub と root HTML 生成物を削除。
- **C-1 対応**: `data/literature_methods.json` をコミット (これが全ての基礎)。

**(1) PR #7 を「マージコミット」でマージ (squash 厳禁)**:
- 検証済み: **squash は PR #3 を 6 コンフリクト、PR #4 を 20 コンフリクトに変える**が、真のマージコミットなら両方クリーンにマージできる (head ブランチに埋まった feature 系譜が main の祖先に必要)。
- **Sunday 2026-07-05 21:00 UTC より前に**マージ — 次の ingest/propose cron が `base:main` を拾えるように。

**(2) head ブランチを GitHub UI から削除** → PR #3/#4 が自動 retarget → PR #3 をマージ (`data/literature_methods.json` を seed して蓄積を開始)、PR #4 をマージ or 再生成。

**(3) 迷子の `ingest-arxiv/28287737193` を削除** (#3 と 100% 冗長・add/add コンフリクト)。

**(4) `speculation-game-cleanup-4inq82`** (main 監査ドキュメント、add-only) はいつでもマージ可。

**(5) PR #6 (yh007)** は #7 と順不同でクリーン (.gitignore だけ重なり自動マージ)。

**(6) PR #5** は自 base とコンフリクト (specs/002)、内容は多分 superseded → close か rebase。

**(7) その他** trusting-clarke の MVA (spec 002→004 renumber + pyproject/uv.lock 解決 か close)、gallant-turing (off-topic 個人メモ) は close。

**(8) 新規稼働する daily/weekly cron を放置する前に** annotate-queue (#34) と snapshot-restore (#14/#55) の state loop を直す。

**post-merge の NaN バグ状況**: `preference.py` は main とバイト同一、`propose.py` の変更は NaN 経路を回避しているので、**マージで壊れたコードは復活しない**。ただし **main 監査が見つけた propose/preference の NaN バグは未修正のまま** — post-merge tree に対してパッチすべき (注意: `propose._call_groq` は今や llm_client の薄い shim なので pre-merge パッチは当たらない)。

---

## 7. 優先アクションプラン

### P0 — 再現性・データ喪失防止 (即時)
1. **C-1**: 今 Mac にあるコーパスを `data/literature_methods.json` にエクスポート → コミット。CI に row-count ratchet。
2. **#1**: `stylized-fact-other --retag` に空応答ガード (extract-untagged と同じ)。既に破壊された行があれば `--retry-empty-past` で復旧。
3. **#2/#5**: `--summary` の削除コマンド印字を全 id + `--yes` 無しに。`scan-pdfs-for-code` の manual-source ガード。
4. **#49**: `.gitignore` の壊れた行を修正 (マージ前必須)。

### P1 — 研究出力の信頼性 (今週)
5. **#11**: 抽出結果を CANONICAL_FACTS に write-time 照合 + reject ログ (enum 外 fact を DB に入れない)。
6. **gap-mine の構造欠陥**: #17 (subfield マッチのハイフン/空白)、#20 ('other' を view A から除外)、#59 (汎用 title_any token) を修正 → gap の順位が信用できるようになる。
7. **#6/#7/#8/#10**: OpenAlex の `<=`/`>=` 演算子、find_citing の空リスト握り潰し、fetch_paper の 429 混同、llm_client の 'billing' 誤分類 (Yo が extract で踏んだやつの共有層版) を修正。
8. **#12/#29/#53**: execute_proposal を atomic 化 + 重複 run ガード + status 遷移ガード。

### P2 — 測定器・curated data・テスト (今月)
9. **#31/#32/#33**: GCMG の誤系列 fingerprint、agg-kurt-decay の発散、compute_hill sentinel を修正。
10. **#37/#38/#39/#40**: curated の誤 arxiv id 4 件を修正 (silicon-fracture / 共形重力 / ボルツマン)。`validate_subfields/techniques` を実際に呼ぶ (#22)。
11. **#43/#44**: executor を実物で叩く統合テスト (adversarial fixture 込み)。0% カバレッジ 9 モジュールに最低限のテスト。
12. **#42**: CI lint の `\|\| true` 除去 → F821 の実クラッシュを露出させて直す。
13. **#16**: literature_map.primary_tag を coverage と同じ正規化に統一。

### P3 — 統合と衛生 (随時)
14. **§6 のマージプラン**を実行 (Sunday cron 前に PR #7 をマージコミットで)。
15. `db doctor` コマンド (§5e)、破壊操作の `--backup` (§5f)、scaffold の実行前ゲート (§5g)。
16. **#60**: pyproject に matplotlib 追加。**#46/#47**: 週次 workflow の Yahoo fetch 依存を fixture 化。

---

*生成: Claude Code — 27 監査エージェント + 敵対的検証 (Fable 5 上限で 48 件は検証未了・除外)、112 エージェント、560 万トークン。全 finding の生データは同ディレクトリの `2026-07-02-branch-findings-full.json` を参照。本レポートは `11e9d59` 時点の snapshot 監査。*
