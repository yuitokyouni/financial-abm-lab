# Theme 9: DAO Ideological Split & Hard Fork — 手法一覧

## 研究ギャップ

LLMエージェントによるDAO分裂シミュレーションは **未発表**。以下4つを統合すれば初の研究になる:
- DAO-AI（提案分析、フォーク機構なし）
- Nouns DAOペルソナ投票（派閥形成なし）
- Democratic Forking（フォーク理論、LLMなし）
- LLM_for_Polarization（LLM分極化、DAO文脈なし）

---

## 1. DAO + LLMガバナンス（直接関連）

### DAO-AI: Evaluating Collective Decision-Making through Agentic AI
- **論文:** [arXiv:2510.21117](https://arxiv.org/abs/2510.21117) (Oct 2025)
- **手法:** 複数エージェントが提案メタデータ・フォーラム議論・投票動態を分析。8つの主要DAOから3,383提案を対象。Modular Composable Programs (MCPs)でガバナンスデータ取得

### Assisted Governance with LLM-based Algorithmic Committees (Nouns DAO)
- **論文:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5569238)
- **コード:** [github.com/xxcg322/LLM-Governance-Research](https://github.com/xxcg322/LLM-Governance-Research)
- **手法:** **7つのガバナンスペルソナ**（P1-P7）× 6つのフロンティアLLM → 508のNouns DAO提案に対し21,336件の構造化判断を生成。ペルソナプロンプトが「プログラム可能な認知的多様性」を実現
- **核心的知見:** ペルソナプロンプトでイデオロギー的に異なるLLM投票者を作成可能。人間の投票結果との体系的乖離あり

### QOC DAO: AI-Driven DAO
- **論文:** [arXiv:2511.08641](https://arxiv.org/html/2511.08641v1) (Nov 2025)
- **手法:** Question-Option-Criteria (QOC) モデル。AIエージェントがステークホルダー視点をシミュレーション。**二次投票 + vote-escrowed トークン**でクジラの影響と共謀を低減

### Democratic Forking: Choosing Sides with Social Choice（理論的基盤）
- **論文:** [arXiv:2103.03652](https://arxiv.org/abs/2103.03652) (2021)
- **手法:** フォーキングの形式的社会選択理論。エージェントは代替案 **AND** 可能なフォーク分割に対する選好を表明。マイノリティが離脱を信頼性をもって脅かせる場合の安定性と戦略的行動を分析
- **活用法:** フォーク決定のゲーム理論的基盤として直接使用可能

### DAO-Agent: ZKP-Verified Incentives for Multi-Agent Coordination
- **論文:** [arXiv:2512.20973](https://arxiv.org/abs/2512.20973) (Dec 2025)
- **手法:** オンチェーンDAOガバナンス + ZKPベースShapley値貢献度測定 + ハイブリッドオン/オフチェーン

---

## 2. LLM意見動態・分極化（コア手法論文）

### Emergence of Human-like Polarization Among LLM Agents (清華大学)
- **論文:** [arXiv:2501.05171](https://arxiv.org/abs/2501.05171) (Jan 2025)
- **コード:** [github.com/tsinghua-fib-lab/LLM_for_Polarization](https://github.com/tsinghua-fib-lab/LLM_for_Polarization)
- **手法:** 数千のLLMエージェントがネットワーク上で自発的に同質的クラスタリングとエコーチェンバーを形成。最大1,000エージェント・4,000関係をサポート
- **核心的知見:** LLMエージェントは自然にイデオロギー的クラスタリングと分極化を生む → フォーク前の派閥形成に直接対応

### Decoding Echo Chambers: LLM-Powered Simulations
- **論文:** [arXiv:2409.19338](https://arxiv.org/abs/2409.19338) (Sep 2024)
- **コード:** [github.com/ZongfangLiu/EchoChamberSim](https://github.com/ZongfangLiu/EchoChamberSim)
- **手法:** 古典モデル（Bounded Confidence Model, Friedkin-Johnsen）との検証済み比較

### MTOS: Multi-topic Opinion Simulation
- **論文:** [arXiv:2510.12423](https://arxiv.org/abs/2510.12423) (Oct 2025)
- **手法:** 多トピックフレームワーク。正相関トピックはエコーチェンバーを増幅、負相関トピックは抑制、無関係トピックはリソース競合で緩和
- **活用法:** DAOガバナンスは複数の相関提案を含む（例: 財務支出とプロトコル方向性）

### LLM-Driven Echo Chamber Formation (意見+ネットワーク同時更新)
- **論文:** [arXiv:2502.18138](https://arxiv.org/abs/2502.18138) (Feb 2025)
- **手法:** 意見更新 **AND** ネットワーク再配線の両方をLLMが駆動。文脈認識型、意味的に豊かな社会的相互作用
- **活用法:** トークンホルダーが見解を変える＋社会的接続/委任を再配分するDAO動態に対応

### Multi-Agent LLM Communities Driven by Value Diversity
- **論文:** [arXiv:2512.10665](https://arxiv.org/html/2512.10665v1) (Dec 2025)
- **手法:** エージェント価値観（博愛/普遍性/快楽 vs 権力/安全）をイデオロギー的ルール型（ルソー型 vs ホッブズ型）にマッピング。価値多様性からの集団動態創発
- **活用法:** DAOフォークにおけるイデオロギー的整合性の測定に直接適用可能

### Competing LLM Agents in Opinion Polarisation
- **論文:** [arXiv:2502.11649](https://arxiv.org/html/2502.11649) (Feb 2025)
- **手法:** 非協力ゲーム理論。敵対的LLM相互作用による偽情報の戦略的拡散/対抗

### LLM-Agent Opinion Dynamics（確証バイアス注入）
- **コード:** [github.com/yunshiuan/llm-agent-opinion-dynamics](https://github.com/yunshiuan/llm-agent-opinion-dynamics)
- **核心的知見:** LLMには「コンセンサスバイアス」があり、プロンプト設計で意図的に対抗しないと現実的な断片化が生じない

---

## 3. 投票・集合的意思決定

### FlockVote: U.S. Presidential Election Simulation
- **論文:** [arXiv:2512.05982](https://arxiv.org/abs/2512.05982) (Dec 2025, ICAIS 2025)
- **手法:** 高忠実度人口統計プロファイル + 動的コンテキスト → 生成的推論で投票判断

### Persona-driven EU Parliament Voting Simulation
- **論文:** [arXiv:2506.11798](https://arxiv.org/abs/2506.11798) (Jun 2025)
- **手法:** ゼロショットペルソナプロンプトでF1~0.793の個人投票予測精度

### From Debate to Deliberation: Structured Collective Reasoning
- **論文:** [arXiv:2603.11781](https://arxiv.org/abs/2603.11781) (Mar 2026)
- **手法:** Deliberative Collective Intelligence (DCI)。4推論アーキタイプ、14種の認識的行為、共有ワークスペース、収束フローアルゴリズム
- **活用法:** DAOフォーラム議論フェーズのモデル化に

### LLM Voting: Human Choices and AI Collective Decision Making
- **論文:** [arXiv:2402.01766](https://arxiv.org/abs/2402.01766) (Feb 2024)
- **手法:** LLaMA-2/GPT-4エージェントと人間参加者の投票パターン比較

---

## 4. ガバナンスシミュレーションフレームワーク

### Concordia (Google DeepMind)
- **論文:** [arXiv:2312.03664](https://arxiv.org/abs/2312.03664)
- **コード:** [github.com/google-deepmind/concordia](https://github.com/google-deepmind/concordia)
- **手法:** Game Master (GM) + プレイヤーエージェント。モジュラーコンポーネント（記憶、観察、行動）。自然言語行動をGMが結果に変換。NeurIPS 2024コンテストに「State Formation」「Labor Collective Action」シナリオ
- **適合度:** ★★★★★ — GMアーキテクチャがDAOガバナンスシミュレーションに最適。「State Formation」はDAOフォークに近い

### GovSim: Governance of the Commons
- **論文:** [arXiv:2404.16698](https://arxiv.org/abs/2404.16698) (Apr 2024)
- **コード:** [github.com/giorgiopiatti/GovSim](https://github.com/giorgiopiatti/GovSim)
- **手法:** LLMエージェントが共有資源の搾取と持続のバランス。3シナリオ（漁業/牧草地/汚染）。最強LLMのみ持続可能な協力達成（<54%生存率）。コミュニケーションが協力に不可欠
- **活用法:** DAOトレジャリー = 共有資源。資源共有意思決定のアーキテクチャが直接転用可能

### ValueFlow: Measuring Value Perturbation Propagation
- **論文:** [arXiv:2602.08567](https://arxiv.org/html/2602.08567) (Feb 2026)
- **手法:** 多エージェントLLMシステム内の価値摂動の伝播を測定。個別にアラインされたエージェントでもシステムレベルの価値ドリフトが発生
- **活用法:** DAOコミュニティ内のイデオロギー変化伝播の測定手法

---

## 5. ブロックチェーンガバナンス・フォーク理論

### Blockchain Governance: Optimal/Suboptimal Outcomes Prediction
- **論文:** [arXiv:2003.09241](https://arxiv.org/pdf/2003.09241) (2020)
- **手法:** ゲーム理論シミュレーション。ハードフォーク発生条件と多数派が新チェーンに移行するかの数学的予測
- **活用法:** LLMシミュレーション結果の検証ターゲット

### Quadratic Voting for Blockchain Governance
- **論文:** [arXiv:2504.12859](https://arxiv.org/abs/2504.12859) (Apr 2025)
- **手法:** 二次投票とその一般化をブロックチェーンガバナンスに適用

### Agent-based Model of Initial Token Allocations
- **論文:** [arXiv:2208.10271](https://arxiv.org/abs/2208.10271) (2022)
- **手法:** フェアローンチ後の取引モダリティ下での投票権トークン集中度のABM

---

## 6. 設計パターン（文献横断）

### 意見形成のモデリング
1. **ペルソナプロンプティング:** 人口統計・価値観・イデオロギーを符号化（Nouns DAO: 7ペルソナ, FlockVote: 人口統計プロファイル, EU議会: ゼロショットF1~0.79）
2. **確証バイアス注入:** デフォルトLLMはコンセンサスに偏る → プロンプトで確証バイアスを注入し現実的断片化を生成
3. **記憶-観察-行動ループ:** 会話履歴保持、ピア意見観察、行動生成（Concordiaパターン）
4. **ネットワーク埋め込み相互作用:** 意見 AND ネットワーク結合の同時進化（2502.18138）

### イデオロギー的整合性の測定
1. **価値→イデオロギーマッピング:** Schwartz価値次元 → ルソー型/ホッブズ型（2512.10665）
2. **埋め込み空間距離:** 意見テキストの埋め込み → コサイン類似度
3. **投票一致率:** 提案投票のペアワイズ一致をイデオロギー的近接の代理指標に
4. **クラスタ分析:** 意見ベクトルまたは投票パターンのコミュニティ検出で派閥識別
5. **ValueFlow伝播:** エージェント相互作用を通じた価値摂動の拡散測定（2602.08567）

### 投票・ガバナンス機構
1. **トークン加重投票:** 標準1-token-1-vote（DAO-AI等）
2. **二次投票:** クジラ影響低減 + vote-escrowed（QOC DAO）
3. **投票前審議:** フォーラム議論フェーズ → 投票フェーズ（DAO-AI）
4. **フォーク選択肢付き多数決:** Democratic Forkingフレームワーク（2103.03652）

### 派閥形成メカニズム
1. **同質的クラスタリング:** 類似エージェントとの優先的相互作用（2501.05171）
2. **エコーチェンバー増幅:** 多トピック相関が思想的サイロを強化（MTOS）
3. **ネットワーク再配線:** 異質なピアとの接続を切り、同質なピアと形成（2502.18138）
4. **価値駆動連合:** 共有価値プロファイルのエージェントが共有ルール選好に収束（2512.10665）

---

## 7. 推奨アーキテクチャ

| 要素 | 推奨 | 根拠 |
|------|------|------|
| フレームワーク | Concordia | GMアーキテクチャ、モジュラー、「State Formation」実績 |
| エージェント設計 | Nouns DAO式7+ペルソナ + 確証バイアス注入 | 認知的多様性の実証済み手法 |
| 意見動態 | 意見更新+ネットワーク再配線の二重メカニズム | 2502.18138パターン |
| 投票機構 | トークン加重 + 二次投票ハイブリッド | QOC DAOの設計 |
| フォーク決定 | Democratic Forking社会選択モデル | 2103.03652のゲーム理論層 |
| 測定 | 価値→イデオロギーマッピング + 投票一致クラスタ + ValueFlow | 多角的評価 |
| 検証 | BCM/FJ古典モデルとの比較 | EchoChamberSimの手法 |
