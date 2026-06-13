# Theme 3: Bank Run via Linguistic Contagion — 手法一覧

## 研究状況

ほぼ同一のテーマの論文が **既に存在**（Ruano & Rajan, Harvard, Feb 2026）。新規性を出すには差別化が必要。

---

## 1. 直接的先行研究（最重要）

### Social Contagion and Bank Runs: An ABM with LLM Depositors
- **論文:** [arXiv:2602.15066](https://arxiv.org/abs/2602.15066) (Feb 2026, Harvard)
- **手法:**
  - プロセスベースABM。銀行はcash-first引き出し処理 + 内生的ストレス指数
  - 預金者は**リスク許容度**と**ファンダメンタルズ vs 社会情報の重み**で異質
  - **Twitter活動から較正した重尾ネットワーク**上で通信（2023年SVB危機）
  - **制約付きLLM**が情報セット → 離散行動（withdraw/hold）+ SNS投稿を生成
  - Diamond-Dybvig理論ベンチマークで検証
- **主要結果:**
  - 銀行内接続性が引き出しカスケードの速度・確率を増大
  - 銀行間伝染に**急峻な相転移**（spillover率 ~0.10付近）
  - 預金者重複とネットワーク増幅が**非線形に相互作用**
  - SVB → First Republic の実際の破綻順序を再現
- **差別化ポイント:** この論文との差別化が必須

---

## 2. 噂拡散・情報伝染

### Simulating Rumor Spreading in Social Networks using LLM Agents
- **論文:** [arXiv:2502.01450](https://arxiv.org/abs/2502.01450) (Feb 2025, UT Austin, AAAI WMAC 2025)
- **コード:** [github.com/UT-SysML/rumors-in-multi-agent](https://github.com/UT-SysML/rumors-in-multi-agent)
- **手法:** 多様なペルソナを持つLLMエージェントを4種のネットワーク（Erdos-Renyi, Scale-Free, Small World, Facebook実データ）上に配置。噂の信頼/拡散/変形を判断
- **結果:** ネットワーク・ペルソナ・拡散方式で0%〜83%の伝播率

### FUSE: Fake News Evolution (EMNLP 2025)
- **論文:** [arXiv:2410.19064](https://arxiv.org/abs/2410.19064) (Oct 2024)
- **手法:** 4種のエージェント役割 — **Spreaders**, **Commentators**, **Verifiers**, **Bystanders**。真実の情報が累積的歪曲でフェイクニュースに変異するプロセスをシミュレーション
- **活用法:** 役割分類（拡散者/分析者/検証者/傍観者）→ 預金者アーキタイプ（パニック拡散者/アナリスト/規制当局/受動的預金者）に対応

---

## 3. LLMベース金融市場ABM

### FCLAgent: Agent-Based Simulation of a Financial Market
- **論文:** [arXiv:2510.12189](https://arxiv.org/abs/2510.12189) (Oct 2025, Springer)
- **手法:** **ハイブリッドアーキテクチャ** — LLMが売買方向を判断（行動/心理的文脈）、ルールベースが注文価格/数量を処理。ファットテール分布、ボラティリティクラスタリング、バブル崩壊サイクルを再現
- **設計パターン:** LLM=定性判断、ルール=定量処理の分離は銀行取り付けモデルに最適

### TradingAgents (TauricResearch)
- **論文:** [arXiv:2412.20138](https://arxiv.org/abs/2412.20138) (Dec 2024)
- **コード:** [github.com/TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **手法:** 専門役割エージェント群（ファンダメンタル/センチメント/テクニカルアナリスト、トレーダー、リスク管理チーム）。Bull/Bear研究者が市場状況を討論。**LangGraph**ベース、Ollama対応

### Adversarial News and Lost Profits
- **論文:** [arXiv:2601.13082](https://arxiv.org/abs/2601.13082) (Jan 2026)
- **手法:** 操作されたニュース見出しがLLMベース取引システムを誤導。FinBERT/FinGPT/FinLLaMA + 6汎用LLMをテスト。1つの操作見出しで年間リターン最大17.7pp低下
- **活用法:** 「言語的伝染」の攻撃面を直接モデル化

### EconAgent: Simulating Macroeconomic Activities
- **論文:** [arXiv:2310.10436](https://arxiv.org/abs/2310.10436) (Oct 2023)
- **手法:** **Perceptionモジュール**で異質エージェント生成 + **Memoryモジュール**で過去の経験・市場動態を振り返り。フィリップス曲線・オークンの法則が創発
- **活用法:** 反復的な噂露出で不安が蓄積するメカニズムに

---

## 4. 意見動態・社会的影響

### Simulating Opinion Dynamics with Networks of LLM-based Agents
- **論文:** [arXiv:2311.09618](https://arxiv.org/abs/2311.09618) (Nov 2023)
- **手法:** LLMエージェントがネットワーク上で自然言語で意見交換。プロンプトで**確証バイアス**を注入 → 意見断片化。10種のネットワーク構造を比較
- **活用法:** プロンプトレベルの「認知バイアス」（損失回避、パニックバイアス）でマクロ動態を制御

### Simulating Influence Dynamics with LLM Agents
- **論文:** [arXiv:2503.08709](https://arxiv.org/abs/2503.08709) (Mar 2025)
- **手法:** エージェントがピア影響とニュースセンチメントに基づき信念を形成・調整

---

## 5. スケーラブルプラットフォーム

### OASIS: Open Agent Social Interaction Simulations (1M agents)
- **論文:** [arXiv:2411.11581](https://arxiv.org/abs/2411.11581) (Nov 2024)
- **コード:** [github.com/camel-ai/oasis](https://github.com/camel-ai/oasis)
- **手法:** Twitter/Reddit風ソーシャルメディアシミュレータ。動的社会ネットワーク、推薦システム。バッチLLM推論で100万エージェント規模。情報拡散、集団分極化、群集効果を再現

### Generative Agents (Stanford Smallville)
- **論文:** [arXiv:2304.03442](https://arxiv.org/abs/2304.03442) (Apr 2023, ICLR 2024)
- **手法:** 基盤アーキテクチャ — **Memory Stream**（観察）+ **Reflection**（高次洞察）+ **Planning**（行動生成）。情報が会話を通じて有機的に伝播
- **活用法:** Reflectionメカニズムで「累積的不安」をモデル化

---

## 6. その他のGitHubリポジトリ

| リポジトリ | URL | 特徴 |
|-----------|-----|------|
| LLM-ABM-StockSim | [GitHub](https://github.com/mihirchhiber/LLM-ABM-StockSim) | Mesa + LangChain + LLaMA3.2、個性的エージェント |
| Chat Bankman-Fried | [GitHub](https://github.com/bancaditalia/llm-alignment-finance-chat-bf) | イタリア銀行、7つの圧力変数での金融シナリオ |
| FinMem | [GitHub](https://github.com/pipiku915/FinMem-LLM-StockTrading) | 階層的記憶アーキテクチャのLLMトレーディング |
| LLM-ABM Survey (清華) | [GitHub](https://github.com/tsinghua-fib-lab/LLM-Agent-Based-Modeling-and-Simulation) | キュレーションリスト |

---

## 7. 設計パターン（文献横断）

### エージェントアーキテクチャ
1. **ハイブリッドLLM+ルール**（FCLAgent）: LLM=定性判断（引き出すべきか？）、ルール=定量（いくら？）
2. **Perception-Memory-Reflection-Action**（Smallville/EconAgent）: 観察蓄積 → 振り返り → 行動計画
3. **制約付きLLMポリシー**（2602.15066）: 構造化状態記述 → 離散行動 + 自然言語出力（投稿/噂）

### 通信トポロジー
- Twitterから較正した重尾ネットワーク（2602.15066）
- Erdos-Renyi, Scale-Free, Small World, Facebook実グラフ（2502.01450）
- 高クラスタリング＋スケールフリー（FUSE）
- 10種のネットワークアーキタイプ（2311.09618）

### 信頼・信用の符号化
- ファンダメンタルズ vs 社会情報の異質な**重み**（2602.15066）
- **ペルソナベース**の信頼傾向（プロンプト設計）（2502.01450）
- 相互作用履歴に基づく**信用スコアリング**（反復ゲーム）

### 噂/ニュースの処理方法
- 構造化プロンプト: エージェント財務状態 + 隣人の行動/投稿 + 銀行健全性指標 + ニュース見出し → LLM出力（2602.15066）
- 役割ベース処理: Spreaders/Commentators/Verifiers/Bystanders（FUSE）
- システムプロンプトで確証バイアスを誘導 → 意見断片化（2311.09618）

### 情報カスケードメカニズム
- 臨界接続/spillover閾値での**相転移**（2602.15066）
- エージェント通過時の**累積的歪曲**（FUSE）
- 単独では弱いチャネルの**非線形相互作用**（2602.15066）

---

## 8. 差別化の方向性（既存研究 2602.15066 との差別化）

| 方向性 | 概要 |
|--------|------|
| 噂の変異・進化 | 拡散中に情報が変容するダイナミクス（FUSEの手法応用） |
| 異質なメディアチャネル | グループチャット/ニュース/SNS/口コミ、それぞれ異なる信用重み |
| 介入モデリング | 規制当局の発表、預金保険メッセージ、カウンターナラティブ注入 |
| 非SVB危機への較正 | 新興国銀行取り付け、歴史的事例 |
| 大規模化 | OASISスタイルのバッチ推論で数百→数千エージェント |
| 敵対的ナラティブ | 意図的パニック誘発の偽情報（2601.13082の手法応用） |
