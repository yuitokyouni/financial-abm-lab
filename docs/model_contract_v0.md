# Model Contract v0 — 被監査シミュレータの最小インターフェース（起草）

**Status**: draft v0（2026-06-11）。Yuito レビュー待ち。本書は設計文書であり、`atlas/protocols.py` への実装反映は toy が必要とするまで行わない（toy-first、CLAUDE.md スコープ規律）。

---

## 0. なぜ契約か

Gym が RL の標準になったのはアルゴリズムではなく `env.step()` の契約だった。Shachi（Sakana）は**エージェント側**の契約を切った。Atlas が切るのは**シミュレータ側**の契約——「このインターフェースを実装すれば、あなたのモデルは Atlas battery で監査可能になる」という採用面である。

契約が決めるのは監査の可能性であって、モデルの正しさではない。Atlas は機構の内部実装に依存しない（`atlas/protocols.py` の設計原理）。契約はその「依存しない」を型として固定する。

## 1. 契約本体（v0 sketch）

```python
@runtime_checkable
class Simulator(Protocol):
    """被監査モデルが実装する最小インターフェース。"""

    name: str
    channels: tuple[str, ...]
    # 宣言された観測チャネル（例: "price", "volume", "aggregate_action"）。
    # ここが介入面の全体。宣言外への介入は型レベルで存在しない。
    # ZI は channels = () —— 陰性対照が型で表現される。

    def reset(self, seed: int) -> None:
        """決定的初期化。同一 (config, seed) → bit 同一の軌道（C0 必須）。"""

    def step(self) -> None:
        """1 tick 進める。時間離散化はモデル宣言制（契約は dt を強制しない）。"""

    def observe(self, channel: str) -> float | NDArray:
        """エージェントが見る値（介入適用後）。channels 外は KeyError。"""

    def intervene(self, iv: Intervention) -> None:
        """do(channel, scheme, θ)。観測チャネルの graded degrade のみ。"""

    def emit(self) -> Mapping[str, NDArray]:
        """出力系列（price 等）。SF battery と Response 構築の入力。"""

    def provenance(self) -> ProvRecord:
        """L2 prov.json 相当（seed/config/output digest）。C2 で必須。"""


@dataclass(frozen=True)
class Intervention:
    channel: str          # 宣言済みチャネル名
    scheme: str           # "average" | "ema" | "noise" | "delay"（B2 の 4 scheme）
    theta: float          # graded 強度（0 = no-op が必須恒等点）
```

## 2. 設計原則（契約が強制するもの）

1. **介入面 = 観測チャネルのみ（B2 ≠ A）**。機構係数への介入（ablation）は契約に存在しない。`intervene` が触れるのは `channels` に宣言された観測の degrade だけ。これは survey（`docs/research/abm_b2_intervention_survey.md` §1-2）の核心区別を型に焼いたもの。
2. **チャネルは静的宣言**。battery は内部実装を知らずに介入面を列挙できる——監査が機構の数に対してスケールする条件。宣言漏れ（実際は観測しているのに宣言しない）は L2 provenance（ctx 経由の観測ログ）との突合で検出する。これが「reported reach」と契約の接続点。
3. **θ=0 恒等性**。`intervene(θ=0)` は no-op と bit 同一であること（property test 対象）。介入実装そのものが軌道を汚す bug を型ではなく契約検査で塞ぐ。
4. **決定論は契約の地金**。reset(seed) の bit 再現が崩れた実装は監査不能（CRN paired 差分が定義できない）。

## 3. 適合レベル

| Level | 要件 | できる監査 |
|---|---|---|
| **C0** | reset / step / emit + 決定論 | SF battery、再現・分散測定（P3 の監査第 1-2 段） |
| **C1** | + channels / observe / intervene | 介入応答プロトコル全体（P3 第 3 段、P1 の主実験） |
| **C2** | + provenance（L2、ctx 経由観測の記録） | 宣言と実観測の突合（reach 監査） |

P3 の被監査モデル（LLM-ABM）は当面 C0 適合のラッパーから始められる——再現と分散測定だけでも監査は立つ。C1 を拒む（介入面を出さない）こと自体が情報になる。

## 4. 参照アダプタ（同梱予定）

| アダプタ | 機構 | 状態 | 契約上の役割 |
|---|---|---|---|
| T | Chiarella-Iori 型 trend-following | toy 実装済（v0.3 正準） | 識別トリオ |
| H | Kirman/ALW 型 herding | toy 実装済（v0.3 正準） | 識別トリオ |
| SG | Speculation Game | 計画 | 識別トリオ（自前モデル、観測チャネル設計自由） |
| ZI | zero-intelligence | toy 実装済 | 陰性対照（channels = ()） |
| CB | Cont-Bouchaud | 計画 | **第二の陰性対照**（古典形は観測チャネル無し。program_claims_v1.md §2.2） |
| LM | Lux-Marchesi | 保留 | 部分観測で B2 困難（既知）。C0 適合のみ先行可 |
| microstructure-002 | ABM-Microstructure 実験B harness | 将来 feature | **最初の外部アダプタ**（P2 = Atlas の最初の実監査） |

## 5. v0 で決めないこと

- スコア機構・leaderboard（スコープ規律で v0 禁止のまま）。
- マルチ資産・連続時間・部分観測チャネルの表現（LM が要求した時点で v1 へ）。
- agent 側契約との接合（Shachi 互換層）。P3 対象選定後に判断。

## 6. 既存コードとの対応

- `atlas/protocols.py` の `Mechanism`（reset のみ）は本契約 C0 の部分集合 → toy 安定後に `Simulator` へ拡張（逆輸入の流儀どおり）。
- `provabm/ctx.py` の observe/read_own_state/random/submit_order は**エージェント側**から見た同じ境界。契約 §2.2 の宣言突合は ctx ログを使う。
- `toy/observation.py` の masking 4 scheme が `Intervention.scheme` の参照実装。
