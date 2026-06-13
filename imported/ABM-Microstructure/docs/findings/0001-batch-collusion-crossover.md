# Finding 0001 — batch×抽出のレジーム依存クロスオーバーと、B の二力対決への含意

**Status**: 検証済（2026-06-02、M1 harness から創発）/ committed-quote モデル前提

## 発見（headline）
連続マッチングを batch auction に置き換えたとき、速度ベース抽出が**減るか増えるかは逆選択レジーム（spread の広さ h）に依存し、クロスオーバーがある**：
- **h ≪ J（tight spread）**: batch は抽出を**減らす**（個別ジャンプが net され picking-off 機会が減る、Budish 的）。
- **h ~ J（広い spread）**: batch は抽出を**増やす**（accumulated net 変位の凸性 `E[(|S_N|−h)+]` が、連続の per-jump `(J−h)+`≈0 を上回る）。

これは単調な定性結果ではなく、メカニズム水準の非自明な結果。

## 検証（artifact でなくモデルの性質）
`anchors.budish_sniping_rent` を sim と独立に厳密計算（net 変位ジャンプ数 K~Binom(N,q)、上方 u~Binom(K,½)、`E[(|2u−K|·J − h)+]`）。
- 独立アンカー自身がクロスオーバーを示す（`test_crossover_is_real_in_anchor`）。
- sim が厳密アンカーと高 h 含む7点で一致（`test_sim_matches_budish_anchor`）、両レジームの符号を再現（`test_crossover_reproduced_by_sim`）。
→ クロスオーバーはモデルの抽出曲面の性質であり coding artifact ではない。

## B（実験B）への直撃：二力の対決
collusion ＝ MM が spread を広げる ＝ **高 h**。上の発見を辿ると、batch が collusion に効くチャネルが二本・逆向きに立つ：

1. **Green-Porter チャネル（促進）**: batch（離散・透明・反復）は監視と懲罰を容易にし tacit collusion を**支える**。
2. **arbitrageur-predation チャネル（破壊, ← finding 0001）**: 高 h では batch が広い collusive spread を arbitrageur の accumulated-displacement sniping に**晒す**。連続は広い spread を守る（個別ジャンプが spread を超えない）。batch は collusion を**掘り崩す**。

⇒ B の中心問題が「batch は collusion を助けるか壊すか（曖昧）」から、**「Green-Porter 促進 vs arbitrageur 捕食――どちらが勝つか」**（名前付き二力の対決）に鋭くなる。これは harness から落ちてきた、当初の monotone な懸念より良い B。

## 前提（finding が乗るモデル仮定）
**committed-quote モデル**：MM はバッチ開始時の belief で気配を出し、バッチ内で更新しない（＝速い arbitrageur に対し遅い MM）。これは速度非対称の自然な表現。MM がバッチ内で気配を更新できる「revisable-quote（純 Budish FBA）」では sniping が消えて別挙動になる。**この機構選択が design lever の定義そのもの**であり、B spec で明示し、必要なら両機構を対比する（捕食チャネルは committed-quote 下で生きる）。

## 残る検証義務（B との関係）
- **③ 本物の Kyle λ — 閉鎖（2026-06-10）**: impact 層を identity-blind flow 回帰に置換。sim `metrics.price_impact`（主体を知らずに測る λ̂=Σx·Δp/Σx²）vs `anchors.kyle_lambda`（flow 組成から独立導出 `λ(N)=α·E[|S_N|1{>h}]/(α·P(|S_N|>h)+N·noise_rate·dt)`）。N=1 で gm_break_even と厳密一致（GM: spread=impact）＝spread 層と impact 層の三角検証。batch λ(N) で netting×noise 希釈も照合。詳細 research.md D5b v2、`tests/test_anchors_match.py`。残: 閉形式は pure-jump、σ>0 impact は ① と同箱。
- **① diffusion σ>0**: pure-jump では収束自明（離散化バイアス無し）。LVR/現実市場は diffusion 由来 → 収束検査が本物になるのは σ>0 から。外部妥当性（④）作業と並走、gate は塞がない。

## 関連
- 検証: `tests/test_budish_anchor.py`、`src/microstructure/anchors.py:budish_sniping_rent`
- 設計: `docs/research-design.md` §3、`.specify/memory/constitution.md`
