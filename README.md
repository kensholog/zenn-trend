# zenn-trend

Zenn の公開データで「**新しいツールのトピックでは、最初の数ヶ月の記事ほどいいねが付くか**（先行者利得）」を測るプロジェクト。あわせて公式トレンド RSS を毎時保存し、「トレンド入りは新参の書き手に開いているか」を後で測る。

状態: **フェーズ 0 通過（2026-09-04）。撤退基準を凍結。フェーズ 1（取得）は未着手。C（トレンド RSS の毎時保存）は仕組みを作成済みで、GitHub への push 待ち。**

| 文書 | 内容 |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | フェーズ一覧、**撤退基準 A/B/C**（凍結）、問い B1〜B5 の事前登録、C の設計、やらないこと |
| [docs/sources.md](docs/sources.md) | 確認済みの事実と出典（API の仕様と規約、先行分析の要点、フェーズ 0 の実測表） |
| [docs/decisions/](docs/decisions/) | 決定記録（0001 問いの採用と撤退基準の凍結） |
| [scripts/fetch_topic_articles.py](scripts/fetch_topic_articles.py) | トピック一覧の全ページ取得（1 req/s、再開可）→ `data/topics/*.jsonl` |
| [scripts/fetch_users.py](scripts/fetch_users.py) | 一覧に出た著者のユーザー API 取得（1 req/s、再開可）→ `data/users.jsonl` |
| [scripts/fetch_trend_feed.py](scripts/fetch_trend_feed.py) | 公式トレンド RSS と新着 48 本の毎時保存 → `trend_feed/`、`latest_feed/`（GitHub Actions で実行） |
| [.github/workflows/trend-feed.yml](.github/workflows/trend-feed.yml) | 毎時の cron |

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
2. `python scripts/fetch_topic_articles.py`（約 2,000 リクエスト、1 req/s で約 35 分。再開可。長引くなら `scripts/run_detached.ps1` で切り離す）
3. `python scripts/fetch_users.py`（著者数は取得後に判明。数千人なら 1〜3 時間）
4. 撤退基準 A → B を判定し、結果を docs/results.md に記録する
5. 通過したら B1〜B5 を出す（`scripts/aggregate.py`、未作成）
6. 記事（zenn-content 側で執筆）
