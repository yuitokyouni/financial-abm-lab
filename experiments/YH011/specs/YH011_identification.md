# YH011 — 収益率から AI トレーダー比率 p2 は同定できるか

対象論文: Nakagawa, Hirano, Minami & Mizuta (2024),
*A Multi-agent Market Model Can Explain the Impact of AI Traders in Financial
Markets — A New Microfoundations of GARCH model*, arXiv:2409.12516

発端: [@blog_uki] が「論文は『AI Trader が増えたら値動きがどうなるか』であって、
『値動きから AI Trader の割合を推定する』のは逆方向」と指摘し、
[@_mhirano] が「GARCH の推定が綺麗にできるなら AI Trader の割合の推定はできた気がする。
ただ、問題は GARCH の推定が精度高くできないのがボトルネックで
そっち向きの実証を諦めた記憶がある」と応答した。

本 spec は**その逆方向を、GARCH を経由せずに定式化し直す**。

---

## 1. モデル(論文の再構成)

需給インバランス信号を

$$D_t = p_1\,(g(x_{t-1}) - \lambda\sigma_{t-1}) + p_2\,(h(x_{t-1},I_{t-1}) - \gamma|u_{t-1}|)$$

とおくと、論文の買い/売り注文式から**厳密に**

$$r_t = \underbrace{\rho D_t}_{f_t} + \underbrace{\rho k (1+D_t)}_{\sigma_t}\,\varepsilon_t,
\qquad u_t = r_t - f_t = \sigma_t\varepsilon_t$$

が出る($x_t\sim N(0,1)$ iid、$g(x)=\log(1+\max(-0.99,x))$、$h=0.1x$、$\varepsilon_t\sim N(0,1)$)。

Theorem 4.1 は $\sigma_t^2$ を展開して交差項を落とし

$$\sigma_t^2 \approx \omega + \alpha u_{t-1}^2 + \beta\sigma_{t-1}^2,\qquad
\boxed{\alpha = \rho^2k^2p_2^2\gamma^2},\qquad \beta = \rho^2k^2p_1^2\lambda^2$$

を得る。**$\alpha$ だけが $p_2$ を運ぶ**ので、素直な逆問題は
$\hat p_2 = \sqrt{\hat\alpha}/(\rho k\gamma)$ である。これが Hirano の言う
「GARCH が綺麗に推定できれば」の中身。

## 2. 何が原理的に同定できないか

**(a) スケール同変性。** モデルは
$(\rho,\lambda,\gamma)\to(c\rho,\lambda/c,\gamma/c)$ で不変。
自由な無次元パラメータは $(k,\,p_1,\,p_2,\,h_{\rm coef},\,\rho\lambda,\,\rho\gamma)$ の6個で、
$\rho$ は単位の取り方でしかない。したがって使う要約統計量は**すべてスケール不変**でなければ、
$\rho k$ という任意単位を読んでいるだけになる。

**(b) $p_2$ と $\gamma$ の交絡。** $\alpha=(\rho k\gamma)^2p_2^2$ は積 $p_2\gamma$ しか決めない。
$\alpha$ 単独からは $p_2$ は出ず、**AI トレーダーのリスク回避度 $\gamma$ を仮定しない限り
絶対水準は同定されない**。UKI の「追加の仮定等が必要」はここで数式として確認できる。
$\omega\approx(\rho k)^2$ を使うと $\rho k$ は落ちて $p_2\gamma=\sqrt{\alpha/\omega}$ まで
は行けるが、$\gamma$ は残る。比 $p_2/p_1=(\lambda/\gamma)\sqrt{\alpha/\beta}$ も同様に
$\lambda/\gamma$ を残す。

**(c) 逃げ道。** $p_2$ は $\alpha$ 以外にも**条件付き平均チャネル** $p_2h(x_{t-1})$ に入る。
$\sigma_t=k(\rho+f_t)$ という恒等式があるため、平均とボラティリティは機械的に結び付いており、
$p_2\gamma$ とは別の経路で $p_2$ が観測量に効く。GARCH の $\alpha$ だけを見る推定は
**この情報を捨てている**。GARCH を経由しない動機はここにある。

## 3. 定常性の天井 — スイープの前に必要な制約

大 $\sigma$ での再帰の傾きは $\rho k(p_1\lambda + p_2\gamma|\varepsilon|)$ なので、

* 共分散定常: $(\rho k)^2(p_2^2\gamma^2+p_1^2\lambda^2)<1$
* 狭義定常: $\mathbb{E}\log\bigl[\rho k(p_1\lambda+p_2\gamma|\varepsilon|)\bigr]<0$

論文のパラメータ($\rho=4,k=0.4,p_1=0.2,\lambda=\gamma=1.2$)では**両者とも
$p_2<0.48$**(共分散 0.4809 / Lyapunov 0.487)。論文が使う $p_2=0.40$ は天井の 83%。
$p_2\gtrsim0.5$ ではモデルは発散し、要約統計量は「AI 比率」ではなく発散を読む。
`nh_model.stability()` がこの上限を返す。スイープは必ずこの下で行う。

## 4. GARCH 経由が失敗する理由 — 精度ではなく一致性

論文と同じパラメータで厳密再帰からデータを生成し、GARCH(1,1) を QMLE で当てると:

| | $\omega$ | $\alpha$ | $\beta$ |
|---|---|---|---|
| Theorem 4.1 | 2.982 | **0.590** | 0.147 |
| QMLE on $r_t$、$T=1000$ | 5.335 | 0.171 | 0.120 |
| QMLE on $r_t$、$T=5000$ | 4.884 | 0.172 | 0.159 |
| QMLE on $r_t$、$T=20000$ | 4.618 | **0.177** | 0.194 |
| 真の潜在 $\sigma_t^2$ への oracle OLS | 0.434 | 0.490 | 0.165 (R²=0.63) |

$T$ を 20 倍にしても $\hat\alpha$ は 0.59 に近づかない。0.177 に**収束**する。
$\hat p_2=\sqrt{\hat\alpha}/(\rho k\gamma)$ は真値 0.40 に対し 0.219
[p05 0.207, p95 0.234] — **区間は締まっていくが真値を含まない**。

つまりボトルネックは Hirano の記憶にある「推定精度」ではなく**特定化の誤り**である:

* 厳密な再帰は $\sigma_t$ が $|u_{t-1}|$ と $\sigma_{t-1}$ に**線形**(TS-GARCH 型)で、
  しかも係数が**負**。それを二乗して初めて正の $\alpha,\beta$ が出るが、
  落とした交差項は $\mathrm{Var}(\sigma_t^2)$ の約 34% を占める
  (oracle OLS の R² = 0.63)。
* 残差成分があるぶん、観測可能な過去に対する条件付き分散は GARCH の再帰と一致しない。
  QMLE は擬似真値に収束し、それは $(\rho k\gamma p_2)^2$ とは別の関数である。

**データを増やしても直らない。** これが「別の方法」を要求する本当の理由。

## 5. GARCH を仮定しない定式化

推定量は変えるが**推論エンジンは共通**にして、要約統計量の情報量だけを比べる:

| ルート | 要約統計量 | GARCH 依存 |
|---|---|---|
| `theorem_qmle` | QMLE の $\hat\alpha$ を Theorem 4.1 で反転 | 仮定する |
| `garch_ii` | 同じ $(\hat\omega,\hat\alpha,\hat\beta)$ を**補助統計量**として使い、$p_2\mapsto$ QMLE 出力の binding function をシミュレーションで学習(間接推論) | 補助としてのみ |
| `sieve_sf` | sieve の prespecified stylized-fact battery + $|r|$ 系の形状統計量 | なし |
| `sieve+garch` | 両方 | 補助としてのみ |

推論は rank 正規化した要約量上の局所線形回帰調整つき ABC
(Beaumont, Zhang & Balding 2002)。rank 正規化は装飾ではない —
このモデルの kurtosis と Hill は seed 分布が重すぎて、生値のユークリッド距離は
1 本の draw で決まってしまう。

sieve の battery を使う理由は 3 つ:

1. 全 metric が `scale_invariant=True` と宣言済み — §2(a) の要請そのもの。
2. `known_blind_spots` が数値と一緒に運ばれる。`acf_abs_1` には
   「GARCH(1,1) で再現される: これが通っても機構については何も言えない」と
   書いてある。AI 比率の推定に使う統計量としてまさに必要な警告。
3. 事前登録された固定セットなので、後から都合の良い統計量を足せない。

## 6. 推定の前に置くゲート — モデル到達可能性

ABC は**必ず数を返す**。観測がモデルの生成し得る領域の外にあっても、
prior の中で一番マシな隅を返すだけである。したがって BTC に数字を出す前に:

> 生成的に寛容な prior(推定用より広い)から定常点を引き、
> BTC の各窓の要約ベクトルが**モデル雲の最近傍からどれだけ離れているか**を測る。
> 帰無分布はモデル自身の held-out draw の同じ距離。

BTC がその帰無分布の右裾に出るなら、モデルはデータに届いていない。
その場合の誠実な出力は「AI 比率 x%」ではなく**「このモデルでは同定されない」**である。
結果は `results/model_adequacy.json`、`docs/YH011_findings.md` を参照。
