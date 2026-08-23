# knowledge.md — 知見・決定事項

## 2026-08-23 方向転換: 画面 → Bedrock 体調分析
- 停止理由は「Google 純正の画面に勝てない」と「Google Health Coach（Gemini）の分析が阿呆で 1,500 円の価値がない」の 2 点。後者が本プロジェクトの新しい価値仮説。
- Fitbit Web API の時系列エンドポイントは日付範囲指定で過去分を一括取得できるため、「毎日の自動取得を先に作る」必要はない。バックフィルで燃料を即日確保する。
- Fitbit のレート上限は 150 リクエスト/時/ユーザー。1 日ずつ `/1d.json` を 60 日 × 5 種叩くと超えるので範囲エンドポイントに切り替える。
- ローカル clone は 2026-04-07 で止まっていた（実装は Claude Code on the web で進んでいた）。`git pull --ff-only` で PR #69 まで同期済み。
- Vault の行動文脈: worklog 56 ファイル（frontmatter `author`/`tags`、`## HH:MM プロジェクト — 見出し` 形式）、reflections 4 ファイル（`## 事実` / `## 気づき`）。体調の主観メモは 5 件のみで薄い。
- `/data/` 丸ごと .gitignore 済み。健康データ・レポートは Git に入れない。
- 認証方式の衝突（毎日 Bedrock 呼び出し vs 長期キーゼロ）はサイクル 1 で arch-sparring。サイクル 0 は手動実行で回避。

## 2026-08-23 サイクル 0 実装（Codex 委譲 → reviewer 差し戻し → 修正）
- Codex 1 回目（gpt-5.6-sol, effort max）は 25 分の timeout で打ち切られ result.json 無し。ただし作業ツリーの実装は完了していた（pytest 12/12）。スクリプト 3 本 + テストの新規実装は 1 本の委譲には大きすぎる。次回は「実装」と「テスト」を分けるか timeout を 40 分にする。
- reviewer（Opus 5）の致命指摘 2 件: (1) HTTP エラー時に空の日次 JSON を保存して exit 0、かつ次回からスキップされ永久に欠測 (2) `aws login` 失効時の botocore 例外（UnauthorizedSSOTokenError / TokenRetrievalError / SSOTokenLoadError / NoCredentialsError / CredentialRetrievalError）を拾えず exit 2 にならない。どちらも「静かに壊れる」型で、受け入れ条件のテストだけでは素通りした。エラー経路のテストを受け入れ条件に含めるべきだった。
- Codex のハマり: activity は 6 リソース（steps 等）を別々に取るため、1 リソース失敗でも日次 activity 全体を error 扱いにする必要があった。botocore の実例外はクラスごとにコンストラクタ引数（provider / error_msg）が異なるため、テストで raise するときは 1.43.78 のシグネチャを確認した。
- fetch_data の既定終了日は「日本時間の昨日」。当日は未確定データのため保存しない（保存すると翌日以降スキップされる）。
- build_context の上限は 120,000 文字（`--max-chars`）。実 Vault の worklog 60 日分は約 166k 文字あるので、全文 → 5 行 → 2 行 → 1 行 → 見出しのみ の順に縮める。
- `.venv` は uv で作成（`uv venv .venv --python 3.12`）。`python` コマンドは無いので `.venv/bin/python` を使う。
