# migration report — v0.3 → CSV
generated: 2026-07-07T07:23:32
source xlsx: `inputs/tape_versions/v0.3/policy_holding_sale_event_tape_v0_3.xlsx`

## counts
- legs: 12
- groups: 11
- sources: 11
- lists (enum families): 12
- field_dictionary: 69
- baseline_spec: 8
- changelog: 25

## truncated URLs in xlsx (auto-resolved by prefix match)
v0.3 Event_Tape has cells where source URLs were truncated to 80 characters with a literal `...` suffix (autofit-save artefact). source_id は Source_Log への一意 prefix match で解決したが、URL 文字列は truncated のまま legs.csv に残す (データ創作禁止)。次バージョン (v0.4+) で xlsx 側の URL を修復すること。

- leg G004/L001: primary URL truncated in xlsx (len=80), resolved by prefix match to S003 but URL string kept truncated in legs.csv
- leg G005/L001: primary URL truncated in xlsx (len=80), resolved by prefix match to S006 but URL string kept truncated in legs.csv
- leg G008/L002: primary URL truncated in xlsx (len=80), resolved by prefix match to S009 but URL string kept truncated in legs.csv

## unresolved source URLs (not in Source_Log)
- leg G001/L001: primary URL not in Source_Log (https://www.toyota-industries.com/news/2023/11/29/008606/index.html)
- leg G003/L001: secondary URL not in Source_Log (https://www.reuters.com/business/autos-transportation/toyota-group-companies-...)
- leg G004/L001: secondary URL not in Source_Log (https://www.reuters.com/business/autos-transportation/japanese-insurers-banks...)
- leg G006/L001: primary URL not in Source_Log (https://www.thepack.co.jp/dcms_media/other/2025.08.29b.pdf)
- leg G007/L001: primary URL not in Source_Log (https://www.nishikawa-rbr.co.jp/upfile/20260119_3_news.pdf)
- leg G008/L002: secondary URL not in Source_Log (https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/disclosure/202602...)

