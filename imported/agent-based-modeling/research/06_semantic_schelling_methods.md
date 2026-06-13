# Theme 6: Semantic Schelling Model — 手法一覧

## 研究ギャップ

LLMエージェントがシェリングモデルの類似性判定を意味的に行う研究は **未発表**。すべての構成要素は既存研究に存在するが、統合した論文はない。

---

## 1. フレームワーク

### Mesa-LLM
- **URL:** [github.com/projectmesa/mesa-llm](https://github.com/projectmesa/mesa-llm) | [Docs](https://mesa-llm.readthedocs.io/en/latest/)
- **概要:** Mesa ABMの公式LLM拡張。Reasoning（CoT, ReAct, ReWoo, ToT）、Memory、Communicationモジュール搭載
- **状態:** v0.1.1、GSoC 2025発、活発に開発中
- **適合度:** ★★★★★ — Mesaの[標準Schellingモデル](https://mesa.readthedocs.io/stable/examples/basic/schelling.html)を拡張する最も自然な選択

### Shachi (Sakana AI)
- **論文:** [arXiv:2509.21862](https://arxiv.org/abs/2509.21862) (Sep 2025)
- **コード:** [github.com/SakanaAI/shachi](https://github.com/SakanaAI/shachi)
- **アーキテクチャ:** エージェントを4モジュールに分解 — **LLM**（推論）、**Configuration**（ペルソナ/アイデンティティ）、**Memory**（文脈持続）、**Tools**（環境操作）
- **適合度:** ★★★★★ — Configurationモジュールが文化的アイデンティティの符号化に直接対応

---

## 2. 大規模都市LLMシミュレーション

### AgentSociety (清華大学)
- **論文:** [arXiv:2502.08691](https://arxiv.org/abs/2502.08691) (Feb 2025)
- **コード:** [github.com/tsinghua-fib-lab/AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety)
- **手法:** GPT-4駆動の10,000+エージェント。認知モジュール（記憶、目標管理、意思決定、社会関係追跡）。感情・欲求・動機を持つ
- **活用法:** 居住移動の意思決定をLLMが行うアーキテクチャを参考に、「幸福度」をLLM評価の文化的適合性に置換可能

### OpenCity (清華大学)
- **論文:** [arXiv:2410.21286](https://arxiv.org/abs/2410.21286) (Oct 2024)
- **コード:** [github.com/tsinghua-fib-lab/Anonymous-OpenCity](https://github.com/tsinghua-fib-lab/Anonymous-OpenCity)
- **手法:** Perception-Planning-Reflection ループ。**Group-and-Distill** 最適化で類似エージェントをクラスタリング → LLM呼び出し600倍高速化、70%削減
- **活用法:** スケーラビリティ手法（クラスタリング、プロンプト蒸留）が計算コスト削減に必須

### CitySim
- **論文:** [arXiv:2506.21805](https://arxiv.org/html/2506.21805v1) (Jun 2025)
- **手法:** 再帰的な価値駆動スケジューリング。必須活動・個人習慣・状況要因のバランス

---

## 3. 都市分離・ジェントリフィケーション（非LLM、方法論的に重要）

### Axelrod-Schelling Model（概念的先駆者）
- **論文:** [arXiv:0907.2360](https://arxiv.org/abs/0907.2360) (2009)
- **手法:** Axelrodの文化伝播（多特徴文化ベクトル、文化的重複に比例する相互作用確率）+ Schelling移動（近隣との平均文化的類似度が閾値以下なら移動）
- **核心的洞察:** 離散的文化特徴ベクトル → LLM生成の意味的表現（埋め込み）に置換。類似度 = 埋め込み空間のコサイン類似度、またはLLM判定

### Dynamic Models of Gentrification
- **論文:** [arXiv:2410.18004](https://arxiv.org/abs/2410.18004) (Oct 2024)
- **手法:** 3所得グループ（低/中/高）が生活コストに基づき移転するABM。時間的ネットワーク指標でジェントリフィケーション早期検出

### LLMによるジェントリフィケーション検出（Airbnb）
- **論文:** [Zenodo](https://zenodo.org/records/15231204) (Apr 2025)
- **手法:** LLMがAirbnb掲載テキストからジェントリフィケーション指標をスコアリング → 時空間近隣変化モデルに投入（Bristol事例）

### 小売ジェントリフィケーションのLLM計測（上海）
- **論文:** [Springer](https://link.springer.com/article/10.1007/s12061-026-09809-z) (2026)
- **手法:** GPT-4oでPOIデータからエンティティ抽出・分類 → 小売ジェントリフィケーション指標化

---

## 4. サーベイ論文

| 論文 | URL | ポイント |
|------|-----|----------|
| LLM-Augmented ABM: Challenges and Opportunities | [arXiv:2405.06700](https://arxiv.org/abs/2405.06700) (May 2024) | 「平均ペルソナ」問題（行動均質化）、ブラックボックス解釈性、計算コスト。ハイブリッド推奨 |
| Integrating LLM in ABSS | [arXiv:2507.19364](https://arxiv.org/abs/2507.19364) (Jul 2025) | 最新サーベイ、統合パターン網羅 |
| LLMs for Complex Systems Research | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1571064524001386) (2024) | LLM-ABMの複雑系科学への応用 |

---

## 5. 設計パターン（文献横断）

### エージェントプロンプト構造（典型5モジュール）
1. **Persona** — 人口統計・文化的アイデンティティ・価値観・許容度（Shachiの"Configuration"）
2. **Perception** — 近隣の構造化記述（隣人プロファイル、アメニティ、文化的マーカー、最近の変化）
3. **Decision** — 「あなたは誰で、何を知覚しているか → 留まるか移動するか？」CoTまたはJSON出力
4. **Reflection** — 意思決定後の内部状態更新
5. **Memory** — 過去の近隣・相互作用・満足度スコアの蓄積（バッファ / 埋め込みRAG）

### 近隣知覚の符号化方法
- **構造化テキスト:** 「あなたの隣人は: [ペルソナリスト]。地元のアメニティ: [リスト]」
- **統計＋ナラティブ:** 「60%が同文化。新しいカフェが開店。2人の長期居住者が転出」
- **エージェント間対話:** 隣人との会話を通じて印象形成

### スケーラビリティ手法
- **エージェントクラスタリング:** 類似プロファイルをグループ化、1回のLLM呼び出しを共有、ノイズ追加（OpenCity）
- **キャッシング:** シミュレーション実行を記録（Mesa-LLM）
- **ハイブリッド:** 複雑な意思決定にLLM、ルーティンにルールベース

---

## 6. 推奨アーキテクチャ

| 要素 | 推奨 |
|------|------|
| プラットフォーム | Mesa + Mesa-LLM |
| エージェント定義 | 文化的背景・言語・価値観・ライフスタイルを符号化したペルソナプロンプト（Shachi Configuration） |
| 近隣知覚 | 隣人ペルソナ＋地域アメニティの構造化プロンプト |
| 意思決定 | LLMが文化的適合性を評価 → 満足度スコア + stay/move判定 |
| スケーラビリティ | OpenCityのGroup-and-Distill |
| 検証 | 古典的Schelling結果＋実世界分離データとの比較 |

### 主要リスク
- **行動均質化:** 多様なペルソナプロンプトとtemperature設定で対処
- **再現性:** Shachiのモジュール分解でアブレーション研究
- **コスト:** ローカルモデル（Gemma等）または埋め込み類似度を安価な代替に
