# zenn-trend

Zenn の公開データで「**新しいツールのトピックでは、最初の数ヶ月の記事ほどいいねが付くか**（先行者利得）」を測るプロジェクト。あわせて公式トレンド RSS を毎時保存し、「トレンド入りは新参の書き手に開いているか」を後で測る。

記事: [Zenn の新興トピックに早く書いても得はない ── 9.8 万記事で先行者利得を測ったら、効いたのは経路と読者だった](https://zenn.dev/kensholog/articles/zenn-first-mover-advantage)（2026-09-05 公開）

状態: **フェーズ 1〜2 通過（2026-09-04）。結論: 新興トピックに早く書くことの利得は検出できない（早期 ÷ 後期の到達率比 1.40 に対し、成熟トピックの同じ暦月でも 1.44）。効いているのは著者の「実績」（他の記事の平均いいね）で、その中身は配信経路と既存の読者。初投稿でも Publication 所属なら 35% がいいね 10 に届き、個人・フォロワー 0 なら 2%。記事 1 は 2026-09-05 公開。第 2 プロジェクト（著者 17,943 人の記事 192,238 本の順番と、はてブ件数 66,981 本）も同日に判定: 当たる記事は 1 本目が最も多く（初投稿の 20.8%、以後単調減）、当たっても次は楽にならず（プラセボで因果は検出できず）、新参のヒットの 62% にはてブが付いていた（[decisions/0005](docs/decisions/0005-q1-q2-verdict.md)）。次は記事 2 と、4 週間後の再取得（2b）。C（トレンド RSS の保存）は 30 分ごとに稼働中。**

| 文書 | 内容 |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | フェーズ一覧、**撤退基準 A/B/C**（凍結）、問い B1〜B5 の事前登録、C の設計、やらないこと |
| [docs/results.md](docs/results.md) | 事前登録の集計結果（撤退基準の判定、B1〜B5）。`scripts/aggregate.py` が生成 |
| [docs/results_posthoc.md](docs/results_posthoc.md) | 事後の参考表（対照の新参層、暦四半期の推移、経過月ごとの合算、著者層別）。判定には使わない |
| [docs/results_q.md](docs/results_q.md) / [docs/results_q_posthoc.md](docs/results_q_posthoc.md) | 第 2 プロジェクト（Q1 実績はどう溜まるか / Q2 新参のヒットは外から来たか）の集計結果と事後の参考表。`scripts/aggregate_q.py` / `posthoc_q.py` が生成 |
| [docs/decisions/](docs/decisions/) | 決定記録（0001 問いの採用と撤退基準の凍結、**0002 フェーズ 1〜2 の判定と結論**、0003 第 2 プロジェクトの事前登録、0004 Q1b の定義修正、**0005 第 2 プロジェクトの判定**） |
| [docs/sources.md](docs/sources.md) | 確認済みの事実と出典（API の仕様と規約、先行分析の要点、フェーズ 0 の実測表） |
| [docs/data/](docs/data/) | 公開する集計 CSV: トピック × 経過月の到達率、暦四半期の到達率、合算の経過月 |
| [scripts/fetch_topic_articles.py](scripts/fetch_topic_articles.py) | トピック一覧の全ページ取得（1 req/s、再開可）→ `data/topics/*.jsonl` |
| [scripts/fetch_users.py](scripts/fetch_users.py) | 一覧に出た著者のユーザー API 取得（1 req/s、再開可）→ `data/users.jsonl` |
| [scripts/aggregate.py](scripts/aggregate.py) / [scripts/posthoc.py](scripts/posthoc.py) | 事前登録どおりの集計（`--criteria` で A/B のみ）/ 事後の参考表 |
| [scripts/fetch_trend_feed.py](scripts/fetch_trend_feed.py) | 公式トレンド RSS と新着 48 本の保存 → `trend_feed/`、`latest_feed/`（GitHub Actions で実行） |
| [.github/workflows/trend-feed.yml](.github/workflows/trend-feed.yml) | 30 分ごとの cron |

- 検証の経緯・備忘は非公開の別リポジトリにある（`ideas/` は junction で、ここには置かない）
- 前の題材: [meccha-chameleon](https://github.com/kensholog/meccha-chameleon)（Steam レビューで拡散経路を再現）、[funding-arb-jp](https://github.com/kensholog/funding-arb-jp)（撤退済み）

## 問い（事前登録。詳細は docs/roadmap.md）

- **B1** 対象トピック合算で、誕生から 0〜2 ヶ月目の記事の到達率（いいね 10 以上）は 6〜11 ヶ月目の 1.5 倍以上か（著者層・文字数層で層別）
- **B2** 著者の過去平均いいねが 1 未満の層でも同じか（いいね 5 以上で）
- **B3** 成熟トピック（react, python など）の同じ暦月で同じ比を出し、age 効果と区別できるか
- **B4** 到達率のピークは誕生から何ヶ月目か。**B5** 供給が増えると薄まるか

## データの扱い

- 取得は 1 リクエスト/秒以下。非公式 API は運営が容認（2020-12-30）、仕様変更は予告なし
- 記事本文は取得しない。公開するのは集計だけ。著者名は集計に出さない
- 生データ（`data/`）はコミットしない。`trend_feed/` と `latest_feed/` は収集の永続化のためコミットする（公開情報のみ）

## 次にやること（順番固定）

1. ~~撤退基準を決めて docs/ に記録する（データを見る前）~~ 2026-09-04 完了
2. ~~`python scripts/phase1.py`（一覧 約 2,000 リクエスト 35 分 → 著者 17,952 人 5 時間）~~ 2026-09-04 完了
3. ~~撤退基準 A → B を判定し、B1〜B5 を出す~~ 2026-09-04 完了（[docs/results.md](docs/results.md)、[decisions/0002](docs/decisions/0002-phase1-verdict.md)）
4. 記事（zenn-content 側で執筆）
5. 2b: 2026-10-02 以降に同じ一覧を再取得し、age 効果と全体低下を分ける（判定は decisions/0002 に事前登録済み）
6. C: 2 週間分たまる前に問いと基準を decisions/0003 で登録し、「トレンド入り記事の著者プロファイル」を出す
