# knowledge.md — 知見・決定事項

## 2026-08-23 方向転換: 画面 → Bedrock 体調分析
- 停止理由は「Google 純正の画面に勝てない」と「Google Health Coach（Gemini）の分析が阿呆で 1,500 円の価値がない」の 2 点。後者が本プロジェクトの新しい価値仮説。
- Fitbit Web API の時系列エンドポイントは日付範囲指定で過去分を一括取得できるため、「毎日の自動取得を先に作る」必要はない。バックフィルで燃料を即日確保する。
- Fitbit のレート上限は 150 リクエスト/時/ユーザー。1 日ずつ `/1d.json` を 60 日 × 5 種叩くと超えるので範囲エンドポイントに切り替える。
- ローカル clone は 2026-04-07 で止まっていた（実装は Claude Code on the web で進んでいた）。`git pull --ff-only` で PR #69 まで同期済み。
- Vault の行動文脈: worklog 56 ファイル（frontmatter `author`/`tags`、`## HH:MM プロジェクト — 見出し` 形式）、reflections 4 ファイル（`## 事実` / `## 気づき`）。体調の主観メモは 5 件のみで薄い。
- `/data/` 丸ごと .gitignore 済み。健康データ・レポートは Git に入れない。
- 認証方式の衝突（毎日 Bedrock 呼び出し vs 長期キーゼロ）はサイクル 1 で arch-sparring。サイクル 0 は手動実行で回避。
