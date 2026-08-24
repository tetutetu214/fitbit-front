# todo.md

## 次の一手 <!-- next-move: 2026-08-24 -->
- PR #71 マージ済み（08-24、merge commit a4334ae、ブランチ削除済み）
- 次: 「起動時に取得→解析→画面表示」の設計（arch-sparring: ローカル API サーバ / 1 日 1 回キャッシュ / aws login 前提）→ コーチカード実装
- 週次運用: 日曜朝に fetch → build_context → analyze（--end は前日）で「前回の答え合わせ」を溜める。次回は 08-31 ごろ
- reviewer の non-blocking 指摘 4 件（見出しの正規表現化・ValueError 前の警告順序・auth 断片入力・+デコード）は次の実装ついでに拾う
- 運用: 週 1 回（日曜朝）に fetch → build_context → analyze を回して「前回の答え合わせ」を溜める

## サイクル 0（2026-08-23 着手）
- [x] 方向転換の整理と docs/plan.md 起草
- [x] `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修（60 日バックフィル）
- [x] `scripts/build_context.py` 新規（Fitbit + Tanita + Vault worklog/reflections → Markdown）
- [x] `scripts/analyze_bedrock.py` 新規（Converse API → `data/reports/`）
- [x] テスト（pytest 30 件、ruff 0 件、reviewer 指摘 10 件修正済み）
- [x] Fitbit 再認証 → 60 日バックフィル（API 12 回、エラー 0）
- [x] Bedrock 分析実行（Opus 4.5。Claude 5 系はアカウント未提供）
- [x] 出力の質を判定 → go（トレーナー役 + プロフィール同梱で再実行済み、出典 URL 実在確認済み）

## 保留（Won't リストは docs/plan.md §3）
- Issue #70 intraday 心拍（サイクル 0 の判定後に再検討）
- ダッシュボード UI 改善 Issue 群（約 20 件 OPEN）
