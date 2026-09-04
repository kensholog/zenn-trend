# zenn-trend

Zenn の公開データで「**新しいツールのトピックでは、最初の数ヶ月の記事ほどいいねが付くか**（先行者利得）」を測るプロジェクト。あわせて公式トレンド RSS を毎時保存し、「トレンド入りは新参の書き手に開いているか」を後で測る。

状態: **フェーズ 1〜2 通過（2026-09-04）。結論: 新興トピックに早く書くことの利得は検出できない（早期 ÷ 後期の到達率比 1.40 に対し、成熟トピックの同じ暦月でも 1.44）。効いているのは著者の実績（実績ゼロの著者 9% vs 実績 20 以上の著者 68% がいいね 10 に到達）。次はフェーズ 3（記事）と、4 週間後の再取得（2b）。C（トレンド RSS の保存）は 30 分ごとに稼働中。**

| 文書 | 内容 |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | フェーズ一覧、**撤退基準 A/B/C**（凍結）、問い B1〜B5 の事前登録、C の設計、やらないこと |
| [docs/results.md](docs/results.md) | 事前登録の集計結果（撤退基準の判定、B1〜B5）。`scripts/aggregate.py` が生成 |
| [docs/results_posthoc.md](docs/results_posthoc.md) | 事後の参考表（対照の新参層、暦四半期の推移、経過月ごとの合算、著者層別）。判定には使わない |
| [docs/decisions/](docs/decisions/) | 決定記録（0001 問いの採用と撤退基準の凍結、**0002 フェーズ 1〜2 の判定と結論**、2b の事前登録） |
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
