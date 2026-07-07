# unwind-tape gaps report

`ts | context | kind | detail` — schema変化 / 取得失敗 / 欠損の追記ログ。
欠損は絶対に埋めない。ここに列挙し、原因を追跡してから raw を再取得すること。

- 2026-07-07T16:42:12+09:00 | pdf_archiver:S010 | fetch_error | HTTP 401
- 2026-07-07T16:42:12+09:00 | pdf_archiver:S015 | fetch_error | HTTP 401
- 2026-07-07T16:42:12+09:00 | pdf_archiver:S016 | fetch_error | HTTP 401
