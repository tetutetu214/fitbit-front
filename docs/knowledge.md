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
- build_context の上限は 160,000 文字（`--max-chars`）。実 Vault の worklog 本文は 1 段落 = 1 行（中央値 404 文字）で行数では縮まらないため、縮約はエントリ本文の**文字数**基準。全文 → 600 → 400 → 300 → 200 → 見出しのみ の順に打ち切り、打ち切ったときは末尾に `…` を付ける。
- `.venv` は uv で作成（`uv venv .venv --python 3.12`）。`python` コマンドは無いので `.venv/bin/python` を使う。

## 2026-08-23 サイクル 0 実行（実 API）
- Fitbit 再認証: 認可コードは 40 文字。コピー時に末尾 1 文字が欠けて `invalid_grant` になった。auth.py をリダイレクト先 URL まるごと受け付ける形に修正（49f81b0）。
- バックフィル: 60 日分を API 12 回で取得、エラー 0。Fitbit は 60 日すべて値あり（安静時心拍・HRV・睡眠・歩数）。Tanita は 4 月以降の測定なしで全欠測。
- boto3 で `aws login` の認証情報を読むには `botocore[crt]`（awscrt）が必要。無いと `MissingDependencyException`。
- **Bedrock のモデル提供状況（このアカウント、us-east-1、2026-08-23 実測）**: Claude Opus 5 / Sonnet 5 / Opus 4.8 / 4.7 / 4.6 は `AccessDeniedException: not available for this account`。契約（agreement）は Sonnet 5 だけ存在するが、アカウント単位の段階的ロールアウト中で未提供（re:Post の同種報告あり）。利用目的フォームは提出済み。**使えた最上位は Claude Opus 4.5（`us.anthropic.claude-opus-4-5-20251101-v1:0`）と Sonnet 4.6**。Opus 4.1 は Legacy 扱いで不可。
- 初回分析: 入力 108,904 トークン / 出力 2,410 トークン（Opus 4.5）。context 151,887 文字 ≒ 109k トークン（日本語 1.4 文字/トークン程度）。
- レポートの評価（Fable）: 数値根拠・欠測の明示・worklog の時刻との突き合わせ（深夜作業→翌日の睡眠効率）はできている。一方、仮説 1 の「8 日中 6 日で上昇（75%）」は表を数えると上昇 4・低下 3・変化なし 1 で計算ミス。平均睡眠 345 分（5 時間 45 分）という最大の事実を見出しに立てていない。worklog 本文の意味（何の作業か）は使われず、時刻だけが使われた。

## 2026-08-23 トレーナー役への転換（本人ヒアリング反映）
- 本人が Google Health Coach に感じた欠陥は 2 つ: (1) 助言の良し悪しを判断する材料が無い (2) 朝の運動メニューを何度伝えても記憶せず毎朝聞き直す。対策として (1) 指示ごとに根拠データ・参考基準と出典・検証可能な予測を必須化し、次回実行で「前回の答え合わせ」をさせる (2) `profile/about_me.md`（Git 管理外）を context 先頭に縮約対象外で同梱し、訂正履歴を追記する運用にした。
- ヒアリング結果（profile に反映済み）: 起床直後に 5 分プランク + 5 分 HIIT をほぼ毎日 / 就寝 0 時・起床 6 時 / Tanita は週 1〜2 回なら可 / 目標は睡眠 → 体組成 → 疲れにくさ / 制約なし。
- トレーナー役の初回出力（Opus 4.5、入力 110,330 / 出力 1,861 トークン）: プロフィールを正しく使った（HIIT 直後の心拍を不調扱いしない、体組成計は「朝トレ前・週 1 回日曜」、就寝を早めるか起床を遅らせるかを朝トレ維持の前提で質問）。引用した出典 2 件（米国睡眠財団、厚労省 身体活動・運動ガイド 2023 PDF）は curl で実在と内容を確認。数値集計（360 分未満 42/60 日、以上 18 日）は整合。
- 出典 URL の実在確認は毎回やる価値がある（LLM の URL は捏造されうる）。自動化候補: analyze_bedrock の後段で本文中の URL に HEAD を打ち、非 200 を frontmatter に記録する。
- 「前回の答え合わせ」は同じ期間のデータで走らせても意味が無い。週 1 回、新しい 7 日分が溜まってから実行する運用にする。

## 2026-08-23 3 回目の実行（Tanita・起床時刻・訂正履歴入り）
- 本人からの指摘 2 件はどちらも取り込み側の欠陥だった: (1) Tanita は本人が乗っていたのに health.py を 4 月以降未実行（リフレッシュトークンは生きていて自動更新で 28 ファイル取得、60 日範囲で 12 日分） (2) 起床 5:45 は Fitbit 睡眠データにあるのに表に就寝・起床時刻を載せていなかった。教訓: **コーチが本人に質問する前に、その答えがデータに無いかを取り込み側で保証する**。
- 3 回目の出力（Opus 4.5、入力 111,285 / 出力 1,794 トークン）: 起床 5:45 固定・就寝前倒しを本人の決定として扱い、HIIT を心肺適応として肯定的に解釈、欠測を「取り込み側の問題か計測なしか不明」と中立に書けた。
- 誤り: 「Tanita 最終計測 07-27、直近 30 日は 0 日」は誤読（実際は 07-30, 08-05, 08-06 あり）。60 行の表にまばらに入る値はモデルが読み落とす。対策: まばらな系列は表と別に「計測日と値の一覧」を 1 行で渡す（build_context に追加予定）。直近 7 日の就寝時刻列挙も 1 日抜けたが件数は正しかった。
- 検算の手順が固まった: レポートの数値主張を `data/context/*.md` の表で grep/awk して突き合わせる。毎回やる。

## 2026-08-24 PR #71 作成まで（レビュー 2 巡）
- reviewer 2 巡目が実物レポートで致命バグを検出: 前回指示の見出しを完全一致で探しており、プロンプトが出させる実際の見出し（括弧付き）と不一致で答え合わせが永久に「初回のため無し」になる。受け入れ条件のテストは括弧なし見出しの fixture しか通していなかった（実装者の想定を写しただけのテスト）。**「実物の生成物 1 件で通す」ことを受け入れ条件に含めるべき**。Codex が修正（startswith + INSTRUCTION_HEADING_PREFIXES 定数化 + 抜粋不能時の警告、pytest 53 件）。
- 見出しリテラルの正本は prompts/health_analysis.md。プロンプトの出力形式を変えたら build_context.py の INSTRUCTION_HEADING_PREFIXES も変える（二重管理に注意）。
- review-gate（判定 JSON 必須）と delegate-gate（書き込みブロック）の hook 衝突が 2 回発生。auto モード分類器は代筆も拒否するため、最終配置はてつてつ本人が実行した。恒久修正は claude-env 側（.review-verdicts/ を delegate-gate の例外に）。
- snap 版 gh は --body-file の /tmp を読めない（再発）。リポジトリ内に cp してから gh pr create → rm。

## 2026-08-24 ADR-001 コーチカードの実行経路（arch-sparring）
- 錨（5 軸）: トラフィック=自分だけ / データ=読み書き・1 日 1 回キャッシュ / 予算=月数百円 / 運用=放置不要だが毎回の手間は最小に / 目的=本人専用。「起動」＝ `npm run dev` でダッシュボードを開いたとき。
- **選んだ案**: Vite dev サーバのミドルウェア（`configureServer`）で `GET /api/coach` を提供し、今日のレポートが無ければ Python パイプラインを 1 回だけ spawn する。1 プロセスで「開く→解析中→カード」の体験が作れる唯一の案。
- **捨てた案**: (a) FastAPI ローカル API — 技術的には素直だが 2 プロセス起動が運用軸に不利。Node 側が 100 行を超えて育ったら移行する（spawn 部分を proxy に差し替えるだけ）。(b) predev 同期実行 — 最も簡単だが解析が終わるまでブラウザが開かず、`aws login` 失効が「無言で古いカード」になる。(c) クラウド常駐（EventBridge Scheduler + Lambda）— Vault が Windows ローカルにあり Lambda から読めない。Fitbit トークンをクラウドに置く必要もあり長期キーゼロ方針と衝突。
- **決め手の軸**: 運用負荷（1 プロセス）と起動の定義（開いたときに動く）。
- **覆る条件**: 静的ビルドで使いたくなった / 進捗ストリームなどで Node 側ロジックが育った / 他人やスマホから見せたくなった → FastAPI へ。Vault を S3 に同期する仕組みができた → クラウド常駐を再検討。
- **自分への反論と対策**: リロード連打で spawn が二重に走り Bedrock を 2 回呼ぶ → モジュールスコープの inflight Promise で排他（受け入れ条件に含めた）。dev サーバに業務ロジックを混ぜる不純さは「本人専用・dev のみ」の軸だけが根拠なので、前提が変わったら即移行。
- **コストの矛盾と 2 段構成**: 前回実績（入力 108,904 / 出力 2,410 トークン、Opus 4.5 $5/$25 per 1M）は 1 回 ≈ $0.61。日次で回すと月 ≈ $18（¥2,700）で「月数百円」を超える。週次 Opus 60 日（月 ≈ ¥390）はそのまま、日次は 7 日文脈＋週次レポート参照を Sonnet 4.5（$3/$15）で ≈ ¥360/月、の 2 段に分けた。Claude 5 系はこのアカウント未提供のため候補外。
- **クレジット調査（本人質問への回答）**: AWS Promotional Credit 規約は AWS Marketplace を対象外と明記し Bedrock の例外条項なし。Bedrock の third-party モデル（Anthropic・Qwen・DeepSeek 等）は Marketplace 経由請求のため、CB クレジットでは規約上は対象外の公算。Activate 規約だけ「AWS Marketplace is an Eligible Service solely when incurring Bedrock 3P Model Spend」の例外あり（2024-04〜）。Amazon 自社モデル（Nova）は Bedrock 本体課金でクレジット対象。**確定は 08-31 の aws login 時に Cost Explorer（RECORD_TYPE=Credit / Usage）で 08-23 の Opus 4.5 分がどう載るかを見る**。当たっていれば日次も Opus に切替（設定値のみ）。出典: aws.amazon.com/awscredits/ 、aws.amazon.com/activate/terms/ 、aws.amazon.com/legal/bedrock/third-party-models/ 、aws.amazon.com/blogs/startups/aws-activate-credits-now-accepted-for-third-party-models-on-amazon-bedrock/（調査日 2026-08-24）。
- 料金 MCP（awspricing）は `aws login` 前提で未認証時は使えない。今回は公式ページ＋AWS ブログで代替した。

## 2026-08-24 spec.md の敵対的検証（Codex gpt-5.6-sol、読み取り専用）
- 1 回目は effort max で料金裏取りの Web 検索を繰り返し 600 秒でタイムアウト（exit 124、result.json 無し）。**ドキュメント検証の委譲では「Web 検索禁止・spec 本文だけで判定・5 分目安」を必ず書く**。2 回目（xhigh・検索禁止）は完走、verdict=revise、18 件。
- 採用（spec v2 に反映）: 一時ファイル→検証→atomic rename / Python 側 flock と inflight の同期設定（TOCTOU）/ 600 秒タイムアウトとプロセスグループ kill・stdout/stderr の常時 drain / `coach_daily.py --date` で対象日を Node が決定・出力先を日次専用ディレクトリに固定 / 終了コードの正規化（認証=3、ロック=4、argparse の 2 は 1 へ）/ `auth_required` を 60 秒失敗キャッシュから除外 / 答え合わせの入力を「前日カードの今日の一手（無ければ週次の指示）」に定義 / frontmatter から modelId・generatedAt を返す / 4 見出しの厳密検証 / フロントのポーリング終了条件 / logTail のバイト上限 / コスト表の内訳化（16k = 12.7k 按分 + 固定 3.3k）と出力上限 maxTokens 1500。
- 不採用: 永続実行台帳（課金後クラッシュの逐次二重呼び出しは最悪 $0.08、本人専用で台帳の実装コストが上回る。要件を「同時実行と当日再実行を防ぐ」に弱めて明記）/ JSON 構造化出力（Markdown のまま Vault に置きたい。検証で代替）/ stderr の機密除去（本人の画面にしか出ない）/ `data_pending` 状態（Fitbit 日次サマリは前日分までで欠測は既存処理が扱う）/ 別プロセス同時起動の自動テスト（flock の単体テストで代替）。
- Codex には spec.md だけ渡したため「参照先の knowledge.md / plan.md が無い」という指摘（#16）が出た。意図的（成果物のみ渡す規律）だが、spec 側に移行条件と Won't の読み替えを転記して自己完結度を上げた。

## 学習済み概念（理解度テスト正解済み）
- 2026-08-24: コーチカードの役割分担（Vite ミドルウェアは起動判定・排他・タイムアウト・整形のみ、解析は Python）/ FastAPI 案を捨てた理由（2 プロセス起動が運用軸に不利、育ったら移行）/ 「1 日 1 回」保証を弱めたトレードオフ（課金後クラッシュの重複は最悪 $0.08、永続台帳の実装コストが上回る）

## 2026-08-24 コーチカード実装（Codex 2 ラウンド + reviewer 2 巡）
- Codex 1 巡目に reviewer（Opus 5）が要修正 11 件（blocking 3: `spawn('python')` ENOENT / ESLint exit 1 / **日次 context が週次 context を同名上書き**）。3 つ目は spec の欠陥で、`build_context.py --output` を追加して日次を `{date}_coach_context.md` に分離した（spec v2.1）。**「中間生成物のファイル名は誰と共有か」を spec 段階で確認するべきだった**。
- Codex のハマり転記: (1) ESLint が `.venv` 内の matplotlib 同梱 JS を走査して警告 → `globalIgnores` に `.venv` 追加 (2) Vite は `VITE_` 接頭辞なしの環境変数を晒さないため `loadEnv(mode, cwd, 'COACH_')` で `COACH_MODEL_ID` だけ注入 (3) YAML 依存を足せないので frontmatter は Python/Node 双方に自作 scalar parser（LF 分割・strip 比較で統一、往復パリティテスト付き） (4) 日次 context のファイル名から analyze が終了日を推定できないため `--end` を明示。
- reviewer 2 巡目 pass。non-blocking 4 件のうちプロンプト内の `## ` 節見出し（モデルが復唱すると検証で `.rejected`）は太字に降格して即修正。残 3 件は todo: パリティテストを差分検出 7 ケース（days の float 受理差・`generated_at` のタイムゾーン表記 4 形態）へ拡張 / `spawn` に `cwd` を明示 / いずれも現行パイプラインでは到達不能。
- reviewer の検証副作用: `data/reports/coach/.lock`（0 バイト・gitignore 配下）が残存。無害。
