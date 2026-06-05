"""toy.agents — 機構モデル。

`base.Agent` を介して全 agent は `ctx.*` 経由でのみ観測・乱数・発注を行う(honest 性確保)。
`trend.TrendAgent` = Model T、`herd.HerdAgent` = Model H(spec §3.2)。
"""
