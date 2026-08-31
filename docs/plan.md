# plan.md — Fitbit 体調分析（Bedrock 連携）

作成: 2026-08-23 / 方向転換の経緯と、サイクル 0 の計画。

## 1. 方向転換の経緯

- 2026-04 に Fitbit Web API → 静的 JSON → React ダッシュボードを構築し、2026-07-16（PR #69）まで画面の作り込みを続けたが停止。理由は Google 純正（Fitbit / Google Health アプリ）の画面に勝てないこと。
- てつてつは Google Health Premium（月 1,500 円）を契約済みで、Gemini 製の Google Health Coach を使ったが、**分析の質が低く実用にならない**と判断。
- よって本プロジェクトの価値は「画面」ではなく「**強いモデル + 本人向けプロンプト + Google が持たない本人の行動文脈（Vault）を掛け合わせた体調分析**」に置き直す。

## 2. 企画の錨（product-sparring Phase 1）

| 軸 | 内容 |
|---|---|
| 誰のどのジョブ | てつてつ本人専用。「自分の体データから、生活習慣の振り返りに使える指摘を得たい」。純正コーチでは得られなかった |
| 成功の定義 | Google Health Coach では出ない指摘が 1 つでも出る。レポートを 4 週続けて読む |
| 検証したい仮説 | 価値仮説「強いモデル + 本人文脈で、純正より刺さる分析になるか」。技術仮説「Bedrock 上の Claude を個人利用の健康分析に使えるか（安全制約で骨抜きにならないか）」 |
| 制約 | ゼロ運用 / 長期キーゼロ（aws login 都度方式）/ ランニングコストは月数百円以下 |
| 学習目的の比重 | 実用が主。Bedrock の学習は副次（「LLM が阿呆」が停止理由なので、質が出なければ意味がない） |

## 3. スコープ（案 B を採用）

- **Must**: 過去 60 日の Fitbit データを一括取得（バックフィル）/ Vault の worklog・reflections を同期間で束ねる / Bedrock の Claude 最上位モデルに 1 回投げて日本語レポートを得る
- **Should**: Tanita 体組成の同梱 / レポートを Vault に保存
- **Could**: Duolingo・Plaud 等の他パイプラインの日次データ同梱
- **Won't（今回は作らない）**: ダッシュボード画面の改修（※2026-08-31 本人フィードバックにより「期間切替」に限り解除 → spec.md §5.1）/ intraday（分単位）取得（Issue #70）/ 対話型チャット UI / 定期実行・自動配信（サイクル 1 で判断）/ 他人が使える汎用化

根拠: Build-Measure-Learn。インフラを作る前に「分析が使えるか」だけを最短で確かめる。
覆る条件: worklog に体感（疲労・気分）がほぼ書かれていない（explorer 調査では 56 ファイル中 5 件のみ）ため、身体×行動の相関が出なければ、worklog 側に 1 行の体調メモを足す運用が先になる。

## 4. サイクル 0 の手順

1. Fitbit 再認証（`scripts/auth.py`、URL 手貼り方式。てつてつ本人が実行）
2. `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修し、60 日分を `data/daily/` にバックフィル（Codex 委譲）
3. `scripts/build_context.py`（新規）で Fitbit 日次 + Tanita + Vault worklog/reflections を 1 つの Markdown 文脈に束ねる（Codex 委譲）
4. `scripts/analyze_bedrock.py`（新規）で Bedrock Converse API に投げ、`data/reports/YYYY-MM-DD_analysis.md` に保存（Codex 委譲）。`aws login` 後にてつてつ本人が実行
5. 出力を読んで判定: 「純正より阿呆ではないか」「純正で出ない指摘が 1 つでもあったか」

判定が「使える」→ サイクル 1（自動化・配信先・認証方式を arch-sparring）。「阿呆」→ モデル/プロンプトの問題なので、インフラを作らずに終了。

## 5. 設計上の決定事項

- **API**: Bedrock Converse API（boto3 `bedrock-runtime`）。`maxTokens` 明示、adaptive retry。モデル ID は cross-region inference profile（`global.` または `us.` prefix）を `aws bedrock list-inference-profiles` で当日確認してから `--model-id` で渡す（skill の指示: コード例の ID は古い可能性があるため実行時に検証）。
- **プロンプト設計**: 「本人の個人利用、医療判断ではなく生活習慣の振り返り」を system で明示し、消費者向け製品の安全制約を外す。出力は「事実（数値）→ 相関の仮説 → 来週試す 1 つ」の固定構成。
- **データの置き場**: `/data/` は .gitignore 済み。レポートも `data/reports/` に置いて Git 管理外にする（健康データをリポジトリに入れない）。
- **認証方式の衝突**: 毎日自動で Bedrock を呼ぶ構成は「長期キーゼロ」と衝突する。サイクル 0 は手動実行なので発生しない。サイクル 1 で (a) 取得・分析とも AWS 側（Lambda + SSM SecureString + LINE 配信）、(b) ローカル + `claude -p`（Bedrock 不使用）のどちらかを arch-sparring で決める。

## 6. 関連

- 旧設計（AWS サーバレス + Cloudflare Pages ダッシュボード）は README.md に残す。`infra/dynamodb.yaml` は未デプロイのまま据え置き。
- Google Health Coach の状況: 2026-05-19 に日本で正式提供、Google Health Premium 月 1,500 円（出典: https://blog.google/products-and-platforms/products/google-health/google-health-coach/ 、確認日 2026-08-23）
