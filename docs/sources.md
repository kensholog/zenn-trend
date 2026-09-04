# 確認済みの事実と出典

凡例: ✅ 一次情報で確認 / 🔶 一部確認・推測を含む / ❌ 未確認

---

## Zenn の API と規約（確認日 2026-09-03、再確認 2026-09-04）

| 事実 | 出典 |
|---|---|
| 利用規約（2025-06-05 更新）に自動取得の条文は無い。禁止事項は運営妨害・サーバー機能破壊など | https://zenn.dev/terms |
| robots.txt は `Disallow: /search` のみ。sitemap 公開 | https://zenn.dev/robots.txt |
| 非公式 API について運営 catnose99 の回答（2020-12-30）:「問題ないのですが、現時点のAPIはあくまでもzenn.dev向けのものなので、告知なく仕様が変更されることがあります」 | https://github.com/zenn-dev/zenn-community/issues/209 |
| 一覧 `zenn.dev/api/articles?topicname=…&order=latest&count=48` は **page=100 で打ち切り**（next_page null、page=101 は 404）。1 ページ最大 48 件 | 実測 2026-09-03 / 09-04 |
| 一覧のフィールド: id, slug, path, title, emoji, article_type, published_at, body_updated_at, liked_count, bookmarked_count, comments_count, body_letters_count, user, publication。**topics は一覧に無い** | 実測 |
| 記事 API `zenn.dev/api/articles/{slug}` に topics・body_html・authenticated_liked_count・anonymous_liked_count | 実測 |
| ユーザー API `zenn.dev/api/users/{username}` に follower_count・total_liked_count・articles_count | 実測 |
| トピック API `zenn.dev/api/topics/{name}` は taggings_count のみ。トピックページ `zenn.dev/topics/{name}` の SSR JSON に articlesCount / booksCount / scrapsCount（表示される「記事 N 本」と一致）。taggings_count は articlesCount より大きい（例 claudecode 13,504 vs 10,058） | 実測 2026-09-04 |
| 公式 RSS: `zenn.dev/feed` = 「現在Zennでトレンドとなっている投稿のRSSフィードです」（2026-09-04 に 20 件）。トピック別 `zenn.dev/topics/{name}/feed`、ユーザー別 `zenn.dev/{user}/feed?all=1` | https://zenn.dev/zenn/articles/zenn-feed-rss（Zenn 公式 2020-09-29）、実測 |
| トレンドの算出は「記事の鮮度」「アクセスの流入元」「文字数あたりの滞在時間」を使う（外部から再現できない） | https://github.com/zenn-dev/zenn-community/issues/9（2020-09-18） |

## 先行分析（本文を読んだ。詳細は非公開備忘）

| 記事 | 要点 |
|---|---|
| krbrr「Zennのバズを3万記事のデータで測ったら、いいねと品質は別軸だった」2026-08-08 https://zenn.dev/zenn_content/articles/buzz-articles-30k-analysis | 歴代トップ 240・定点 30,203・LLM 品質評価 175。品質 S 級でもいいね中央値 0.5。トップ 40 は中央値 11,533 字・外部リンク 35。「次はタグ別のいいね分布」と予告（2026-08-23 時点で未刊）。データ・コード非公開 |
| tabayashi「技術記事のいいね数は、書く前にほぼ決まっている。約 5,500 本を分解して分かったこと」2026-08-27 https://zenn.dev/tabayashi/articles/buzz-anatomy-what-drives-likes | Zenn 2,787 本（最新 100 ページ、約 10 日分）＋ Qiita 2,765 本。疑似 R²: 著者 0.407、はてブ 0.547、中身 0.064、時刻 0.017。著者の過去平均いいねとの順位相関 0.615。過去平均 1 未満の著者 1,433 人からいいね 10 以上はゼロ。Publication で到達率 7 倍。最大の未観測変数は「トレンド入り」。トピックは説明変数に無い |
| mima_ita「Shall we テックブログ? — データで見るQiitaとZennの比較」2025-12-28 https://qiita.com/mima_ita/items/5961d4d572c9e97e3f29 | Qiita 全記事 2015〜2025 の年別: like 平均 31.6 → 3.46、中央値 7 → 0。Zenn の年別は未実施（API が非公開で取れなかった） |

## フェーズ 0 の実測（2026-09-04）

方法: 各トピックについて (1) トピックページの articlesCount、(2) `api/topics`、(3) 一覧の最終ページ `page = min(100, ceil(articlesCount/48))` の最古 `published_at`。1 req/s。`full_history` = articlesCount ≤ 4,800 かつ最終ページの next_page が null。

注記: articlesCount が一覧の件数より数本多いトピックがある（vibecoding は page 27 が空で page 26 が最終、最古 2025-01-31。統計 は page 8 が空で page 7 が最終、最古 2020-11-07）。フェーズ 1 では next_page が null になるまでページングする。

| 群 | topic | 表示名 | 記事 | 本 | スクラップ | taggings | 最終ページ | 遡れる最古 | 全履歴 |
|---|---|---|---|---|---|---|---|---|---|
| new | ai | AI | 23,743 | 490 | 403 | 34,027 | 100 | 2026-06-30 | ✗ |
| new | llm | 大規模言語モデル | 10,450 | 154 | 868 | 345 | 100 | 2026-03-08 | ✗ |
| new | claudecode | Claude Code | 10,058 | 184 | 250 | 13,504 | 100 | 2026-04-26 | ✗ |
| new | claude | Claude | 6,696 | 110 | 145 | 8,818 | 100 | 2025-12-26 | ✗ |
| new | 生成ai | 生成 AI | 5,451 | 105 | 158 | 7,225 | 100 | 2024-10-25 | ✗ |
| new | aiエージェント | AIエージェント | 3,703 | 51 | 73 | 2,833 | 78 | 2024-04-15 | ✓ |
| new | chatgpt | ChatGPT | 3,521 | 80 | 208 | 4,604 | 74 | 2020-09-29 | ✓ |
| new | mcp | Model Context Protocol | 3,479 | 48 | 165 | 4,576 | 73 | 2024-09-22 | ✓ |
| new | gemini | Gemini | 2,854 | 29 | 118 | 3,763 | 60 | 2023-12-08 | ✓ |
| new | openai | OpenAI | 2,550 | 28 | 190 | 3,338 | 54 | 2022-07-27 | ✓ |
| new | rag | RAG | 1,794 | 35 | 307 | 2,687 | 38 | 2023-08-05 | ✓ |
| new | codex | Codex | 1,758 | 16 | 53 | 2,177 | 37 | 2025-04-05 | ✓ |
| new | cursor | Cursor | 1,642 | 11 | 94 | 2,113 | 35 | 2021-12-15 | ✓ |
| new | vibecoding | Vibe Coding | 1,250 | 27 | 44 | 1,104 | 26 | 2025-01-31 | ✓ |
| new | githubcopilot | GitHub Copilot | 1,143 | 10 | 89 | 1,395 | 24 | 2021-09-18 | ✓ |
| new | ollama | Ollama | 787 | 17 | 59 | 1,008 | 17 | 2023-10-06 | ✓ |
| new | copilot | Copilot | 760 | 4 | 20 | 930 | 16 | 2020-12-17 | ✓ |
| new | dify | Dify | 629 | 14 | 38 | 745 | 14 | 2024-04-10 | ✓ |
| new | openclaw | OpenClaw | 363 | 5 | 12 | 613 | 8 | 2026-01-22 | ✓ |
| new | cline | Cline | 354 | 2 | 38 | 428 | 8 | 2024-10-17 | ✓ |
| new | antigravity | Antigravity | 336 | 5 | 14 | 406 | 7 | 2025-11-19 | ✓ |
| new | devin | Devin | 324 | 1 | 16 | 374 | 7 | 2024-03-17 | ✓ |
| new | mastra | Mastra | 324 | 2 | 13 | 385 | 7 | 2025-03-06 | ✓ |
| new | agentskills | Agent Skills | 321 | 1 | 34 | 394 | 7 | 2025-10-18 | ✓ |
| new | langgraph | LangGraph | 319 | 7 | 15 | 478 | 7 | 2024-03-30 | ✓ |
| new | geminicli | Gemini CLI | 308 | 7 | 29 | 372 | 7 | 2025-06-25 | ✓ |
| new | kiro | Kiro | 297 | 1 | 18 | 349 | 7 | 2025-07-15 | ✓ |
| new | n8n | n8n | 266 | 10 | 10 | 329 | 6 | 2020-11-07 | ✓ |
| new | deepseek | DeepSeek | 252 | 2 | 12 | 327 | 6 | 2024-04-14 | ✓ |
| new | codexcli | Codex CLI | 176 | 1 | 11 | 198 | 4 | 2025-04-25 | ✓ |
| new | a2a | A2A | 132 | 2 | 2 | 203 | 3 | 2025-04-10 | ✓ |
| new | windsurf | Windsurf | 128 | 1 | 8 | 159 | 3 | 2024-12-03 | ✓ |
| new | v0 | v0 | 82 | 1 | 8 | 100 | 2 | 2023-10-19 | ✓ |
| new | bolt | Bolt | 58 | 0 | 3 | 70 | 2 | 2020-09-18 | ✓ |
| new | roocode | Roo Code | 45 | 0 | 1 | 49 | 1 | 2025-02-10 | ✓ |
| new | openhands | OpenHands | 40 | 0 | 10 | 55 | 1 | 2024-09-02 | ✓ |
| new | replit | Replit | 38 | 0 | 3 | 48 | 1 | 2020-11-19 | ✓ |
| new | aider | Aider | 18 | 0 | 5 | 24 | 1 | 2024-12-22 | ✓ |
| new | lovable | Lovable | 9 | 1 | 0 | 13 | 1 | 2025-03-06 | ✓ |
| control | python | Python | 17,589 | 436 | 1,089 | 24,034 | 100 | 2026-01-03 | ✗ |
| control | aws | AWS | 16,693 | 154 | 1,224 | 20,759 | 100 | 2025-11-02 | ✗ |
| control | typescript | TypeScript | 13,665 | 292 | 1,274 | 17,439 | 100 | 2025-05-26 | ✗ |
| control | react | React | 11,075 | 244 | 1,255 | 14,646 | 100 | 2024-07-31 | ✗ |
| control | nextjs | Next.js | 8,483 | 209 | 987 | 10,699 | 100 | 2024-04-28 | ✗ |
| control | 個人開発 | 個人開発 | 6,729 | 116 | 156 | 8,673 | 100 | 2025-12-05 | ✗ |
| control | docker | Docker | 6,459 | 92 | 710 | 8,257 | 100 | 2022-08-29 | ✗ |
| control | go | Go | 6,415 | 101 | 770 | 7,350 | 100 | 2022-10-17 | ✗ |
| control | rust | Rust | 4,486 | 74 | 924 | 6,359 | 94 | 2015-06-22 | ✓ |
| control | データ分析 | データ分析 | 947 | 21 | 21 | 1,248 | 20 | 2020-09-19 | ✓ |
| control | 統計 | 統計 | 338 | 11 | 7 | 448 | 7 | 2020-11-07 | ✓ |
| control | 投資 | 投資 | 130 | 7 | 1 | 196 | 3 | 2020-11-07 | ✓ |

フェーズ 0 の判定: 全履歴に到達した new 群は 30。そのうち最古が 2024-01-01 以降で記事 100 本以上は **17**（aiエージェント, mcp, codex, dify, openclaw, cline, antigravity, devin, mastra, agentskills, langgraph, geminicli, kiro, deepseek, codexcli, a2a, windsurf。vibecoding は最古 2025-01-31 で 18 個目）。基準「5 個以上」を満たす → **通過**。対象トピックの最終確定は roadmap.md の誕生月規則で機械的に行う。

トレンド履歴の第三者データは存在しない（kaisugi/zenn-trend-api は現在値のみ、tada246/zenn-trend-history はサーバー停止、Wayback のトップページ快照はトレンド欄が JS 描画で空）。確認日 2026-09-04。
